from pathlib import Path

ROOT = Path(__file__).resolve().parent


def add_block_once(relative_path: str, marker: str, block: str) -> None:
    path = ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {relative_path}")

    content = path.read_text(encoding="utf-8")
    if marker in content:
        print(f"Already present: {marker}")
        return

    separator = "" if content.endswith("\n") else "\n"
    path.write_text(
        content + separator + "\n" + block.strip() + "\n",
        encoding="utf-8",
    )
    print(f"Updated: {relative_path}")


MANIFEST_BLOCK = '''
FUNCTION_TESTS.update(
    {
        "app.api.v1.dependencies.get_multiplayer_map_service": "test_multiplayer_map_endpoint_requires_login_and_shares_other_players",
        "app.api.v1.map.list_map_traffic": "test_multiplayer_map_endpoint_requires_login_and_shares_other_players",
        "app.bootstrap.build_multiplayer_map_service": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.repositories.multiplayer_map.MultiplayerMapRepository.__init__": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.repositories.multiplayer_map.MultiplayerMapRepository.list_player_states": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.services.multiplayer_map.MultiplayerMapService.__init__": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.services.multiplayer_map.MultiplayerMapService.list_traffic": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.services.multiplayer_map.player_color": "test_player_color_is_stable_and_changes_between_users",
    }
)
'''

PRODUCT_BLOCK = '''
## Gemeinsamer Live-Verkehr

Aktive Straßentransporte angemeldeter Spieler werden als minimale öffentliche
Kartenprojektion gemeinsam angezeigt. Private Spielstände bleiben getrennt:
Kapital, Verträge, Erlöse, Kosten und übrige Flottendaten werden nicht geteilt.
Jeder Account erhält aus seiner stabilen Benutzer-ID eine reproduzierbare
Kartenfarbe. Unterstützte Brand-Free-Fahrzeugsprites werden je Kombination aus
Modell und Spielerfarbe einmal rasterisiert; Modelle ohne Sprite verwenden einen
Fallback-Punkt in derselben Spielerfarbe. Fremde Transportdetails bleiben nicht
aufrufbar; ein Klick identifiziert lediglich den öffentlichen Spielernamen.
'''

TARGET_BLOCK = '''
## Abnahme – gemeinsamer Live-Verkehr

- [x] Aktive Transporte anderer angemeldeter Spieler sind auf derselben Karte sichtbar.
- [x] Private Wirtschafts- und Vertragsdaten bleiben aus der öffentlichen Projektion ausgeschlossen.
- [x] Spielerfarben sind stabil und unterscheiden Fahrzeughalter visuell.
- [x] Brand-Free-Sprites werden pro Modell/Farbe wiederverwendet; fehlende Modelle behalten einen farbigen Fallback.
- [x] Eigene Routenlinien bleiben privat; fremde Fahrzeugklicks öffnen keine privaten Transportdetails.
- [x] Ausgeführte/abgelaufene Transporte werden nicht mehr als Live-Verkehr projiziert.
'''

MILESTONE_BLOCK = '''
### Gemeinsamer Live-Verkehr

Für M4 vorgezogen ist nun eine geteilte, read-only Verkehrssicht auf aktive
Straßentransporte vorhanden. Die eigentlichen Spielstände bleiben pro Account
isoliert. Spielerfarben werden deterministisch aus der Account-ID erzeugt; eine
spätere frei wählbare Unternehmensfarbe kann dieselbe Darstellungsgrenze nutzen.
Ein gemeinsamer knapper Auftragsmarkt und Marktanteilsmechaniken bleiben offen.
'''

ARCHITECTURE_BLOCK = '''
## Read-only Multiplayer-Verkehrsprojektion

`MultiplayerMapRepository` liest ausschließlich Benutzer-ID, öffentlichen
Benutzernamen sowie die persistierten Fahrzeug-/Transport-Snapshots aus den
getrennten `user:<id>:`-Namespaces. `MultiplayerMapService` filtert bereits
abgelaufene Transporte und projiziert nur Transport-ID, Fahrzeug-ID, Modell-ID,
Route, Zeitfenster, öffentlichen Namen, Eigentümerflag und stabile Spielerfarbe.
Private Vertrags-, Kosten-, Erlös- und Kontodaten verlassen den Namespace nicht.

`GET /api/v1/map/traffic` benötigt weiterhin eine gültige Sitzung, ist aber im
Gegensatz zu Fleet-/Transport-Detailendpoints absichtlich accountübergreifend.
`GameState` lädt diese Projektion zusammen mit dem privaten Snapshot alle zehn
Sekunden. `OverlayData` hält private Routenlinien und öffentliche Fahrzeugmarker
getrennt. `VehicleIconRegistry` lädt jedes Brand-Free-SVG je Modell nur einmal
und erzeugt daraus bei Bedarf farbige MapLibre-Atlasbilder pro Spielerfarbe.
Die Position zwischen Polls wird weiterhin rein lokal aus Route und Serverzeit
interpoliert; es entstehen keine hochfrequenten Positionsschreibvorgänge.
'''

add_block_once(
    "tests/function_test_manifest.py",
    "app.services.multiplayer_map.player_color",
    MANIFEST_BLOCK,
)
add_block_once(
    "docs/PRODUCT.md",
    "## Gemeinsamer Live-Verkehr",
    PRODUCT_BLOCK,
)
add_block_once(
    "docs/TARGET.md",
    "## Abnahme – gemeinsamer Live-Verkehr",
    TARGET_BLOCK,
)
add_block_once(
    "docs/MILESTONES.md",
    "### Gemeinsamer Live-Verkehr",
    MILESTONE_BLOCK,
)
add_block_once(
    "docs/ARCHITECTURE.md",
    "## Read-only Multiplayer-Verkehrsprojektion",
    ARCHITECTURE_BLOCK,
)

print("Multiplayer map metadata patch complete.")
