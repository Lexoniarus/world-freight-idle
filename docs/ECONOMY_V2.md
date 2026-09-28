# Frontend-v2: Mengen, Tarif und tatsächliche Kosten

Verbindlicher Stand vom 25.09.2026. Referenzen bleiben read-only: World 4.2.0
und Vehicle 2.2.0; das relationale Game-Schema ist seit dem Vorratsumbau 1.2.0.
Vorlagen ändern weder Tonnagenverteilung noch Tarif-/Kostenberechnung. Persönliche
Angebote bleiben immutable und haben `expires_at = null`; historische Konditionen
einschließlich gespeicherter Ablaufwerte bleiben unverändert.

## Unabhängige Menge und Vergütung

`biased_load_factor(minimum, maximum, draw)` berechnet
`minimum + (maximum - minimum) * draw ** (1 / 3)`.
Die Factory liefert genau einen Draw aus ihrem injizierten RNG. Alle vier
Scales verwenden dieselbe Verteilung; ausschließlich NHM-/Distanzprofile
bestimmen die Grenzen. Der normierte Erwartungswert ist 0,75, der Median
ca. 0,794; 87,5 % liegen in der oberen Hälfte, 1,5625 % im unteren Viertel.
Gleiche Grenzen liefern exakt denselben Wert. Kleine Teilbeladungen bleiben
möglich. Die Hundertsteltonnen werden anschließend abgerundet und niemals
über die gespeicherte Fahrzeugkapazität angehoben.

Die Candidate-Gewichtung verwendet die maximale kompatible Suitability.
Erst danach wählt `ContractFactory` einen Fahrzeugkontext separat gewichtet.
Seine gespeicherte Kapazität bestimmt die Menge; sein Energieprofil und der
explizite Katalog-Wartungssatz bestimmen den Referenztarif. Die Factory
kennt weder Routing noch Spielerprofit und versucht keine Neuziehung, um
Profitabilität herzustellen. Das Offer reserviert keine Fahrzeug-ID.
Spätere kompatible größere Fahrzeuge dürfen übernehmen; zu kleine nicht.
Menge und Tarif ändern sich durch die Auswahl nicht.

## Gespeicherter NHM-Tarif

`FreightTariff` speichert `version=nhm-minimum-v1`, `nhm_factor`,
`reference_nhm_factor`, `reference_cost_eur_per_km` und
`minimum_eur_per_km`. Der kleinste operative Faktor der aktuellen World ist
0,65; er wird aus den validierten Profilen berechnet, nicht fest kodiert.

```text
Referenzkosten/km = Wartung/km + Verbrauch/km × Gameplaypreis
Mindestfracht/km = Referenzkosten/km / 0,80 × NHM-Faktor / Referenzfaktor
Erlös = round_half_up(220 + Lieferkilometer ×
    max(Tonnen × STANDARD_RATE × NHM-Faktor, Mindestfracht/km))
```

Die 20-%-Referenzmarge ist eine Balancegrundlage. Warenwert ist kein Erlös.
Anfahrt, ungünstige Fahrzeugwahl und Energieeinkäufe können ein negatives
Spielerergebnis erzeugen. Quote und UI zeigen dieses unverändert.

## Tatsächliche Kosten

Der geprüfte lokale Vehicle-Katalog enthält für alle 14 Modelle
`vehicle_balance.maintenance_eur_per_1000_km_game`. Das Repository projiziert
diesen Wert direkt nach `VehicleModel.maintenance_eur_per_1000_km` und
validiert ihn. `VehicleCostResolver` liefert daraus Wartung/km. Fehlende,
nichtnumerische, nichtendliche oder negative Werte verhindern neue Quotes;
es gibt keine Rückrechnung aus dem alten aggregierten Kostensatz.

```text
Wartung = round_half_up((Anfahrt-km + Lieferung-km) × Wartung/km)
Haltkosten = round_half_up((end_energy - start_energy) × Energiepreis)
Gesamtkosten = 80 + Wartung + Summe der gerundeten Haltkosten
Ergebnis = Erlös - Gesamtkosten
```

