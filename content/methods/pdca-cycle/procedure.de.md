## Purpose

Führen Sie einen begrenzten Plan–Do–Check–Act-Zyklus für eine operative Verbesserungshypothese aus. Ziel, Maß, kleiner Ausführungsumfang, Vergleichsregel und Standardisierungsentscheidung werden sichtbar, sodass Evidenz und organisatorisches Gedächtnis wachsen. Die kontrollierte Lernschleife ersetzt weder Diagnose unbekannter Grundursachen noch Reaktion auf aktive Sicherheitsvorfälle.

## Use when

Wenn Prozesse oder Leistungen kleinräumig und umkehrbar geändert werden können, erwartete Verbesserung messbar ist und wiederholte Zyklen Standards erhöhen. Geeignet für kurze Beobachtungsfenster und klare Entscheidungen zwischen Standardisierung, Überarbeitung und Aufgabe. Lernen aus Ausführung, ohne den gesamten Betrieb ungeprüfter Änderung auszusetzen.

## Do not use when

Nicht bei unbekannter Grundursache, wenn Experimente Schaden verdecken oder verschlimmern, bei verbindlichen Regeln ohne Spielraum oder dringlichen Sicherheits-, Rechts- oder Vorfallsreaktionen. Keine bloße Aktivität ohne Prüfregel. Mechanische Aufgaben nicht zu Verbesserungsprogrammen machen; einmalige Ankündigung oder Durchführung rechtfertigt keine Standardisierung.

## Inputs to establish

Klären Sie Verbesserungsziel, beobachteten Ausgangswert oder Prozesszustand, Hypothese, Umfang, Verantwortlichen und erwartete Richtung. Kennzahl, Einheit, Quelle, Fenster, Schutzgrenzen, Stoppbedingung und Vergleichsregel vor Do festlegen. Evidenz für Standardisierung, Überarbeitung oder Aufgabe und Ablage des nächsten Zyklus oder versionierten Standards definieren. Höchstens zwei knappe Fragen, nur bei Einfluss auf Sicherheitsgrenze, Maß oder Act; sonst ungeprüft markieren und entscheidende Lücken zurückstellen.

## Procedure

1. **Plan-Karte veröffentlichen.** Ziel, Ausgangswert, Hypothese, Richtung, Umfang, Verantwortlichen und Zeitgrenze nennen. Ausgangswert als verifiziert, berechnet, nutzerbereitgestellt, abgeleitet, angenommen oder ungeprüft markieren. **Sichtbares Ergebnis/Zustandsänderung:** Planzustand.
2. **Check-Spezifikation veröffentlichen.** Kennzahl, Einheit, Quelle, Erhebung, Fenster, Vergleich, Schutzgrenzen und Stoppbedingung nennen. Evidenz für Standardisieren, Überarbeiten oder Aufgeben vorab festlegen. **Sichtbares Ergebnis/Zustandsänderung:** Prüfregel.
3. **Do-Protokoll veröffentlichen.** Nur im genehmigten kleinen Umfang ausführen; tatsächliche Änderung, Abweichungen, Ausschlüsse, Vorfälle und Beobachtungen erfassen. Rücknahme sichern; günstiges erstes Signal rechtfertigt keine Expositionsausweitung. **Sichtbares Ergebnis/Zustandsänderung:** Prüfbares Ausführungsprotokoll.
4. **Check-Ergebnis veröffentlichen.** Erwartungen und beobachtete Werte oder Beschreibungen nach vorab festgelegter Regel vergleichen. Fehlende Daten, Störfaktoren, Quellengrenzen und Widersprüche nennen. **Sichtbares Ergebnis/Zustandsänderung:** Ergebnislücke mit Evidenzstatus.
5. **Act-Entscheidung veröffentlichen.** Evidenz- und schutzgrenzenbasiert standardisieren, überarbeiten, aufgeben oder zurückstellen. Gemischte Ergebnisse oder fehlendes entscheidendes Maß bleiben vorläufig mit offener Bedingung. **Sichtbares Ergebnis/Zustandsänderung:** Act oder Zurückstellung.
6. **Folgezyklus veröffentlichen.** Versionierten Standard oder revidierte Hypothese, Verantwortlichen, nächste Beobachtung und ein oder zwei beobachtbare Umkehrbedingungen erfassen. Gelerntes und Ungeprüftes weiterführen. **Sichtbares Ergebnis/Zustandsänderung:** Folgeplan oder zurückgestelltes Ergebnis.

## Public output contract

Liefern Sie `plan_objective_measure`, `do_scope`, `check_rule` und `act_standardize_decision` mit Evidenzstatus jedes wesentlichen Grunds. Das erste Feld enthält Ausgangswert oder dessen Fehlen; Do zeigt begrenzte Exposition; Check Vergleich und Stopp; Act unterscheidet Standardisierung, Überarbeitung, Aufgabe und Zurückstellung. Folgezyklushypothese oder klaren Abbruchgrund nennen. Fehlendes entscheidendes Maß führt zu Zurückstellung.

## Evidence and uncertainty rules

Unterscheiden Sie direkte Beobachtung, Quelle, reproduzierbare Berechnung, nutzerbereitgestelltes Protokoll, Schluss und Arbeitsannahme. Für `computed` Eingaben, Ausdruck, Einheiten und relevante Rundung zeigen. Ohne belastbaren Ausgangswert oder bei geänderter Erhebung Vergleich ungeprüft markieren. Keine erfundenen Wahrscheinlichkeiten, Effektgrößen, Stichproben oder kausale Gewissheit. Ein Zyklus kann lokales Lernen stützen, selten dauerhaften Standard beweisen. Glaubwürdige Konflikte halten Act widersprüchlich oder zurückgestellt. Abweichungen und Negativsignale bewahren.

## Stop conditions

Bei entscheidungswirksam fehlendem Ziel, Ausgangswert, Maß, Vergleich, Verantwortlichen oder sicherem Umfang zurückstellen. Sofort stoppen bei fortdauerndem Schaden, geschwächter Kontrolle, überschrittener Autorisierung oder verlorener Rücknahme. Unbekannte verdeckbare Grundursache an `root-cause-analysis` geben. Nach erfolgloser oder uneindeutiger Prüfung ohne revidierte Hypothese oder sichere Beobachtung stoppen; Do nicht ohne Lernen wiederholen.

## Complement handoff

An `root-cause-analysis` übergeben, wenn Check wiederholtes Versagen, konkurrierende Kausalpfade oder Kontrollschwäche vor erneutem Zyklus zu diagnostizieren offenlegt. Plan, begrenztes Do, Check, Abweichungen, Evidenzstatus und Kontrollfrage übermitteln. Keine unbelegte Schuldbehauptung; nicht allein wegen Uneindeutigkeit eine zweite vollständige Methode starten.
