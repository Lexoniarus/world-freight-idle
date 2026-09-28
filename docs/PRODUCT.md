# Produktdokumentation – World Freight Idle MVP

Die ergänzende UI-Zielrichtung steht in [UI DESIGN.md](<UI DESIGN.md>):
UI First: Die OSM-Karte mit MapLibre ist die primäre Oberfläche, Management
erfolgt über Kontextpanels. Die folgenden URLs sind direkt aufrufbare
Ansichten innerhalb derselben Kartenanwendung. Aufträge, Shop, Flotte,
Tracking und Rangliste nutzen das vorhandene Backend. Satellitenbilder,
eigene Depots und Spielerunternehmen folgen nach der Frontend-Abnahme.

## Produktidee

World Freight Idle ist ein browserbasiertes Echtzeit-Idle-Transportspiel auf realer Geografie. Der Spieler schaut wenige Male am Tag hinein, nimmt Frachtaufträge an, weist Fahrzeuge zu und verfolgt Fahrzeuge live auf einer Weltkarte. Die Zeit läuft in realer Zeit weiter, auch wenn der Browser geschlossen ist.

## MVP-Spielversprechen

Der MVP muss einen vollständigen Road-Freight-Loop liefern:

1. Spieler meldet sich an und öffnet die Weltkarte.
2. Spieler öffnet über ein eigenes idle Fahrzeug dessen Stadtmarkt.
3. Der Fahrzeugmarkt zeigt ausschließlich für das gewählte idle Fahrzeug geeignete Angebote mit validierter Delivery und erforderlicher vorbereiteter Anfahrt.
4. Spieler öffnet einen Auftrag mit **realer Von-Adresse und realer Zu-Adresse**.
5. Spieler wählt vor der Quote ausdrücklich ein geeignetes Fahrzeug in der Abholstadt. Sein tatsächlicher Standort darf von der Abholung abweichen.
6. Die Quote lädt die vorbereitete Delivery-Route und eine erforderliche vorbereitete Anfahrt; sie berechnet daraus die fahrzeugspezifische Journey.
7. Gesamtdistanz, Fahrzeit, Kosten, Vergütung und Ergebnis werden angezeigt.
8. Der Transport startet und wird persistent gespeichert.
9. Auf der Weltkarte bewegen sich aktive Trucks entlang echter Routengeometrien.
10. Browser darf geschlossen werden. Beim erneuten Öffnen wird die Position aus Realzeit + Route rekonstruiert.
11. Nach Ankunft wird das Fahrzeug an den Zielort verschoben und die Vergütung verbucht.

## Seiten des MVP

- `/` – Weltkarte mit Kapital, Reputation und Flottenstatus
- `/contracts` – Auftragsmarkt
- `/contracts/{id}` – Auftragsdetail, Route, Kalkulation, Annahme
- `/fleet` – Flottenübersicht und aktuelle Fahrzeugstandorte
- `/fleet?tab=shop` – Fahrzeugshop
- `/transports` – aktive Transporte
- `/transports/{id}` – Live-Tracking eines Transports
- `/docs` – automatisch generierte OpenAPI-Dokumentation

## Realität vs. Simulation

**Real:**
- Von-/Zu-Adressen
- 79 verifizierte Facility-Positionen mit Koordinatennachweis
- Referenzunternehmen, Facilities und dokumentierte Waren
- Straßennetz
- Truck-Routengeometrie
- Routing-Distanz
- Routing-Fahrzeit
- Echtzeit-Timestamps

**Simuliert:**
- 273 ausdrücklich geschätzte Facility-Positionen, getrennt von verifizierten Koordinaten
- Konkrete Geschäftsbeziehung
- Tonnage und konkrete Lieferung
- Auftragsentstehung
- Preis-/Kostenmodell

Damit behauptet das Spiel nicht, reale Firmen würden konkrete reale Lieferungen durchführen.

## MVP-Nichtziele

- kein globales Bahn-Routing
- kein SeaRoute-Produktionspfad
- keine Flugfracht
- keine echte Firmenlieferdatenbank
- kein komplexes Personal-/Wartungs-/Treibstoffsystem
- keine vollständige Weltwirtschaftssimulation

Diese Themen sind Folge-Meilensteine und dürfen M1 nicht blockieren.

## M1-Teilumfang – Aktueller Mehrspielerumfang

