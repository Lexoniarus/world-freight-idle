# Frontend-Gesamtkonzept aus dem Designinterview

Stand: 28.10.2026. Dieses Dokument hält die im Interview bestätigte Zielrichtung
fest. Es beschreibt das gesamte Spiel-Frontend, nicht nur Kartenmaterialien.
Der [Umsetzungsplan](FRONTEND_IMPLEMENTATION_PLAN.md) ordnet den Ausbau den
vorhandenen Modulen zu. Offene Fragen stehen beim jeweiligen Thema.

**Status:** Konzept und Reihenfolge sind dokumentiert. Damit ist keine
Frontend-Implementierung, Produktasset-Freigabe oder zusätzliche M1-Abnahme
verbunden. Die bestehenden Spielregeln und Datenverträge gelten bis zu ihrer
ausdrücklich geplanten Änderung weiter.

## 1. Spielerlebnis und Zeitbezug

- Aufstieg vom selbstständigen Unternehmer mit einem einzelnen Lkw zum
  Transportmogul. Firmenverwaltung ist von Anfang an Teil des Erlebnisses.
- Anfangs steht der eigene kleine Betrieb im Vordergrund; Mitarbeiter sollen
  anschließend früh eine Rolle spielen.
- WIF spielt in der Gegenwart. Der Grafikstil orientiert sich an den späten
  90ern und frühen 2000ern.
- Alte, zusammengewürfelte Ausstattung darf den wirtschaftlichen Anfang
  zeigen. Der Betrieb entwickelt sich zu einer modernen, professionellen
  Zentrale mit Mitarbeitern und Abteilungen. Das ist Unternehmensfortschritt,
  kein historischer Wechsel der Spielepoche.
- Wirtschaft und Folgen von Entscheidungen bleiben glaubwürdig. Skurrile
  Geschäftspartner und gelegentlich absurde Alltagssituationen sind erwünscht,
  aber dosiert.

**Offene Frage F01:** Wie früh werden Mitarbeiter im Spielablauf benötigt,
welche Rollen kommen zuerst und welche Zuordnung zu MVP/Folgemeilensteinen
wird dafür beschlossen? Der gewünschte frühe Übergang ist festgelegt; die
konkreten Spielregeln und der Lieferumfang sind es noch nicht.

## 2. Grafische Referenzen und gemeinsame Bildsprache

Die beiden Hauptreferenzen sind das ursprüngliche **Airline Tycoon** und
**American Dream – Von der Pommesbude zum Fast-Food-Imperium! (1996)**.

- Airline Tycoon liefert vor allem die polierte, ausgearbeitete Comic- und
  Bitmap-Bildsprache. Seine blaulastige Farbgebung ist keine Farbvorlage für WIF.
- American Dream liefert Inspiration für Buntheit, dunklere Kontraste,
  überzeichnete Figuren und Skurrilität bei klaren Informationsstrukturen.
- Gesucht ist eine geschlossene, illustrierte Wirtschaftsspieloberfläche mit
  leichter Pixelästhetik. Kleine Rauschmuster auf sonst realistischen oder
  glatten 3D-Flächen erfüllen dieses Ziel allein nicht.
- Gezeichnete Konturen, Lichtkanten, Farbabstufungen und Materialdetails sollen
  zusammenwirken. Eine grobe 8-Bit-Ästhetik ist nicht das festgelegte Ziel.
- Figuren, Räume und Symbole dürfen kräftig und eigenwillig sein. Listen,
  Zahlen und längere Texte erhalten ruhigere, gut lesbare Flächen.

**Offene Frage F02:** Welche konkreten Schriften, Icon-/Illustrationsquellen
und lokal nutzbaren Produktassets tragen diese Bildsprache? Herkunft,
Nutzungsrechte, Quelldateien und Ablage müssen vor dem Import geklärt sein.
Die Referenzspiele liefern Stilreferenzen, keine zu übernehmenden Spielassets.

## 3. Farbe, Firmenidentität und Schrift

