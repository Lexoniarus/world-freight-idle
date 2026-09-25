# World Freight Idle

## Projektdefinition, Produktvision und Entwicklungsrahmen

**Dokumentstatus:** Product North Star

**Version:** 0.2 (Vision unverändert; Statusabgleich ergänzt)

**Projektart:** Browserbasierter Multiplayer-Logistik-Tycoon / Real-Time-Idle-Game

**Primäre Plattform:** Webbrowser

**Backend-Schwerpunkt:** Python

**Grundprinzip:** Reale Welt als Spielbrett, reale Daten als Grundlage, generierte Spielwirtschaft als Gameplay

---

## Umsetzungsstand am 23.09.2026

**Verbindliche Priorität: UI First.** Die Oberfläche wird auf dem bestehenden
Backend fertiggestellt, bevor Spielerunternehmen, eigene Depots und weitere
Wirtschaftsmechaniken ausgebaut werden. [UI DESIGN.md](<UI DESIGN.md>) ergänzt
die Vision um Abschnitte 42–63. Für M1 gilt die neuere Entscheidung:
MapLibre GL JS mit OSM-Standardkarte, Pan/Zoom, World Wrapping und
Kontextpanels. Satellitenbilder folgen später über einen austauschbaren
SatelliteTileProvider; sie sind keine M1-Abnahmevoraussetzung.

Dieser Abschnitt beschreibt den geprüften Ist-Stand. Die folgenden 41
Abschnitte bleiben das langfristige Zielbild und sind keine Behauptung,
dass sämtliche Funktionen bereits implementiert sind.

| Bereich | Stand |
| --- | --- |
| Python-Module, OOP, PEP 8, main.py | Bestehende Basis konsolidiert; Ruff mit 79 Zeichen, differenzierte Architekturabnahme in TARGET.md |
| Registrierung, Login, Logout, Sessions | Implementiert; eigene Spielstände |
| Eigenständiges Spielerunternehmen | Offen; aktuell Konto mit Spielerkapital und Reputation |
| Eigenes Depot / Depotkauf | Offen; aktuell öffentliche Facilities und Start in Berlin Westhafen |
| Fahrzeuge kaufen, Standort und Kapazität | Implementiert; 14 DB-Modelle mit Spiel-Nutzlast, Kaufpreis und Freigaben |
| Reale Hersteller-/Modell-/Verbrauchsdaten | 14 Modellprofile von acht Herstellern integriert; konstante Verbrauchssimulation, 10 % Reserve und automatische Tank-/Ladepausen aktiv |
| Reale Adressen, Straßenroute, Distanz, ETA | WorldCatalogue mit 79 verifizierten und 273 ausdrücklich geschätzten Positionen und Valhalla-Truck-Routing; Nominatim nur offline |
| Aufträge, parallele Transporte, Offline-Auszahlung | Implementiert und auf konkurrierende Zugriffe getestet |
| Tracking | Alle aktiven Transporte als Layer, Serverzeit und gespeicherte Route |
| Primäre Weltkarte mit Kontextpanels | MapLibre/OSM implementiert; Satelliten später |
| Wettbewerb | Gemeinsame Lieferungsrangliste und öffentlicher Live-Verkehr implementiert |
| Gemeinsamer knapper Markt / dynamische Frachtraten | Offen; aktuell eigene generierte Märkte |
| Transporthistorie und Geldbewegungsjournal | Aktive und abgerechnete Transporte werden gespeichert; Historienoberfläche und Geldjournal bleiben offen |
| Reale Firmen / statistische Warenströme | Referenzunternehmen/Facilities und dokumentierte Waren integriert; Beziehungen, Mengen und Einzelaufträge simuliert; statistische Wirtschaftsmechanik offen |
| PostgreSQL, öffentlicher Betrieb, Account-Recovery | Offen; lokaler SQLite-MVP mit einem Prozess |

**M1 gemäß Abschnitt 35 ist noch nicht vollständig abgeschlossen.**
Der ausführbare Stand ist eine geprüfte Mehrspielergrundlage. Die nächsten
M1-Lücken sind das eigenständige Unternehmensmodell und ein persistentes
Startdepot mit Besitz und Kapazität. Weitere Standorte, Leerfahrten und
Wartung folgen gemäß M3. Rangliste und einfacher Fahrzeugshop sind bereits
vorhandene Teilfunktionen der späteren M3-/M4-Ziele.

Die Standards-Bereinigung konkretisiert Abschnitte 21 und 27–29 für die
vorhandene UI-Basis: getrennte Controller/Views/Kartenmodule, definierte
Ressourcenfreigabe, Provider-Ports, sichere DOM-Ausgabe und Frontend-Gates.
Sie ergänzt keine Backend-Spielmechaniken. Werkzeugerfolg und Architektur-
review werden getrennt dokumentiert; künftige Änderungen benötigen erneut
Verhaltenstests und ein Review ihrer Verantwortlichkeiten.

Verbindliche Umsetzungssicht: [TARGET.md](TARGET.md),
[MILESTONES.md](MILESTONES.md), [ARCHITECTURE.md](ARCHITECTURE.md).
Prüfbelege und verbleibende Grenzen: [QUALITY_REPORT.md](../QUALITY_REPORT.md).

