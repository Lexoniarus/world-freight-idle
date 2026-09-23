"""Account and session persistence."""

import hashlib
import sqlite3
import time
import uuid

from app.domain.account_ports import AccountCredentials, AccountIdentity
from app.domain.errors import DuplicateAccountError
from app.repositories.game_database import SqliteGameDatabase

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS auth_attempts (
    bucket TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL,
    expires_at REAL NOT NULL
);
"""


class AccountRepository:
    """Keep credentials and session tokens outside game state."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        self._database = database
        with database.connect() as connection:
            connection.executescript(_SCHEMA)

    def create_user(
        self, username: str, password_hash: str
    ) -> AccountIdentity:
        """Insert a uniquely named account; SQLite resolves signup races."""
        user: AccountIdentity = {"id": uuid.uuid4().hex, "username": username}
        with self._database.connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?)",
                    (user["id"], username, password_hash, time.time()),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateAccountError(
                    "Spielername bereits vergeben."
                ) from exc
        return user

    def find_user(self, username: str) -> AccountCredentials | None:
        """Look up a case-insensitive login name."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return (
            AccountCredentials(
                id=row["id"],
                username=row["username"],
                password_hash=row["password_hash"],
                created_at=row["created_at"],
            )
            if row
            else None
        )

    def save_session(self, token: str, user_id: str, lifetime: int) -> None:
        """Persist only a digest of the bearer token and prune expired rows."""
        with (
            self._database.transaction(),
            self._database.connect() as connection,
        ):
            connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (time.time(),),
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (
                    hashlib.sha256(token.encode()).hexdigest(),
                    user_id,
                    time.time() + lifetime,
                ),
            )

    def session_user(self, token: str) -> AccountIdentity | None:
        """Resolve a live session without returning any credential data."""
        with self._database.connect() as connection:
            row = connection.execute(
                """SELECT u.id, u.username FROM users u
                JOIN sessions s ON s.user_id = u.id
                WHERE s.token_hash = ? AND s.expires_at > ?""",
                (hashlib.sha256(token.encode()).hexdigest(), time.time()),
            ).fetchone()
        return (
            AccountIdentity(id=row["id"], username=row["username"])
            if row
            else None
        )

    def revoke_session(self, token: str) -> None:
        """Invalidate a session immediately, including copied cookies."""
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            )

    def allow_attempt(self, bucket: str) -> bool:
        """Limit authentication to 30 attempts per IP per 15 minutes."""
        now = time.time()
        digest = hashlib.sha256(bucket.encode()).hexdigest()
        with (
            self._database.transaction(),
            self._database.connect() as connection,
        ):
            connection.execute(
                "DELETE FROM auth_attempts WHERE expires_at <= ?",
                (now,),
            )
            row = connection.execute(
                """INSERT INTO auth_attempts VALUES (?, 1, ?)
                ON CONFLICT(bucket) DO UPDATE SET attempts = attempts + 1
                RETURNING attempts""",
                (digest, now + 900),
            ).fetchone()
        return row["attempts"] <= 30
