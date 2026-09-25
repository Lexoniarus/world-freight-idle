# Qualitätsbericht: tatsächliche Abholanfahrt

Abgenommener Quellstand: `548336f`, 25.09.2026. Umsetzung auf dem ausdrücklich gewählten Branch
`feature/frontend-v2`, ausgehend von `fbeca0b`. Bestehende Frontendänderungen
wurden erhalten. Repository-Hooks sind aktiv; keine Veröffentlichung, kein Merge.
Umgebung: Windows, Python 3.11.9, Node 24, Microsoft Edge / Playwright.

## Ergebnis

- Fahrzeuge starten am gespeicherten Standort A, fahren automatisch zur
  Abholung B und weiter nach C. Der gespeicherte Standort bleibt bis zur
  Zielankunft der Abfahrtscheckpoint. Status bleibt enroute.
- Injizierter DispatchPlanningService und immutable DispatchRoutePlan trennen
  tatsächlichen Start, Abholung, Straßenabschnitte und historische Providerwerte.
  GameService delegiert Routing, Energieplanung und Wirtschaftskalkulation.
- Abschnittsweise Geschwindigkeitsbegrenzung, kontinuierliche Energie und
  automatische Halte; Gesamtkosten für beide Strecken, Erlös nur für B → C.
  Grundbeträge werden jeweils einmal berechnet.
- Additive API-/Snapshotfelder, getrennte Kilometer, gemeinsames Abschnitts-
  Tracking für eigene/öffentliche Fahrzeuge und zwei Fahrphasen in der UI.
- Routing bleibt außerhalb der Schreibtransaktion. Angebot, Fahrzeug und
  tatsächlicher Start werden vor Commit erneut validiert. Dispatch/Pruning
  bleiben atomar; Refill besitzt weiterhin eine separate Transaktion.
- Historische Transporte ohne neuen Plan bleiben unveränderte Einzelfahrten.
  World 4.2.0, Vehicle 2.2.0 und Spielschema 1.1.0 bleiben unverändert.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Gezielte Backend-/Lifecycle-/Manifesttests | 20 bestanden |
| Ergänzte Anfahrts-/Konkurrenz-/Rollbacktests | 9 bestanden; zusätzlicher strikter Mapper-Gegentest separat bestanden |
| Frontend-Verhalten | 77 bestanden |
| python scripts/quality.py, finaler Quellstand | 381 Tests bestanden; 4086 Statements, 100 % Coverage; alle Gates bestanden |
| npm run test:e2e, finaler Quellstand | 20 bestanden; 8,4 Minuten |
| Einzelreview aller geänderten Core-Funktionen | 24 Python-Funktionen einzeln plus Frontendfunktionen geprüft |
| git diff --check | bestanden |

Verbindliche finale Logs: `artifacts-approach-quality-verified.log` und
`artifacts-approach-e2e-verified.log`, lokal und nicht versioniert. Zwischenläufe
waren keine Abnahme: ein Formatierungsfehler im Manifest wurde korrigiert;
der erste vollständige Quality-Lauf wurde nach dem Review vorzeitig beendet,
um die strengere Snapshot-Decodierung und zusätzliche Konkurrenztests gemeinsam
auf dem finalen Stand zu prüfen. Im ersten beendeten Gesamt-Pythonlauf
wurden außerdem Altimport-Fixtures auf ihr tatsächliches historisches Feldformat
und die öffentliche Verkehrs-Feldliste auf die neue Projektion korrigiert.
Der Importer selbst wurde nicht geändert; 18 Import- und drei Verkehrstests
bestanden danach separat. Die Browserregression hatte alte Warteannahmen für nur eine Strecke. Die Offline-Wartezeit folgt jetzt der Quote,
die UI-Settlement-Wartefenster berücksichtigen die längere Gesamtfahrt. Kein
Test, keine Coverage-Schwelle und keine Architekturregel wurde deaktiviert.

## Fachliche Gegenproben

A ≠ B, A = B und unterschiedliche Facilities mit gleichen Koordinaten werden
separat geprüft. Verschiedene Providerzeiten und Höchstgeschwindigkeiten gelten
je Abschnitt. Tests kontrollieren die exakte Grenze bei B, Halte davor, direkt
bei B und danach, kontinuierlichen Verbrauch sowie den neuen Füllstand erst am
Pausenende. Wirtschaftstests sichern Frachterlös nur auf B → C und einmalige
Grundbeträge einschließlich negativer Gewinne.

