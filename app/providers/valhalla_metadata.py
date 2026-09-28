"""Normalize optional graph metadata without inventing a revision."""

from collections.abc import Mapping


def graph_revision(headers: Mapping[str, str]) -> str | None:
    """Prefer a graph revision over the routing engine's software version."""
    return headers.get("x-graph-revision") or headers.get("x-valhalla-version")
