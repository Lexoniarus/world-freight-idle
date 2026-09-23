# Domain-/Persistenz-Refactor: Ausführungsstand

## Überarbeiteter Ablaufplan mit verbindlichem Cleanup

Planungsstand nach Rückmeldung des Auftraggebers am 23.09.2026. Die folgenden
Regeln ersetzen die frühere Forderung nach vollständig grünen Zwischencommits.
Der Auftraggeber hat diesen Ablauf zur Umsetzung freigegeben. Die darunter
stehenden Zwischenberichte dokumentieren Vergangenheit und sind keine Freigabe
des gesamten Refactors.

### Ausgangslage

- A ist als PR #7 integriert. B hat drei Arbeitscommits und weitere noch nicht
  committete Änderungen. C–G sind noch offen.
- Die selbst eingeführte KV-Übergangsschicht, game_store und der alte KV-Traffic-
  Leser sind im Arbeitsbaum entfernt. Die Laufzeitverdrahtung wurde unmittelbar
  auf die relationalen Repositories umgestellt.
- Die Umstellung ist noch nicht vollständig geprüft. Domain und Services
  enthalten weiterhin Serialisierung; GameService importiert noch den
  Transport-Mapper aus dem Repository. Diese Grenzen sind nicht abgenommen.
- Die echte game.db wurde weder gelesen noch geändert. Es wurde kein neuer
  Server gegen diese Datei gestartet und keine Migration ausgeführt.

### Arbeitsweise und Integration

Kleine fachliche Arbeitscommits bleiben verbindlich. Tests und Manifest werden
mit den jeweiligen Funktionen angepasst. Vor jedem Arbeitscommit müssen die
betroffenen Unit-, Integrations- und Architekturtests grün sein, einschließlich
der unmittelbar abhängigen Aufrufer. Tests werden auf das Zielverhalten
umgestellt; unveränderte fachliche Garantien behalten ihre Gegentests. Keine
Abschwächung, kein Skip und kein Zusatzadapter, nur um Tests grün zu bekommen.

Das vollständige Projekt-Gate einschließlich aller Frontend- und E2E-Prüfungen
läuft nach dem gesamten Umbau und Cleanup vor der Integration. Es wird nicht
nach jedem kleinen Commit wiederholt. Ein fachlich unabhängiger Testbereich
muss nicht bei jeder Änderung erneut ausgeführt werden. Der aktuelle noch
uncommittete Arbeitsstand erhält vor seinem Commit diese betroffenen Prüfungen.

Für den verbleibenden zusammenhängenden Umbau ist ein abschließender
Integrations-PR auf dem bestehenden Refactor-Branch vorgesehen. Damit muss
zwischen B und G kein künstlich kompatibler Stand auf main gebracht werden.
Der bereits integrierte Abschnitt A bleibt bestehen. Kein Merge, bevor der
Endstand einschließlich Cleanup, vollständigem Gate, E2E, Architekturreview
und CI bestanden hat. Keine direkten main-Commits und kein Force-Push.

### 0. Arbeitsbaum ordnen

Vor weiteren fachlichen Änderungen alle offenen Diffs zuordnen: vorhandene
Nutzeränderung, notwendiger Zielumbau oder selbst verursachter Übergangscode.
Nutzeränderungen bewahren. Nur eigenen unnötigen Code und sachfremden
Formatierungs-/Zeilenendungsdiff entfernen. Bereits sinnvolle Domain- und
Repositoryarbeit erhalten; keinen pauschalen Reset durchführen.

Arbeitscommit: `refactor: remove temporary kv compatibility path`.
Umstellungen, die für diese Entfernung unmittelbar erforderlich sind, gehören
in denselben Commit; weitere Zielarbeiten werden getrennt festgehalten.

### 1. B abschließen: eine relationale Laufzeit

- Game-/Fleet-/Maintenance-Use-Cases arbeiten mit typisierten Entities und den
  geplanten GameStateRepository-/GameUnitOfWork-Ports.
