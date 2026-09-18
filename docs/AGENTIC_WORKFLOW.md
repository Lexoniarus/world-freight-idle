# Agentischer Entwicklungsworkflow

## Product Agent

Pflegt `PRODUCT.md`, `TARGET.md`, `MILESTONES.md`. Prüft zuerst, ob ein Feature wirklich zum definierten MVP gehört.

## Architecture Agent

Definiert Modulgrenzen, API-Contracts, Ports/Adapter und verhindert God Objects sowie Cross-Layer-Zugriffe.

## Provider Agent

Implementiert externe Integrationen hinter internen Ports. Kein stiller Fake-/Luftlinien-Fallback.

## Core Agent

Implementiert Use Cases als kleine Single-Responsibility-Methoden. `GameService` orchestriert auf hoher Ebene; Detailentscheidungen liegen in spezialisierten Services.

## Frontend Agent

Baut getrennte Nutzerflows. Spielaktionen greifen über `frontend/api.js`
auf `/api/v1` zu. Basiskarten-Tiles lädt MapLibre separat ohne Spiel-Header.
Views, Controller und Kartenprojektionen bleiben getrennt. Ressourcen
werden über den Lebenszyklus ihrer zuständigen Komponenten freigegeben.

## QA Agent

Schreibt den Gegentest **mit** jeder neuen Funktion. Aktualisiert Function-Test-Manifest und führt Quality Gate aus.

## Observability Agent

Prüft Logging, Trace-Propagation und aussagekräftige Events.

## Documentation Agent

Aktualisiert Produkt-, Ziel-, API-, Architektur-, Testing- und Meilensteindokumentation im selben Change.

## Reviewer Agent

Ein Feature gilt erst nach bestandenem `make quality` und Dokumentationsabgleich als fertig.

## Git und Integration

Alle Rollen folgen [BRANCHING.md](BRANCHING.md). Jede Änderung erfolgt auf
einem passenden Arbeitsbranch; main wird nur nach Prüfungen integriert.