- Die eigene Firmen-CI hat einen prägenden, wiedererkennbaren Einfluss auf
  Oberfläche, Zentrale, Unterlagen, Fahrzeuge und Firmengebäude.
- Alle Spieler behalten dieselben Basisansichten und dieselbe Bedienung.
  Firmenidentität ist eine Gestaltungsdimension dieses gemeinsamen Systems.
- Einzelne Bereiche dürfen eigene Farbwelten erhalten. Gemeinsame Schriften,
  Rahmen, Reiter und Bedienregeln halten sie zusammen.
- Weinrot und Gold sowie das Zusammenspiel mit dem Logo wurden im ersten
  Gesamtentwurf als passende Richtung bestätigt. Die konkrete dargestellte
  Firmen-CI war ein Beispiel, keine Festlegung derselben Farben für alle Firmen.
- Wiederkehrende Farben und Symbole machen Auswahl, Status und Aktionen klar.
  Buntheit darf die Informationshierarchie nicht auflösen.
- Retro-Schrift wird für Überschriften und Beschriftungen eingesetzt; Tabellen,
  Zahlen und längere Texte verwenden eine gut lesbare Schrift.

**Offene Frage F03:** Welche verbindlichen Farbwerte, Bereichsakzente und
Prioritäten zwischen Firmenfarbe, Bereichsfarbe und Statusfarbe werden im
Designsystem festgelegt? Welche Teile des Logos werden Produktassets und
welche gehören zur individuell konfigurierbaren Firmenidentität?

## 4. Karte, Navigation und Verwaltungsflächen

- Die reale Karte ist die Hauptoberfläche. Sie erhält den größten Raum.
- Kontostand, laufende Transporte, freie Fahrzeuge und wichtige Meldungen
  bleiben kompakt und direkt sichtbar.
- Größere Bereiche wie Personal, Fuhrpark oder Finanzen dürfen eine eigene,
  weitgehend bildschirmfüllende Ansicht erhalten. Der Rückweg zur Karte ist
  schnell und direkt; der Kartenkontext soll erhalten bleiben.
- Kompakte Listen enthalten kleine Porträts beziehungsweise Fahrzeugbilder
  und die wichtigsten vergleichbaren Werte. Weitere Details öffnen sich
  beim Anklicken.
- Die Verwaltungswelt verbindet Akten, Ordner und Arbeitsunterlagen mit
  Office-PCs und digitalen Übersichten. Diese Motive gehören zu einer
  gemeinsamen Bedienoberfläche.
- Die Zentrale kombiniert anklickbare Gegenstände beziehungsweise passende
  Ansprechpartner mit direkten Menüzugängen für häufige Aufgaben.
- Bestehende funktionsfähige Bereiche wie Fahrzeugshop, Transporte und
  Rangliste dürfen durch das neue Navigationsbild nicht verloren gehen.

**Offene Frage F04:** Wie werden bestehende Routen und Unterbereiche in die
neue Navigation einsortiert, und wie sehen die konkreten Tablet-/Mobilansichten
aus? Die vorhandene Touch-, Tastatur- und Fokusbedienung ist zu erhalten.

## 5. Mitwachsende Firmenzentrale

Der Firmensitz entwickelt sich sichtbar vom kleinen Büro zur großen Zentrale
mit Mitarbeitern und Abteilungen. Einrichtung und Technik vermitteln den
wirtschaftlichen Aufstieg. Personalisierte Mitarbeiter müssen dafür nicht als
individuelle Figuren im Büro erscheinen; ihre Verwaltung erfolgt über Porträts.

**Offene Frage F05:** Welche Ausbaustufen, sichtbaren Ausstattungsmerkmale und
Freischaltbedingungen bilden dieses Wachstum ab? Wie hängt die sichtbare
Zentrale mit dem noch auszubauenden Firmen- und Depotmodell zusammen?

## 6. Mitarbeiter und Porträts

- Mitarbeiter werden in einer verwalteten Ansicht mit individuellen Werten,
  Eigenschaften und Porträts dargestellt.