- Accounts, Cache, Rangliste und Mehrspielerkarte werden direkt verdrahtet.
  SQL bleibt in Repositories. Kein zweiter KV-Laufzeitpfad und kein Fallback.
- MarketGenerator erzeugt und erhält typisierte Angebote. Persistenzmapping
  liegt im Repository, HTTP-Projektion an der API-Grenze. Domainobjekte und
  fachliche Services kennen keine Speicherformate oder Legacy-KV-Schlüssel.
- Kauf, Disposition und Settlement bleiben atomar; Routing bleibt außerhalb
  der Transaktion. Settlement-Historie bleibt unveränderlich und einmalig.

Arbeitscommits nach Verantwortung:
`refactor: complete relational account and projection wiring`,
`refactor: keep market and game workflows typed`,
`refactor: isolate persistence and api mappings`.

### 2. C abschließen: normalisierte Referenzwelt

NhmProduct und FacilityNhmProfile trennen. Coordinates, Country, City und
Address komponieren. WorldCatalogue 4.0.0 über Backup und neue Zieldatei
aufbauen. Versioniertes Zuordnungsmanifest verwenden; Company-/Facility-UUIDs
bewahren, Stadt-UUIDs einmalig speichern, mehrdeutige Zuordnungen abweisen.
Runtime-Reader bleibt read-only. NHM-Matching und Marktverhalten erhalten.

Arbeitscommits: `refactor: separate nhm products from facility profiles`,
`feat: normalize catalogue geography with stable city identities`,
`refactor: compose facility addresses and coordinates`.

### 3. D abschließen: World-Scopes

Immutable World-/Country-/City-/Company-Filter implementieren und vorhandene
Standortabfragen umstellen. Eindeutige UID-Abfragen und ausdrücklich geprüfte
Namensmehrdeutigkeit. Companies bleiben unabhängig von einer einzelnen Stadt.

Arbeitscommits: `feat: add immutable world query scopes`,
`refactor: use world scopes in location queries`.

### 4. E: fachlicher Cleanup vor Datenübernahme

Ersetzte Modelle, alte Hydrierungswege, KV-Spielstandzugriffe, doppelte Mapper,
ungenutzte Factories und tote Imports entfernen. Hub, Minimal-Contract,
CargoType und CargoProfile erst entfernen, wenn ihre aktiven Aufrufer vollständig
umgestellt sind. Keine bloße Verschiebung dieser Altpfade in neue Wrapper.

Tests auf die finalen fachlichen Schnittstellen umstellen. Tests ausschließlich
entfernter Übergangskonstruktionen entfernen; ihre fachlich relevanten
Gegentests am neuen Verhalten erhalten. Verwaiste Manifest-Einträge bereinigen.
Architekturtests sichern SQL-, Import- und Serialisierungsgrenzen ab.

Arbeitscommits: `refactor: remove obsolete domain and persistence paths`,
`test: enforce final domain and persistence boundaries`.

### 5. F: isolierter Offline-Import

Prüf- und Ausführungsmodus auf separaten Fixtures entwickeln. Quelle read-only,
Backup obligatorisch, neue Zieldatei ohne Überschreiben, transaktionaler Import
mit vollständigem Abgleich. Unbekannte/beschädigte Daten führen zum Abbruch;
nicht spielbare Angebote werden ausdrücklich im Bericht ausgeschlossen.

Erst danach den laufenden Spielserver stoppen, echte game.db sichern und die
drei Testkonten übernehmen. IDs, Namen, Passwort-Hashes, Guthaben, Fahrzeugwerte
und historische Transportdaten bewahren. Keine Sessions/Caches übernehmen,
keine neue Routenabfrage, keine vorzeitige Abrechnung fälliger Transporte.
Erst nach erfolgreichem Abgleich die neue Datei aktivieren. Personenbezogene
Daten und Berichte bleiben außerhalb Git. Der Importer bleibt ein isoliertes
Offline-Werkzeug und wird niemals beim normalen Start aufgerufen.