Registrierung und Anmeldung mit öffentlichem Spielernamen, privatem
Spielstand, 175.000 Euro Startkapital und einem kostenlosen IVECO S-Way 500 XC13 (24,2 t). Der
Fahrzeugshop bietet 14 reale Modellprofile aus dem SQLite-Katalog mit
getrennten Spielwerten für Preis, Nutzlast, Reputationsfreigabe und Kilometerkosten. Pro Fahrzeug kann ein Transport aktiv
sein; mehrere Fahrzeuge fahren parallel. Spieler konkurrieren in einer
Lieferungsrangliste. Aufträge sind pro Spieler generiert, kein geteilter
knapper Weltmarkt. Preise und Nutzlast sind Spielwerte, keine realen Marktangebote.

Zusätzliche Seiten: `/login` für Konten und `/leaderboard` für die Rangliste.

## Technische Konsolidierung

Die Standards-Bereinigung erhält Spielablauf, Erscheinungsbild und URLs.
Frontend-Komponenten besitzen getrennte Verantwortlichkeiten und geregelte
Lebenszyklen. Ergänzt sind Katalogkauf und fahrzeugbezogene Kilometerkosten;
die UI-First-Reihenfolge bleibt bestehen. Konstanter Verbrauch, Restmengen und
automatische Energiehalte sind aktiv; Wartung und Zuverlässigkeit folgen später.
Öffentliche Frachtstandorte bleiben von eigenen Depots unterschieden.

Der WorldCatalogue ergänzt reale Referenzunternehmen; dies ist kein Ausbau
der Spielerunternehmens- oder Depotmechanik. Eigene idle Fahrzeuge aktivieren
Stadtmärkte über city_uid. Alle geeigneten Facilities dieser Städte liefern
NHM-kompatible Angebote; Ziele bleiben weltweit verfügbar. Pan/Zoom verändert
diesen Markt nicht. Mengen verwenden gespeicherte Fahrzeugkapazität und
Waren-/Distanzprofile, die Frachtrate einen NHM-Faktor auf 0,18 €/km/t.
Unterschiedliche Facilities derselben Stadt dürfen handeln. Quote und Dispatch
verlangen ein geeignetes Fahrzeug. Details: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).

## Gemeinsamer Live-Verkehr

Aktive Straßentransporte angemeldeter Spieler werden als minimale öffentliche
Kartenprojektion gemeinsam angezeigt. Private Spielstände bleiben getrennt:
Kapital, Verträge, Erlöse, Kosten und übrige Flottendaten werden nicht geteilt.
Jeder Account erhält aus seiner stabilen Benutzer-ID eine reproduzierbare
Kartenfarbe. Unterstützte Brand-Free-Fahrzeugsprites werden je Kombination aus
Modell und Spielerfarbe einmal rasterisiert; Modelle ohne Sprite verwenden einen
Fallback-Punkt in derselben Spielerfarbe. Fremde Transportdetails bleiben nicht
aufrufbar; ein Klick identifiziert lediglich den öffentlichen Spielernamen.

Die gemeinsame Verkehrssicht bleibt read-only und accountübergreifend.
Der relationale Leser validiert gespeicherte Transport-Snapshots und liefert
über den TrafficReader-Port ausschließlich öffentliche Trackingwerte.
Fehler des Multiplayer-Verkehrsendpoints bleiben sichtbar;
der letzte gültige Kartenstand kann weiter dargestellt werden, während die UI
den Ausfall meldet. Spielerfarben werden zusätzlich als Kartenring sichtbar,
auch wenn die Einfärbung eines Fahrzeugs auf kleinem Kartenmaßstab dezent ist.


## Aktuelle technische Grundlage

Typisierte Entities, relationale SQLite-Spielpersistenz (Schema 1.1.0) und
WorldCatalogue 4.2.0 bilden die einzige Laufzeit. Historische Snapshots bleiben
bei Katalogupdates erhalten. Details beschreiben [Architektur](ARCHITECTURE.md),
[Domainmodell](DOMAIN_MODEL.md) und [Persistenz](RELATIONAL_STATE.md).
Die abgeschlossene Umbauchronik liegt im [Archiv](archive/REFACTOR_EXECUTION.md).
Aktuelle Prüfungen und Grenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).
Dieser technische Stand ersetzt weder die vollständige MVP- noch reale iPad-Abnahme.


## Erste Verbrauchssimulation

