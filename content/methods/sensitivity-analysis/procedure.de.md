## Purpose

Prüfen Sie Änderungen von Modellresultat, Vergleich oder Entscheidung bei Variation wesentlicher Eingaben oder Gewichte in begründbaren Bereichen. Identifizieren Sie einflussreiche Variablen, Wechselwerte, Interaktionen und fragile Annahmen. Ergebnis ist transparente Robustheitsprüfung, keine dramatische Bereichswahl oder behauptete Zukunftswahrheit eines Modells.

## Use when

Bei bestehender Berechnung, Prognosemodell, Geschäftsfall, Bewertungsregel oder Vergleich, wenn unsichere Eingaben die Wahl ändern könnten. Hilft Datenerhebung priorisieren, versteckte Schwellen zeigen und robuste von eng annahmeabhängigen Schlüssen unterscheiden. Numerische oder ordinale Änderungen bei ausdrücklichem Maßstab möglich.

## Do not use when

Nicht ohne variierbares Modell, Vergleich, Regel oder Variablenbeziehung. Keine Sensitivität aus Faktenfrage, undefinierter Basis oder herkunftslosen Bereichen erfinden. Korrelierte Variablen nicht unabhängig bewegen, Nichtlinearität nicht ungeprüft linearisieren oder präzise Wechselwerte aus unzureichenden Eingaben berichten.

## Inputs to establish

Klären Sie Basismodell oder Regel, Ergebnismaß, Schwelle, Eingaben oder Gewichte, Einheiten und Resultat. Plausible Bereiche und Herkunft samt Abhängigkeiten und Grenzen definieren. Variationsdesign, Rundung sowie Einzelvariation, strukturierte Kombination oder ordinalen Vergleich nennen. Unterstützte Option oder Politik erfassen. Höchstens zwei entscheidende Fragen bei Einfluss auf Basis oder Bereich.

## Procedure

1. Basisformel oder Regel, Eingaben, Einheiten und Ergebnis veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Reproduzierbare Basis und benannte Schwelle.
2. Bereiche, Gewichte, Abhängigkeiten und Evidenz veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Grenzen als verifiziert, berechnet, abgeleitet, angenommen, ungeprüft oder widersprüchlich statt effekthaschend gewählt.
3. Einzeltests und dann nur begründbare strukturierte Kombinationen ausführen. **Sichtbares Ergebnis/Zustandsänderung:** Protokoll je geänderter Eingabe, Ausgabe, Methode, Einheit und Rundung; korrelierte Eingaben gegebenenfalls gemeinsam bewegen.
4. Richtung, Größenordnung oder ordinale Änderung, Interaktionen und Schwellenwechselwerte veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Einflussreich, einflussarm, robust oder fragil; Rang beweist keine Kausalität.
5. Entscheidungsfolge und Recherchepriorität entscheidungswirksamer Variablen veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Forschung an benannte Umkehrbedingung statt größte Rohvariation binden.
6. Robusten, fragilen, vorläufigen oder zurückgestellten Schluss samt nächster Validierung veröffentlichen. **Sichtbares Ergebnis/Zustandsänderung:** Fehlende Basis, Bereich oder Schwelle führt ausdrücklich zu Zurückstellung statt erfundener Sensitivität.

## Public output contract

Liefern Sie `baseline`, `tested_ranges`, `perturbation_results`, `switching_values`, `robust_or_fragile_conclusion`, `research_priority`, `flip_condition` und gestützten, vorläufigen oder zurückgestellten Status. Schwelle und sie überschreitende Eingaben benennen. Kartengründe identifizieren Berechnungen samt Eingaben; Unsicherheit nennt Bereichs- oder Modellgrenzen; Umkehrbedingung ist beobachtbare Eingabe-/Schwellenänderung. Vollständige Formeln und Protokolle im Trace oder Artefakt.

## Evidence and uncertainty rules

Bereiche brauchen Quelle, Nutzergrenze, Historie oder ausdrückliche Annahme; bequeme Bereiche sind keine Evidenz. Formel, Operanden, Einheiten und Rundung offenlegen. Relevante Nichtlinearität, Korrelation, Sprünge und Modellformunsicherheit erhalten. Nur ordinale Gewichte erlauben Richtung oder Schwellenordnung statt pseudopräziser Prozente. Testhäufigkeit begründet keine reale Wahrscheinlichkeit. Robustes Modell kann bei falscher Schwelle oder Ziel trotzdem fragile Entscheidung liefern.

## Stop conditions

Bei materiell verschiedenen Deutungen von Basis, Schwelle oder Ziel eine blockierende Frage stellen und stoppen. Unbestimmbare erforderliche Bereiche, Abhängigkeiten oder Regel führen zu Zurückstellung. Stoppen bei unveränderlicher Entscheidung über alle belastbaren Variationen oder Restarbeit aus Evidenzprüfung, Kausalerklärung oder breiterem Zielkonflikt.

## Complement handoff

An `trade-off-analysis` übergeben, wenn Ergebnisse mit Kriterien, Gewichten und Beteiligtenpräferenzen verbunden werden müssen. Basis, Wechselwerte, Robustheit/Fragilität, Bereichsherkunft und Recherchepriorität übermitteln. Grenzen verwenden; Sensitivitätsrang ist weder Präferenz noch Wahrscheinlichkeit.
