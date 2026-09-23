# ADR 0005: Typed domain objects, snapshots and navigable world scopes

- Status: Accepted
- Date: 2026-09-21

## Context

World Freight Idle hat inzwischen klare Service-, Repository-, Provider- und
Frontend-Grenzen. Teile des Game-Core verwenden jedoch weiterhin dynamische
JSON-/dict-Strukturen. Gleichzeitig ist das WorldCatalogue-Domainmodell bereits
stärker typisiert.

Dadurch entstehen mehrere Nachteile:

- Services kennen teilweise Persistenzdetails und KV-Schlüssel.
- Runtime-Snapshots sind strukturell nur durch Konvention geschützt.
- das alte `Contract`-Modell entspricht dem aktuellen NHM-Contract nicht mehr.
- geografische Beziehungen sind teilweise als redundante Strings modelliert.
- Full-Facility- und kompakte Location-Snapshots können versehentlich
  verwechselt werden.
- das heutige `CargoProfile` vermischt NHM-Produktidentität und
  Facility-spezifisches Verhalten.
- natürliche Abfragen über Land, Stadt, Firma und Facility benötigen
  wiederholte manuelle Filterlogik.

## Decision

Der Core wird schrittweise auf typisierte Domainobjekte umgestellt.

Wir unterscheiden:

1. Entities mit stabiler Identität und Lebenszyklus.
2. Immutable Value Objects für strukturierte Werte und Invarianten.
3. Immutable Snapshots/Projektionen für persistierte historische oder
   API-relevante Zustände.
4. Query-Scopes als navigierbare Fassade über dem normalisierten World-Graph.

NHM-Waren werden als `NhmProduct` modelliert. Die Beziehung einer Facility zu
einem NHM-Produkt wird separat als `FacilityNhmProfile` modelliert.
`DocumentedGood` bleibt davon getrennt, damit belegte Warenhinweise und
abgeleitete operative Fähigkeiten nicht vermischt werden.

Komposition wird gegenüber Vererbung bevorzugt. Vererbung wird nur bei einem
echten `is-a`-Verhältnis mit gemeinsamem Verhalten verwendet.

Das normalisierte World-Modell wird nicht künstlich als Baum gespeichert.
Insbesondere gehört eine Company nicht exklusiv zu einer City. Navigierbare
Aufrufe wie

```python
world.country("DE").city("Berlin").company("BEHALA").facilities
```

werden über Filter-/Scope-Objekte realisiert.

Services sollen langfristig gegen Repository-Ports arbeiten und weder konkrete
SQLite-Adapter noch KV-Schlüssel kennen.

## Consequences

Positive Folgen:

- fachliche Invarianten werden an einer Stelle geschützt;
- mypy/Pyright können Snapshot- und Entity-Grenzen prüfen;
- Persistenzdetails verlassen die Services;
- Query-Code wird lesbarer;
- Full-Reference-Objekte und kompakte Runtime-Projektionen bleiben klar
  getrennt;
- NHM-Produkt und Facility-spezifisches Verhalten können unabhängig
  weiterentwickelt und abgefragt werden.

Kosten:

- schrittweise Migration bestehender JSON-Zustände;
- zusätzliche Serializer/Repository-Adapter;
- neue Core-Callables benötigen Manifest-Einträge und Verhaltenstests;
- API-Kompatibilität muss während der Migration explizit erhalten bleiben.

## Non-goals

Diese Entscheidung führt nicht sofort Spielerunternehmen, Depots, neue
Wirtschaftsregeln oder neue Transportmodi ein. Sie strukturiert zuerst die
bereits vorhandenen fachlichen Konzepte.