Arbeitscommits: `feat: add offline legacy game state importer`,
`test: verify migration reconciliation and rollback`.
Die tatsächliche Profilübernahme erzeugt keinen Datenbank-Commit.

### 6. G: abschließender Struktur- und Dokumentations-Cleanup

Jedes verbleibende Port-/Repository-/Factory-Modul auf seinen tatsächlichen
Zweck prüfen: notwendige technische Grenze oder fachliche Verantwortung.
Reine Durchreicher, doppelte Zuständigkeiten, unbenutzte Übergangsoptionen und
übriggebliebene Hilfsskripte aus diesem Umbau entfernen. Keine neuen generischen
Abstraktionen ohne konkreten Bedarf. Kein zusätzlicher Adapter nur für alte
Tests oder einen grünen Zwischenstand.

DOMAIN_MODEL und ARCHITECTURE beschreiben den Ist-Zustand; ADRs die Gründe.
README, API, WorldCatalogue, DATA_SOURCES, GOAL und UI DESIGN abgleichen.
Refactor-Tagebuch aus Hauptdocs entfernen bzw. als Historie eindeutig ablegen.
Qualitätsbericht ausschließlich mit ausgeführten Prüfungen aktualisieren.

Arbeitscommits: `refactor: clean up completed domain persistence refactor`,
`docs: consolidate domain architecture and verification results`.

### Abschlusskriterien

- Ein aktiver relationaler Spielstandpfad; keine KV-Kompatibilität im Runtime.
- Keine SQL-/konkreten Repositoryimporte und keine Persistenzserialisierung
  in Domain oder fachlichen Services; öffentliche API-Projektionen kompatibel.
- Stabile Referenzidentitäten, unveränderte historische Snapshots und
  nachgewiesene Spielertrennung, Konkurrenzsicherheit und einmalige Abrechnung.
- Vollständiges Python-Gate: Ruff/79 Zeichen/Format, mypy, Pyright, explizite
  Funktionstest-Zuordnung und 100 % Core-Statement-Coverage.
- Frontend-Gates, Produktionsbuild und Desktop-/Mobil-E2E: Registrierung,
  Wiederanmeldung, Kauf, parallele Transporte, Offline-Ankunft, Rangliste,
  Mehrspielerkarte und Bildstabilität. Reales iPad nur bei tatsächlicher Prüfung.
- Vollständiger Migrationsabgleich und Wiederanmeldung der übernommenen Konten.
- Manueller Architektur-/Cleanup-Review, geprüfter finaler Diff und grüne CI
  vor Squash-Merge. Offene wesentliche Befunde verhindern Abschlussbehauptungen.


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

Die Port-Umstellung wurde als 246a404 committet. Anschließend bestanden alle
zehn Browserszenarien; Desktop-/Mobil-Screenshots wurden erneut geprüft.

Profilpflege, Authentifizierung, Provider-Caches und Mehrspielerprojektionen
erhalten eigene Ports. Neue relationale Ranglisten-/Traffic-Leser und der
Provider-Cache bestehen gezielte Gegentests mit 59/59 Statements. Weitere
39 Auth-/Profil-/Mehrspielertests und 41 Architektur-/Manifest-/Providerprüfungen
bestehen; mypy/Pyright sind grün. Die abschließende relationale Verdrahtung und
Mapping-Isolation bleiben der nächste Schritt innerhalb B.

## Korrektur der Umsetzung und Prüfzeitpunkte

Der Auftraggeber hat am 23.09.2026 klargestellt: Arbeitscommits enthalten die jeweils betroffenen grünen Tests. Das vollständige
Projekt-Gate ist vor der Integration und nach dem gesamten Umbau verpflichtend,
nicht nach jedem Zwischencommit. Diese Präzisierung ersetzt die vorherige
Interpretation, betroffene fehlschlagende Tests seien im Commit akzeptabel. Kleine Commits dokumentieren
den fachlichen Fortschritt; keine zusätzlichen Kompatibilitätsschichten bauen,
nur um Zwischenstände lauffähig zu halten.