---

## 1. Executive Summary

**World Freight Idle** ist ein browserbasierter, persistenter Multiplayer-Logistik-Tycoon, der auf der realen Welt basiert.

Spieler gründen ein eigenes Logistikunternehmen, kaufen Fahrzeuge und Depots, nehmen Frachtaufträge an und bauen schrittweise ein regionales, nationales und später internationales Transportnetz auf.

Das Spiel unterscheidet sich von klassischen Transport-Tycoons dadurch, dass die reale Welt nicht lediglich als optischer Hintergrund dient.

Wo immer sinnvoll, basieren zentrale Spielelemente auf realen Daten:

* reale geografische Standorte

* reale Straßen

* reale Streckenverläufe

* reale Entfernungen

* reale Unternehmen und Betriebsstandorte

* reale Fahrzeugmodelle

* realistische Fahrzeugdaten

* reale Häfen, Flughäfen und Bahninfrastruktur

* reale Branchenstrukturen

* reale statistische Warenströme

* reale Reise- und Transportzeiten

Die konkreten Frachtaufträge werden dagegen spielerisch generiert.

Das Spiel behauptet daher beispielsweise **nicht**, dass ein reales Unternehmen tatsächlich eine bestimmte Lieferung an ein anderes reales Unternehmen verschickt.

Stattdessen können reale wirtschaftliche Strukturen dazu verwendet werden, plausible Spielaufträge zu erzeugen.

Das Ergebnis soll sich anfühlen wie:

**Transport Tycoon + reale Weltkarte + Flightradar/Food-Tracking + Idle-Game + persistente Multiplayer-Wirtschaft.**

---

## 2. Produktvision

Die langfristige Vision ist eine lebendige digitale Logistikwelt, in der viele Spieler parallel ihre eigenen Transportunternehmen betreiben.

Die reale Welt bildet dabei das Spielfeld.

Ein Spieler kann beispielsweise:

* ein Depot in Berlin besitzen,

* dort drei LKW stationieren,

* einen Auftrag von Berlin nach Prag annehmen,

* einen Truck zuweisen,

* die reale Straßenroute berechnen lassen,

* das Fahrzeug anschließend über mehrere reale Stunden auf der Karte verfolgen,

* bei Ankunft Geld und Reputation erhalten,

* den Truck nun tatsächlich in Prag stehen haben,

* dort einen Rückauftrag nach Dresden suchen,

* später ein zweites Depot in Hamburg erwerben,

* einen eigenen Fuhrpark aufbauen,

* in den Schienenverkehr einsteigen,

* Hafenstandorte erschließen,

* Schiffe kaufen,

* internationale Lieferketten aufbauen

* und mit anderen Spielern um attraktive Aufträge und Märkte konkurrieren.

Der Spieler soll langfristig nicht nur Fahrzeuge besitzen.

Er soll ein **Logistiknetzwerk besitzen und optimieren**.

---

## 3. Kernfantasie des Spielers

Die zentrale Player Fantasy lautet:

> „Ich baue aus einem kleinen regionalen Transportbetrieb ein internationales Logistikunternehmen auf einer realen Weltkarte.“

Der Fortschritt soll physisch sichtbar sein.

Am Anfang besitzt der Spieler möglicherweise:

* ein kleines Depot,

* einen gebrauchten LKW,

* wenig Kapital,

* wenige verfügbare Aufträge.

Später sieht derselbe Spieler auf seiner Weltkarte:

* Dutzende Fahrzeuge,

* mehrere Depots,

* laufende Transporte,

* internationale Relationen,

* Schiffe auf See,

* Züge zwischen Terminals,

* Flugzeuge zwischen Cargo-Hubs

* und ein eigenes logistisches Netzwerk.

Wachstum wird dadurch nicht nur durch Zahlen dargestellt, sondern unmittelbar auf der Karte sichtbar.

---

## 4. Produktprinzipien

## 4.1 Die reale Welt ist das Spielbrett

Die Welt soll nicht künstlich nachgebaut werden, wenn reale Geodaten verfügbar sind.

Straßen, Orte, Grenzen, Häfen, Flughäfen und andere relevante Infrastrukturen sollen möglichst aus etablierten Geodatenquellen stammen.

Die Karte ist nicht nur Dekoration.

Sie beeinflusst das Gameplay.

---

## 4.2 Standort ist Gameplay

Ein Fahrzeug besitzt immer einen geografischen Standort.

Ein Truck in Prag kann keinen Auftrag übernehmen, der in Rotterdam startet.

Ein Spieler muss deshalb über folgende Fragen nachdenken:

* Wo stationiere ich Fahrzeuge?

* Wo kaufe ich Depots?

* Welche Regionen bediene ich?

* Lohnt sich eine Leerfahrt?

* Suche ich Rückfracht?

* Verlege ich Teile meiner Flotte?

* Welche Korridore sind wirtschaftlich interessant?

Geografie wird dadurch zu einer strategischen Ressource.

---

## 4.3 Zeit ist real

World Freight Idle ist grundsätzlich ein Real-Time-Idle-Game.

