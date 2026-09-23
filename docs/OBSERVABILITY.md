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
- `world.geography_migrated`, `world.geography_migration_failed`
  (Katalog-/Mappingversion und Anzahlen, keine Zugangsdaten)

Passwörter und Session-Tokens erscheinen nicht in Domain-Logs. Nutzer-IDs
sind pseudonyme interne IDs; öffentliche Spielernamen werden nicht geloggt.
Passwort-Hashes werden ebenfalls weder geloggt noch im Importbericht ausgegeben.
Personenbezogene Importberichte und Backups bleiben außerhalb von Git.

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
