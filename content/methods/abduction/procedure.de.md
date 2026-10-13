## Purpose

Nutze dieses Verfahren, um konkurrierende Erklärungen für eine beobachtete oder überraschende Tatsache zu vergleichen und die derzeit beste Erklärung auszuwählen, ohne sie als bewiesen darzustellen. Es verlangt mindestens zwei noch plausible Kandidaten, bewertet Erklärungspassung und Risiken und benennt Belege, die zwischen ihnen unterscheiden würden. Das Ergebnis ist eine vorläufige Diagnose mit einem konkreten nächsten Prüfschritt, keine Erlaubnis, eine bevorzugte Geschichte nachträglich passend zu machen.

## Use when

Nutze es zur Fehlersuche, Diagnose, Untersuchung und Deutung von Auffälligkeiten sowie dann, wenn mehrere Ursachen dieselbe Beobachtung erklären könnten. Es passt zu unvollständigen Informationen und Fragen danach, was wahrscheinlich geschieht oder warum ein unerwartetes Ergebnis eintrat. Nutze es, wenn keine deduktive Regel das Ergebnis bereits entscheidet.

## Do not use when

Nutze es nicht, wenn ausdrückliche Regeln und gesicherte Prämissen den Schluss erzwingen oder keine Beobachtung die Erklärungen unterscheiden kann. Behandle einen einzelnen Kandidaten nicht als Erklärungsmenge, bewerte Geschichten nicht mit erfundener Präzision und verwechsle fehlende Widerlegung nicht mit Bestätigung. Vermeide kausale Gewissheit, wenn die Kandidaten lediglich beschreibende Deutungen sind.

## Inputs to establish

Kläre die überraschende Beobachtung, den erwarteten Ausgangszustand, die betroffene Entscheidung oder Diagnose, bekannte Tatsachen, plausible Erklärungen und verfügbare Tests oder Quellen. Kennzeichne jeden Kandidaten als Ursache, Mechanismus, Datenfehler oder Erklärung durch den Geltungsbereich. Stelle höchstens eine entscheidende Frage, wenn Beobachtung oder Entscheidungsziel unklar sind; arbeite sonst mit ausdrücklich benannten Annahmen weiter.

## Procedure

1. Veröffentliche die erklärungsbedürftige Beobachtung und den Ausgangszustand, von dem sie abweicht. Kennzeichne geprüfte Tatsachen, Nutzerberichte und Annahmen; dadurch entsteht der sichtbare Auffälligkeitszustand.
2. Veröffentliche mindestens zwei Kandidatenerklärungen samt vorhergesagten Beobachtungen und Geltungsbereich. Ergänze bei Plausibilität Mess-, Auswahl- oder Berichtsfehler, statt die erste inhaltliche Geschichte zur Vorgabe zu machen.
3. Veröffentliche einen qualitativen Vergleich von Erklärungspassung, Abdeckung, Einfachheit, Übereinstimmung mit gesichertem Wissen und Prüfbarkeit. Nutze ordinale Angaben wie stark, mittel, schwach oder unbekannt; erfinde keine Wahrscheinlichkeiten.
4. Veröffentliche unterscheidende Belege: die Beobachtung, das Experiment oder die Quelle, die führende Kandidaten auseinanderhalten würden. Gib an, welches Ergebnis jeden Kandidaten stärkt, schwächt oder unverändert lässt.
5. Veröffentliche die derzeit beste Erklärung, ihren Vorsprung und ihren vorläufigen Status. Halte Alternativen sichtbar und kennzeichne das Ergebnis als Diagnose, Arbeitshypothese oder ungeklärte Kandidatenmenge.
6. Veröffentliche die nächste Prüfhandlung und den wesentlichen Fehlermodus, einschließlich dessen, was die Erklärung widerlegen oder eine unzuverlässige Belegverknüpfung zeigen würde.
7. Veröffentliche aktuellen Schluss, Kandidatenmenge und beobachtbare Bedingung für eine Urteilsänderung. Fehlt unterscheidende Unterstützung für alle Kandidaten oder eine entscheidende Beobachtung, setze das Ergebnis aus, statt die anschaulichste Geschichte auszuwählen.

## Public output contract

Liefere `observation`, `candidate_explanations`, `comparison_criteria`, `discriminating_evidence`, `provisional_best_explanation`, `next_test` und `flip_condition`. Bei vorläufigen Ergebnissen muss die erste Zeile „derzeit beste Erklärung“ oder eine gleichwertige Formulierung enthalten. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**; die Passung eines Kandidaten ist eine Schlussfolgerung, kein unmittelbarer Beweis.

## Evidence and uncertainty rules

Eine überraschende Tatsache kann eine Hypothese anregen, aber ihre Ursache nicht feststellen. Verlange unabhängige oder unterscheidende Unterstützung, bevor du einen Kandidaten höher einstufst. Zähle dieselbe Beobachtung nicht unter mehreren Kriterien doppelt. Bei gleicher Passung melde ungeklärte Konkurrenz. Ist ein wesentlicher Test nicht verfügbar, bleibt die beste Erklärung vorläufig oder ausgesetzt; benenne die fehlenden Belege.

## Stop conditions

Stoppe und stelle eine blockierende Frage, wenn Beobachtung oder Entscheidungsziel zu vage für Kandidatenerklärungen sind. Setze das Ergebnis aus, wenn nur ein Kandidat, keine prüfbare Konsequenz oder keine entscheidenden Belege vorliegen. Stoppe, wenn ausdrückliche Prämissen das Ergebnis erzwingen oder nur noch Quellenqualität, formale Gültigkeit oder Optionenvergleich zu bearbeiten sind.

## Complement handoff

Übergib an `value-of-information`, wenn die Hauptentscheidung darin liegt, unterscheidende Informationen zu kaufen, zu sammeln oder auf sie zu warten. Übermittle Kandidatenmenge, entscheidungsändernde Belege sowie Kosten oder Verzögerung des nächsten Tests. Die Ergänzung soll den Erklärungsvergleich nicht wiederholen.