Eine Fahrt muss nicht in wenigen Sekunden abgeschlossen sein.

Wenn eine realistische beziehungsweise spielerisch realistische Transportzeit acht Stunden beträgt, darf das Fahrzeug auch mehrere reale Stunden unterwegs sein.

Eine Seereise kann Tage dauern.

Der Spieler soll deshalb nicht dauerhaft online sein müssen.

Das System speichert unter anderem:

* Startzeit

* geplante Route

* erwartete Ankunft

* Fahrzeug

* Auftrag

* Status

Beim erneuten Öffnen des Spiels wird der Zustand aus der real vergangenen Zeit rekonstruiert.

Ist das Spiel geöffnet, wird das Fahrzeug sichtbar entlang der gespeicherten Route bewegt.

---

## 4.4 Realismus dient dem Gameplay

World Freight Idle ist keine wissenschaftliche Logistik-Simulation.

Reale Daten werden dort genutzt, wo sie Gameplay glaubwürdiger, interessanter oder strategischer machen.

Realismus ist kein Selbstzweck.

Beispielsweise können echte Straßen und echte Entfernungen verwendet werden, während Preise, Wartungsintervalle oder Vertragswerte spielerisch balanciert werden.

---

## 4.5 Reale Grundlage, generierte Ereignisse

Das Spiel trennt strikt zwischen:

**realen Basisdaten**

und

**generierten Spielereignissen**.

Ein realer Produktionsstandort kann existieren.

Ein realer Hafen kann existieren.

Eine reale Firma kann existieren.

Eine reale Branche kann existieren.

Die konkrete Aussage:

> „Unternehmen A liefert heute 18 Tonnen Fahrzeugteile an Unternehmen B“

ist jedoch ein generierter Spielauftrag und keine Tatsachenbehauptung.

Diese Trennung muss technisch und in der Produktkommunikation klar bleiben.

---

## 5. Kernspielschleife

Die wichtigste Spielschleife lautet:

**Auftrag finden → wirtschaftlich bewerten → Fahrzeug auswählen → Transport starten → Transport verfolgen → Lieferung abschließen → Kapital erhalten → Netzwerk ausbauen**

Im Detail:

1. Spieler öffnet den Auftragsmarkt.

2. Das System zeigt verfügbare Frachtaufträge.

3. Ein Auftrag besitzt Start- und Zieladresse.

4. Das System berechnet die reale Route.

5. Entfernung und Fahrzeit werden ermittelt.

6. Betriebskosten werden kalkuliert.

7. Der Spieler sieht den erwarteten Gewinn.

8. Er wählt ein geeignetes Fahrzeug.

9. Das Fahrzeug muss geografisch verfügbar sein.

10. Der Auftrag wird angenommen.

11. Der Transport startet.

12. Das Fahrzeug bewegt sich über reale Zeit entlang der Strecke.

13. Der Spieler kann die Fahrt live verfolgen.

14. Bei Ankunft wird der Auftrag abgeschlossen.

15. Umsatz, Kosten, Gewinn und Reputation werden verbucht.

16. Das Fahrzeug befindet sich anschließend am Ziel.

17. Der Spieler sucht dort neue Fracht oder verlegt das Fahrzeug.

18. Gewinne werden in weitere Fahrzeuge, Depots oder Infrastruktur investiert.

Diese Schleife ist der Kern des gesamten Spiels.

Alle späteren Systeme müssen sie erweitern und nicht ersetzen.

---

## 6. Session-Struktur

World Freight Idle soll unterschiedliche Nutzungsintensitäten ermöglichen.

## Kurzer Check-in

Dauer ungefähr 1–3 Minuten.

Der Spieler:

* prüft Ankünfte,

* kassiert abgeschlossene Transporte,

* weist neue Aufträge zu,

* überprüft wichtige Fahrzeuge.

## Normale Session

Dauer ungefähr 5–15 Minuten.

Der Spieler:

* analysiert Aufträge,

* optimiert Fahrzeugstandorte,

* kauft Fahrzeuge,

* plant Expansion,

* untersucht neue Märkte.

## Intensive Management-Session

Der Spieler:

* analysiert komplette Netzwerke,

* optimiert Depots,

* verschiebt Fahrzeuge,

* plant internationale Transportketten,

* beobachtet Marktpreise,

* vergleicht sich mit Konkurrenten.

Das Spiel soll keinen permanenten Online-Zwang erzeugen.

---

## 7. Spielerunternehmen

Jeder Account besitzt mindestens ein Spielerunternehmen.

Ein Unternehmen enthält langfristig unter anderem:

* Name

* Logo

* Firmensitz

* Kapital

* Unternehmenswert

* Reputation

* Erfahrung

* Rang

* Flotte

* Depots

* laufende Transporte

* abgeschlossene Transporte

* Statistiken

* freigeschaltete Transportarten

* Marktpositionen

Die Spielfirma ist die zentrale Besitzstruktur.

---

## 8. Flottensystem

Fahrzeuge bilden einen zentralen Wirtschaftsfaktor.

Jedes Fahrzeug ist eine individuelle Entität.

