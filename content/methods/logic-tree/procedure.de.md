## Purpose

Zerlegen Sie eine breite Diagnose-, Planungs- oder Abdeckungsfrage in eine Hierarchie mit klar voneinander abgegrenzten, insgesamt ausreichenden Zweigen und handlungsfähigen Blättern. Wählen Sie pro Ebene eine Zerlegungsachse, trennen Sie Warum- und Wie-Bäume und ordnen Sie jedem Endzweig eine Prüfung oder nächste Handlung zu. Der Baum strukturiert die Suche; er beweist nicht die Wahrheit jedes Zweigs.

## Use when

Bei breitem Problem, unklaren Ursachen, erforderlicher Planabdeckung oder einer Warum-, Wie- beziehungsweise Was-Frage mit Bedarf an umfassender Struktur. Geeignet für Diagnose, Risikoabdeckung, Anforderungen und Lösungssuche, wenn Überschneidungen Verantwortlichkeit doppeln oder Arbeit auslassen würden.

## Do not use when

Nicht bei eng gekoppelten Rückkopplungen, die eine Hierarchie irreführend darstellen würde, oder ausreichender einfacher Liste beziehungsweise Berechnung. Mischen Sie Ursachen und Lösungen nicht auf derselben Ebene, verdecken Sie materielle Lücken nicht mit „Sonstiges“ und teilen Sie keinen Zweig weiter, sobald seine nächste Handlung klar ist.

## Inputs to establish

Klären Sie Wurzelfrage, Baumtyp (`why`, `how` oder `what`), Erfolgsmaß, Reichweite, bekannte Fakten und verfügbare Prüfungen. Wählen und begründen Sie die erste Zerlegungsachse. Höchstens eine entscheidende Frage, wenn Wurzel oder Typ die Analyse verändern; sonst eine begrenzte Wurzel angeben.

## Procedure

1. Veröffentlichen Sie messbare Wurzelfrage und Baumtyp samt Reichweite und Erfolgsmaß als sichtbare Ausgangsstruktur.
2. Veröffentlichen Sie erste Zweige anhand einer benannten einheitlichen Achse. Kennzeichnen Sie jeden als beobachtet, abgeleitet oder noch zu prüfenden Kandidaten.
3. Veröffentlichen Sie weitere Ebenen nur bei handlungs- oder testrelevanter Verfeinerung. Zeigen Sie auf jeder Ebene gegenseitigen Ausschluss und Abdeckungsprüfung als Zustandsänderung.
4. Veröffentlichen Sie zu jedem Blatt eine Verifikationsmethode, Datenanfrage, Verantwortlichkeit oder nächste Handlung. Abstrakte Blätter sind nicht abschließend: Baum offenhalten oder Wurzel eingrenzen.
5. Veröffentlichen Sie entfernte Zweige samt Grund, etwa Gegenbeleg, außerhalb der Reichweite oder doppelte Abdeckung. Unbequeme Zweige nicht allein deshalb löschen.
6. Veröffentlichen Sie Priorität nach Wesentlichkeit, Evidenz und Handlungsfähigkeit statt erfundener Zahlenpräzision. Markieren Sie Zweige für separate Kausal- oder Evidenzmethoden.
7. Veröffentlichen Sie fertigen Baum, Abdeckungslücken und beobachtbare Bedingung für eine Urteilsänderung. Ist ein kritischer Zweig weder testbar noch begrenzt, Urteil zurückstellen oder eine blockierende Frage stellen.

## Public output contract

Liefern Sie `root_question`, `tree_type`, `decomposition_axis`, `mutually_clear_branches`, `branches`, `leaf_tests`, `leaves_with_tests`, `pruned_branches_and_reasons`, `coverage_gaps`, `priority_order` und `flip_condition`. Das Ergebnis zeigt klare Abgrenzung, insgesamt relevante Abdeckung und ausführbare Blätter. Kartengründe mit **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted** kennzeichnen. Der Baum selbst beweist keine kausale Behauptung.

## Evidence and uncertainty rules

ME und CE sind getrennte Prüfungen: Überschneidungsfreiheit impliziert keine Abdeckung und umgekehrt. Vertraute Formeln sind Kandidaten, bis ihre Voraussetzungen zum Bereich passen. Jedes Blatt braucht identifizierbare Evidenz oder Test; unbelegte Zweige bleiben Hypothesen. Konflikte oder entscheidungsrelevante fehlende Zweige offenlegen; Schluss zurückstellen oder abschwächen.

## Stop conditions

Stoppen und eine blockierende Frage stellen, wenn Wurzel oder Baumtyp nicht eingrenzbar sind und Alternativen unterschiedliche Arbeit bedeuten. Bei unprüfbarer wesentlicher Abdeckungslücke oder irreführender hierarchischer Darstellung abhängiger Zweige zurückstellen. Stoppen, sobald Blätter klare Aktionen haben und Restarbeit einer Kausal-, Evidenz- oder Entscheidungsmethode gehört.

## Complement handoff

An `root-cause-analysis` übergeben, wenn ein ausgewählter Zweig wiederkehrendes Versagen betrifft und eine Ursachenkette statt weiterer Zerlegung braucht. Wurzel, Zweig, Evidenzlücken und Blatttests übermitteln. Unbeteiligte Zweige nicht neu aufbauen.