- Die Porträts dürfen dosiert skurril sein, angelehnt an American Dream.
  Aussehen darf Eigenschaften andeuten, ohne den Mitarbeiter dauerhaft auf
  seine Anfangswerte festzulegen.
- Mitarbeiter sollen sich entwickeln und hochleveln können.
- **Die Porträts bleiben zunächst unverändert.** Entwicklung wird über Stats,
  Rang und Abzeichen gezeigt; Wiedererkennbarkeit ist ausdrücklich gewünscht.
- Individuell unterschiedliche Mitarbeiter werden nicht zusätzlich als ihre
  jeweiligen Figuren in Büros ausgespielt.

**Offene Frage F06:** Welche Stats, Eigenschaften, Ränge, Abzeichen und
Levelregeln gehören zum Fachmodell? Die Zahlen und Namen der Vorschauen sind
keine beschlossenen Spielwerte. Porträtvarianten und ihre Zuordnung müssen
ebenfalls noch ausgearbeitet werden.

## 7. Fahrzeug-Informationsbubble

- Klick auf einen Lkw öffnet eine am Fahrzeug verankerte Informationsbubble.
- Reiter gliedern Informationen zu **Fahrer, Fahrzeug und Auftrag**.
- Die Bubble dient hauptsächlich der Information. Passende Verweise führen
  zum zugehörigen Auftragshub oder zur jeweiligen Verwaltungsübersicht.
- Aktionen richten sich logisch nach dem aktuellen Zustand. Fehlt ein
  erforderlicher Fahrer, soll von dort aus eine Zuweisung möglich sein.
  Ein bereits transportierendes Fahrzeug erhält keine unpassende Aufforderung,
  einen nächsten Auftrag zu suchen.
- Die vorhandene serverseitige Freigabe bleibt maßgeblich. Ein zukünftig
  dargestellter Reiter darf kein noch fehlendes Mitarbeitermodell vortäuschen.

**Offene Frage F07:** Welche Felder und Aktionen erhält jeder Reiter,
welche Bubble bleibt bei Auswahlwechseln offen und wie verhält sie sich bei
Bewegung, Kartenrand und kleinen Bildschirmen? Die Verankerung und die drei
Informationsbereiche sind bereits entschieden.

## 8. Meldungen, Bewegung und Klang

- Normale Hinweise erscheinen kompakt mit Symbol und Text.
- Wichtige Meldungen dürfen einen passenden Absender mit Porträt bekommen.
- Die fahrenden Fahrzeuge sind die Hauptbewegung auf der Karte.
- Dokumente dürfen eine Blätteroptik besitzen; gelegentliches dezentes
  Bildschirmflackern, passende Übergänge und Aktionsgeräusche sind erwünscht.
- Dezente Hintergrundmusik und passende Umgebungsgeräusche sind erwünscht,
  solange sie nicht aufdringlich sind und abgeschaltet werden können.
- Bestehende Reduced-Motion-, Fokus- und Lesbarkeitsanforderungen gelten weiter.

**Offene Frage F08:** Welche Ereignisse sind wichtig, dürfen sie unterbrechen
und gibt es dafür ein dauerhaftes Postfach? Welche Animationen und Klangkanäle
werden konkret verwendet, wie werden Lautstärke und Abschaltung gespeichert?

## 9. Reale Geografie, Gelände und Materialien

- Die reale Grundszene bleibt die räumliche Grundlage. Eine frei erfundene,
  illustrierte Stadt ersetzt weder Straßennetz noch Gebäudegrundrisse.
- **Gelände aus Höhendaten / Heightmap gehört zum Kartenfundament.** Mit der
  im Gespräch genannten „Heatmap“ war keine farbige Daten-Dichteebene gemeint.
- Gebäude, Straßen und Fahrzeuge müssen auf derselben Höhenbasis stehen.
- In der Entfernung tragen Farben und Formen die Lesbarkeit. Beim Heranzoomen
  werden Materialdetails sichtbar; aus der Entfernung sollen sie zurücktreten.
- Ein generischer Materialbaukasten umfasst Fassaden, Fenster, Sockel,
  Dachflächen, Gras, Asphalt und Pflaster. Wiederholungen und Detailmaßstab
  müssen zusammenpassen.
