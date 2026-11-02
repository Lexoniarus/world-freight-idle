"""World-catalogue composition remains independent from player state."""

from dataclasses import replace

import pytest

from app.bootstrap import build_world_catalogue
from app.domain.errors import WorldCatalogueError
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


def test_world_catalogue_composition_uses_explicit_path_without_game_state(
    tmp_path,
):
    settings = build_synthetic_application_settings(tmp_path)
    catalogue = build_world_catalogue(settings)
    assert len(catalogue.read().cities) == 2
    assert not settings.db_path.exists()
    missing = build_world_catalogue(
        replace(settings, world_catalogue_path=None)
    )
    with pytest.raises(WorldCatalogueError):
        missing.read()
    assert not settings.db_path.exists()
