## Purpose

Nutze dieses Verfahren für normalerweise folgende Schlüsse, die bei Ausnahmen oder neuen Belegen zurückgenommen werden können. Es nennt eine Standardregel, wendet sie vorläufig an, unterscheidet widerlegende von die Begründung untergrabenden Einwänden und erfasst Rücknahmebedingungen. Das Ergebnis ist kontrolliertes vorläufiges Urteil, keine abgeschwächte Form einer unbedingten Regel.

## Use when

Nutze es in Recht, Richtlinien, Medizin, Betrieb, Alltagsregeln und anderen Bereichen mit ausnahmefähigen Verallgemeinerungen oder zeitlich eintreffenden Belegen. Es passt zu „normalerweise“, „es sei denn“ und „prima facie“ sowie Urteilen, die revidierbar, aber nicht beliebig bleiben müssen.

## Do not use when

Nutze es nicht bei strikt folgendem Ergebnis aus festen Regeln und gesicherten Prämissen oder bei reiner Quellenrangfolge beziehungsweise statistischer Aktualisierung. Liste nicht jede vorstellbare Ausnahme, behandle Glaubwürdigkeitsprobleme nicht als direkte Gegenbeweise und bevorzuge Aussagen nicht nur wegen Aktualität. Fehlende bekannte Gegenargumente beweisen den Schluss nicht.

## Inputs to establish

Kläre Standardregel, auslösende Tatsachen, Regelumfang, bekannte Ausnahmen, mögliche widerlegende und untergrabende Einwände und betroffene Entscheidung. Identifiziere speziellere vorrangfähige Regeln. Stelle höchstens zwei entscheidende Fragen bei unklarer Regel oder Auslösung; kennzeichne die Prämisse sonst als vorläufig.

## Procedure

1. Veröffentliche begrenzte Standardregel, etwa „normalerweise impliziert P Q“, mit Quelle, Umfang und Belegstatus. Das erzeugt den sichtbaren Regelzustand.
2. Veröffentliche anwendbare Tatsachen und Prima-facie-Schluss. Kennzeichne Vorläufigkeit und Anwendungsbedingungen des Standards.
3. Veröffentliche widerlegende Einwände für Nicht-Q getrennt von untergrabenden Einwänden gegen P-Q-Verbindung. Erfasse jeweils geprüft, behauptet oder unbekannt.
4. Veröffentliche konkurrierende Regeln und wende Spezifität nur bei echter Teilmengenbeziehung an. Löst sie den Konflikt nicht, markiere widersprüchlich oder ausgesetzt statt Auswahl durch Aktualität oder sicheren Ton.
5. Veröffentliche ausdrückliche Rücknahmebedingungen: beobachtbare Tatsache, die Q zurücknimmt, Schlussberechtigung schwächt oder Neubeurteilung erfordert. Bleibe enger als „neue Informationen“.
6. Veröffentliche Status nach bekannten Einwänden: vorläufig, gestützt, zurückgenommen, widersprüchlich oder ausgesetzt. Benenne Widerlegung, Untergrabung oder ungeklärten Konflikt als Änderungsgrund.
7. Veröffentliche aktuellen Schluss, anwendbare Einwände und Bedingung für eine Urteilsänderung. Fehlen entscheidende Auslösetatsache oder Ausnahme, setze aus oder bewahre Vorläufigkeit statt Gewissheit.

## Public output contract

Liefere `default_rule`, `applicable_facts`, `prima_facie_conclusion`, `exceptions_defeaters`, `rebutting_defeaters`, `undercutting_defeaters`, `specificity_resolution`, `withdrawal_conditions`, `current_status` und `flip_condition`. Mache Vorläufigkeit und wesentliche Gegenargumente in der Karte sichtbar. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**; nenne den Standardschluss niemals unbedingt.

## Evidence and uncertainty rules

Widerlegende Einwände widersprechen dem Schluss; untergrabende schwächen die Tatsachen-Schluss-Begründung, ohne das Gegenteil zu beweisen. Spezifität ist struktureller Vorrang, keine Aktualitätsregel. Prüfe neue Belege auf Umfang und Unabhängigkeit vor Statusänderung. Bei ungeklärtem wesentlichem Einwand schwäche ab oder setze aus und benenne nötige Prüfung.

## Stop conditions

Stoppe mit einer blockierenden Frage bei nicht identifizierbarer Regel oder Auslösetatsache und handlungsändernden Konkurrenzregeln. Setze aus ohne entscheidende Ausnahme, Quelle oder Anwendungsbedingung. Stoppe bei strikter ausnahmsloser Regel oder verbleibender probabilistischer Aktualisierung.

## Complement handoff

Übergib an `premortem-analysis`, wenn der vorläufige Regelschluss einen gewählten Plan stützt und dessen Scheitern die Restfrage ist. Übermittle Standardschluss, bekannte Einwände und Rücknahmebedingungen. Die Ergänzung soll Einwände nicht neu klassifizieren oder Regelinventar wiederholen.
