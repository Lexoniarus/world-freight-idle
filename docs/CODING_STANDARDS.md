# Coding Standards

- Python >= 3.11, PEP 8, vier Leerzeichen, 79 Zeichen je Codezeile.
- `snake_case` für Module/Funktionen/Variablen, `PascalCase` für Klassen,
  `UPPER_CASE` für Konstanten. Aussagekräftige englische Bezeichner.
- Öffentliche Funktionen erhalten Typannotationen und kurze Docstrings.
- Stateful Services/Repository/Provider als Klassen; reine Hilfslogik darf funktional bleiben.
- Abhängigkeiten explizit injizieren. API übersetzt HTTP, Services
  orchestrieren Use Cases, Repositories kapseln SQL, Provider externe APIs.
- Geldbeträge sind ganzzahlige Spiel-Euro; der Browser bestimmt keine Preise,
  Besitzverhältnisse, Guthaben oder Zeitstempel.
- Zusammengehörige Mutationen sind atomar. Keine Schreibtransaktionen
  während externer API-Aufrufe; nach dem Await erneut validieren.
- Strukturierte Events und Trace-ID verwenden; keine Passwörter/Cookies loggen.
- Neue Core-Funktionen erhalten Verhaltenstests und einen Eintrag im
  Function-Test-Manifest. Fehlerpfade und konkurrierende Geldmutationen testen.
- Ruff und Formatter laufen im Quality Gate. Lange Testbeschreibungen sind
  von E501 ausgenommen; Core-Code hat keine solche Ausnahme.
- mypy prüft Core und Einstiegspunkt, verlangt annotierte Funktionen und
  prüft auch Funktionskörper. Vollständig typisierte statt dynamischer
  JSON-Spielzustände sind eine spätere Verbesserung; kein Strict-Mode-Anspruch.
- Eine Funktion erfüllt eine zusammenhängende Aufgabe. Orchestratoren setzen
  benannte Schritte zusammen; sie implementieren deren Details nicht selbst.
  Zeilenzahl allein ist kein Kriterium für Single Responsibility.
- Frontend als native ES-Module. Funktionen/Variablen verwenden `camelCase`,
  Klassen `PascalCase`, Moduldateien `kebab-case`. Python behält `snake_case`.
- Zustandsbehaftete Browserkomponenten besitzen einen definierten Lebenszyklus
  mit `start()` und `destroy()`, soweit sie Ressourcen halten. Timer, Listener,
  Animationen und laufende Anfragen müssen beim Beenden freigegeben werden.
- API-Zugriff ausschließlich über `frontend/api.js`; externe Basiskarten-Tiles
  und verifizierte Fahrzeugfotos sind getrennte Medienquellen ohne
  Backend-Header oder Zugangsdaten.
- Views erzeugen DOM-Knoten, führen keine Requests aus und verändern keine
  Spielregeln. Dynamische Texte werden über `textContent`/Textknoten gesetzt.
  Der DOM-Template-Helfer parst ausschließlich statische Template-Teile;
  Werte und Attribute werden anschließend gebunden. Kein `innerHTML`.
- Öffentliche JS-Modulgrenzen erhalten JSDoc-Verträge, gemeinsame Projektionen
  stehen in `frontend/types.js`. `checkJs` prüft alle Anwendungsdateien.
  Kein TypeScript-Umbau und kein Strict-Mode-Anspruch; API-JSON bleibt eine
  dynamische Grenze. Formulare brauchen Labels und sichtbare Fehler.
- ESLint, Stylelint, Prettier und checkJs sind verbindlich. CSS verwendet
  benannte Klassen und generische Schrift-Fallbacks. Die Reihenfolge
  komponentenbezogener Selektoren wird nicht über Spezifitätsheuristiken erzwungen.
- Architekturtests prüfen Importgrenzen zusätzlich zu Verhaltenstests.
  OOP und Single Responsibility benötigen weiterhin ein inhaltliches Review.

Befehle: `python -m ruff check app tests main.py`,
`python -m ruff format app tests main.py`.

Gesamtprüfung: `python scripts/quality.py` oder `make quality`.
Frontend separat: `npm run quality:frontend`; Browser: `npm run test:e2e`.
Formatierung: `npm run format`. Die Python-Grenze von 79 Zeichen bleibt
unverändert; Prettier verwendet für JavaScript/CSS eine Zielbreite von 100.

Katalogregeln: technische Referenzdaten und Spielstände bleiben getrennt.
Katalog-Repositories öffnen SQLite nur lesend; Kauf-/Freigaberegeln liegen im
Service. Gekaufte Werte sind Snapshots. JSDoc beschreibt auch injizierte
Abhängigkeiten und neue Modell-/Quote-Projektionen; dynamisches API-JSON
entbindet öffentliche Komponenten nicht von ihren Parameterverträgen.


## Transaktionen, Lebenszyklen und Wartungswerkzeuge

- Öffentliche zustandsändernde Service-Methoden besitzen ihre Transaktionsgrenze
  selbst. Private Schritte dürfen eine bereits aktive Transaktion voraussetzen;
  dies wird im Docstring benannt. Reset und Initialisierung teilen dieselbe
  äußere Transaktion, sodass ein Fehler den gesamten Ablauf zurückrollt.
- Ressourcen unmittelbar nach erfolgreicher Erstellung zur Freigabe registrieren.
  Auch Fehler während Start und Shutdown werden getestet; ein fehlgeschlagener
  Cleanup darf das Schließen weiterer Ressourcen nicht verhindern.
- CLI-Programme verarbeiten Eingaben und orchestrieren. SQL gehört in Repositories,
  Spielvalidierung in Services, konkrete Abhängigkeiten in den Composition Root.
  Die lokale Profilpflege erhält Repository, Katalog und Store-Factory injiziert.
- Ein Backup muss vor Profilmutationen erfolgreich abgeschlossen sein. Bestehende
  Backupdateien werden nicht überschrieben. Wartungslogik unter app unterliegt
  ebenfalls dem Function-Test-Manifest und 100 % Core-Statement-Coverage.
- Nach externen Await-Punkten werden auch veränderliche Fahrzeugkostensätze für
  den Start erneut gelesen und kalkuliert, bevor das Guthaben geprüft wird.
- Das Profilpflege-CLI ist zusätzlich zu Core und Einstiegspunkt in mypy enthalten.
