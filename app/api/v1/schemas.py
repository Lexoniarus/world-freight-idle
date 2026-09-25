"""Stable public API schemas for version 1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DispatchRequest(BaseModel):
    """Vehicle selection for accepting one contract."""

    vehicle_id: str = Field(min_length=1)


class QuoteRequest(BaseModel):
    """Required owned vehicle for an authoritative cost preview."""

    vehicle_id: str = Field(min_length=1)


class Credentials(BaseModel):
    """Bounded credentials with an intentionally simple public player name."""

    username: str = Field(pattern=r"^[A-Za-z0-9_]{3,24}$")
    password: str = Field(min_length=12, max_length=128)


class PurchaseRequest(BaseModel):
    """The server decides vehicle price, specifications and delivery hub."""

    model_id: str = Field(min_length=1, max_length=40)


class HealthResponse(BaseModel):
    """Provider configuration exposed by the health endpoint."""

    ok: bool
    api_version: str
    routing_provider: str
    geocoding_provider: str
    routing_profile: str


class MessageResponse(BaseModel):
    """Generic mutation acknowledgement."""

    ok: bool
    message: str


class JsonEnvelope(BaseModel):
    """Loose envelope for domain-shaped MVP resources."""

    data: dict[str, Any]
