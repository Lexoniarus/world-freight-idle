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

## A: ActiveTransport

Transporte besitzen typisierte, unveränderliche Route-/Endpunktsnapshots und
die Zustände active/settled. Der Aufrufer liefert die Zeit; die Entity erlaubt
Settlement ausschließlich ab Ankunft und genau einmal je Zustandsversion.
Die Datenbanktransaktion bleibt für konkurrierende Abrechnung verantwortlich.
Die aktuelle KV-Stufe entfernt abgewickelte Reisen noch aus der Aktivliste;
das relationale Repository in B wird den Settlement-Zustand dauerhaft speichern.
Historische Legacy-Transporte bleiben bis zum separaten Import kompatibel.

## A: Entity-Invarianten

PlayerState und OwnedVehicle kapseln ihre veränderlichen Werte. Öffentliche
Eigenschaften sind schreibgeschützt; Konstruktion und benannte Mutationen
weisen ungültige Zahlen, Statuswechsel und widersprüchliche Standortidentitäten
ab. Die Profilpflege ersetzt Guthaben über eine validierte Entity-Methode.
Modellwerte werden vollständig geprüft, bevor ein Fahrzeug geändert wird.
Tests verwenden konsistente Standorte und setzen vor Ankunft einen tatsächlich
fahrenden Fahrzeugstatus. Der Schutz der Zustandswechsel wird separat geprüft.