Die eigenständig eingeführten TransitionGameRepository/TransitionGameUnitOfWork
und TransitionLeaderboardReader wurden vollständig entfernt, ebenso der alte
KV-MultiplayerMapRepository. Die Laufzeit verwendet unmittelbar die relationalen
Repositories. GameRuntime bündelt im bestehenden Composition Root die geteilten
Abhängigkeiten; es besitzt keine Spielzustände und keine Speicherübersetzung.
Tests greifen direkt auf die Entities/Repositories zu. Die alte game.db wurde
weiterhin weder gelesen noch verändert. Mapping-Trennung und Gesamtabnahme
bleiben offen. Der vorherige Pythonlauf hatte 241 bestandene Tests und einen
fehlgeschlagenen Cache-Logging-Test; er ist kein Nachweis für diesen neuen Stand.

## Schritt 0: direkte relationale Laufzeit geprüft

Die Übergangsschicht und der KV-Traffic-Leser sind entfernt. Auch das zunächst
zusätzlich eingeführte SqliteConnectionOwner-Protokoll wurde entfernt; konkrete
SQLite-Repositories verwenden unmittelbar SqliteGameDatabase. Account-, Cache-
und öffentliche Leseports bleiben die im Zielplan vorgesehenen Servicegrenzen.

Ausgeführt: 171 betroffene Tests erfolgreich, anschließend 58 Tests der
angepassten Spieler-/Maintenance-/Multiplayer-Prüfungen und zehn gezielte
Account-/Cache-/Architekturprüfungen erfolgreich. Pyright und mypy waren grün;
Ruff/Format werden für den Commit geprüft. Keine erneute vollständige Projekt-
oder Browserabnahme in diesem Zwischenschritt. Persistenz-/API-Mapping im Core
bleibt der nächste fachliche Umbau; die echte game.db bleibt unangetastet.

## B: typisierter Markt

Schritt 0 ist als 161bf9b committet. MarketGenerator erzeugt und verarbeitet
jetzt ContractOffer-Objekte. Die interne Marktauffrischung des GameService
speichert diese direkt; der Dict-Roundtrip zwischen Generator und Repository
ist entfernt. HTTP-Projektionen bleiben unverändert. Die noch vorhandene
Darstellung am Service-Ausgang wird im folgenden Mapping-Schritt verlagert.
34 betroffene Markt-/Spiel-/Port-/Manifesttests bestanden; ein zusätzlicher
Gegentest verbietet Serialisierung während Generierung und Wiederverwendung.

## B: typisierte Spielabläufe und HTTP-Projektion

Der Markt-Schritt wurde als dec290a committet. Spiel-, Flotten- und Karten-
Services liefern nun typisierte Ergebnisse statt öffentlicher JSON-Dicts.
Die v1-Endpunkte projizieren diese explizit; Fahrzeugbild-Präsentation wurde
vom Service- in den API-Bereich verschoben. Valhalla liefert RouteSnapshot.
GameService kennt keinen Repository-Mapper und keine Persistenzserialisierung.
Domain-Serialisierungsmethoden bestehen noch bis zum folgenden Mapping-Schritt.

Prüfung: 150 bestandene Fälle und eine falsche Tuple-/List-Testannahme im
betroffenen Lauf; diese korrigiert und zusammen mit neuen Gegentests in einem
Lauf mit 38 bestandenen Fällen geprüft. mypy und Pyright bestehen. Neue
Gegentests prüfen typisierte Rückgaben, fehlende gespeicherte Koordinaten und
Angebotsänderung während Routing ohne Abbuchung. Keine vollständige Projekt-
oder Browserabnahme für diesen Arbeitscommit behauptet.

## B: kanonische historische Dokumente

