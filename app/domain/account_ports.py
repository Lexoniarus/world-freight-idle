"""Account persistence contracts, separate from player-owned game state."""

from typing import Protocol, TypedDict


class AccountIdentity(TypedDict):
    """Public identity returned after successful authentication."""

    id: str
    username: str


class AccountCredentials(AccountIdentity):
    """Private authentication record; never an HTTP response."""

    password_hash: str
    created_at: float


class AccountStore(Protocol):
    """Account/session operations without storage-specific exceptions."""

    def create_user(
        self, username: str, password_hash: str
    ) -> AccountIdentity: ...

    def find_user(self, username: str) -> AccountCredentials | None: ...

    def save_session(
        self, token: str, user_id: str, lifetime: int
    ) -> None: ...

    def session_user(self, token: str) -> AccountIdentity | None: ...

    def revoke_session(self, token: str) -> None: ...

    def allow_attempt(self, bucket: str) -> bool: ...


class PasswordVerifier(Protocol):
    """Explicit password-hashing dependency for the authentication use case."""

    def hash_password(self, password: str, salt: str | None = None) -> str: ...

    def verify_password(self, password: str, encoded: str) -> bool: ...