Diesel nutzt Liter, Gas Kilogramm und Elektro nutzbare kWh. Verbrauch ist konstant
nach Katalog je 100 km, ohne Last-/Wetterfaktoren. Neue und explizit übernommene
Fahrzeuge beginnen einmalig voll; danach bleibt die Restmenge erhalten.
Automatische Halte sichern 10 % Reserve. Diesel tankt 10, Gas 25, Elektro lädt
35 Minuten vor Spielzeitbeschleunigung. Erst am Ende wird vollständig aufgefüllt.
Zielankunft genau mit Reserve erzeugt keinen zusätzlichen Halt. Bei leerem
Startvorrat ist ein Halt am Ursprung möglich; weitere Halte liegen entlang der
Route. Diese Positionen behaupten keine realen Tankstellen/Ladestationen.

Fahrzeit vor Beschleunigung ist das Maximum aus Providerzeit und
Strecke/Höchstgeschwindigkeit. Providerdaten bleiben erhalten. Neue Quotes
verwenden Wartung und tatsächliche Energieeinkäufe gemäß Economy v2; der
alte aggregierte Kilometersatz wird nicht zusätzlich berechnet. Offline-Pausen
und -Ankunft benötigen keine Hintergrundjobs; beim nächsten Zugriff wird der
Endfüllstand mit Auszahlung und Settlement atomar gespeichert.


## Market v2 – implementierter Stand vom 25.09.2026

Stadtmärkte eigener idle Fahrzeuge ersetzen Nutzlastklassen und Viewport-Scope.
V2 bewahrt gültige fahrbare Angebote und ergänzt Facility-/Distanz-Coverage.
Explizite Fahrzeugwahl steuert Quote, Betriebskosten und Energie. Die tatsächliche
Anfahrt wird mitgeplant; Dispatch und anschließender Markt-Refill besitzen
getrennte Transaktionen. Historische Transporte und gespeicherte Konditionen
bleiben erhalten. Trailer, Versicherungen und weitere Simulationen sind nicht
Bestandteil dieser Änderung. World 4.2.0 und Vehicle 2.2.0 sind die einzigen
Referenzschemata. Frühere Bestandszahlen in der Fortschrittschronik beschreiben
den damaligen Katalog; OwnedVehicle-Zahlen sind kein Architekturvertrag.
Details und Abnahme: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md),
[Qualitätsbericht](../QUALITY_REPORT.md).


## Frontend v2 – operatives Unternehmen auf der Weltkarte

Die Stadt ist der zentrale Dispositionskontext, ihre UUID die Identität.
Eine bewusst gewählte Stadt bleibt auch ohne aktiven Markt erhalten; Markt v2
wird weiterhin ausschließlich durch eigene idle Fahrzeuge aktiviert. Flotte
unterscheidet stationierte, abfahrende und ankommende Fahrzeuge, der Stadtmarkt
verbindet Cargo, Facility, geeignetes Fahrzeug und fahrzeuggebundene Quote.
Unternehmen ergänzt private belegte Finanz-/Leistungsstatistik. Importierte
Fortschrittszähler und laufende erwartete Ergebnisse sind separat bezeichnet.
Map-first, echte Routengeometrie, OSM, World 4.2.0 und Catalogue 2.2.0 bleiben.
Keine Änderung an Marktregeln, Preisen, Refill-/Dispatch-Transaktionsgrenzen.
Gestaltung und Bedienung: [UI DESIGN](UI%20DESIGN.md).


## Tatsächliche Anfahrt zur Abholung

Das ausgewählte idle Fahrzeug startet am gespeicherten Standort A, fährt zur
Abholung B und anschließend zum Lieferziel C. Es muss weiterhin zur Abholstadt
gehören. A → B verursacht Fahrzeit, Energieverbrauch und Betriebskosten;
Frachterlös entsteht nur für B → C. Grundbeträge werden einmal pro Auftrag
berechnet. Abholung und Weiterfahrt sind automatisch und ohne Ladezeit.

Angebotsdetails zeigen Fahrzeugstandort, Abholung und Lieferung, getrennte
Straßenkilometer sowie Gesamtdauer und Gesamtkosten. Tracking unterscheidet
„Zur Abholung“ und „Fracht unterwegs“; Tank-/Ladepausen bleiben sichtbar.
Bei identischem Standort oder exakt gleichen Koordinaten entfällt die Anfahrt.
Routingfehler verhindern eine Annahme ohne Abbuchung. Historische Fahrten werden
nicht verändert. Die kostenlose Same-City-Reposition entfällt im Dispatch.

## Frontend-v2: verbindliche Stabilisierung

