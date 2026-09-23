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

Abschnitt A wurde über PR #7 als 015b2ee integriert. Die Arbeitscommits waren
d3c5330, c837a34 und a649917. Ausgeführt: 230 Python-Tests, 2.378 Statements
mit 100 % Core-Coverage, Ruff/Format/mypy/Pyright/Manifest, 54 Frontendtests,
ESLint/Stylelint/Prettier/checkJs/Produktionsbuild und zehn Browserszenarien.
Desktop-/Mobil-Screenshots wurden geprüft; keine reale iPad-Abnahme.
GitHub-Push- und PR-CI waren vor dem Squash-Merge erfolgreich.

## B: Relationale Spielpersistenz

Der Implementierungsvertrag in RELATIONAL_STATE.md beschreibt Tabellen,
Besitzgrenzen, Snapshotversionierung und atomare Abläufe. Die Implementierung
beginnt auf refactor/game-state-persistence von integriertem main. Bis zum
vollständigen Repository-/Service-Umbau gilt die bestehende KV-Laufzeit weiter.

Die eigenständig geprüften relationalen Adapter verwenden Besitzer-Fremdschlüssel,
einen partiellen Unique-Index für aktive Fahrzeuge und geschützte Settlement-
Historie. Snapshot-Dokumente tragen Version und Typ; beim Lesen müssen ihre
Inhalte zu den indizierten Spalten passen. Alte/unbekannte Spielstandschemata
und fehlende Struktur werden abgewiesen. Acht gezielte Tests inklusive Manifest
bestehen; die drei neuen ausführbaren Repository-Module erreichen zusammen
172/172 Statements. Ruff/Format/mypy/Pyright sind ebenfalls grün. Der vollständige
Anwendungs- und Browserlauf folgt nach der Service-/Composition-Umstellung.

Game-/Fleet-Use-Cases verwenden jetzt die Repository-/Unit-of-Work-Ports.
Der temporäre KV-Adapter hält den bisherigen Composition Root bis zum gemeinsamen
Cutover der übrigen Leser funktionsfähig; er ist kein Importer. Direkte
relationale Use-Case-Tests prüfen Kauf, Dispatch, Settlement, Reset und Rollback
nach erfolgter Abbuchung. Unvollständige Transport-Testdicts wurden durch
vollständige typisierte Fixtures ersetzt. Die echte Altformatübernahme bleibt F.

Zwischenprüfung der Port-Umstellung: Gesamtlauf mit 237 bestandenen Tests und
zwei veralteten Fixture-Annahmen; korrigierte Fälle separat mit drei bestandenen
Parametervarianten nachgeprüft. Kombinierte Core-Statement-Coverage: 2.602/2.602.
Ruff/Format/mypy/Pyright und Manifest bestehen. Vor PR-Integration folgt erneut
ein vollständiger Lauf auf dem endgültigen relationalen Stand.
