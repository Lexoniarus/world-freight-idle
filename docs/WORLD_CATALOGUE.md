# WorldCatalogue und Market v2

Stand: 25.09.2026. Kanonisch ist ausschließlich
`data/world_freight_company_facility_mvp.sqlite3` (World-Schema 4.2.0).
Der bereitgestellte Dateiinhalt wird unverändert verwendet. Der Fahrzeugkatalog
`data/world_freight_vehicle_catalog.sqlite3` verlangt Vehicle-Schema 2.2.0.
Beide Referenzen werden read-only geöffnet, nie als Spielerzustand verwendet.

## Referenzverträge

Der Reader prüft Version, Pflichtabellen, Fremdschlüssel, bekannte Klassen und
vollständige operative NHM-Profile: genau drei Distance-Bands und vier Scales.
Zahlen müssen endlich sein; Warenwert/Frachtfaktor positiv, Suitability und
Selection-Weights in [0,1], Load Factor mit 0 < min ≤ max ≤ 1.

Die Segmentzuordnung ist explizit: light_commercial_van → van,
light_distribution_truck → light_distribution,
medium_distribution_truck → medium_distribution,
heavy_long_haul_tractor → heavy. Unbekannte Segmente werden abgewiesen.
NhmProduct bleibt auf Identität, Code, Namen und Hierarchie beschränkt.

CachedWorldCatalogue lädt eine validierte immutable Revision. TradeNetwork
baut globale NHM-Zielindizes, berechnet Origin-Relationen jedoch ausschließlich
bei Bedarf. Unterschiedliche Facilities derselben Stadt dürfen handeln.
Das spezifischere kompatible NHM-Produkt bleibt erhalten. Komponenten-/Modul-
Semantik kommt aus dem Katalog; zusätzliche Waren werden nicht erfunden.

## Stadtmarkt

Eigene idle OwnedVehicles aktivieren eindeutige Städte anhand city_uid.
Der gespeicherte Standort-Snapshot hat Vorrang; fehlt er, wird die gespeicherte
Facility-ID exakt aufgelöst. Alle geeigneten Facilities dieser Städte sind
Origins, Ziele bleiben katalogweit verfügbar. Pan/Zoom haben keinen Einfluss.

Jeder Candidate braucht mindestens ein kompatibles idle Fahrzeug: passender
Modus, auflösbares Modell, positive Transport-Capability und NHM-Scale.
Für jedes Fahrzeug gilt Capability-Suitability × Scale-Suitability.
Candidate-Gewicht ist Evidenz-/Match-/Confidence-/Priority-Gewicht ×
Distance-Selection-Weight × höchster kompatibler Fahrzeugwert. Gewicht null
schließt den Candidate aus. Der Maximalwert wählt kein Fahrzeug aus.
Erst die Factory zieht separat einen kompatiblen Generierungskontext nach
dessen eigenem Gewicht. Das Offer reserviert keine Fahrzeug-ID.

Haversine liefert short ≤150 km, medium ≤600 km, sonst long. Während der
Generierung findet kein Routing statt. Gespeicherte Fahrzeugkapazität × Load
Factor ergibt Tonnage, abgerundet auf zwei Dezimalstellen, mindestens 0,01 t
und höchstens Kapazität. Warenwert wird auf ganze Spiel-Euro gerundet;
Frachtrate ist STANDARD_RATE (0,18) × freight_rate_factor_game.

## Coverage und Retention

Fahrbare, strukturell aktuelle V2-Angebote mit mehr als 60 Sekunden Restlaufzeit
bleiben erhalten. Zuerst erhält jede geeignete Origin-Facility ein Angebot,
danach jedes vorhandene Distanzband einer Stadt mindestens drei. Bereits
geplante Angebote zählen mit. Seltenere Candidates, dann Waren und Zielstädte
werden bevorzugt; Gleichstände werden gewichtet entschieden. Wiederholungen
sind zulässig. Es gibt keine globale Mindestzahl sechs.

Bands ohne Candidate werden als unmet Coverage protokolliert; fehlende
Katalogrelationen werden nicht synthetisch ersetzt. Neue Angebote gelten
sechs Stunden und speichern vollständigen V2-Kontext. Manueller Refresh
ersetzt ausschließlich die Angebote aktiver Städte.