Es besitzt beispielsweise:

* Fahrzeug-ID

* Eigentümer

* Hersteller

* Modell

* Baujahr

* Fahrzeugklasse

* Transportmodus

* Kapazität

* Geschwindigkeit

* Verbrauch

* Betriebskosten

* Zustand

* Kilometerstand

* aktueller Standort

* Heimatdepot

* aktueller Auftrag

* Status

* Kaufpreis

* Restwert

Langfristig können weitere Faktoren ergänzt werden:

* Wartung

* Zuverlässigkeit

* Alter

* Emissionsklasse

* Versicherung

* Fahrer

* Spezialisierung

* Kühlfähigkeit

* Gefahrgutzulassung

---

## 9. Reale Fahrzeuge

Fahrzeugmodelle sollen langfristig möglichst reale Vorbilder haben.

Beispiele:

* Mercedes-Benz Actros

* MAN TGX

* Volvo FH

* Scania R-Serie

Später:

* reale Lokomotivmodelle

* reale Containerschifftypen

* reale Cargo-Flugzeuge

Dabei muss jedoch frühzeitig geklärt werden, welche Marken-, Bild- und Produktdaten verwendet werden dürfen.

Fahrzeugbilder, Markenlogos und Produktnamen sind getrennt von technischen Fakten zu betrachten.

Der Datenlayer muss deshalb so gestaltet sein, dass reale Fahrzeugdaten notfalls auch mit generischen Präsentationsdaten kombiniert werden können.

---

## 10. Depots und Standorte

Depots bilden die geografische Infrastruktur des Spielerunternehmens.

Ein Depot besitzt mindestens:

* geografischen Standort

* Eigentümer

* Kapazität

* verfügbare Stellplätze

* unterstützte Fahrzeugtypen

* Kauf- beziehungsweise Mietkosten

* laufende Kosten

Später können Depots zusätzliche Funktionen erhalten:

* Wartung

* Reparatur

* Betankung

* Fahrzeughandel

* Cargo-Umschlag

* Zwischenlagerung

* Personal

* Spezialisierungen

Standorte sollen strategisch relevant sein.

Ein Depot in Hamburg eröffnet andere Möglichkeiten als eines in München.

---

## 11. Auftragsmarkt

Der Auftragsmarkt ist eines der wichtigsten Systeme.

Ein Contract enthält mindestens:

* Contract-ID

* Auftraggeber

* Absender

* Empfänger

* Startadresse

* Zieladresse

* Startkoordinate

* Zielkoordinate

* Frachtart

* Gewicht

* Volumen

* erforderlicher Fahrzeugtyp

* mögliche Transportmodi

* Deadline

* erwartete Transportdauer

* Vergütung

* Betriebskosten

* erwartete Marge

* Verfügbarkeit

* Ablaufzeit

---

## 12. Quest- beziehungsweise Contract-Generierung

Aufträge werden dynamisch erzeugt.

Dabei sollen reale Daten als Grundlage verwendet werden.

Das System kann beispielsweise berücksichtigen:

* Unternehmensbranche

* Standort

* Produktionsstruktur einer Region

* Import-/Exportstruktur

* statistische Warenströme

* verfügbare Transportmodi

* Fahrzeugkapazität

* Entfernung

* regionale Nachfrage

* Spieleraktivität

Beispiel:

Eine reale Automobilregion produziert statistisch viele Fahrzeugkomponenten.

Ein anderes Wirtschaftszentrum besitzt entsprechende Industrie.

Das Spiel kann daraus einen plausiblen Auftrag erzeugen.

Der einzelne Auftrag bleibt fiktiv.

Die strukturelle Wahrscheinlichkeit basiert jedoch auf realen Daten.

---

## 13. Firmen

Langfristig sollen reale Unternehmen und reale Betriebsstandorte einen wichtigen Bestandteil der Welt bilden.

Mögliche Datenquellen können unter anderem sein:

* OpenStreetMap

* GLEIF

* öffentliche Unternehmensregister

* andere geeignete offene Firmendaten

Dabei werden Unternehmen intern normalisiert.

Ein Company-Datensatz könnte enthalten:

* interne ID

* offizieller Name

* Branche

* Standort

* Adresse

* Koordinaten

* Unternehmensgröße

* wirtschaftliche Rolle

* mögliche Input-Güter

* mögliche Output-Güter

* Datenquelle

* Datenstand

* Lizenzinformationen

Der Game-Core darf niemals unmittelbar von einem einzelnen externen Anbieter abhängig sein.

---

## 14. Reale Strecken

Routen müssen möglichst aus echten Verkehrsnetzen berechnet werden.

## Straße

Grundlage:

* reale Straßen

* reale Straßengeometrie

* reale geografische Restriktionen

* geeignete Routing-Profile für LKW

Mögliche Grundlage:

OpenStreetMap + Valhalla oder vergleichbarer selbst hostbarer Routing-Stack.

## Schiene

Später:

* reales Schienennetz

* Terminals

* Güterbahnhöfe

* Streckenrestriktionen

## See

Später:

* reale Häfen

* Seewege

* Kanäle

* maritime Routing-Netze

## Luft

