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
2. Spieler wechselt auf den Auftragsmarkt.
3. Spieler öffnet einen Auftrag mit **realer Von-Adresse und realer Zu-Adresse**.
4. Das System liest die bei Auftragserzeugung gespeicherten Facility-Koordinaten.
5. Das System berechnet eine echte Truck-Route über Valhalla/OpenStreetMap.
6. Distanz, Routing-Zeit, Kosten, Vergütung und Marge werden angezeigt.
7. Spieler weist ein passendes Fahrzeug am Startort zu.
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
Strecke/Höchstgeschwindigkeit. Providerdaten, Kilometerkosten und Erlösformel
bleiben erhalten. Es gibt keine zusätzlichen Kraftstoffgebühren. Offline-Pausen
und -Ankunft benötigen keine Hintergrundjobs; beim nächsten Zugriff wird der
Endfüllstand mit Auszahlung und Settlement atomar gespeichert.


## Market v2 – implementierter Stand vom 25.09.2026

Stadtmärkte eigener idle Fahrzeuge ersetzen Nutzlastklassen und Viewport-Scope.
V2 bewahrt gültige fahrbare Angebote und ergänzt Facility-/Distanz-Coverage.
Explizite Fahrzeugwahl steuert Quote, Betriebskosten und Energie. Same-City-
Reposition ist kostenlos; Dispatch und anschließender Markt-Refill besitzen
getrennte Transaktionen. Historische Transporte und gespeicherte Konditionen
bleiben erhalten. Trailer, Versicherungen und weitere Simulationen sind nicht
Bestandteil dieser Änderung. World 4.2.0 und Vehicle 2.2.0 sind die einzigen
Referenzschemata. Frühere Bestandszahlen in der Fortschrittschronik beschreiben
den damaligen Katalog; OwnedVehicle-Zahlen sind kein Architekturvertrag.
Details und Abnahme: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md),
[Qualitätsbericht](../QUALITY_REPORT.md).
