# ADR 0006: Eine relationale Laufzeit und explizite historische Übernahme

- Status: Accepted
- Date: 2026-09-23

## Entscheidung

Der Spielkern arbeitet ausschließlich mit Domainobjekten hinter
GameStateRepository/GameUnitOfWork. KV-Kompatibilitätsadapter und parallele
Laufzeiten sind entfernt. Benutzerkennung und lokale Objektkennung bilden
zusammen die Persistenzidentität. Häufig gefilterte Werte sind relationale
Spalten; unveränderliche historische Dokumente werden gezielt versioniert.

ActiveTransport enthält HistoricalContractSnapshot, keinen verfügbaren
ContractOffer. Bestehende dokumentierte Waren ohne NHM-Bezug bleiben historische
Fakten und werden nicht nachträglich umklassifiziert. Standortquellen bleiben
in Snapshots erhalten, auch wenn die HTTP-Darstellung kompakt bleibt.

Die Normalisierung des Referenzkatalogs auf 4.0.0 verwendet ein versioniertes
Facility-/Stadtmanifest. Stadt-UUIDs sind gespeichert und werden nicht aus Namen
abgeleitet. Firmen bleiben unabhängig von einer Stadt; Scopes filtern Facilities.

## Migration und Konsequenzen

Alte Spielschemata werden beim Start abgewiesen. Das Offline-Werkzeug sichert,
liest readonly, schreibt eine neue Datei und gleicht alle übernommenen Werte
ab. Sessions und wiederherstellbare Caches bleiben ausgeschlossen. Unbekannte
Daten führen zum Abbruch. Die kontolose Demo blieb auf ausdrücklichen
Nutzerentscheid im Backup; die drei Konten wurden übernommen.

Zwischencommits prüfen betroffene Tests. Vollständiges Gate, E2E, manuelles
Architekturreview und CI sind vor dem abschließenden Squash-PR erforderlich.
Der Arbeitsverlauf steht getrennt von den Ist-Dokumenten in REFACTOR_EXECUTION.md.
