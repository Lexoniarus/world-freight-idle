"""Location projection exposes public identity without catalogue evidence."""

from dataclasses import replace

from app.api.v1.location_projection import project_location
from app.domain.evidence import SourceReference
from app.domain.world_scopes import WorldScope


def test_location_projection_hides_repository_evidence(
    synthetic_world_catalogue,
):
    berlin = WorldScope(synthetic_world_catalogue.read()).facility(
        "berlin_westhafen"
    )
    berlin = replace(
        berlin,
        geocoding_status="verified_coordinates",
        coordinate_evidence=(
            SourceReference(
                "https://example.test/coordinates",
                "verified test coordinates",
                None,
            ),
        ),
    )
    assert berlin.company is not None
    payload = project_location(berlin.location_snapshot())
    assert payload["id"] == berlin.facility_uid
    assert payload["company_uid"] == berlin.company.company_uid
    assert payload["location_verified"] is True
    assert "sources" not in payload["company"]
    assert "website" not in payload["company"]
    assert "cargo" not in payload
    assert "handled_goods" not in payload
    assert "facility_id" not in payload
    assert "company_id" not in payload

    payload["company"]["display_name"] = "changed"
    assert berlin.company.display_name != "changed"
    without_company = replace(berlin, company=None).location_snapshot()
    assert project_location(without_company)["company_uid"] is None
