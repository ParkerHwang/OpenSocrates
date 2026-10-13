## Purpose

Nutze dieses Verfahren zur Verallgemeinerung von Beobachtungen mit probabilistischem, stichprobenbegrenztem Schluss. Es benennt Induktionstyp, prüft Größe, Vielfalt und Repräsentativität, sucht aktiv Gegenbeispiele und nennt Reichweite und Stärke. Wiederholung erhöht Unterstützung nur, wenn Stichproben- und Messgrundlage die Erweiterung rechtfertigen.

## Use when

Nutze es für Datenmuster, Umfragen, Nutzerfeedback, wiederholte Vorfälle und Schlüsse von Fällen auf größere Populationen oder zukünftiges Verhalten. Es passt zu statistischer, aufzählender, kausaler oder analogischer Verallgemeinerung und Fragen nach Beobachtungsreichweite.

## Do not use when

Nutze es nicht für unrepräsentative Gelegenheitsstichproben, strikte Regelanwendung oder Kausalbehauptungen mit Bedarf an kausalem Design. Duplikate bedeuten keine Vielfalt, kleine Stichproben kein „alle“, plausible Trends keine notwendige Folgerung.

## Inputs to establish

Kläre Beobachtungen, Zielpopulation oder Zukunftsumfang, Auswahlprozess, Messdefinition, Vergleichsgruppen, Zeitraum und Entscheidung. Benenne Induktionstyp sowie Auswahl-, Überlebenden-, Nichtantwort- oder Messverzerrungen. Stelle höchstens eine entscheidende Frage bei unbekannter und reichweitenändernder Population oder Stichprobengrundlage.

## Procedure

1. Veröffentliche Beobachtungsprämissen und vorgeschlagene Verallgemeinerung getrennt. Kennzeichne Herkunft und Belegstatus jeder Beobachtung; so entsteht sichtbare Induktionsbasis.
2. Veröffentliche Typ – aufzählend, statistisch, kausal oder analogisch – und Brücke von Stichprobe zum Zielumfang. Benenne die plausibilisierenden Annahmen.
3. Veröffentliche Stichprobengrundlage: Größe, Vielfalt, Auswahl, fehlende Fälle, Messqualität und Zeitabdeckung. Trenne Quellenbeschreibung von erschlossener Repräsentativität.
4. Veröffentliche stärkste Gegenbeispielsuche und Ergebnis. Ergänze verfügbare ausgeschlossene Fälle, Negativergebnisse, Untergruppenunterschiede und mögliche Zukunftsausnahmen.
5. Veröffentliche begrenzte Verallgemeinerung mit Reichweite und qualitativer Stärke wie stark, mittel oder schwach. Ersetze universelle Aussagen nur bei vertretbarer Herkunft durch Populations- oder Anteilsbereiche.
6. Veröffentliche Entscheidungsfolge und nächste stärkende oder herausfordernde Beobachtung. Benenne Unterstützung für Handlung, Überwachung oder weitere Stichproben.
7. Veröffentliche aktuellen Schluss und beobachtbare Umkehrbedingung. Bei wesentlich verzerrter, dünner oder unpassender Stichprobe setze aus oder bewahre Vorläufigkeit statt Extrapolation.

## Public output contract

Liefere `observations`, `induction_type`, `sample_basis`, `generalization`, `scope_limit`, `counterexample_risk`, `counterexample_search`, `strength`, `decision_consequence` und `flip_condition`. Trenne beobachtete Fälle von breiterer Behauptung. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**; Verallgemeinerungen sind gewöhnlich erschlossen, nicht direkt geprüft.

## Evidence and uncertainty rules

Stichprobengröße allein belegt keine Repräsentativität. Prüfe Auswahl, Abdeckung, Ausfälle, Messung, Untergruppenbalance und Zeitrelevanz. Ein Gegenbeispiel begrenzt universelle Aussagen, ohne Gegenrichtung zu beweisen. Nutze dieselbe Beobachtung nicht als unabhängige Unterstützung und Gegenbeispieltest. Ohne Stichprobengrundlage oder Zielumfang schwäche ab oder setze aus.

## Stop conditions

Stoppe mit einer blockierenden Frage bei unkenntlicher Zielpopulation oder Auswahl und handlungsändernder Reichweite. Setze aus bei wesentlicher Unrepräsentativität, designüberschreitender Kausalbehauptung oder offenem entscheidendem Gegenbeispielrisiko. Stoppe bei strikter Regel, Konkurrenzhypothesendiagnose oder Quellenqualitätsvergleich.

## Complement handoff

Übergib an `evidence-hierarchy`, wenn die Restfrage das angemessene Gewicht von Stichprobe oder Studiendesign ist. Übermittle Stichprobengrundlage, Verallgemeinerung, Umfangsgrenze und Hauptrisiko von Gegenbeispielen. Wiederhole kein Verallgemeinerungsverfahren.
