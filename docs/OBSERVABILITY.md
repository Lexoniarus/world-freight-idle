# Logging und Tracing

## Strukturierte Logs

Python schreibt JSON-Logs. Relevante Domain-Events:

- `market.refresh`
- `contract.quote`
- `trip.dispatch`
- `trip.complete`
- `auth.register`
- `auth.login`
- `auth.failure`
- `fleet.purchase`
- `state.schema_validated` (relationale Schemaversion)
- `state.persistence_error` (neutraler Speicherfehler)
- `state.import_rejected`, `state.import_rolled_back`
- `state.import_completed` (Anzahlen übernommener und ausgeschlossener Daten)
- `state.import_demo_excluded` (ausdrücklich freigegebener Backup-only-Demostand)
- `state.energy_upgraded` (Quell-/Zielversion und Anzahlen, keine Datensätze)
- `state.energy_upgrade_rejected` (ungültiges Quellschema oder Integrität)
- `state.energy_upgrade_rolled_back` (fehlgeschlagene Zieldatei entfernt)
- `world.geography_migrated`, `world.geography_migration_failed`
  (Katalog-/Mappingversion und Anzahlen, keine Zugangsdaten)

Passwörter und Session-Tokens erscheinen nicht in Domain-Logs. Nutzer-IDs
sind pseudonyme interne IDs; öffentliche Spielernamen werden nicht geloggt.
Passwort-Hashes werden ebenfalls weder geloggt noch im Importbericht ausgegeben.
Personenbezogene Importberichte und Backups bleiben außerhalb von Git.

`trip.dispatch` ergänzt `energy_stop_count` und `journey_seconds` zur vorhandenen
Fahrzeug-/Auftragskennung. Bewegung und Auffüllen benötigen keine Logeinträge
oder Schreibzugriffe pro Animationstakt; `trip.complete` markiert das atomare
Settlement. Die reine Fahrtplanberechnung erzeugt selbst keine Seiteneffekte.

## Trace-ID

`TraceIdMiddleware` erzeugt je HTTP-Request eine ID oder übernimmt `X-Trace-Id` des Clients. Die ID wird:

1. in ContextVar gespeichert,
2. in strukturierte Logs aufgenommen,
3. als `X-Trace-Id` zurückgegeben,
4. an externe Provider weitergereicht, soweit der Adapter Header unterstützt.

Offline-CLIs besitzen keinen HTTP-Request. Ihre Ereignisse verwenden den
Trace-Standardwert `-`; sie behaupten keine Zugehörigkeit zu einem Browserabruf.

## Ziel

Ein Fehler aus dem Browser soll über API → Service → Provider in Logs korrelierbar sein, ohne personenbezogene Nutzdaten loggen zu müssen.

## Frontend-v2: Marktstart und Preferences

`market.startup` bestätigt den vollständigen Neuaufbau.
`market.startup_failed` protokolliert den betroffenen Account und Fehler
strukturiert; die äußere Transaktion rollt zurück. `account.color_updated`
protokolliert die Farbänderung ohne Zugangsdaten. Bestehende Dispatch-/
Refill-Events unterscheiden erfolgreichen Start und späteren Refill-Fehler.

## Routing-Anchor-Ereignisse

Der Anchor-Pfad protokolliert strukturierte Ereignisse
`routing_anchor.locate_request`, `routing_anchor.provider_unavailable`,
`routing_anchor.cache_hit`, `routing_anchor.resolved` und
`routing_anchor.failure`. Der globale `JsonFormatter` ergänzt die aktuelle
Trace-ID; Valhalla-Requests erhalten dieselbe Trace-ID als `X-Trace-Id`.
Facility-UID, Methode, Status, Snap-Distanz und Provider werden nur dort
protokolliert, wo sie für Diagnose relevant sind.
