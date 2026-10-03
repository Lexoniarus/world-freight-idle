# Supabase/PostgreSQL production runtime

Stand: 28.09.2026. Die Produktionsadapter sind im aktuellen Runtime-Aufbau
integriert.

## Ziel

Die Produktionslaufzeit verwendet eine serverseitige PostgreSQL-Verbindung zu
Supabase. Die bereits migrierten Daten liegen getrennt in:

- `game`
- `world_catalogue`
- `vehicle_catalogue`

Der Browser spricht weiterhin ausschließlich mit FastAPI `/api/v1`. Es gibt
keinen direkten Browserzugriff auf das private `game`-Schema und keine
Datenbank-Credentials im Frontend.

Die Migration `harden_private_schemas` entzieht `PUBLIC`, `anon` und
`authenticated` alle Rechte an `game`, `world_catalogue` und
`vehicle_catalogue`, einschließlich Tabellen, Sequenzen und Funktionen. Sie
setzt dieselben Default-Privileges für zukünftige Objekte und aktiviert RLS
auf allen vorhandenen Tabellen als zusätzliche Schutzschicht ohne
Browser-Policies. Die Backend-Rolle bleibt der einzige Runtime-Zugang und
besitzt ausdrücklich `BYPASSRLS`; der Browser verwendet weiterhin nur
`/api/v1`. Die PostgreSQL-Initialisierung verweigert den Start, sobald bei
einer benötigten `game`-Tabelle RLS fehlt.

Für die drei fehlenden Runtime-Fremdschlüsselindizes auf Sessions und
Marktvorlagen legt dieselbe Migration gezielte Indizes an. Hinweise auf
weitere Indizes in den immutable Katalogschemas werden nicht ungeprüft
übernommen, weil sie aktuell keine gemessene Runtime-Abfrage unterstützen.

## Authentifizierung

Der Browser verwendet `@supabase/supabase-js` mit der Publishable Key und hält
die Supabase-Session samt automatischer Token-Erneuerung. FastAPI akzeptiert
den Access Token im `Authorization: Bearer`-Header und prüft ihn lokal gegen
die gecachten öffentlichen ES256-Schlüssel des projektgebundenen JWKS-
Endpunkts. Erwartet werden der exakte Issuer, Audience `authenticated`, Ablauf
und eine UUID als `sub`. Eine fremde oder symmetrisch signierte JWT wird
abgelehnt.

Der stabile Supabase-Subject wird beim ersten gültigen Request atomar in
`game.users` projiziert. `user_metadata.username` ist dabei nur ein geprüfter
Anzeigename und niemals Autorisierungsgrundlage. Bestehende Cookie-Sessions
bleiben für die drei bereits vorhandenen lokalen Konten übergangsweise lesbar;
neue Browseranmeldungen laufen über Supabase Auth.

Die drei vor Supabase Auth vorhandenen Konten besitzen zusätzlich eine private
Zuordnung in `game.account_emails`. Beim Login versucht der Browser zuerst
Supabase Auth. Solange für ein migriertes Konto dort noch kein Passwortkonto
existiert, fällt ausschließlich der Login auf den same-origin Legacy-Endpunkt
zurück; dieser löst die hinterlegte E-Mail auf den bestehenden scrypt-Account
auf. Dadurch bleiben vorhandenes Passwort, Spieler-ID und kompletter Spielstand
erhalten. Neue Registrierungen verwenden diesen Fallback nicht. Ein späterer
Supabase-Subject mit derselben UUID darf außerdem die historische kompakte
UUID-Darstellung ohne Bindestriche wiederverwenden, statt einen zweiten Spieler
anzulegen.

Der Server lädt JWKS nur bei Bedarf über einen zeitlich begrenzten Cache und
protokolliert Refresh beziehungsweise Ablehnung strukturiert, aber niemals den
Token. `SUPABASE_SECRET_KEY` wird nicht verwendet. Ein solcher Schlüssel darf
weder über `/auth/config` noch in das Browser-Bundle gelangen.

## Aktivierung

`DATABASE_URL` schaltet die Produktionsadapter ein. Ohne `DATABASE_URL` bleiben
die vorhandenen SQLite-Adapter für Tests und explizite Offline-Werkzeuge aktiv.
Das erlaubt die bestehende lokale Testsuite, ohne eine Produktionsdatenbank zu
mutieren.

Die lokale `.env` wird beim Start geladen, bleibt durch `.gitignore` außerhalb
von Git und benötigt für Auth:

