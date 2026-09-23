# Verbindlicher Git- und Branch-Workflow

Gilt für Menschen und Agenten. Produkt- und Coding Standards gelten zusätzlich.

## Branches

`main` enthält den integrierten, geprüften Stand. Er ist kein Nachweis, dass
M1 oder der öffentliche Betrieb vollständig abgenommen sind. Es gibt keinen
permanenten develop-Branch. Jede Änderung beginnt auf einem kurzen Arbeitsbranch
von aktuellem main; ein Branch behandelt ein zusammenhängendes Thema.

| Präfix | Verwendung | Beispiel |
| --- | --- | --- |
| feature/ | Neue Produktfunktion | feature/company-registration |
| fix/ | Fehlerkorrektur | fix/vehicle-image-refresh |
| refactor/ | Strukturänderung | refactor/profile-maintenance |
| docs/ | Dokumentation | docs/m1-acceptance |
| chore/ | Werkzeuge, CI, Dependencies | chore/git-foundation |
| test/ | Reine Testergänzung | test/session-expiry |
| hotfix/ | Dringender Fehler eines veröffentlichten Stands | hotfix/login-failure |

Beschreibungen verwenden ausschließlich Kleinbuchstaben, Zahlen und einzelne
Bindestriche, ohne führenden/abschließenden Bindestrich. Keine direkten Commits
auf main, kein Arbeiten auf detached HEAD, kein Force-Push auf geteilte Branches.
Hotfixes durchlaufen dieselben Prüfungen; das Präfix umgeht keine Freigabe.

## Arbeitsablauf

1. Sauberen Arbeitsbaum prüfen: `git status`. Fremde Änderungen nicht zurücksetzen.
2. `git switch main`; bei konfiguriertem origin anschließend `git pull --ff-only`.
3. Arbeitsbranch anlegen, beispielsweise `git switch -c fix/vehicle-image-refresh`.
4. Kleine nachvollziehbare Commits. Nachrichten: `typ: konkrete Änderung`, mit
   feat, fix, refactor, docs, chore oder test als Typ. Nur zusammengehörige Dateien
   stagen; den Index vor jedem Commit mit `git diff --cached` prüfen.
   Betroffene Tests einschließlich unmittelbar abhängiger Aufrufer müssen vor
   dem Commit grün sein. Kein vollständiger Projekt-Testlauf pro Commit und
   keine zusätzlichen Kompatibilitätsschichten allein für grüne Zwischenstände.
   Noch offene Gesamtprüfungen werden sichtbar dokumentiert.
5. Vor Integration Quality Gate, Browserregression und Dokumenten-/Architekturreview
   durchführen. Grüne Linter ersetzen keine Prüfung der Verantwortlichkeiten.
6. Sobald ein Remote besteht: Branch pushen, Pull Request nach main erstellen,
   aktuelle Prüfungen und Review abwarten, anschließend Squash-Merge. Bei mehreren
   Mitwirkenden mindestens eine Freigabe durch eine andere Person einholen.
7. Nach Merge main aktualisieren und den erledigten Branch lokal/remote entfernen.
   Release-Tags `vX.Y.Z` nur für ausdrücklich freigegebene Releases erstellen.

Die einmalige Aufnahme des vorhandenen Projekts ist der dokumentierte Bootstrap-
Commit auf main. Danach werden die lokalen Hooks aktiviert. Es wird kein Release
oder MVP-Abschluss aus dieser Bestandsaufnahme abgeleitet.

## Lokale Durchsetzung

Nach jedem Clone einmal aus der Repositorywurzel ausführen:

```sh
git config --local core.hooksPath .githooks
```

Der pre-commit-Hook blockiert main/detached HEAD, ungültige Branchnamen sowie
zwangsweise gestagte Dateien, die .gitignore ausschließt. Der gesamte Testlauf
wird bewusst vor Integration ausgeführt. Hooks lassen sich technisch umgehen;
`--no-verify` ist für den normalen Workflow untersagt. Der Guard ersetzt weder
Secret-Scanning noch serverseitigen Branchschutz.

Solange das Repository rein lokal ist, erfolgt die Integration eines geprüften
Arbeitsbranches ausschließlich mit `git merge --ff-only <branch>` auf main.
Falls das wegen paralleler Änderungen scheitert, zuerst auf dem Arbeitsbranch
main integrieren, Konflikte lösen und die Prüfungen erneut ausführen. Keine
Merge-Commits direkt auf main und kein Zurücksetzen von main.

## Remote und tatsächlicher Schutzstatus

`origin` verweist auf das private Repository
[Lexoniarus/world-freight-idle](https://github.com/Lexoniarus/world-freight-idle).
GitHub Actions und PR-Vorlage sind eingerichtet. Nur Squash-Merge ist freigegeben;
GitHub löscht gemergte Arbeitsbranches automatisch.

**Serverseitiger Branchschutz ist nicht aktiv.** GitHub lehnt Schutzregeln für
dieses private Repository mit HTTP 403 ab und verlangt ein Pro-Upgrade oder eine
öffentliche Sichtbarkeit. Das Repository bleibt privat; die Sichtbarkeit wird
nicht als Umgehung geändert. Lokale Hooks, CI und die verpflichtende PR-Prüfung
sind vorhanden, können serverseitige Zugriffsbeschränkungen aber nicht ersetzen.

Sobald der GitHub-Tarif es erlaubt, für main einen Ruleset/Branchschutz aktivieren:
PR erforderlich, Statuschecks `quality` und `branch-policy` erforderlich, Branch
aktuell, Force-Push und Löschen untersagt. Bei mehreren Mitwirkenden eine fremde
Review-Freigabe erzwingen. Bis dahin müssen auch Administratoren den dokumentierten
PR-Workflow ohne direkte main-Pushes einhalten.

Der CI-Branchcheck prüft PR-Quellnamen und das Ziel main sowie Namen gepushter
Arbeitsbranches. Ein main-Push ist nur das erwartete Ergebnis der Integration;
seine Autorisierung erzwingt später der serverseitige Branchschutz.

## Was versioniert wird

Code, Tests, Dokumentation, Konfigurationsvorlagen, Lockfile und der geprüfte
Referenzkataloge `data/world_freight_vehicle_catalog.sqlite3` und
`data/world_freight_company_facility_mvp.sqlite3` gehören ins Git.
Spielstände, Konten, Backups, lokale .env-Dateien, Schlüssel, node_modules,
virtuelle Umgebungen, generierte Builds und Prüfartefakte bleiben lokal.
Katalogänderungen müssen Herkunft/Lizenz, Schema und Spielwerte im PR erläutern;
die Katalogtests und Auslieferungsprüfung sind Pflicht. Der Katalog darf keine
Spieler- oder Sitzungsdaten enthalten. Git ersetzt kein Spielstand-Backup.