Speicherformate enthalten keine HTTP-Aliase, doppelten Endpunkte oder
berechneten Gewinnfelder mehr. Repository-Decoder stellen verschachtelte
Domainwerte wieder her und weisen fehlende beziehungsweise fremde Felder ab.
66 betroffene Tests und Pyright bestanden. Die echte game.db wurde nicht
geöffnet. Die verbleibenden Domain-Serialisierungsmethoden werden als nächster
zusammenhängender Schritt samt Aufrufern entfernt.

## B: Auftragsobjekte ohne Serialisierung

ContractOffer und ContractOfferSnapshot kennen keine Dict-Formate mehr.
Die öffentliche Darstellung liegt vollständig in project_contract; gespeicherte
Aufträge werden ausschließlich durch den Repository-Decoder hergestellt.
Die betroffenen Domain-, Markt-, Spiel-, Repository-, Transport-, Multiplayer-,
Migrations- und API-Tests bestanden; Pyright meldet keine Fehler. Regeltests
verändern typisierte Angebote gezielt über immutable Kopien.

## B: Domainwerte ohne Datenformate

PlayerState, OwnedVehicle, Referenzwerte und Katalogmodelle besitzen keine
from_dict-/to_dict-Methoden mehr. Das API projiziert Spieler-, Fahrzeug- und
Standortwerte; die relationalen Repositories konstruieren Entities direkt.
Tests verwenden Konstruktoren und benannte Zustandswechsel statt
Domain-Hydrierung öffentlicher JSON-Dokumente. Die alte separate
KV-Weltmigration bleibt ausschließlich bis zum geplanten Legacy-Abbau erhalten.

Im betroffenen Lauf bestanden 137 von 138 Fällen. Der verbleibende Test hatte
beim Aufbau eines reisenden Fahrzeugs start_trip ausgelassen; der korrigierte
Aufbau und die unmittelbar betroffenen Änderungen bestanden im Nachlauf
(fünf Fälle). mypy, Pyright und Function-Test-Manifest sind grün.

## C: NHM-Warenidentität und Facility-Evidenz getrennt

NhmProduct und FacilityNhmProfile ersetzen CargoProfile direkt, ohne Alias-
oder Übergangsklassen. Der Katalogreader komponiert gemeinsame Produkte mit
standortbezogener Evidenz; TradeNetwork verwendet ihre Produkt-Hierarchien.
API-Evidenzfelder bleiben kompatibel. Historische Dokumente speichern beide
Konzepte getrennt; DocumentedGood und Quellen bleiben eigenständige Werte.
Die NHM-/Markt-/Snapshot-/Manifesttests und unmittelbar abhängigen Spiel-,
Transport-, Repository- und API-Tests bestanden; mypy und Pyright sind grün.

## C: Referenzkatalog auf Schema 4 normalisiert

Der ausgelieferte Katalog enthält jetzt Länder, Städte mit dauerhaft
festgelegten UUIDs und verpflichtende Facility-Zuordnungen. Alle bestehenden
Referenzwerte außerhalb der aufgeteilten Geografiespalten wurden vor Aktivierung
vollständig verglichen; Company-/Facility-UUIDs blieben erhalten. Vorher wurde
ein SQLite-Backup erstellt. Eine vorhandene Katalog-View musste ebenfalls auf
Stadt-Joins umgestellt werden; ein neuer Regressionstest deckt dies ab.

Die alte Schema-2-Aufbereitung ist entfernt. Das neue Offline-Werkzeug erstellt
eine separate Datei und prüft Manifest, Identitäten und Integrität. Im
betroffenen Testlauf scheiterte nur die bisherige Korruptionsfixture an dem
nun stärkeren Koordinaten-CHECK; die Fixture erzeugt absichtlich beschädigte
Daten mit abgeschalteten CHECKs, damit der Runtime-Reader weiterhin geprüft
wird. Der Nachlauf mit diesem Fall und den drei Migrationstests bestand.
mypy/Pyright, Ruff und Formatprüfung sind grün. Die Zusammensetzung der
Facility-Domain aus Address/City/Country/Coordinates folgt als nächster Schritt.
Die echte game.db ist weiterhin unangetastet.
