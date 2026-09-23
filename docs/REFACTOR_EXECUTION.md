# Domain-/Persistenz-Refactor: Ausführungsstand

Verbindliche Reihenfolge, vereinbart am 23.09.2026:

1. A: ContractOffer, ActiveTransport und Entity-Invarianten abschließen.
2. B: relationales Spielstandschema, Repository-/Transaktionsports,
   Services, Maintenance, Rangliste, Mehrspielerkarte und Mapping umstellen.
3. C: NHM-Produkt/Profile trennen; WorldCatalogue 4.0.0 mit Länder-/Stadt-
   Identitäten und komponierten Standortobjekten einführen.
4. D: immutable World-/Country-/City-/Company-Scopes einführen und nutzen.
5. E: ungenutzte Legacy-Modelle entfernen und Architekturgrenzen absichern.
6. F: separate, gesicherte Offline-Übernahme der drei Testprofile.
7. G: Ist-Dokumentation und tatsächlich ausgeführte Prüfergebnisse konsolidieren.

Je Abschnitt: kleine fachliche Commits, Tests und Manifest mitführen,
vollständiges Quality Gate und E2E vor geprüftem Squash-PR. Keine direkten
main-Commits. Die alte game.db bleibt bis F unangetastet. Entwicklung nutzt
temporäre Datenbanken. Konten und Passwort-Hashes bleiben beim Import erhalten;
Sessions werden nicht übernommen. Keine neue Wirtschaft und keine UI-Neugestaltung.

## A: ContractOffer

Der übernommene Arbeitsstand wird vervollständigt. Die Baseline hatte vier
Regressionen: Tuple-/List-Unterschiede im JSON-Roundtrip und drei Tests mit
alten Dict-Argumenten an bereits typisierten Methoden. Der neue Offer-Typ
validiert Identität, endliche Mengen/Konditionen, Zeitreihenfolge und getrennte
Endpunkte. Persistenz-/API-Mapping verbleibt nur bis Abschnitt B übergangsweise
an den bestehenden Grenzen.