Später:

* reale Airports

* Great-Circle-Routen

* Cargo-Hubs

Jeder Transportmodus erhält einen eigenen Provider beziehungsweise Routing-Adapter.

---

## 15. Live-Tracking

Ein zentrales visuelles Feature ist die Live-Verfolgung laufender Transporte.

Das Erlebnis soll sich eher wie modernes Delivery Tracking oder Flight Tracking anfühlen als wie eine klassische abstrakte Tycoon-Tabelle.

Der Spieler sieht:

* Fahrzeug

* aktuelle Position

* Route

* Fortschritt

* Start

* Ziel

* aktuelle beziehungsweise simulierte Geschwindigkeit

* ETA

* Fracht

* verbleibende Entfernung

Der Server muss dafür kein Fahrzeug permanent bewegen.

Persistiert werden:

* Route

* Abfahrtszeit

* Ankunftszeit

* gegebenenfalls Geschwindigkeitsprofil

Aus der aktuellen Uhrzeit kann jederzeit die aktuelle Position rekonstruiert werden.

---

## 16. Multiplayer

World Freight Idle soll langfristig ein Multiplayer-Spiel sein.

Multiplayer bedeutet dabei zunächst nicht direkte Fahrzeugkollisionen oder Echtzeit-PvP.

Der Wettbewerb entsteht hauptsächlich wirtschaftlich.

Spieler konkurrieren beispielsweise um:

* attraktive Aufträge

* profitable Regionen

* Depotstandorte

* Frachtraten

* Marktanteile

* Rankings

* Unternehmenswert

* Effizienz

---

## 17. Gemeinsamer Auftragsmarkt

Langfristig können bestimmte Aufträge global oder regional geteilt werden.

Beispiel:

Ein besonders profitabler Auftrag erscheint.

Mehrere Spieler können ihn sehen.

Wer ihn zuerst sinnvoll bedienen kann, besitzt einen Vorteil.

Später können weitere Mechanismen entstehen:

* Ausschreibungen

* Mindestpreisangebote

* langfristige Verträge

* Exklusivverträge

* Großkunden

* Auktionen

---

## 18. Dynamische Wirtschaft

Die Wirtschaft soll langfristig auf Spieleraktivität reagieren.

Beispiel:

Viele Spieler stationieren Trucks auf Berlin–Paris.

Dadurch steigt die verfügbare Transportkapazität.

Die durchschnittliche Vergütung kann sinken.

Auf Rotterdam–München fehlt dagegen Kapazität.

Dort steigen die Frachtraten.

Spieler reagieren darauf und verschieben Fahrzeuge.

Dadurch verändert sich der Markt erneut.

So entsteht eine teilweise spielergetriebene Wirtschaft.

---

## 19. Progression

Die Progression soll mehrere Ebenen besitzen.

## Kurzfristig

* Auftrag erfolgreich abschließen

* Gewinn erzielen

* Reputation erhalten

## Mittelfristig

* weiteres Fahrzeug kaufen

* besseres Fahrzeug kaufen

* zweites Depot eröffnen

* neue Regionen erschließen

## Langfristig

* nationales Netzwerk

* internationale Expansion

* multimodale Logistik

* Unternehmensimperium

* Wettbewerb mit großen Spielerfirmen

Progression soll möglichst aus realer wirtschaftlicher Expansion entstehen und nicht primär aus abstrakten Levelzahlen.

---

## 20. Website-Struktur

Die Anwendung soll als echte Website mit getrennten Produktbereichen aufgebaut werden.

Mindestens vorgesehen:

## Login / Account

* Registrierung

* Anmeldung

* Passwortverwaltung

* Sessionverwaltung

## Dashboard

* Kapital

* Unternehmensstatus

* aktive Transporte

* verfügbare Fahrzeuge

* letzte Ankünfte

* wichtige Ereignisse

## Auftragsmarkt

* Auftragsliste

* Filter

* Startregion

* Zielregion

* Frachtart

* Fahrzeugtyp

* Profitabilität

## Auftragsdetail

* Von-Adresse

* Zu-Adresse

* reale Karte

* Strecke

* Distanz

* ETA

* Cargo

* Einnahmen

* Kosten

* Marge

* geeignete Fahrzeuge

## Flotte

* alle Fahrzeuge

* Standort

* Status

* Zustand

* Heimatdepot

## Fahrzeugdetail

* technische Daten

* aktuelle Position

* Historie

* Aufträge

* Betriebskosten

## Transporte

* laufende Transporte

* abgeschlossene Transporte

## Transportdetail

* Live-Karte

* aktuelle Position

* ETA

* Route

* Fracht

## Depots

* eigene Standorte

* Kapazität

* Fahrzeuge

## Depotmarkt

* verfügbare Standorte

* Preise

* wirtschaftliche Region

## Wettbewerb

Später:

* Rankings

* Unternehmenswerte

* Marktanteile

* regionale Rankings

---

## 21. Technische Architektur

Das Projekt soll modular aufgebaut werden.

Grundprinzip:

**UI → API → Application Layer → Domain → Provider/Repositories**

Nicht:

**Frontend → GameService → SQLite → externe API in derselben Funktion**

