## Purpose

Nutze dieses Verfahren, um Vertrauen in konkurrierende Hypothesen bei neuen Belegen zu aktualisieren, sofern Grundlage des Priors und Likelihood-Richtung verantwortbar angegeben werden können. Es macht Basisraten, Belegwirkung, Posterioränderung und Sensitivität sichtbar. Exakte Wahrscheinlichkeiten sind optional; ohne Herkunft numerischer Eingaben ist eine ordinale Aktualisierung ehrlich. Ein präziser Posterior muss jedoch Eingaben und Normierung zeigen.

## Use when

Nutze es für diagnostische Signale, Testdeutung, aufeinanderfolgende Belege, Risikoschätzungen und Entscheidungen, bei denen eine neue Beobachtung das Vertrauen in konkurrierende Hypothesen ändern sollte. Es passt zur Wahrscheinlichkeit einer Hypothese nach Belegen, besonders bei drohender Vernachlässigung der Basisrate.

## Do not use when

Nutze es nicht ohne vertretbare Priorgrundlage oder wenigstens ordinale Angabe, wie sich Belege zwischen Hypothesen unterscheiden, sowie bei strikter Regelanwendung. Verwechsle `P(E|H)` nicht mit `P(H|E)`, verwende dieselben Belege nicht als unabhängige Aktualisierungen und erfinde keine exakten Prozentsätze zur Erzeugung falscher Sicherheit.

## Inputs to establish

Kläre einander ausschließende, hinreichend abdeckende Hypothesen, aktuelle Entscheidung, Prior- oder Basisratengrundlage, neue Belege, Likelihood-Richtung oder -Werte je Hypothese, Abhängigkeiten zwischen Belegen und Handlungsschwelle. Stelle höchstens zwei entscheidende Fragen, wenn fehlender Prior oder fehlende Belegdefinition die Aktualisierung ändern; nutze sonst einen gekennzeichneten ordinalen Prior.

## Procedure

1. Veröffentliche konkurrierende Hypothesen und Entscheidungsschwelle. Benenne den Aktualisierungsgegenstand und kennzeichne Hypothesen als nutzerseitig angegeben, quellenbelegt oder vorläufig; so entsteht der sichtbare Aktualisierungszustand.
2. Veröffentliche die Priorgrundlage je Hypothese: Basisratenquelle, Referenzpopulation oder begrenzten ordinalen Prior. Zeige bei unbekannten Priors Unsicherheit, statt eine bequeme Zahl zu wählen.
3. Veröffentliche jeden Beleg und seine Richtung für sämtliche Hypothesen: stützend, schwächend oder weitgehend neutral. Prüfe Unabhängigkeit beziehungsweise teilweise Wiederverwendung desselben Signals.
4. Veröffentliche Posterioränderungen mit exakter Rechnung nur bei vertretbaren Eingaben; gib sonst qualitative Aktualisierung oder Bandbreite an. Zeige die Normierung konkurrierender Hypothesen und bewahre die Richtung vom Prior zum Posterior.
5. Veröffentliche Sensitivität gegenüber Prior- und Likelihood-Annahmen. Benenne Werte oder Richtungsänderungen, die Rangfolge oder Handlungsschwelle umkehren würden.
6. Veröffentliche derzeit führende Hypothese, Posteriorstatus und nächste entscheidungsverbessernde Belege. Halte eine niedriger eingestufte, aber plausible Hypothese sichtbar, wenn sie wesentlich bleibt.
7. Veröffentliche aktualisierten Schluss und beobachtbare Bedingung für eine Urteilsänderung. Fehlen Prior oder Likelihood-Richtung, setze aus oder bewahre Vorläufigkeit, statt einen erfundenen Posterior anzugeben.

## Public output contract

Liefere `hypotheses`, `prior_basis`, `evidence_direction`, `posterior_change`, `normalization_or_update_range`, `sensitivity`, `decision_threshold` und `flip_condition`. Unterscheide in der Karte berechneten Posterior von ordinaler oder erschlossener Aktualisierung. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**; eine numerische Basisrate ist dadurch nicht automatisch geprüft.

## Evidence and uncertainty rules

Der Prior benötigt eine vertretbare Basisrate, fachliche Schätzung mit Herkunft oder einen früheren Posterior. Die Likelihood ist `P(E|H)`, nicht die Hypothesenwahrscheinlichkeit nach Belegen. Aktualisiere nicht zweimal anhand abhängiger Belege. Zeige widersprüchliche glaubwürdige Eingaben und schwäche das Ergebnis ab oder setze es aus. Überschreitet die Sensitivität die Handlungsschwelle, kennzeichne die Entscheidung als fragil.

## Stop conditions

Stoppe mit einer blockierenden Frage, wenn Hypothesenmenge oder Belegdefinition fehlen und andere Festlegungen die Handlung umkehren würden. Setze aus ohne vertretbaren Prior oder Likelihood-Richtung beziehungsweise bei Abhängigkeit, die vertrauenswürdige Aktualisierung verhindert. Stoppe, wenn eigentlich strikte Regelanwendung, Erklärungssuche oder Quellenqualitätsrangfolge gefragt ist.

## Complement handoff

Übergib an `abduction`, wenn hauptsächlich Erklärungen erzeugt und verglichen werden müssen, statt definierte Hypothesen zu aktualisieren. Übermittle beobachtete Belege, Kandidatenhypothesen und unterscheidenden Test. Die Ergänzung soll die Posteriorberechnung nicht wiederholen.
