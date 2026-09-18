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

Passwörter und Session-Tokens erscheinen nicht in Domain-Logs. Nutzer-IDs
sind pseudonyme interne IDs; öffentliche Spielernamen werden nicht geloggt.

## Trace-ID

`TraceIdMiddleware` erzeugt je HTTP-Request eine ID oder übernimmt `X-Trace-Id` des Clients. Die ID wird:

1. in ContextVar gespeichert,
2. in strukturierte Logs aufgenommen,
3. als `X-Trace-Id` zurückgegeben,
4. an externe Provider weitergereicht, soweit der Adapter Header unterstützt.

## Ziel

Ein Fehler aus dem Browser soll über API → Service → Provider in Logs korrelierbar sein, ohne personenbezogene Nutzdaten loggen zu müssen.