Neue Aufträge bevorzugen hohe zulässige Auslastung und speichern einen
NHM-Mindesttarif. Neue Quotes berechnen 80 € Grundkosten, Wartung für A → B → C
und tatsächlich geplante Energieeinkäufe. Nur B → C erzeugt Frachtvergütung;
negative Ergebnisse bleiben möglich. Historie bleibt unverändert.
Der Stadtmarkt zeigt ausschließlich eigene idle-Städte. Firmenfarben sind
für Front-, Seiten- und Kartendarstellung persistent auswählbar. Analytics
zeigt aktuelle verständliche Fahrzeugnamen bei unveränderter ID-Gruppierung.
Verbindliche Formeln: [ECONOMY_V2.md](ECONOMY_V2.md).

## Karten- und Firmenfarbenstabilisierung

Fahrzeuge gruppieren ausschließlich bei tatsächlicher Bildschirmüberlappung
ihrer dargestellten Assetflächen. Eigentümer und idle/enroute bleiben getrennt;
Singletons zeigen keinen Count. Gruppen behalten ein reales Fahrzeug samt
Position und Fahrtrichtung. Firmenfarbe betrifft nur explizite Lackflächen.
Die Palette ist sichtbar und besitzt Lade-/Fehler-/Retry-Zustände.
Navigation fokussiert einmalig; anschließendes Pan/Zoom bleibt frei.
Economy, Markt, Anfahrt und historische Konditionen bleiben unverändert.


Ergänzung zum freigegebenen Navigationsmodell: Weltkarte als Überblick ohne
„Alle Städte“-Scope. Fahrzeug → Transport beziehungsweise idle Fahrzeug →
Stadtmarkt. Dieser zeigt ausschließlich Angebote, deren serverseitige
`eligible_vehicle_ids` das ausgewählte eigene idle Fahrzeug enthalten.
Liste und Kartenmarker verwenden dieselbe Eignungsprojektion. Ohne gültige
Auswahl erscheint „Fahrzeug wählen“. Bei Abfahrt wird der Kontext geleert;
Polling wählt kein Ersatzfahrzeug. Der gespeicherte Spielerpool bleibt geteilt;
ein Offer darf mehrere Fahrzeuge versorgen.

## Truck-Routing-Anker

Facilities behalten ihre dokumentierte oder als Simulation gekennzeichnete
WorldCatalogue-Koordinate für Karte und historische Anzeige. Lkw-Routing
verwendet davon getrennte globale Routing-Anker je `facility_uid` und Profil.
Die strukturelle Candidate-Erzeugung bleibt facility-basiert und routerfrei.
Die anschließende Market Preparation prüft für jede Lieferung und Anfahrt
echte Hin- und Rückwege mit vier passenden Straßenendpunkten (Toleranz 10 Meter).
Erst dann veröffentlicht sie die gewählten Anker und beide Richtungen atomar.
Bis zu fünf reale Straßenkandidaten je Standort dürfen höchstens 1.000 Meter
von der ursprünglichen Facility entfernt liegen. Fehlschläge veröffentlichen
keinen Auftrag. Die Wiederprüfung erfolgt nach Nachfrage; erfolgreiche
Nachweise verfallen nach 24 Stunden, definitive Fehler nach einer Stunde und
vorübergehende Providerfehler nach 60 Sekunden.
Quote und Dispatch laden vorbereitete Routen. Die Fahrzeug-Journey ergänzt
Geschwindigkeit, Energie und Pausen; Facility-Anzeigekoordinaten bleiben erhalten.

Umsetzung und isolierte Wolfsburger Abnahme:
[Durchgängig befahrbare Standortverbindungen](CONNECTED_ROUTING_REVIEW.md).


## Route-ready Market v2

Structural Candidate → RoutingAnchor / RoutingReadiness → validierte Delivery
→ Offer mit separater RouteReference → Quote → fahrzeugspezifische Journey.
Ein partial Market enthält ausschließlich route-ready Offers; nur Coverage fehlt.
Die Fahrzeug-Eignung verlangt außerdem eine bereite Anfahrt vom tatsächlichen
Standort, außer bei identischer Facility. Bestehende geprüfte Offers erscheinen
sofort, während der Backend-Worker fehlende Coverage vorbereitet. Es gibt kein
Browser-Geocoding und keine Rückkehr zum ungeprüften Quote-Routing.