## Bestand und Historie

Vor Einführung sind alle vorhandenen OwnedVehicles zu prüfen. Gespeicherte
model_id müssen auflösbar sein. Unaufgelöste Altbestände verlangen explizite
Zuordnung; weder Name noch Kapazität dienen als Heuristik. Die Zahl eigener
Fahrzeuge ist kein Architekturvertrag. Ungelöste idle Modelle werden explizit
abgewiesen. Aktive Transporte rechnen weiter mit ihren gespeicherten Werten.

V1-Angebote werden beim Refresh verworfen, bevor V2-Pflichtfelder verlangt
werden. Alte payload_band-Werte bleiben historisch lesbar; PayloadBand und
seine Generierung sind entfernt. Spielschema 1.1.0 und Snapshot-Hüllen bleiben
unverändert. Aktive und settled Transporte werden weder umgeschrieben noch
aus aktuellen Referenzwerten rekonstruiert.

## Geografie und Datenqualität

City-/Company-/Facility-UUIDs sind die dauerhaften Identitäten. Companies
bleiben unabhängig von einer einzelnen Stadt. Facility.is_routable und
has_verified_location trennen Spielbarkeit von verifizierter Datenqualität.
Der ausgelieferte Stand enthält 559 Facilities in 333 Städten; diese Zählung
beschreibt den Referenzstand, keine Mindestgröße des Marktalgorithmus.

`GET /map/facilities` unterstützt weiterhin BBox und liefert Koordinatenstatus;
Contract-Endpunkte besitzen keine Viewport-Parameter. Runtime-Geocoding ist
nicht Teil des Markts. Standortmarker stammen aus eigener Flotte, Transporten
und den aktuell geladenen Angeboten.

Das historische Manifest docs/data/world-geography-v4.json dokumentiert die
frühere Geografie-Normalisierung von Schema 3 auf 4.0.0. Es ist kein Generator
oder Migrationsauftrag für den aktuellen 4.2.0-Referenzkatalog.

Prüfstrategie: [TESTING.md](TESTING.md), Zuständigkeiten:
[ARCHITECTURE.md](ARCHITECTURE.md), tatsächliche Abnahme:
[QUALITY_REPORT.md](../QUALITY_REPORT.md).


## Abholanfahrt und Marktentfernung

Market v2 erzeugt weiterhin ohne Routing und bewertet die Luftlinie zwischen
Abholung B und Lieferung C. Das angebotene Distanzband beschreibt diese
Frachtrelation. Die spätere Fahrzeugquote ergänzt die tatsächliche Anfahrt
A → B und Straßenkilometer beider Abschnitte; sie verändert weder Candidates
noch Coverage-Bands. Kataloge und deren read-only Zugriff bleiben unverändert.

## Wirtschaftsprofile und direkte Wartungsquelle

World-Load-Factor-Grenzen bleiben unverändert. Die reine Beta(3,1)-Transformation
begünstigt hohe Werte innerhalb dieser Grenzen für alle vier Scales. Der
kleinste operative NHM-Frachtfaktor wird aus dem validierten Snapshot gelesen
und revisionsgebunden indexiert. Vehicle 2.2.0 liefert Wartung direkt aus
`vehicle_balance.maintenance_eur_per_1000_km_game`; alle 14 lokalen Modelle
sind befüllt. Fehlende/ungültige Wartung wird abgelehnt, niemals aus dem
aggregierten alten Betriebskostenfeld hergeleitet. Beide DBs bleiben read-only.
Audit und Formeln: [ECONOMY_V2.md](ECONOMY_V2.md).


Beide Referenzkataloge werden beim Serverstart validiert und für die Laufzeit
als immutable Revision gecacht. `CachedVehicleCatalogue` lädt seinen
injizierten validierenden Port unter einem Lock einmal erfolgreich; Fehler
werden nicht gecacht. Ein neuer Katalogstand erfordert einen Serverneustart
mit erneuter Validierung und globalem Marktneuaufbau. Offline-Werkzeuge lesen
weiterhin explizit ihren gewählten Katalog. Historische Transporte bleiben
von neuen Revisionen unabhängig.
