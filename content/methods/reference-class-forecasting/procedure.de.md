## Purpose

Ersetzen Sie eine Innenperspektivprognose durch Außenvergleich anhand einer belastbaren Klasse abgeschlossener vergleichbarer Fälle. Schätzen Sie anhand beobachteter Ergebnisse und benennen Sie aktuelle Anpassungsgründe ausdrücklich. Das ist Kalibrierung, keine Zusage oder Erlaubnis, Population, Verteilung oder Wahrscheinlichkeit zu erfinden.

## Use when

Für Zeitplan-, Kosten-, Nachfrage-, Nutzungs-, Zuverlässigkeits- oder Lieferprognosen bei vergleichbaren Vergangenheitsfällen und möglicherweise optimistischem Eigenplan. Besonders hilfreich bei unbelegter Behauptung „dieser Fall ist anders“. Für fundierte Bandbreite statt Einzelpunktschätzung.

## Do not use when

Nicht ohne belastbare abgeschlossene Referenzfälle, klares Ziel und Einheit oder bei einzigartigem Fall ohne Vergleichsergebnis. Anekdoten sind keine Basisverteilung; nicht nur Erfolgsfälle wählen oder interne Prognose als Evidenz behandeln. Mechanische Aufgabe oder kausale Diagnose statt Kalibrierung umleiten.

## Inputs to establish

Klären Sie Zielergebnis, Einheit, Horizont, Stichtag und akzeptable Grenze. Ein- und Ausschlussregeln vor Ergebnisbetrachtung definieren. Fälle, Ergebnisdefinitionen, Abdeckung, fehlende Angaben und Quellenstatus sammeln. Bekannte Unterschiede des Projekts und Eigenprognose erfassen. Höchstens zwei Fragen, nur wenn Klasse oder Ziel beeinflusst werden. Eingaben als verifiziert, berechnet, abgeleitet, angenommen, ungeprüft oder widersprüchlich markieren.

## Procedure

1. Ziel, Einheit, Horizont und Entscheidungsgrenze in einem Satz veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Prognosebasis; mehrdeutiges Ziel zurückstellen statt still eingrenzen.
2. Referenzklassenregel mit Einschluss, Ausschluss, Ähnlichkeitsdimensionen und Abdeckungslücken veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Prüffähige Klasse statt Intuition.
3. Beobachtete Verteilung nur aus verfügbaren Fällen veröffentlichen: Anzahl, Mitte, Streuung, Bandbreite und berechenbare Ränder. **Sichtbares Ergebnis/Zustandsänderung:** Eingaben und Quellen-/Evidenzstatus jeder Statistik; nicht verfügbare Statistik bleibt ungeprüft.
4. Außenbasis neben Eigenplan veröffentlichen und Differenzrichtung erklären. **Sichtbares Ergebnis/Zustandsänderung:** Plan innerhalb, oberhalb oder unterhalb beobachteter Verteilung; Position ist keine Wahrscheinlichkeit.
5. Anpassungen für wesentliche aktuelle Unterschiede einzeln veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Richtung, Grund und Evidenzstatus je Anpassung; Zahl nur bei begründbarer Größenordnung.
6. Begrenzte Bandbreite samt Bedingungen plausibler Ränder veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Bei schwacher Abdeckung, Auswahl- oder Randevidenz verbreitern oder zurückstellen; keine erfundene Basisrate.
7. Status gestützt, vorläufig oder zurückgestellt mit Umkehrbedingung und nächster Prüfung veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Fehlende entscheidende Klassen- oder Ergebnisangabe bedeutet ausdrückliche Zurückstellung statt willkürlicher Empfehlung.

## Public output contract

Liefern Sie `target`, `reference_class`, `base_distribution`, `adjustments`, `range`, `inside_view_comparison`, `flip_condition` und Status gestützt, vorläufig oder zurückgestellt. Schluss benennt Unterstützung durch beobachtete Klasse, keine sichere Übereinstimmung des aktuellen Falls. Gründe als **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted** markieren. Fehlende Abdeckung oder Auswahlrisiko nennen; Umkehrbedingung muss beobachtbar sein statt bloß „bei neuen Informationen“.

## Evidence and uncertainty rules

Nur abgeschlossene Fälle mit definiertem Ziel, Einheit und Einschluss stützen die Klasse. Ergebnisquelle belegt nicht automatisch Vergleichbarkeit des Projekts; diese bleibt ohne direkte Unterstützung abgeleitet. Berechnungen zeigen Fälle oder Referenzen und Rundung. Median, Verteilungsränder, Stichprobenzahl, Basisrate oder Wahrscheinlichkeit nicht erfinden. Auswahlverzerrung, fehlende Fälle, widersprüchliche Definitionen und kleine Stichproben bewahren. Andersartigkeit bleibt Anpassungshypothese bis Richtung und Wirkung belegt sind.

## Stop conditions

Bei materiell verschiedenen Deutungen von Ziel, Einheit oder Grenze eine blockierende Frage stellen und stoppen. Ohne belastbare Klasse, Ergebnisdefinition oder entscheidenden Vergleich zurückstellen. Bei verbleibender Kausalerklärung, Optionswahl oder mechanischer Berechnung übergeben statt Außenprognose erzwingen.

## Complement handoff

An `sensitivity-analysis` übergeben, wenn Änderungen der Referenzverteilung oder Anpassung die Wahl bestimmen. Ziel, beobachtete Basis, geprüfte Anpassungsbereiche, Abdeckungsgrenzen und Wechselbedingung übermitteln. Eingaben variieren, ohne Klasse neu aufzubauen oder Ergebnis als neue Basisrate auszugeben.
