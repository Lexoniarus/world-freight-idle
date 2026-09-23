"""NHM product identities separated from facility handling evidence."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.evidence import SourceReference
from app.domain.validation import (
    require_finite,
    require_identity,
    require_integer,
)


@dataclass(frozen=True, slots=True)
class NhmProduct:
    """One reference goods category and its self-to-root NHM hierarchy."""

    nhm_row_id: int
    code: str
    name: str
    ancestor_row_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        """Require an immutable self-to-root hierarchy and named identity."""
        require_integer(self.nhm_row_id, "NHM row identity")
        require_identity(self.code, "NHM code")
        require_identity(self.name, "NHM name")
        if (
            self.nhm_row_id == 0
            or not isinstance(self.ancestor_row_ids, tuple)
            or not self.ancestor_row_ids
            or self.ancestor_row_ids[0] != self.nhm_row_id
            or len(set(self.ancestor_row_ids)) != len(self.ancestor_row_ids)
        ):
            raise ValueError("Invalid NHM hierarchy.")
        for identifier in self.ancestor_row_ids:
            require_integer(identifier, "NHM ancestor")
            if identifier == 0:
                raise ValueError("Invalid NHM ancestor.")

    def is_compatible_with(self, other: NhmProduct) -> bool:
        """Match the same NHM category or a category on its ancestor chain."""
        return (
            self.nhm_row_id in other.ancestor_row_ids
            or other.nhm_row_id in self.ancestor_row_ids
        )


@dataclass(frozen=True, slots=True)
class FacilityNhmProfile:
    """Facility-specific role and evidence for a shared NHM product."""

    product: NhmProduct
    role: str
    evidence_type: str
    confidence: float
    priority_score: float
    source: SourceReference | None

    def __post_init__(self) -> None:
        """Reject unsupported handling roles and invalid evidence weights."""
        if self.role not in {"input", "output", "both"}:
            raise ValueError("Invalid NHM handling role.")
        require_identity(self.evidence_type, "Evidence type")
        require_finite(self.confidence, "Confidence")
        require_finite(self.priority_score, "Priority")
        if self.confidence > 1 or self.priority_score > 1:
            raise ValueError("NHM weights must be between zero and one.")


@dataclass(frozen=True, slots=True)
class DocumentedCargo:
    """Historical goods description without claiming an NHM identity."""

    code: str
    name: str
    role: str
    standard: bool
    evidence_type: str
    source: SourceReference | None

    def __post_init__(self) -> None:
        """Require an identified description and explicit handling evidence."""
        require_identity(self.code, "Goods code")
        require_identity(self.name, "Goods description")
        require_identity(self.evidence_type, "Evidence type")
        if (
            self.role not in {"input", "output", "both"}
            or type(self.standard) is not bool
        ):
            raise ValueError("Invalid documented goods evidence.")