- Gebäudetypen und passende Materialvarianten werden aus Kartendaten genutzt,
  soweit diese Informationen verlässlich vorhanden sind. Unbekannte Typen
  erhalten eine zurückhaltende Standardgestaltung.
- Materialien sollen zur bestätigten Retro-Bildsprache und zum UI passen.
  Fotografische Körnung oder sichtbares Rauschen allein sind kein Stilnachweis.
- Satellitenbilder wurden erkundet; der aktuelle gestalterische Schwerpunkt
  liegt auf einer eigenen, gezeichnet wirkenden Kartendarstellung.
- Das Ziel bleibt eine Lösung ohne laufende externe Providergebühren.

**Offene Frage F09:** Welche Vektor- und Höhenquellen erfüllen Kosten-,
Lizenz-, Attributions-, Abdeckungs- und Betriebsanforderungen? Wie erfolgen
Laden, Caching, Fehleranzeige und die Umstellung des bisherigen Rasterproviders?

**Offene Frage F10:** Welche Gebäudetypen, Höhen und Dachangaben liefern diese
Quellen tatsächlich? Welche Materialvarianten, Größen und Zoomübergänge
werden visuell abgenommen? Die jüngste Materialstudie ist keine abschließende
Freigabe ihrer Fassaden oder Dächer.

## 10. Fahrzeuge mit leicht erhobener Darstellung

- Die vorhandene Fahrzeuggestaltung bleibt die Grundlage. Mehr Firmenfarben
  und verbessertes Einfärben sind gezielte Weiterentwicklungen.
- Front-, Seiten- und Draufsicht können einen einfachen räumlichen Aufbau
  texturieren. Sie liefern noch kein automatisch fertiges 3D-Modell.
- Der einzelne MAN-TGL-Test mit Kabine, Koffer, Rädern und etwas Höhe wurde als
  passende erste Richtung bestätigt. Übergänge und Ansichten von allen Seiten
  brauchen noch Feinschliff.
- Bestehende Fahrzeugidentität, Farbe, echte Position, Bewegungsrichtung,
  Auswahl und Gruppierung bleiben Teil der Integrationsaufgabe.

**Offene Frage F11:** Welche Modellmaße, Bildausschnitte und zusätzlichen
Ansichten werden benötigt? Wie werden rechte Seite und Rückseite behandelt,
Farbmasken auf die Flächen übertragen und Leistung, Trefferfläche und
Gruppierung über Zoom und Kartenneigung verlässlich gehalten?

## 11. Stellenwert der bisherigen Vorschauen

Die Vorschauen sind lokale, nicht versionierte Gestaltungs- und Technikproben:

- Der erste Gesamtentwurf bestätigte UI, Icons, Menüführung und Farb-/Logo-
  Zusammenspiel. Seine frei illustrierte Kartenstadt wurde ausdrücklich verworfen.
- Der korrigierte Gesamtentwurf mit echter Grundszene bestätigte die Richtung
  von UI und Karte im Zusammenspiel.
- Die Lkw-Studie bestätigt einen ersten räumlichen Ansatz, keinen fertig
  ausgearbeiteten Fahrzeugbestand.
- Die Materialversuche liefern Anschauung, ersetzen aber keine konkrete
  Integration und Abnahme an den vorhandenen Produktmodulen.

Die lokalen Dateien `combined-preview.html`, `truck-study.html` und
`material-study.html` sowie das UI-Konzeptbild sind Referenzen außerhalb des
Repos. Lokaler Server und Dateien sind keine dauerhaft verfügbare Produktquelle.
Keine kopierten Vorschau-Skripte, Beispieldaten oder aus dem Gesamtbild
ausgeschnittenen UI-Teile werden automatisch zu Produktionskomponenten.

Die nächste Arbeit erfolgt gemäß [Umsetzungsplan](FRONTEND_IMPLEMENTATION_PLAN.md)
schrittweise an den echten Modulen. Dieses Dokument startet keine Implementierung.
