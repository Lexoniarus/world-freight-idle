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
- Verifizierte Koordinaten mit Quellen
- Referenzunternehmen, Facilities und dokumentierte Waren
- Straßennetz
- Truck-Routengeometrie
- Routing-Distanz
- Routing-Fahrzeit
- Echtzeit-Timestamps

**Simuliert:**
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
Fahrzeugshop bietet acht reale Modellprofile aus dem SQLite-Katalog mit
getrennten Spielwerten für Preis, Nutzlast, Reputationsfreigabe und Kilometerkosten. Pro Fahrzeug kann ein Transport aktiv
sein; mehrere Fahrzeuge fahren parallel. Spieler konkurrieren in einer
Lieferungsrangliste. Aufträge sind pro Spieler generiert, kein geteilter
knapper Weltmarkt. Preise und Nutzlast sind Spielwerte, keine realen Marktangebote.

Zusätzliche Seiten: `/login` für Konten und `/leaderboard` für die Rangliste.

## Technische Konsolidierung

Die Standards-Bereinigung erhält Spielablauf, Erscheinungsbild und URLs.
Frontend-Komponenten besitzen getrennte Verantwortlichkeiten und geregelte
Lebenszyklen. Ergänzt sind Katalogkauf und fahrzeugbezogene Kilometerkosten;
die UI-First-Reihenfolge bleibt bestehen. Wartung, Energiehalte, Reichweite
und Zuverlässigkeit sind noch keine aktiven Mechaniken. Öffentliche Frachtstandorte bleiben von eigenen
Depots unterschieden.

Der WorldCatalogue ergänzt reale Referenzunternehmen; dies ist kein Ausbau
der Spielerunternehmens- oder Depotmechanik. Jeder routbare Standort erhält Aufträge. Verwendet werden dokumentierte
Standardwaren oder ausdrücklich simulierte Standardfracht ohne Warenbeleg
(DB-nutzlastabhängige Mengen, 0,18 €/km/t). Derselbe Ort oder dieselbe
Firma darf beide Endpunkte besitzen; dieselbe Facility nicht. Details und
Bestandskompatibilität: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).

## Gemeinsamer Live-Verkehr

Aktive Straßentransporte angemeldeter Spieler werden als minimale öffentliche
Kartenprojektion gemeinsam angezeigt. Private Spielstände bleiben getrennt:
Kapital, Verträge, Erlöse, Kosten und übrige Flottendaten werden nicht geteilt.
Jeder Account erhält aus seiner stabilen Benutzer-ID eine reproduzierbare
Kartenfarbe. Unterstützte Brand-Free-Fahrzeugsprites werden je Kombination aus
Modell und Spielerfarbe einmal rasterisiert; Modelle ohne Sprite verwenden einen
Fallback-Punkt in derselben Spielerfarbe. Fremde Transportdetails bleiben nicht
aufrufbar; ein Klick identifiziert lediglich den öffentlichen Spielernamen.
