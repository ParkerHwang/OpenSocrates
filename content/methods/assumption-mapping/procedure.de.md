## Purpose

Nutze dieses Verfahren, um die Überzeugungen hinter einer Idee sichtbar zu machen, Wichtigkeit von Belegen zu trennen und den kleinsten sicheren Test für entscheidungsrelevante Annahmen auszuwählen. Es erzeugt eine priorisierte Lernübersicht, kein Wahrheitsurteil.

## Use when

Nutze es vor einer Festlegung auf eine Produktidee, betriebliche Änderung, Forschungsrichtung oder ein Urteil, das auf unsicheren Überzeugungen beruht. Es hilft bei Uneinigkeit darüber, was wahr sein muss, ungleichmäßiger Beleglage oder benötigter Testreihenfolge. Besonders nützlich ist es vor einem umkehrbaren Experiment oder Ressourceneinsatz, solange sich die Entscheidung sicher ändern lässt.

## Do not use when

Nutze es nicht für mechanische Aufgaben, bindende Regeln ohne Ermessensspielraum oder irreversible Entscheidungen. Lege private oder sensible Annahmen nicht bloß, um eine Karte zu vervollständigen; beschränke das Ergebnis auf autorisierte Informationen. Erfinde keinen Test ohne unterscheidbaren beobachtbaren Ausgang oder bei rechtlichen, sicherheitsbezogenen, Datenschutz- oder wesentlichen betrieblichen Risiken. Ist ein Marktexperiment nötig, übergib die ausgewählte Annahme an `lean-startup`, statt die Karte zum vollständigen Bericht auszubauen.

## Inputs to establish

Kläre Entscheidungsfrage, gewünschtes Ergebnis, vorgeschlagene Handlung und wesentliche Änderungsbedingungen. Sammle Annahmen als prüfbare Aussagen und ordne sie Erwünschtheit, wirtschaftlicher Tragfähigkeit, Machbarkeit oder einem anderen benannten Bereich zu. Erfasse jeweils Quelle, Nutzerbeobachtung, Berechnung oder Schlussfolgerung. Definiere kleinste sichere Tests, Einschränkungen, Verantwortlichen, Beobachtungszeitraum und Entscheidungsregel. Stelle höchstens zwei kurze Fragen, nur wenn die Antwort Risikomenge oder Testsicherheit ändern könnte; kennzeichne das Fehlende sonst als angenommen.

## Procedure

1. **Veröffentliche den Rahmen.** Halte Entscheidungsfrage, beabsichtigtes Ergebnis, Umfang und Entscheidungsgrenze kompakt fest. Kennzeichne Grenzangaben als nutzerseitig angegeben, quellengeprüft, erschlossen oder angenommen. **Sichtbare Ausgabe/Zustandsänderung:** Rahmenzustand.
2. **Veröffentliche das Annahmenregister.** Formuliere jede Überzeugung als durch Beobachtung stützbare, schwächbare oder ungeklärt bleibende Aussage. Ergänze Bereich und Konsequenz ihrer Falschheit. **Sichtbare Ausgabe/Zustandsänderung:** gekennzeichnetes Annahmenregister.
3. **Veröffentliche die beiden Achsen.** Ordne jede Annahme einer ordinalen Wichtigkeitsachse und einer Belegstatusachse zu. Verwende hoch, mittel oder niedrig nur begründet sowie `verified`, `computed`, `inferred`, `assumed`, `unverified` oder `conflicted` für Unterstützung. **Sichtbare Ausgabe/Zustandsänderung:** Wichtigkeits-/Belegkarte.
4. **Veröffentliche die riskanteste Menge.** Wähle Annahmen, deren Scheitern das Ergebnis wesentlich ändern würde und deren Unterstützung am schwächsten oder widersprüchlich ist. Begründe jede Auswahl, bewahre ununterscheidbare Gleichstände und erfasse offene Unsicherheit. **Sichtbare Ausgabe/Zustandsänderung:** Risikomenge und Unsicherheit.
5. **Veröffentliche eine sichere Testkarte.** Benenne für jede ausgewählte Annahme den günstigsten umkehrbaren Test, beobachtbares Signal, Beobachtungszeitraum, Verantwortlichen und Entscheidungsregel. Ergänze eine Stopp- oder Rückabwicklungsgrenze. **Sichtbare Ausgabe/Zustandsänderung:** sichere Testkarte oder Aussetzung.
6. **Veröffentliche die Entscheidungskarte.** Gib an, was stützende, schwächende, widersprüchliche oder fehlende Signale ändern würden: fortfahren, überarbeiten, Belege suchen oder aussetzen. **Sichtbare Ausgabe/Zustandsänderung:** vorläufiger Schluss und Umkehrbedingungen.

## Public output contract

Liefere kartenfähige Felder `assumptions`, `importance_evidence_axes`, `riskiest_set`, `next_test` und `flip_condition`. Bewahre je Annahme Bereich, Konsequenz und Belegstatus. `next_test` enthält beobachtbares Signal, sichere Grenze und Entscheidungsregel; er darf keinen Beweis der gesamten Idee versprechen. Die eingeklappte Ausgabe enthält höchstens drei wesentliche Annahmen und zwei ungeklärte Unsicherheiten, weitere Äste verbleiben in der Ablaufspur. Fehlen entscheidende Annahme oder Testgrenze, kennzeichne Aussetzung oder Vorläufigkeit.

## Evidence and uncertainty rules

Eine Annahme ist nicht durch Wiederholung, Wichtigkeit oder Plausibilität eine Tatsache. Verknüpfe `verified` nach Möglichkeit mit Quellen; zeige Eingaben für `computed`; kennzeichne abgeleitete Überlegungen als `inferred`, übernommene Prämissen als `assumed`, fehlende Prüfungen als `unverified` und Uneinigkeit als `conflicted`. Ordinale Wichtigkeit verlangt genannte Konsequenz oder Entscheidungsabhängigkeit. Erfinde keine Wahrscheinlichkeiten, Stichprobengrößen oder Ergebnisse. Ein Testsignal aktualisiert die Annahme nur im geprüften Kontext; Verallgemeinerung benötigt weitere Unterstützung.

## Stop conditions

Setze aus, wenn Entscheidungsfrage, wesentliche Konsequenz oder Offenlegungsberechtigung fehlen. Setze bei zwei gleichrangigen Annahmen aus, wenn fehlende Belege die Testfolge ändern könnten. Stoppe vor unsicheren, rechtswidrigen, irreversiblen oder nicht sinnvoll beobachtbaren Tests. Bei mechanischen Aufgaben oder Entscheidungen ohne Ermessen beende das Verfahren zugunsten direkter oder regelgebundener Bearbeitung. Mache eine leere Karte nicht zur Empfehlung.

## Complement handoff

Übergib an `lean-startup`, wenn die veröffentlichte riskanteste Annahme eine Markt-, Produkt-, Wert-, Wachstums- oder Umsatzhypothese mit minimalem Lernexperiment ist. Übermittle nur Aussage, Bereich, Konsequenz, Belegstatus, ausgewähltes sicheres Signal und Entscheidungsregel. Wiederhole nicht die ganze Karte und behaupte keinen bereits durchgeführten Test. Nutze `value-of-information` gesondert, wenn vorrangig fraglich ist, ob zusätzliche Recherche ihre Kosten wert ist.