---

## 22. API-First-Ansatz

Das Frontend kommuniziert ausschließlich über dokumentierte APIs.

Beispielstruktur:

`/api/v1/auth`

`/api/v1/company`

`/api/v1/contracts`

`/api/v1/fleet`

`/api/v1/vehicles`

`/api/v1/depots`

`/api/v1/transports`

`/api/v1/market`

`/api/v1/rankings`

API-Versionierung ist verpflichtend.

DTOs und Domain-Objekte werden getrennt behandelt.

---

## 23. Provider-Abstraktion

Externe Systeme werden ausschließlich über definierte Provider-Interfaces eingebunden.

Beispiele:

`GeocodingProvider`

`RoadRoutingProvider`

`RailRoutingProvider`

`SeaRoutingProvider`

`AirportProvider`

`CompanyDataProvider`

`VehicleDataProvider`

`TradeDataProvider`

Dadurch ist das Spiel nicht fest an Nominatim, Valhalla oder einen anderen Dienst gekoppelt.

---

## 24. Externe Datenquellen

Mögliche Datenquellen beziehungsweise Technologien:

**Geografie**

* OpenStreetMap

* Natural Earth

**Geocoding**

* Nominatim

**Straßenrouting**

* Valhalla

**Unternehmen**

* GLEIF

* OpenStreetMap

* weitere offene Register

**EU-Warenströme**

* Eurostat

**USA**

* Freight Analysis Framework

**Internationaler Handel**

* UN Comtrade

**Airports**

* OurAirports

**Seewege**

* SeaRoute oder vergleichbare Routing-Lösung

Diese Liste ist nicht als unveränderliche technische Bindung zu verstehen.

Provider müssen austauschbar bleiben.

---

## 25. Daten-Normalisierung

Externe Daten werden nicht unmittelbar im Gameplay verwendet.

Pipeline:

**External Source → Provider → Normalizer → Internal Model → Cache/Database → Game Logic**

Dadurch können:

* Datenquellen wechseln,

* Schemas geändert werden,

* fehlerhafte Daten bereinigt werden,

* Lizenzinformationen gespeichert werden,

* Caches aufgebaut werden.

---

## 26. Persistenz

Langfristig muss das System mindestens folgende Daten persistent speichern:

* Benutzer

* Unternehmen

* Fahrzeuge

* Depots

* Aufträge

* Transporte

* Wirtschaftsstatus

* Marktstatus

* Reputation

* Fahrzeugstandorte

* Geldbewegungen

* Provider-Caches

* Audit-Ereignisse

Für einen lokalen MVP kann SQLite verwendet werden.

Für Multiplayer-Produktion ist ein relationales System wie PostgreSQL vorgesehen.

---

## 27. Python-Entwicklungsregeln

Python-Code folgt konsequent PEP 8.

Architekturprinzipien:

* OOP, wo sinnvoll

* klare Verantwortlichkeiten

* sinnvolle Modularisierung

* sprechende Namen

* keine God Classes

* keine God Functions

* Funktionen erfüllen genau eine Aufgabe

* komplexe Abläufe werden über Orchestratoren zusammengesetzt

* Abhängigkeiten werden injiziert

* externe Provider werden abstrahiert

* Domain-Logik ist unabhängig von HTTP und Datenbank

---

## 28. Testprinzip

Grundregel:

> Keine Funktion ohne Gegentest.

Jede konkrete Funktion beziehungsweise Methode muss mindestens einen zugeordneten Test besitzen.

Dabei reicht reine Coverage nicht aus.

Tests müssen Verhalten prüfen.

Erwartete Testebenen:

* Unit Tests

* Domain Tests

* Provider Contract Tests

* Repository Tests

* API Tests

* Integration Tests

* End-to-End-Tests

Zusätzlich:

* Happy Path

* Fehlerpfade

* ungültige Daten

* Provider-Ausfälle

* Timeout-Verhalten

* Persistenzfehler

---

## 29. Quality Gates

Ein Build darf nur als erfolgreich gelten, wenn mindestens:

* Tests erfolgreich

* Function-Test-Guard erfolgreich

* Coverage-Gate erfolgreich

* Linting erfolgreich

* Type Checks erfolgreich

* API-Contract-Tests erfolgreich

* Build erfolgreich

sind.

---

## 30. Logging

Logging erfolgt strukturiert.

Mindestens gespeichert beziehungsweise ausgegeben werden:

* Timestamp

* Log-Level

* Trace-ID

* User-ID, soweit zulässig

* Company-ID

* Request

* Modul

* Event

* Provider

* Dauer

* Ergebnis

* Fehlercode

Keine unstrukturierten `print()`-Statements im produktiven Code.

---

## 31. Tracing

Jeder Request erhält eine Trace-ID.

Diese Trace-ID wird durch alle relevanten Layer weitergegeben:

**Frontend Request → API → Application Service → Provider → Repository**

Dadurch muss beispielsweise nachvollziehbar sein:

> Warum konnte Spieler X Auftrag Y um 14:32 Uhr nicht starten?

---

## 32. Dokumentation

