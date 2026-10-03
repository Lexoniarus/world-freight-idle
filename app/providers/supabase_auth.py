"""Cached local verification for Supabase Auth access tokens."""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol
from uuid import UUID

import jwt
from jwt import InvalidTokenError, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from app.domain.account_ports import AccountIdentity
from app.domain.errors import SupabaseAuthUnavailable

LOGGER = logging.getLogger(__name__)
_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,24}$")
_MAX_TOKEN_LENGTH = 8192


class SigningKeyClient(Protocol):
    """Minimal injectable contract required from a JWKS client."""

    def get_signing_key_from_jwt(self, token: str) -> Any:
        """Resolve the public key selected by a token header."""
        ...


class TracingJwkClient(PyJWKClient):
    """Trace remote JWKS refreshes while retaining PyJWT's bounded cache."""

    def fetch_data(self) -> Any:
        """Fetch public signing keys without ever logging bearer tokens."""
        LOGGER.info(
            "Refreshing Supabase signing keys",
            extra={
                "event": "auth.jwks_refresh",
                "data": {"provider": "supabase"},
            },
        )
        return super().fetch_data()


class SupabaseJwtVerifier:
    """Verify asymmetric Supabase JWTs locally and project safe identity."""

    def __init__(
        self,
        supabase_url: str,
        jwks_url: str,
        jwks_client: SigningKeyClient | None = None,
    ) -> None:
        self._issuer = supabase_url.rstrip("/") + "/auth/v1"
        self._jwks = jwks_client or TracingJwkClient(
            jwks_url,
            cache_keys=True,
            lifespan=600,
            timeout=5,
        )

    def verify(self, token: str) -> AccountIdentity:
        """Require a valid ES256 user token and return its stable subject."""
        if not token or len(token) > _MAX_TOKEN_LENGTH:
            raise ValueError("Invalid Supabase access token.")
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
                issuer=self._issuer,
                options={"require": ["aud", "exp", "iss", "sub"]},
            )
            subject = str(UUID(str(claims["sub"])))
        except PyJWKClientConnectionError as exc:
            LOGGER.error(
                "Supabase signing keys unavailable",
                extra={
                    "event": "auth.jwks_failure",
                    "data": {"provider": "supabase"},
                },
            )
            raise SupabaseAuthUnavailable(
                "Supabase authentication is temporarily unavailable."
            ) from exc
        except (
            InvalidTokenError,
            PyJWKClientError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            LOGGER.info(
                "Supabase access token rejected",
                extra={
                    "event": "auth.failure",
                    "data": {"provider": "supabase"},
                },
            )
            raise ValueError("Invalid Supabase access token.") from exc
        metadata = claims.get("user_metadata")
        candidate = (
            metadata.get("username") if isinstance(metadata, dict) else None
        )
        username = (
            candidate
            if isinstance(candidate, str) and _USERNAME.fullmatch(candidate)
            else "Driver_" + subject.replace("-", "")[:12]
        )
        return AccountIdentity(id=subject, username=username)
