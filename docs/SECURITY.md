# Sicherheitsmodell und Betriebsgrenzen

## Implementiert

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

## Noch kein Produktionsfreigabestatus

Der geprüfte Stand ist ein lokaler Mehrspieler-MVP. HTTPS, ein kontrollierter
Reverse Proxy, Backups/Restore-Tests, Lasttests und Betriebsmonitoring sind
vor öffentlichem Betrieb einzurichten. Forwarded-Header ausschließlich von
vertrauenswürdigen Proxies übernehmen. Ohne korrekte Client-IP teilen Nutzer
das Proxy-IP-Limit. Bei mehreren Workern Provider-Limiter neu auslegen.

Offen: Passwortänderung/-Recovery, E-Mail-Verifikation, Mehrfaktor-Anmeldung,
Kontolöschung, Moderation, Account-Sperren, manipulationssicheres Auditjournal,
verteiltes Rate-Limiting und allgemeine Ressourcen-/Missbrauchslimits.
MapLibre, Anwendung und Schriften werden lokal gebündelt ausgeliefert.
Öffentliche OSM-Tiles und verifizierte Wikimedia-Fotos bleiben externe Medien.
Fotos nutzen HTTPS, erlaubte Quellhosts, anonymes CORS und no-referrer;
interne API-Header und Backend-Zugangsdaten werden nicht mitgeschickt.
Der lokale Einstieg bindet für WLAN-Tests an 0.0.0.0; HOST=127.0.0.1
beschränkt ihn auf diesen Rechner.

SQLite-Datei und Backups enthalten Passworthashes und Spielerdaten; passende
Dateirechte und geschützte Backups sind Aufgabe des Betriebs.
Eine hohe Testabdeckung ersetzt keine unabhängige Sicherheitsprüfung.
