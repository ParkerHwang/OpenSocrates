## Purpose

Nutze dieses Verfahren, um sichtbar zu machen, wie Behauptungen, Begründungen, Einwände und Entkräftungen einen Schluss stützen oder schwächen. Es erstellt eine überprüfbare Argumentkarte statt einer freien Mindmap; gemeinsame Prämissen, unbelegte Verknüpfungen und ungeklärte Einwände bleiben sichtbar. Es kann Streitfragen vor einer Entscheidung klären, macht eine Prämisse aber nicht dadurch wahr, dass sie übersichtlich angeordnet wird.

## Use when

Nutze es, wenn ein politisches, rechtliches, strategisches, wissenschaftliches oder produktbezogenes Argument verschachtelte Behauptungen enthält und unklar ist, welche Belege welchen Schluss stützen. Es passt zu Streitfragen mit mehreren Einwänden, Entkräftungen oder gemeinsamen Annahmen. Nutze es, wenn Unterstützungs- und Angriffsbeziehungen entwirrt und anschließend Schlussstärke oder Aussetzungsbedingung angegeben werden sollen.

## Do not use when

Nutze es nicht für einfache Listen, direkte Berechnungen oder reine Quellenqualitätsfragen. Stelle Assoziation, zeitliche Folge oder Themenähnlichkeit nicht als logische Unterstützung dar. Eine vollständige Karte beweist keine tragfähige Schlussfolgerung. Verberge Wertentscheidungen nicht in neutral wirkenden Prämissen.

## Inputs to establish

Kläre Zielschluss, Entscheidung oder Frage, relevanten Geltungsbereich, unmittelbare Begründungen, gemeinsame Prämissen, Einwände, Entkräftungen und verfügbare Quellen. Kennzeichne jedes Element als Tatsache, Regel, Schlussfolgerung, Präferenz oder Annahme. Stelle höchstens zwei entscheidende Fragen, wenn fehlende Behauptungen oder Grenzen die Karte ändern würden; markiere sonst die Lücke und fahre fort.

## Procedure

1. Veröffentliche den obersten Schluss und die Entscheidung, die er stützen soll. Kennzeichne ihn als gestützt, vorläufig, widersprüchlich oder ausgesetzt; das erzeugt den sichtbaren Argumentzustand.
2. Veröffentliche unmittelbar stützende Prämissen und unterscheide sie von gemeinsam erforderlichen Prämissen. Zeichne nur ausdrücklich benannte Unterstützungsverknüpfungen und markiere jede als angegeben, erschlossen oder ungeprüft.
3. Veröffentliche Unterbegründungen unter jeder Prämisse und bewahre die Hierarchie zwischen Behauptungen und Gründen. Füge verfügbare Quellen- oder Berechnungsreferenzen bei und erfasse unbelegte Verbindungen als Lücken.
4. Veröffentliche Einwände als eigene Angriffsäste. Ergänze Entkräftungen nur, wenn sie auf die tatsächliche Aussage des Einwands antworten. Bleiben dessen Belege und Geltungsbereich unverändert, gilt der Einwand als ungeklärt.
5. Veröffentliche verborgene oder gemeinsame Prämissen und prüfe, ob ihre jeweilige Entfernung den Schluss ändert. Dieser Zustandswechsel identifiziert die kleinste wesentliche Schwäche, statt jeden Satz gleich zu zählen.
6. Veröffentliche ein Kartenurteil: stärkste gestützte Verbindung, schwächste Verbindung, ungeklärter Einwand sowie redundante oder irrelevante Äste. Unterscheide Kartenvollständigkeit von Prämissenwahrheit und Schlussgültigkeit.
7. Veröffentliche aktuellen Belegstatus des Schlusses und eine beobachtbare Bedingung für eine Urteilsänderung. Fehlt eine wesentliche Prämisse oder bleibt ein entscheidender Einwand ungeklärt, schwäche den Schluss ab oder setze ihn aus, statt das Argument stillschweigend zu reparieren.

## Public output contract

Liefere `claim_ground_objection_map`, `top_level_conclusion`, `direct_grounds`, `shared_premises`, `subgrounds`, `objections`, `rebuttals`, `unsupported_links`, `map_verdict` und `flip_condition`. Zeige eine kompakte Behauptungs-Begründungs-Einwandskarte, kein privates Denkprotokoll. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**. Nimm nur wesentliche Äste in die Karte auf und verlagere Details bei Bedarf in die Ablaufspur.

## Evidence and uncertainty rules

Eine Quelle kann eine Behauptung stützen, ohne deren Verbindung zum Schluss zu stützen. Bewerte Unmittelbarkeit, Relevanz und Geltungsbereich getrennt. Zähle gemeinsame Prämissen nicht zweimal als unabhängige Unterstützung. Eine Entkräftung gegen Zeugen oder Messungen kann Unterstützung schwächen, ohne den gegenteiligen Schluss zu beweisen. Widersprüchliche glaubwürdige Grundlagen erfordern sichtbaren Konflikt und Aussetzung oder Abschwächung, sofern keine angegebene Vorrangregel ihn löst.

## Stop conditions

Stoppe und stelle eine blockierende Frage, wenn Zielschluss oder Entscheidungsumfang fehlen und konkurrierende Deutungen unterschiedliche Karten erzeugen würden. Setze aus, wenn eine wesentliche Prämisse nicht gestützt oder ein entscheidender Einwand nicht geklärt werden kann. Bei reiner Quellenrangfolge, einfacher Berechnung oder stabiler Definition stoppe und übergib an das spezifischere Verfahren.

## Complement handoff

Übergib an `evidence-hierarchy`, wenn die Karte Quellenqualität, Studiendesign oder Unmittelbarkeit statt Argumentstruktur als verbleibenden Engpass zeigt. Übermittle nur Behauptungs-Quellen-Verknüpfungen, unbelegte Verbindungen und wesentliche Konflikte. Die Ergänzung soll nicht die gesamte Argumentkarte neu aufbauen.