Ein zweiter SQLite-Writer kann während Routing geöffnet werden. Standortwechsel
während Routing oder zwischen Quote und Commit verhindert Dispatch ohne
Abbuchung. Überlappende Routings führen nur zu einem Transport und einer
Abbuchung. Fehler nach Transportanlage oder beim Pruning rollen Fahrzeugstatus,
Geld, Transport und Offers gemeinsam zurück. Bestehende Lifecycle-Tests belegen
Refill nach sichtbarem Commit, isolierten Refill-Rollback und späteren Refresh
ohne erneuten Dispatch. Reload/Offline-Fortschritt in beiden Abschnitten und
Settlement schreiben Ziel, Endenergie und Auszahlung einmalig.

Neue Snapshots werden roundtripped, unbekannte Felder und leere Anfahrtsobjekte
abgelehnt. Alte Snapshots benötigen weder aktuellen Katalog noch neue Route.
Öffentliche route_legs und Journey-Intervalle enthalten keine Kosten, Erlöse,
Energiefüllstände oder Verbrauchsprofile. Die JS-Gegenprobe verwendet bewusst
gegensätzliche Geometrie-/Straßenlängen; eigene/fremde Fahrzeuge erreichen B
exakt am selben Abschnittswechsel, nicht bei einer Gesamtrouten-Fraction.

## Browser und visuelle Prüfung

Neue Playwright-Fälle: Desktop 1440×900 und Mobile 390×844 mit Reduced Motion,
Fahrzeugwahl, sichtbare Start-/Abholstationen, getrennte Kilometer, „Zur Abholung“,
automatischer Wechsel zu „Fracht unterwegs“ sowie Reload auf beiden Abschnitten.
Bestehende Desktop-/Tablet-/Mobilfälle decken Markt, Auswahlwechsel, verspätete
Quotes, Pan/Zoom ohne Marktreads, Energiehalte, Offline-Ankunft und Analytics ab.

Die gerenderten Screenshots `world-freight-approach-desktop.png` und
`world-freight-approach-mobile.png` wurden visuell geprüft: Statuslabel,
Fahrzeugabbildung, Start-/Abholfolge und responsive Panels bleiben lesbar,
kein horizontaler Überlauf. Delivery-Screenshots dokumentieren den Wechsel.
Alle Bilder liegen im temporären Verzeichnis und werden nicht versioniert.
Automatisierte OSM-Kacheln sind lokale Testbilder. Reale Straßenprovider werden
über die vorhandenen Port-/Provider-Tests geprüft; dieser Regressionslauf ist
keine neue Live-Valhalla- oder physische Mobilgeräte-/Safari-Abnahme.

## Architekturreview und verbleibende Grenzen

Das [Einzelreview](docs/DISPATCH_APPROACH_REVIEW.md) benennt für jede neue oder
wesentlich geänderte öffentliche/private Core-Funktion Zweck, Schicht,
Abhängigkeiten und Seiteneffekte. Es wurde zusätzlich zum Manifest durchgeführt.
Keine neue Markt-, SQL- oder HTTP-Verantwortung wurde in GameService verlagert.
Planung bleibt deterministisch, Services injiziert, Repositories auf Mapping
und Speicherung begrenzt, Views auf Darstellung. Öffentliches Tracking nutzt
dieselben Abschnittsgrenzen wie eigenes Tracking. Keine Assets/Kataloge wurden
verändert, keine Spieler-DBs, Backups oder Prüfartefakte aufgenommen.

100 % Statement-Coverage ist eine Codeprüfung, keine Behauptung vollständiger
geografischer Daten. Katalogseitig bleiben 559 Facilities, davon 95 mit
verifizierten und 464 mit ausdrücklich geschätzten Koordinaten. Fehlende
NHM-/Fahrzeug-kompatible Distanzbänder bleiben datenbedingte unmet Coverage;
diese Änderung erfindet dafür weder Relationen noch Angebote. Kein neuer
Vollscan sämtlicher Stadt-/Flottenkombinationen wurde behauptet. Historische
Transporte erhalten keine nachträgliche Anfahrt oder aus aktuellen Katalogen
rekonstruierte Konditionen. Provider-Snapping und vereinfachter konstanter
Energieverbrauch bleiben bestehende Modellgrenzen.