Status des aktuellen Review-/Vehicle-Ready-Fixes: implementiert; gezielte
Prüfungen siehe Qualitätsbericht. Vollständige Nutzer-Gesamtabnahme ausstehend.
Reale Providerprüfungen bleiben eine gesonderte Betriebsabnahme.


## Vehicle-Ready-Coverage

Die Stadt-/Facility-/Distanzziele bleiben erhalten. Zusätzlich benötigt jedes
eigene idle Fahrzeug fahrbare Angebote für seine geeigneten Abholstandorte und
mindestens drei pro strukturell verfügbarem Distanzband. Geteilte Offers zählen
für jedes tatsächlich geeignete Fahrzeug. Die Vorbereitung berücksichtigt
Kapazität und ready Approaches bereits vor Materialisierung; kleinere Fahrzeuge
werden nicht mit nur für große Fahrzeuge geeigneten Angeboten abgefertigt.
Bei unerreichbarer Coverage bleiben nur tatsächlich fahrbare Angebote sichtbar,
mit Diagnose fehlender Standorte/Bänder. `partial` bedeutet fehlende Coverage,
`exhausted` einen ausgeschöpften nutzbaren Pool; beide erlauben keine ungeprüften
Angebote. Ein späterer Anchor-/Providerwechsel kann die Vorbereitung reaktivieren.
Tonnagenverteilung, Tarif, Anfahrt, Energie und historische Transporte bleiben
unverändert. Ein Generierungsfahrzeug reserviert weiterhin kein Angebot.


## Runtime-Trennung und Alttransport-Reparatur (27.09.2026)

Die neue verbindliche Abschlussvoraussetzung ersetzt die fruehere Beschraenkung
auf gezielte Routingtests: vollstaendiges Quality-Gate mit 100 % app-Statement-
Coverage sowie komplette Browserregression vor Commit/Push auf feature/frontend-v2.
Runtime und Vorbereitung laufen getrennt; Spielstand und Flotte erscheinen vor
Geometrien und Markt. Read-Ziel p95 <= 250 ms, weitere Spielerstarts <= 2 s
(einmaliger Kaltstart mit Settlement bei 3,39 s am 28.09.2026 akzeptiert),
Runtime plus Verkehr <= 250 KiB pro Poll. Keine unveraenderten Geometrien im Polling.

Die beiden bestaetigten optionalen Alt-Anfahrtsplaene werden nur offline auf
einer gesicherten Kopie repariert. Live-Aktivierung und echte iPad-Abnahme bleiben
separate Betriebsschritte. Implementierung und tatsaechlicher Abnahmestand:
[Runtime-Review](RUNTIME_ISOLATION_REVIEW.md) und [Qualitaetsbericht](../QUALITY_REPORT.md).


## Gemeinsamer Auftragsvorrat (28.09.2026)

Das ausgewählte Fahrzeug erhält genau drei fahrbare Angebote je Streckentyp,
sofern genügend geprüfter Bestand verfügbar ist. Der gemeinsame Hintergrundvorrat
hält mindestens zehn Vorlagen je Bedarfsstadt, konkretem Modell und Band; jede
Vorlage ist einmal je Spieler verwendbar. Die drei sichtbaren gehören zu diesen
zehn. Kompatible eigene Fahrzeuge dürfen dieselben persönlichen Angebote nutzen.

Ungenutzte Vorlagen und Angebote verfallen nicht zeitlich und bleiben bei Abfahrt
und Rückkehr erhalten. Ein Verbrauch lässt gespeicherte Reserve sofort nachrücken;
der Worker füllt nach. Bedarf entsteht im Stand und ab 60 Minuten vor gespeicherter
Ankunft. Fehlende Hin-/Rückwege, veraltete Prüfnachweise oder unbrauchbare
Katalogbezüge geben keine Angebote frei. Alle 14 Modelle werden in Bedarfsstädten
berücksichtigt, tatsächlich wartende Fahrzeuge zuerst.

Die Schemaübernahme nach 1.2.0 ist ein expliziter Offline-Schritt mit Backup und
neuer Ausgabe. Live-Aktivierung ist nicht Teil von Commit/Push. Verbindliche
Gesamtabnahme: Quality-Gate mit 100 % app-Statement-Coverage, vollständige
Browserregression und Leistungsabnahme. Tatsächlicher Stand und Grenzen stehen
im [Qualitätsbericht](../QUALITY_REPORT.md); Verantwortlichkeiten in
[ADR 0008](adr/0008-shared-market-stock.md).
