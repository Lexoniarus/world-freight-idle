# ADR 0003 – Spielertrennung und atomare Wirtschaft

Status: angenommen für den lokalen Mehrspieler-MVP.

Konten/Sitzungen liegen in relationalen SQLite-Tabellen. Bestehende JSON-Zustände
bleiben im KV-Repository; Schlüssel sind pro Spieler mit `user:<uuid>:` getrennt.
Die Session bestimmt den Eigentümer, niemals eine vom Client gesendete User-ID.
Das reduziert die Migration des bestehenden MVP, ohne fremde Spielstände freizugeben.

`BEGIN IMMEDIATE` schützt Kauf, Initialisierung, Markterneuerung und Auszahlung.
Der Transaktionskontext bindet alle Repository-Operationen eines synchronen
Use Cases an eine Verbindung. Fehler führen zum Rollback. Route/Geocoding
laufen außerhalb der Schreibtransaktion; Dispatch validiert anschließend erneut.

Ein gemeinsamer Geocoder begrenzt Anfragen über alle Konten innerhalb eines
Prozesses. Provider-Caches bleiben gemeinsam. Start über `main.py` nutzt einen
Worker. Ein skalierter Mehrprozessbetrieb benötigt ein anderes Limiter-Konzept.

Die Rangliste zählt abgeschlossene sowie bereits angekommene, noch nicht
abgerechnete Transporte. Die Projektion erfolgt in einer SQL-Abfrage, damit
Offline-Spieler nicht benachteiligt und Lieferungen nicht doppelt gezählt werden.

SQLite + JSON ist eine bewusste MVP-Grenze. Vor größerer öffentlicher Nutzung
folgen PostgreSQL, normalisierte Tabellen, Schema-Migrationen und Lasttests.