Diesel kostet 1,50 €/l, Gas 1,20 €/kg, Strom 0,30 €/kWh. Ohne Halt entstehen
keine Einkaufskosten. Fahrtplanung führt den Füllstand über A → B → C fort.
Dezimale Berechnung und kaufmännische Rundung gelten für jeden Geldbetrag.
`CostBreakdown` speichert Policy, Wartungssatz, Energieträger/-einheit/-preis,
Grundkosten, Wartung, jeden Einkauf mit Segmentindex/Menge/Kosten, Energie-
summe und Gesamtkosten. Gerundete Komponenten addieren sich exakt.

Routing läuft außerhalb von Schreibtransaktionen. Vor Dispatch werden
Fahrzeug, tatsächlicher Start, Kompatibilität, Kosten und Guthaben erneut
geprüft. Start, Reservierung, Abbuchung, Transport, Offer-Verbrauch und
Pruning bleiben atomar. Refill beginnt erst nach dem Commit und kann den
Transport nicht zurückrollen. Der gespeicherte Standort bleibt bis zur
Ankunft A; der gespeicherte Abschnittsplan liefert die laufende Position.

## Start und Historie

Die API validiert Schema und beide Referenzen vor Freigabe. Der frühere globale
Start-Rebuild wurde durch den getrennten Vorbereitungsprozess ersetzt (ADR 0007).
Dieser plant Bedarf für vorhandene Profile ein und veröffentlicht vorbereitete
Angebote atomar pro Profil, nur für eigene idle-Städte. Ein Vorbereitungsfehler
verhindert keine API-Freigabe. World-Snapshot und abgeleitete NHM-Indizes werden
revisionsgebunden wiederverwendet. Neue Spielprofile und fälliges Settlement
bleiben Aufgaben der Runtime.

Historische Transporte behalten Routen, Beträge und eingebettete Offers.
Fehlende `tariff`-/`cost_breakdown`-Zusätze bleiben optional lesbar und werden
nicht rekonstruiert. Die UI zeigt fehlende alte Kostenaufteilungen als
nicht verfügbar. Der Offline-Importer erhält seinen damaligen Feldvertrag.

## Reproduzierbares Wirtschaftsaudit

`python scripts/audit_economy.py` schreibt ausschließlich lokale Artefakte
unter `artifacts/economy/`: CSV-Matrix und JSON-Zusammenfassung. Der Audit
liest keine Spieler-DB und nutzt dieselben Domainfunktionen wie die Factory
und der Dispatch. Seed: 20260925. Alle 14 Modelle, kompatible operative
NHM-Profile, drei Distanzbänder (75/375/1000 km), niedriger Draw 0,
Median aus 101 tatsächlichen RNG-Draws und hoher Draw 1 werden untersucht.
Ungeeignete Kombinationen sind ausdrücklich als inkompatibel markiert.
Zusätzlich: 0/10/50 km Anfahrt mit 100/50/10 % Startfüllung.

Die Referenzmarge bewertet verbrauchte Energie der Frachtstrecke. Der
Cashflow berechnet dagegen tatsächliche Einkäufe und gesamte Fahrstrecke.
Beide Größen sind separat auszuweisen; ein voller Starttank ist kein
kostenloser Energieverbrauch im Referenzvergleich. Messwerte und Gates:
[Qualitätsbericht](../QUALITY_REPORT.md).


Beide Referenzkataloge werden beim Serverstart validiert und für die Laufzeit
als immutable Revision gecacht. `CachedVehicleCatalogue` lädt seinen
injizierten validierenden Port unter einem Lock einmal erfolgreich; Fehler
werden nicht gecacht. Ein neuer Katalogstand erfordert einen Serverneustart
mit erneuter Validierung und globalem Marktneuaufbau. Offline-Werkzeuge lesen
weiterhin explizit ihren gewählten Katalog. Historische Transporte bleiben
von neuen Revisionen unabhängig.


Der Audit wird durch `EconomyAuditService` mit injizierten Katalogports und RNG
ausgeführt. Bootstrap verdrahtet die read-only SQLite-Adapter; die CLI übernimmt
nur Argumente, CSV-/JSON-Projektion und Exitstatus. Typisierte Matrix-/Summary-
Werte und fachliche Szenarien unterliegen Manifest und Core-Coverage. Der
Review-Fix vom 27.09.2026 änderte weder Seed noch Reihenfolge oder Berechnungen;
Matrix und Summary wurden byteidentisch gegen den vorherigen Stand geprüft.
