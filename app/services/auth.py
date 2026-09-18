"""Password hashing and account authentication use cases."""

import hashlib
import hmac
import logging
import secrets
import sqlite3

from app.repositories.accounts import AccountRepository

LOGGER = logging.getLogger(__name__)
SESSION_LIFETIME = 7 * 24 * 60 * 60
SESSION_COOKIE = "freight_session"


class PasswordHasher:
    """Salted scrypt hashes with fixed, memory-hard work parameters."""

    def hash_password(self, password: str, salt: str | None = None) -> str:
        """Derive a password hash; never log or persist the plaintext."""
        salt = salt or secrets.token_hex(16)
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=16384,
            r=8,
            p=5,
            dklen=32,
        ).hex()
        return f"scrypt${salt}${digest}"

    def verify_password(self, password: str, encoded: str) -> bool:
        """Compare password hashes in constant time."""
        salt = encoded.split("$")[1]
        return hmac.compare_digest(self.hash_password(password, salt), encoded)


class AuthService:
    """Register users and issue revocable server-side sessions."""

    def __init__(self, accounts: AccountRepository) -> None:
        self.accounts = accounts
        self.hasher = PasswordHasher()
        self._dummy_hash = self.hasher.hash_password(secrets.token_hex(32))

    def register(self, username: str, password: str) -> dict:
        """Create an account while enforcing case-insensitive uniqueness."""
        try:
            user = self.accounts.create_user(
                username,
                self.hasher.hash_password(password),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Dieser Spielername ist bereits vergeben."
            ) from exc
        LOGGER.info(
            "Account created",
            extra={
                "event": "auth.register",
                "data": {"user_id": user["id"]},
            },
        )
        return user

    def authenticate(self, username: str, password: str) -> dict:
        """Use one generic failure message for invalid credentials."""
        user = self.accounts.find_user(username)
        encoded = user["password_hash"] if user else self._dummy_hash
        valid = self.hasher.verify_password(password, encoded)
        if not valid or user is None:
            LOGGER.info("Login rejected", extra={"event": "auth.failure"})
            raise ValueError("Spielername oder Passwort ist falsch.")
        LOGGER.info(
            "Login accepted",
            extra={
                "event": "auth.login",
                "data": {"user_id": user["id"]},
            },
        )
        return {"id": user["id"], "username": user["username"]}

    def issue_session(self, user_id: str) -> str:
        """Issue an unpredictable token and store its digest."""
        token = secrets.token_urlsafe(32)
        self.accounts.save_session(token, user_id, SESSION_LIFETIME)
        return token
