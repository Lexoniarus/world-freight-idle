"""Supabase Auth verification and local account projection tests."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
)
from fastapi import HTTPException
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from app.api.v1.auth import auth_config
from app.api.v1.dependencies import get_current_user
from app.domain.errors import DuplicateAccountError, SupabaseAuthUnavailable
from app.providers.supabase_auth import (
    SupabaseJwtVerifier,
    TracingJwkClient,
)
from app.repositories.accounts import AccountRepository
from app.services.auth import AuthService, PasswordHasher


class _StaticSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class _StaticJwkClient:
    def __init__(self, key: object) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, token: str) -> _StaticSigningKey:
        del token
        return _StaticSigningKey(self._key)


def _token(
    private_key: EllipticCurvePrivateKey,
    subject: str,
    *,
    issuer: str = "https://project.supabase.co/auth/v1",
    username: object = "FreightPilot",
) -> str:
    return jwt.encode(
        {
            "aud": "authenticated",
            "exp": int(time.time()) + 300,
            "iss": issuer,
            "sub": subject,
            "user_metadata": {"username": username},
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )


def test_supabase_jwt_verification_accepts_only_stable_valid_identity():
    private_key = ec.generate_private_key(ec.SECP256R1())
    verifier = SupabaseJwtVerifier(
        "https://project.supabase.co/",
        "https://project.supabase.co/auth/v1/.well-known/jwks.json",
        _StaticJwkClient(private_key.public_key()),
    )
    subject = str(uuid4())

    assert verifier.verify(_token(private_key, subject)) == {
        "id": subject,
        "username": "FreightPilot",
    }
    fallback = verifier.verify(_token(private_key, subject, username="<bad>"))
    assert fallback == {
        "id": subject,
        "username": "Driver_" + subject.replace("-", "")[:12],
    }

    for rejected in (
        "",
        "x" * 8193,
        _token(private_key, "not-a-uuid"),
        _token(
            private_key, subject, issuer="https://attacker.example/auth/v1"
        ),
    ):
        with pytest.raises(ValueError, match="Invalid Supabase"):
            verifier.verify(rejected)

    class FailedJwks:
        def __init__(self, error):
            self.error = error

        def get_signing_key_from_jwt(self, token: str) -> Any:
            del token
            raise self.error

    invalid_key = SupabaseJwtVerifier(
        "https://project.supabase.co",
        "https://project.example/jwks",
        FailedJwks(PyJWKClientError("unknown key")),
    )
    with pytest.raises(ValueError, match="Invalid Supabase"):
        invalid_key.verify("header.payload.signature")
    unavailable = SupabaseJwtVerifier(
        "https://project.supabase.co",
        "https://project.example/jwks",
        FailedJwks(PyJWKClientConnectionError("offline")),
    )
    with pytest.raises(SupabaseAuthUnavailable):
        unavailable.verify("header.payload.signature")


def test_supabase_jwks_client_is_cached_and_refreshes_through_pyjwt(
    monkeypatch,
):
    calls = []

    def fake_fetch(_client):
        calls.append("refresh")
        return {"keys": []}

    monkeypatch.setattr(PyJWKClient, "fetch_data", fake_fetch)
    client = TracingJwkClient("https://project.example/jwks")
    assert client.fetch_data() == {"keys": []}
    assert calls == ["refresh"]
    verifier = SupabaseJwtVerifier(
        "https://project.supabase.co",
        "https://project.example/jwks",
    )
    assert isinstance(verifier._jwks, TracingJwkClient)


def test_external_identity_provisioning_is_stable_and_collision_safe(database):
    accounts = AccountRepository(database)
    first_id = str(uuid4())
    second_id = str(uuid4())
    assert accounts.ensure_external_user(first_id, "FreightPilot") == {
        "id": first_id,
        "username": "FreightPilot",
    }
    assert accounts.ensure_external_user(first_id, "RenamedMetadata") == {
        "id": first_id,
        "username": "FreightPilot",
    }
    collision = accounts.ensure_external_user(second_id, "FreightPilot")
    assert collision["id"] == second_id
    assert collision["username"].startswith("Driver_")
    with pytest.raises(ValueError, match="falsch"):
        AuthService(accounts, PasswordHasher()).authenticate(
            "FreightPilot", "legacy-password"
        )

    class FailedCursor:
        def fetchone(self):
            return None

    class FailedConnection:
        def executescript(self, _script):
            return None

        def execute(self, statement, _parameters=()):
            if statement.startswith("INSERT"):
                raise sqlite3.IntegrityError("collision")
            return FailedCursor()

    class FailedDatabase:
        @contextmanager
        def connect(self):
            yield FailedConnection()

    failed_accounts = AccountRepository(cast(Any, FailedDatabase()))
    with pytest.raises(DuplicateAccountError):
        failed_accounts.ensure_external_user(str(uuid4()), "FreightPilot")

    class RaceConnection:
        def __init__(self):
            self.reads = 0

        def executescript(self, _script):
            return None

        def execute(self, statement, _parameters=()):
            if statement.startswith("INSERT"):
                raise sqlite3.IntegrityError("race")
            self.reads += 1
            row = (
                {"id": "race-id", "username": "RacePilot"}
                if self.reads > 1
                else None
            )
            return SimpleNamespace(fetchone=lambda: row)

    race_connection = RaceConnection()

    class RaceDatabase:
        @contextmanager
        def connect(self):
            yield race_connection

    race_accounts = AccountRepository(cast(Any, RaceDatabase()))
    assert race_accounts.ensure_external_user("race-id", "RacePilot") == {
        "id": "race-id",
        "username": "RacePilot",
    }


def test_migrated_email_uses_existing_password_and_compact_player_id(database):
    accounts = AccountRepository(database)
    password = "existing-password-123"
    password_hash = PasswordHasher().hash_password(password)
    legacy_id = uuid4().hex
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            (legacy_id, "LegacyPilot", password_hash, time.time()),
        )
        connection.execute(
            "INSERT INTO account_emails VALUES (?, ?)",
            (legacy_id, "legacy@example.test"),
        )

    authenticated = AuthService(accounts, PasswordHasher()).authenticate(
        "LEGACY@example.test", password
    )
    assert authenticated == {"id": legacy_id, "username": "LegacyPilot"}
    assert accounts.ensure_external_user(
        str(UUID(legacy_id)), "IgnoredMetadata"
    ) == {"id": legacy_id, "username": "LegacyPilot"}


def test_bearer_dependency_provisions_verified_user_and_rejects_bad_tokens(
    database,
):
    accounts = AccountRepository(database)
    identity = {"id": str(uuid4()), "username": "BearerPilot"}

    class Verifier:
        def verify(self, token):
            if token != "valid":
                raise ValueError("invalid")
            return identity

    class UnavailableVerifier:
        def verify(self, _token):
            raise SupabaseAuthUnavailable("offline")

    auth: Any = SimpleNamespace(accounts=accounts)
    state = SimpleNamespace(supabase_auth=Verifier())

    def request(authorization) -> Any:
        return SimpleNamespace(
            headers={"authorization": authorization},
            cookies={},
            app=SimpleNamespace(state=state),
        )

    assert get_current_user(request("Bearer valid"), auth) == identity

    class ConflictAccounts:
        def ensure_external_user(self, _user_id, _username):
            raise DuplicateAccountError("collision")

    conflict_auth: Any = SimpleNamespace(accounts=ConflictAccounts())
    with pytest.raises(HTTPException) as caught:
        get_current_user(request("Bearer valid"), conflict_auth)
    assert caught.value.status_code == 409
    for authorization in ("Basic valid", "Bearer invalid"):
        with pytest.raises(HTTPException) as caught:
            get_current_user(request(authorization), auth)
        assert caught.value.status_code == 401
    state.supabase_auth = None
    with pytest.raises(HTTPException) as caught:
        get_current_user(request("Bearer valid"), auth)
    assert caught.value.status_code == 401
    state.supabase_auth = UnavailableVerifier()
    with pytest.raises(HTTPException) as caught:
        get_current_user(request("Bearer valid"), auth)
    assert caught.value.status_code == 503


def test_auth_config_exposes_only_browser_safe_values():
    settings = SimpleNamespace(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_jwks_url=(
            "https://project.supabase.co/auth/v1/.well-known/jwks.json"
        ),
    )
    request: Any = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )
    assert auth_config(request) == {
        "enabled": True,
        "url": "https://project.supabase.co",
        "publishable_key": "sb_publishable_test",
    }
    settings.supabase_publishable_key = ""
    assert auth_config(request) == {
        "enabled": False,
        "url": None,
        "publishable_key": None,
    }