```dotenv
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_JWKS_URL=https://PROJECT_REF.supabase.co/auth/v1/.well-known/jwks.json
```

Alle drei Werte müssen vorhanden sein, bevor der Backend-Endpunkt die
Supabase-Anmeldung für den Browser aktiviert. Die Datenbankverbindung bleibt
separat in `DATABASE_URL` und wird nie an den Browser ausgegeben.

Für einen lang laufenden lokalen/VM-Backendprozess ist die Supabase Direct
Connection geeignet, sofern IPv6 verfügbar ist. Bei IPv4-only Netzen ist der
Supabase Session Pooler auf Port 5432 die passende persistente Alternative.
Die URL wird nur als Prozess-Secret gesetzt und niemals committed.

PowerShell-Beispiel:

```powershell
$env:DATABASE_URL = "postgresql://..."
$env:GAME_DATABASE_SCHEMA = "game"
$env:WORLD_DATABASE_SCHEMA = "world_catalogue"
$env:VEHICLE_DATABASE_SCHEMA = "vehicle_catalogue"
$env:DATABASE_POOL_SIZE = "5"
python main.py
```

## Konsistenz

Die bestehende SQLite-Writer-Semantik war durch `BEGIN IMMEDIATE` global
serialisiert. Der PostgreSQL-Adapter erhält diese konservative Eigenschaft für
den jetzigen MVP über `pg_advisory_xact_lock` pro äußerer Schreib-UoW. Damit
bleiben Kauf, Dispatch, Settlement, Marktveröffentlichung und Lease-bezogene
Writes atomar, ohne Provider-Awaits in einer Schreibtransaktion einzuführen.

Read-UoWs verwenden `REPEATABLE READ READ ONLY`. Normale Einzelreads und
Einzelwrites leihen Verbindungen aus einem pro Prozess besessenen psycopg-Pool.
Runtime und Prewarm besitzen getrennte Pools und schließen sie beim Shutdown.
Der Adapter setzt den zuvor validierten Schema-`search_path` bei jedem Checkout
explizit; damit ist die Namensauflösung auch hinter dem Supabase Session Pooler
unabhängig von verworfenen PostgreSQL-Startup-Optionen.

## SQL-Dialektgrenze

Die bestehenden Repository-Verantwortlichkeiten bleiben bestehen. Der neue
PostgreSQL-Adapter übersetzt nur die kleine SQLite-Dialektoberfläche, die diese
Repositories tatsächlich verwenden:

- `?`-Parameter nach psycopg `%s`
- SQLite JSON1-Projektionen nach PostgreSQL `jsonb`
- `json_each` nach `jsonb_array_elements_text`
- boolesche SQLite-Summen nach PostgreSQL-Integer-Summen
- historische `rowid`-Sortierungen auf stabile fachliche Sortierschlüssel
- SQLite-DDL/PRAGMA-Aufrufe werden in Produktion nicht ausgeführt; das bereits
  migrierte PostgreSQL-Schema wird beim Start validiert

Snapshot-Spalten bleiben `TEXT`. Historische JSON-Dokumente werden nicht beim
Start oder beim Lesen umgeschrieben.

## Kataloge

World 4.2.0 und Vehicle 2.2.0 werden aus ihren PostgreSQL-Schemas in einer
read-only Repeatable-Read-Transaktion geladen. Danach behalten die bestehenden
`CachedWorldCatalogue`/`CachedVehicleCatalogue`-Grenzen jeweils eine immutable
Revision pro Prozess.

Facility-Provenienz, Geocoding-Nachweise, Aliasse und dokumentierte Güter werden
jeweils als geordneter Batch gelesen, nicht pro Facility. Der reale Read-only-
Smoke-Test über den Session Pooler lud 558 Facilities am 28.09.2026 in 0,98 s;
Game-Schemavalidierung und 14 Fahrzeugmodelle zusammen benötigten 1,58 s.

## Git

Keine `.db`, `.sqlite` oder `.sqlite3`-Datei ist nach diesem Umbau eine
versionierte Produktionsquelle. Bereits getrackte Referenzdateien müssen einmal
aus dem Git-Index entfernt werden, ohne sie lokal zu löschen:

```powershell
git rm --cached data/world_freight_company_facility_mvp.sqlite3
git rm --cached data/world_freight_vehicle_catalog.sqlite3
```

Die lokale `game.db` bleibt ebenfalls außerhalb von Git und kann als
Migrations-/Rollback-Backup aufbewahrt werden.
