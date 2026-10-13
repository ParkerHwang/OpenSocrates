## Purpose

Nutze dieses Verfahren, um Behauptungen an Qualität, Unmittelbarkeit, Anwendbarkeit und Verzerrungsrisiko ihrer Quellen anzupassen. Es klassifiziert Behauptungstypen, vergleicht Studien- oder Belegdesigns ohne starre universelle Hierarchie und benennt Belegstatus und Schlussstärke. Niedrigere Quellenstufen können nützlich sein, wenn sie unmittelbar zur Frage passen und stärkere Designs nicht.

## Use when

Nutze es bei gemischter Forschung, Richtlinien, Produktexperimenten, Fachmeinungen, Nutzerberichten oder anderen Belegen, wenn vertretbare Stärkeangaben nötig sind. Es passt zu Fragen nach Behauptungsunterstützung, Studienanwendbarkeit auf Zielkontext und belegqualitätsabhängiger Wortwahl.

## Do not use when

Nutze es nicht primär bei Wertpräferenzen statt Tatsachenunterstützung oder spezifischerer formaler Regel, Kausalmodellierung beziehungsweise Quellenkonfliktfrage. Ordne nicht allein nach Prestige, verwerfe passende niedrigere Stufen nicht automatisch und nenne Quellen nicht stark ohne Prüfung von Unmittelbarkeit und Grenzen.

## Inputs to establish

Kläre Behauptung, Zielpopulation oder Kontext, Typ (Wirkung, Prognose, Mechanismus oder Erfahrung), Entscheidungsschwelle, Quellen, Designs, Stichproben, Maße und Konflikte. Identifiziere direkte, indirekte und bloß kontextgebende Quellen. Stelle höchstens eine entscheidende Frage, wenn Zielkontext die Anwendbarkeit ändert.

## Procedure

1. Veröffentliche Behauptung, Zielkontext und Entscheidungsschwelle. Benenne Wirkung, Vorhersage, Mechanismus oder Erfahrung; das erzeugt sichtbaren Belegprüfzustand.
2. Veröffentliche Behauptungs-Quellen-Tabelle mit Quellentyp, Design, Stichprobe oder Grundlage, Unmittelbarkeit und Umfang. Kennzeichne geprüft, nutzerseitig angegeben, erschlossen oder unverfügbar.
3. Veröffentliche Qualitätsdimensionen – Designstrenge, Verzerrungsrisiko, Messgültigkeit, Vollständigkeit und Anwendbarkeit – qualitativ oder ordinal mit Herkunft. Erfinde keinen präzisen Gesamtscore.
4. Veröffentliche Hierarchiestufe und Grenzen je Quelle. Begründe Stärke oder Schwäche für diese Behauptung statt universeller Stufenautorität.
5. Veröffentliche Quellenübereinstimmung, Inkonsistenz und fehlende Belege. Halte glaubwürdigen Konflikt sichtbar; Bilde keine Mittelwerte aus unvereinbaren Ergebnissen ohne gerechtfertigte Syntheseregel.
6. Veröffentliche Belegstatus und angepassten Schluss: stark gestützt, gestützt, vorläufig, ungeprüft, widersprüchlich oder ausgesetzt. Benenne kleinste quellen- oder anwendungsbezogene Sprachgrenze.
7. Veröffentliche nächste Verifizierung und beobachtbare Bedingung für eine Urteilsänderung. Ohne entscheidende Unterstützung setze aus oder schwäche ab, statt folgenschwere Behauptungen als festgestellt darzustellen.

## Public output contract

Liefere `claim`, `claim_type`, `claim_to_source_table`, `quality_limits`, `quality_dimensions`, `hierarchy_position_and_limits`, `agreement_and_conflicts`, `missing_evidence`, `resulting_evidence_state`, `calibrated_conclusion` und `flip_condition`. Die Karte zeigt Belegstatus und gegebenenfalls sicheren Quellenlink oder Nutzerangabenmarkierung. Grundlagen tragen **verified**, **computed**, **inferred**, **assumed**, **unverified** oder **conflicted**.

## Evidence and uncertainty rules

Designhierarchie ist Orientierung, kein Ersatz für Fragenpassung. Prüfe Unmittelbarkeit, Population, Ergebnis, Zeit, Messung, Auswahl-, Ausfall- und Berichtsverzerrung. Fachmeinungen können Mechanismen benennen ohne Effektgröße; Nutzerberichte Erfahrung ohne Prävalenz. Bei wesentlichem Quellenwiderspruch oder indirekter bester Quelle schwäche ab oder setze aus und benenne die Grenze.

## Stop conditions

Stoppe mit einer blockierenden Frage ohne definierten Zielkontext oder Behauptung, wenn Anwendbarkeit die Entscheidung ändert. Setze aus ohne direkte Unterstützung wesentlicher Behauptungen, bei unlösbarem Konflikt oder unzureichender sicherer Stärkeangabe. Stoppe bei Wertwahl, formaler Folgerung oder Erklärungserzeugung statt Belegkalibrierung.

## Complement handoff

Übergib an `triangulation`, wenn unabhängige Belegströme wesentliche Konflikte bestätigen oder offenlegen könnten. Übermittle Behauptungs-Quellen-Tabelle, Qualitätsgrenzen und offene Uneinigkeit. Die Ergänzung prüft Unabhängigkeit und Übereinstimmung ohne neue Quellenrangfolge.