Dokumentation ist Bestandteil des Produkts und keine nachträgliche Aufgabe.

Das Repository soll mindestens enthalten:

`README.md`

`PRODUCT.md`

`TARGET.md`

`ARCHITECTURE.md`

`API.md`

`DATA_SOURCES.md`

`DOMAIN_MODEL.md`

`TESTING.md`

`OBSERVABILITY.md`

`SECURITY.md`

`MILESTONES.md`

`AGENTIC_WORKFLOW.md`

`CHANGELOG.md`

sowie Architecture Decision Records.

---

## 33. Agentischer Entwicklungsworkflow

Neue Features werden nicht direkt implementiert.

Vorgesehener Ablauf:

**Ziel analysieren**

→ bestehende Dokumentation prüfen

→ Architekturgrenzen definieren

→ Interfaces und Contracts definieren

→ Tests definieren

→ Domain implementieren

→ Provider implementieren

→ Application-Service implementieren

→ API implementieren

→ Frontend integrieren

→ Tests durchführen

→ Quality Gates durchführen

→ Dokumentation aktualisieren

→ Meilensteinstatus aktualisieren

Dadurch soll verhindert werden, dass sich Feature für Feature technische Schulden ansammeln.

---

## 34. Observability

Ein produktiver Multiplayer-Titel muss beobachtbar sein.

Langfristig erforderlich:

* strukturiertes Logging

* Distributed Tracing

* Error Tracking

* Performance Metrics

* Provider-Latenzen

* API-Latenzen

* Fehlerraten

* aktive Spieler

* laufende Transporte

* Auftragsvolumen

* Wirtschaftszustand

---

## 35. MVP – genaue Definition

Der erste echte MVP konzentriert sich ausschließlich auf **Road Freight in Europa**.

Der MVP beweist den vollständigen Kernloop.

Ein Nutzer kann:

1. Account erstellen.

2. Logistikunternehmen erstellen.

3. Startstandort beziehungsweise Depot besitzen.

4. Startkapital erhalten.

5. reales oder realitätsnahes Truck-Modell erwerben.

6. Auftragsmarkt öffnen.

7. generierten Cargo-Auftrag sehen.

8. reale Von-Adresse sehen.

9. reale Zu-Adresse sehen.

10. reale Strecke berechnen lassen.

11. Entfernung und ETA sehen.

12. Betriebskosten sehen.

13. erwartete Marge sehen.

14. passendes Fahrzeug auswählen.

15. Auftrag annehmen.

16. Transport starten.

17. Fahrzeug live auf der Karte verfolgen.

18. Browser schließen.

19. später zurückkehren.

20. korrekten realzeitbasierten Fortschritt sehen.

21. Lieferung abschließen.

22. Geld erhalten.

23. Reputation erhalten.

24. Fahrzeug am Zielstandort vorfinden.

25. neuen Auftrag suchen.

26. langfristig ein zweites Fahrzeug beziehungsweise weiteres Depot erwerben.

Wenn dieser komplette Ablauf stabil funktioniert, ist der MVP erreicht.

---

## 36. Was ausdrücklich nicht zum ersten MVP gehört

Nicht erforderlich für M1:

* Schifffahrt

* Luftfracht

* internationale Bahnlogistik

* komplexe multimodale Lieferketten

* Fahrer

* Personalmanagement

* komplexe Wartung

* Börsensystem

* dynamische Treibstoffmärkte

* vollständige Weltwirtschaft

* Echtzeit-PvP

* Auktionen

* Spielerhandel

* komplexe Allianzen

Diese Systeme dürfen die Architektur beeinflussen, aber den MVP nicht aufblähen.

---

## 37. Milestones

## M0 – Foundation

* Repository-Struktur

* Coding Standards

* Testsystem

* Logging

* Tracing

* Dokumentation

* CI/Quality Gates

* Provider Contracts

## M1 – European Road Freight MVP

* Accounts

* Spielerunternehmen

* Depot

* Truck

* reale Straßenroute

* Contract Market

* Live-Tracking

* Real-Time-Idle

* Geld

* Reputation

* Flottenwachstum

## M2 – Real Economy Data

* Unternehmensdaten

* Branchen

* realistischere Cargo-Erzeugung

* Eurostat-Warenströme

* regionale Wirtschaftsprofile

## M3 – Fleet Management

* Fahrzeugmarkt

* mehrere Fahrzeugklassen

* Wartung

* Alter

* Verbrauch

* mehrere Depots

* Leerfahrten

* Rückfracht

## M4 – Multiplayer Economy

* gemeinsamer Auftragsmarkt

* Wettbewerb

* Rankings

* regionale Märkte

* dynamische Frachtraten

## M5 – Rail Freight

* Schienennetz

* Güterterminals

* Zugflotten

## M6 – Sea Freight

* Häfen

* Schiffe

* maritime Routen

* Containerlogistik

## M7 – Air Cargo

* Cargo-Airports

* Flugzeuge

* Luftfrachtnetz

## M8 – Multimodal Logistics

* LKW → Bahn

* Bahn → Hafen

* Schiff → Hafen

* LKW → Empfänger

* Container

* Terminals

* globale Logistikketten

