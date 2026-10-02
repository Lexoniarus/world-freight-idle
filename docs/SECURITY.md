# Sicherheitsmodell und Betriebsgrenzen

## Implementiert

- Supabase Auth im Browser ausschließlich mit Publishable Key; kein Secret Key
  im Bundle oder in einer API-Antwort.
- Lokale ES256-JWT-Prüfung in FastAPI gegen gecachte, projektgebundene JWKS mit
  exaktem Issuer, Audience, Ablauf und UUID-Subject; Tokens werden nie geloggt.
- Autorisierung verwendet ausschließlich den signierten `sub`. Benutzer-
  Metadata liefert höchstens einen validierten Anzeigenamen.
- Gesalzene scrypt-Passworthashes; kein Klartextpasswort in der Datenbank.
- Kryptografisch zufällige Sitzungen; nur Token-Digests werden gespeichert.
- Sieben Tage Laufzeit; Logout widerruft die Sitzung, Login rotiert sie.
- HttpOnly und SameSite=Strict; Secure über `COOKIE_SECURE=true`.
- Authentifizierter Besitzer bestimmt den Spielstand, keine Client-User-ID.
- CSRF: eigener Header für Schreibzugriffe und Origin-Abgleich; kein CORS.
- 30 Authentifizierungsversuche je Client-IP pro 15 Minuten, persistent limitiert.
- Parametrisierte SQL-Abfragen, validierte Eingaben, geschützte Geldmutationen.
- API-Antworten ohne Browsercache; Passwörter und Tokens werden nicht geloggt.
- Öffentlicher Spielreset entfernt; Rangliste zeigt nur Name und Lieferungen.
- `game`, `world_catalogue` und `vehicle_catalogue` sind private Schemas ohne
  Rechte für `PUBLIC`, `anon` oder `authenticated`; auch zukünftige Objekte
  erben diese Default-Privileges. Alle 72 vorhandenen Tabellen besitzen RLS
  ohne Browser-Policies. Nur die Backend-Rolle greift auf sie zu.
- Die PostgreSQL-Initialisierung bricht ab, wenn RLS auf einer erforderlichen
  `game`-Tabelle fehlt.
- Der Legacy-Login-Fallback gilt ausschließlich für die drei in
  `game.account_emails` hinterlegten migrierten Konten. Er löst E-Mail auf den
  bestehenden scrypt-Account auf und bewahrt dessen kompakte UUID. Neue
  Registrierungen werden ausschließlich durch Supabase Auth angelegt.

## Noch kein Produktionsfreigabestatus

Der geprüfte Stand ist ein lokaler Mehrspieler-MVP. HTTPS, ein kontrollierter
Reverse Proxy, Backups/Restore-Tests, Lasttests und Betriebsmonitoring sind
vor öffentlichem Betrieb einzurichten. Forwarded-Header ausschließlich von
vertrauenswürdigen Proxies übernehmen. Ohne korrekte Client-IP teilen Nutzer
das Proxy-IP-Limit. Bei mehreren Workern Provider-Limiter neu auslegen.

Supabase stellt E-Mail-Verifikation und Recovery als Providerfunktionen bereit;
deren Templates, Redirect-Allowlist und produktive Zustellbarkeit müssen vor
Freigabe noch betrieblich abgenommen werden. Offen bleiben Mehrfaktoranmeldung,
Kontolöschung, Moderation, Account-Sperren, manipulationssicheres Auditjournal,
verteiltes Rate-Limiting und allgemeine Ressourcen-/Missbrauchslimits.
MapLibre, Anwendung und Schriften werden lokal gebündelt ausgeliefert.
Öffentliche OSM-Tiles und verifizierte Wikimedia-Fotos bleiben externe Medien.
Fotos nutzen HTTPS, erlaubte Quellhosts, anonymes CORS und no-referrer;
interne API-Header und Backend-Zugangsdaten werden nicht mitgeschickt.
Der lokale Einstieg bindet für WLAN-Tests an 0.0.0.0; HOST=127.0.0.1
beschränkt ihn auf diesen Rechner.

Produktive PostgreSQL-Daten und Backups enthalten Passworthashes und Spielerdaten;
Zugriffsschutz sowie verschlüsselte, geprüfte Backups sind Aufgabe des Betriebs.
SQLite-Kopien dürfen nur als private Testfixture oder Offline-Arbeitskopie
existieren und unterliegen denselben Schutzanforderungen.
Eine hohe Testabdeckung ersetzt keine unabhängige Sicherheitsprüfung.


Firmenfarben verwenden ausschließlich zehn serverseitig erlaubte Hexwerte.
Preference-Endpunkte übernehmen den Account aus der Sitzung und besitzen
bestehenden CSRF-/Origin-Schutz. Öffentliche Bewegung enthält die wirksame
Farbe, weiterhin keine Wirtschafts- oder Energiedetails. SVG-Kolorierung
verwendet lokale registrierte Quellen und normalisierte Hexwerte; keine
beliebigen SVGs oder CSS-Werte aus Client-Eingaben.
