## Purpose

Prüfen Sie, ob eine Klassifikation oder Zerlegung auf derselben Ebene gegenseitig ausschließend und gemeinsam vollständig ist. Fixieren Sie eine Klassifikationsachse, testen Sie Überschneidungen und Lücken getrennt und wahren Sie einheitliche Granularität. Ergebnis ist eine begründbare Regel mit bekannten Grenzfällen, kein Versprechen natürlich sauberer Kategorien in der Wirklichkeit.

## Use when

Wenn Kategorien, Verantwortungsbereiche, Optionen, Anforderungen, Ursachen oder Problembaumzweige wesentliche Fälle doppeln oder auslassen. Als Prüfung vorhandener Klassifikationen oder gezielte Kontrolle innerhalb eines Logikbaums beziehungsweise einer Führungsstruktur geeignet. Nutzen Sie es, wenn die Klassifikationsregel selbst statt einer Faktenquelle den Entscheidungsengpass bildet.

## Do not use when

Nicht wenn natürliche Überschneidung Gegenstand der Untersuchung ist, Kategorien bewusst verschiedene Achsen repräsentieren oder eine verbindliche Taxonomie lediglich anzuwenden ist. Alter, Geografie, Absicht und Prozessphase nicht auf derselben Ebene mischen. Große fehlende Klassen nicht in „Sonstiges“ verstecken; keine falsche Ausschließlichkeit bei echter Mehrfachzuordnung erzwingen.

## Inputs to establish

Klären Sie Grundgesamtheit, Entscheidungszweck, Kandidatenkategorien, vorgeschlagene einzige Achse, Einschluss- und Ausschlussregel sowie bekannte Grenzfälle. Benennen Sie Einfach- oder Mehrfachzuordnung. Höchstens eine Frage bei materiell unklarer Grundgesamtheit oder Zweck; sonst begrenzte Grundgesamtheit angeben.

## Procedure

1. Veröffentlichen Sie Grundgesamtheit, Zweck und eine Klassifikationsachse in einem Satz. Das fixiert den sichtbaren Klassifikationszustand und verhindert gemischte Kriterien.
2. Veröffentlichen Sie Kandidatenkategorien mit jeweils einer Einschluss- und Ausschlussregel. Grenzen als ausdrücklich, abgeleitet oder ungeprüft markieren.
3. Veröffentlichen Sie den Ausschließlichkeitstest mit plausiblen Fällen, die in zwei Kategorien passen. Kategorien zusammenführen, neu schneiden oder Mehrfachzuordnung ausdrücklich erlauben; jede Änderung dokumentieren.
4. Veröffentlichen Sie die Vollständigkeitsprüfung mit Randfällen und bekannten Beobachtungen. Kategorie nur bei relevantem fehlendem Fall ergänzen; andernfalls Grundgesamtheit eingrenzen und Ausschluss offenlegen.
5. Veröffentlichen Sie eine Granularitätsprüfung: Abstraktion, Größe und Entscheidungsnutzen vergleichen. Versteckte Unterkategorien oder nicht handlungsfähige zu breite Kategorien überarbeiten.
6. Veröffentlichen Sie Grenzfälle, endgültige Regel und absichtlich offene Überschneidungen. Kein vages „Sonstiges“ für wesentliche Anteile verwenden.
7. Veröffentlichen Sie klassifiziertes Ergebnis, Überschneidungs-/Lückenurteil und beobachtbare Umkehrbedingung. Bei ungeeigneter Achse oder nicht klassifizierbarem wichtigem Fall zurückstellen statt Zuordnung erzwingen.

## Public output contract

Liefern Sie `classification_universe`, `classification_rule`, `classification_axis`, `categories`, `inclusion_rules`, `exclusion_rules`, `overlap_gap_check`, `overlap_check`, `coverage_check`, `granularity_check`, `boundary_cases` und `flip_condition`. Unterscheiden Sie ME und CE sowie Einfach- und Mehrfachzuordnung. Gründe als **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted** kennzeichnen. Kategorien beweisen keine Häufigkeit.

## Evidence and uncertainty rules

ME und CE sind logische Abdeckungsprüfungen, kein empirischer Nutzennachweis. Beispiele zeigen mögliche Überschneidung oder Lücke ohne deren Häufigkeit zu belegen. Trennen Sie quellenbasierte Beobachtungen und Gestaltungsentscheidungen. Bei fehlender wesentlicher Kategorie, strittigem offenem Fall oder entscheidungswirksamer Achse Ergebnis vorläufig oder zurückgestellt kennzeichnen.

## Stop conditions

Stoppen und eine blockierende Frage stellen, wenn Grundgesamtheit oder Zweck nicht begrenzt werden können. Zurückstellen, wenn die Achse wesentliche Fälle nur mit irreführender Überschneidung abbildet oder fehlende Kategorien die Entscheidung ändern. Stoppen, sobald ME/CE in erforderlicher Reichweite erfüllt sind und Restarbeit strukturelle Zerlegung oder Optionsvergleich ist.

## Complement handoff

An `logic-tree` übergeben, wenn validierte Kategorien die erste Ebene einer breiteren Diagnose oder Planung bilden und rekursive Zweige samt Blatttests brauchen. Grundgesamtheit, Achse, Kategorien, Grenzfälle und Abdeckungsurteil übermitteln. MECE-Prüfungen derselben Ebene nicht wiederholen.