---

## 38. Langfristiges Endgame

Im späteren Spiel betreibt der Spieler kein einzelnes Transportunternehmen mehr im klassischen Sinn.

Er kontrolliert ein Netzwerk.

Beispiel:

**Shanghai**

→ Schiff

**Rotterdam**

→ Bahn

**Duisburg**

→ Truck

**München**

Ein Auftrag kann dadurch aus mehreren Legs bestehen.

Der Spieler entscheidet:

* welche Transportart,

* welcher Hub,

* welches Depot,

* welche Fahrzeuge,

* welcher Zeitplan,

* welche Kostenstruktur.

Damit entwickelt sich World Freight Idle langfristig von einem einfachen Idle-Tycoon zu einem echten Netzwerk-Optimierungsspiel.

---

## 39. Entscheidungsregel für neue Features

Bei jeder neuen Idee werden fünf Fragen gestellt:

**1. Verstärkt sie den Kernloop?**

**2. Nutzt sie die reale Welt sinnvoll?**

**3. Erzeugt sie eine interessante wirtschaftliche Entscheidung?**

**4. Passt sie in die bestehende modulare Architektur?**

**5. Ist sie für den aktuellen Meilenstein notwendig?**

Ist insbesondere Frage 5 mit „Nein“ zu beantworten, wird das Feature dokumentiert, aber nicht automatisch in den aktuellen Scope aufgenommen.

---

## 40. Definition of Success

World Freight Idle ist erfolgreich, wenn Spieler das Gefühl entwickeln:

> „Meine Firma existiert wirklich auf dieser Karte.“

Der Spieler soll nicht denken:

> „Mein Truck hat jetzt abstrakt Mission 47 abgeschlossen.“

Sondern:

> „Mein Truck ist heute Morgen in Berlin gestartet. Als ich in der Mittagspause reingeschaut habe, war er hinter Leipzig. Heute Abend kommt er in Prag an. Danach brauche ich dort Rückfracht.“

Genau dieses Gefühl bildet den emotionalen Kern des Projekts.

---

## 41. North-Star-Satz

**World Freight Idle verwandelt reale Geografie, Infrastruktur und Wirtschaftsdaten in einen persistenten Multiplayer-Logistik-Tycoon, in dem Spieler ihre eigene Transportfirma von einem einzelnen Fahrzeug zu einem internationalen Logistiknetzwerk entwickeln.**


## Konkretisierung der aktuellen UI-First-Phase (18.09.2026)

M1 verwendet weiterhin OSM-Raster; Satelliten, Unternehmen und eigene Depots
folgen später. Neue Profile starten mit 175.000 Euro und einem kostenlosen
IVECO S-Way 500 XC13 aus dem Referenzkatalog. Dessen Spielwerte werden wie bei
Käufen als Snapshot gespeichert. Ältere Flotten bleiben kompatibel und werden
nur auf ausdrücklichen Auftrag angepasst. Alle 14 Modelle besitzen lokale Karten-, Front- und Seitenansichten.
Für Modelle ohne lokale Grafik bleiben verifizierte Katalogfotos mit Lizenz-/
Quellenangaben und Modellfamilienhinweis verfügbar; fehlende Fotos und deren
Ladefehler haben eine Illustration als Ersatz. Die Regeln aus Abschnitten 21 und 27–29 bleiben
verbindlich: injizierte Grenzen, klare Module und zusammenhängende Funktionen.

## Verbindliche WorldCatalogue-Ergänzung (18.09.2026)

Reale Facilities ergänzen die UI-First-Basis; keine Spielerunternehmen oder
eigenen Depots. Stand, stabile Identitäten, Quellenprüfung und explizite
Bestandsmigration: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md). Die umfassendere
Wirtschaftsvision bleibt Zielbild. 559 Facilities sind spielbar; 95
Positionen sind verifiziert und 464 ausdrücklich für die Simulation geschätzt.
Neue Aufträge verwenden ausschließlich NHM-basierte Warenprofile; konkrete
Geschäftsbeziehungen und Einzelaufträge bleiben simuliert.

Market v2 ergänzt Angebote für geeignete Facilities aktiver Fahrzeugstädte
und deren verfügbare Distanzbänder. Mengen verwenden gespeicherte Kapazität
und NHM-Load-Factors; reale Warenbelege bleiben von simulierten Aufträgen
getrennt. Historische payload_band-Werte bleiben ausschließlich lesbar.
Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).


## Aktuelle technische Grundlage

Typisierte Entities, relationale SQLite-Spielpersistenz (Schema 1.1.0) und
WorldCatalogue 4.2.0 bilden die einzige Laufzeit. Historische Snapshots bleiben
bei Katalogupdates erhalten. Details beschreiben [Architektur](ARCHITECTURE.md),
[Domainmodell](DOMAIN_MODEL.md) und [Persistenz](RELATIONAL_STATE.md).
Die abgeschlossene Umbauchronik liegt im [Archiv](archive/REFACTOR_EXECUTION.md).
Aktuelle Prüfungen und Grenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).
Dieser technische Stand ersetzt weder die vollständige MVP- noch reale iPad-Abnahme.


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
