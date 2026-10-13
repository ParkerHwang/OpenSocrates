## Purpose

Nutze dieses Verfahren, um festzustellen, ob ein Schluss notwendig aus ausdrücklichen Prämissen und einer Regel folgt. Trenne dabei Gültigkeit von Prämissenwahrheit. Es vereinheitlicht das Argument, legt verborgene Prämissen offen, prüft die Form und benennt die Prämisse, deren Scheitern den Schluss entkräften würde. Gültige Form allein macht ein reales Argument nicht schlüssig und wahrheitsbasiert.

## Use when

Nutze es für Regelanwendung, formale Argumentprüfung, Vertrags- oder Richtlinienauslegung und Behauptungen notwendiger Folgen genannter Bedingungen. Es passt bei ausdrücklichen Prämissen und Fragen logischer Folgerung statt empirischer Verallgemeinerung.

## Do not use when

Nutze es nicht bei unsicheren Prämissen, wenn eigentlich Schätzung, Diagnose, Verallgemeinerung oder Vertrauensaktualisierung benötigt wird. Verwechsle wahrscheinliche nicht mit bewiesenen Prämissen, `P(E|H)` nicht mit Folgerung und wahre Schlüsse nicht mit gültiger Form. Erfinde keine Regel ohne Nutzer- oder maßgebliche Quellenvorgabe.

## Inputs to establish

Kläre vorgeschlagenen Schluss, Prämissen, maßgebliche Regel oder Implikation, Geltungsbereich, Definitionen und Prämissenquellen. Kennzeichne verborgene Prämissen ausdrücklich und unterscheide geforderte Gültigkeit, Schlüssigkeit oder bloß bedingtes Ergebnis. Stelle höchstens eine entscheidende Frage, wenn fehlende Regel oder Prämisse die Form ändert; benenne sonst die bedingte Annahme.

## Procedure

1. Veröffentliche Schluss und standardisiere Argument als nummerierte Prämissen, Regel und Schluss. Markiere verborgene Prämissen als `[implicit]`; dadurch entsteht der sichtbare Formalisierungszustand.
2. Veröffentliche die Form, etwa Modus ponens, Modus tollens, gültigen Syllogismus, Bejahung des Konsequens oder Verneinung des Antezedens. Ohne passende bekannte Form zeige strukturelle Beziehung statt erzwungenem Etikett.
3. Veröffentliche Gültigkeitsurteil: Muss bei wahren Prämissen der Schluss wahr sein? Benenne bei ungültiger Form ein Gegenbeispielmuster.
4. Veröffentliche Prämissenstatustabelle mit Quelle, Umfang und Belegstatus jeder Prämisse und Regel. Trenne gültige Form von schlüssigem Argument; das aktualisiert das Urteil sichtbar.
5. Veröffentliche entkräftende Prämisse oder Regelbedingung. Benenne exakt, was die Folgerung brechen würde, und trenne Regelausnahme von falscher Prämisse.
6. Veröffentliche Schluss als schlüssig, gültig-aber-nicht-schlüssig, ungültig oder bedingt samt kleinster fehlender Prüfung. Plausibilität rechtfertigt keine Hochstufung.
7. Veröffentliche aktuellen Schluss und beobachtbare Umkehrbedingung. Fehlen entscheidende Prämisse oder Regel, setze die reale Behauptung aus und bewahre die bedingte Implikation.

## Public output contract

Liefere `premises`, `hidden_premises`, `rule`, `rule_or_form`, `conclusion`, `validity_verdict`, `premise_status`, `invalidating_premise`, `soundness_verdict` und `flip_condition`. Gib Formgültigkeit und Prämissenunterstützung getrennt an, statt sie zu einem Vertrauensetikett zu verschmelzen. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**.

## Evidence and uncertainty rules

Gültigkeit ist strukturell und prüft keine Prämissen. Eine Quelle kann eine Prämisse stützen, ohne die Regelanwendbarkeit im Umfang zu beweisen. Verborgene Prämissen bleiben bis zur Unterstützung Annahmen. Bewahre bei strittigen Prämissen den bedingten Schluss und schwäche angewandte Folgerung ab oder setze sie aus. Ein einzelner wahrer Schluss validiert keine ungültige Inferenz.

## Stop conditions

Stoppe mit einer blockierenden Frage, wenn maßgebliche Regel oder Schluss fehlen und mögliche Formen andere Ergebnisse ergeben. Setze bei ungeprüfter wesentlicher Prämisse aus, berichte aber eine vorhandene gültige Bedingungsfolge. Stoppe bei probabilistischer, kausaler oder vergleichender Aufgabe statt logischer Folgerung.

## Complement handoff

Übergib an `conceptual-analysis`, wenn formaler Streit von mehrdeutigem Begriff oder Umfang abhängt. Übermittle standardisierte Prämissen, strittigen Begriff und betroffene Regel. Die Ergänzung klärt den Begriff ohne erneutes Gültigkeitsurteil.
