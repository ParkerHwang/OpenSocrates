<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Denkunterstützung für Ergebnisse, die Sie verstehen, beurteilen und nutzen können.**

OpenSocrates bietet 48 Denkmethoden zum Zusammenführen von Quellen, Verstehen
von Perspektiven, Vergleichen von Optionen und Schreiben hilfreicher Nachrichten.
v1.5.2 ergänzt Deutsch (`de`), Französisch, Italienisch, Spanisch, Portugiesisch
und Thai zu Englisch, Koreanisch, vereinfachtem Chinesisch und Japanisch.
Die zehn Sprachen enthalten 480 vollständige Verfahren, 3.840 kanonische Fälle
und 1.440 Fragen an den Agenten, jeweils drei pro Methode und Sprache.
Inhaltsrevision 5 erhält Texte und Werte der bisherigen vier Sprachen; die
Revisionskennung jeder Methode wechselt jedoch von 4 zu 5. Spezielle Methoden
für Programmieraufgaben kommen nicht hinzu.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md) | [Français](README.fr.md) | **Deutsch** | [Italiano](README.it.md) | [Español](README.es.md) | [Português](README.pt.md) | [ไทย](README.th.md)

## Anwendungen und Plattformen

| Anwendung | Bereitstellung | Plattform und Aktivierung |
| --- | --- | --- |
| Codex | Bestehende Hooks und native Entscheidungsruntime | Apple-Silicon-Mac und Windows x64; Vertrauen für 7 Hooks in einer interaktiven Sitzung prüfen |
| Claude Code CLI / lokaler Desktop-Code | Zustandsloser nativer Einstieg und vollständige Referenzen | Apple-Silicon-Mac; Claude CLI, Anmeldung und Plugin-/Hook-Berechtigungen |
| Claude Web / Desktop Chat / Cowork | Konto-Skill als ZIP ohne ausführbaren Code | Export auf Mac oder Windows; Upload und Aktivierung im Konto sind getrennte Schritte |
| Antigravity | Modulare Regel und Skill | Apple-Silicon-Mac und Windows x64; Arbeitsbereich oder globaler Geltungsbereich |

Der Plattformumfang bleibt wie in v1.5.0. Natives Claude Code unter Windows
gehört nicht dazu. Windows ARM64 und die Go-Migration sind separate Arbeiten
für v1.6.0. Ein Konto-Skill installiert keine native Claude-Integration.

## Installieren oder aktualisieren

Installieren Sie Node.js 20 oder neuer und melden Sie sich bei der gewünschten
Anwendung an. Native Laufzeitprogramme sind enthalten; Python ist zur Installation
nicht nötig. Archive und SHA-256-Dateien finden Sie auf der
[Release-Seite v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
npx --yes opensocrates@1.5.2 update --host codex
```

Verwenden Sie bei einer vorhandenen Installation `update` statt `install`.
Öffnen Sie `/hooks` im interaktiven Codex, prüfen Sie die 7 OpenSocrates-Hooks
und erteilen Sie erforderliche Freigaben über die Vertrauensfunktion des Hosts.
Starten Sie danach eine neue Unterhaltung. `status` prüft Installation und
Integrität, beweist jedoch keine Hook-Freigabe oder tatsächliche Anwendung.

Für Claude Code auf einem Apple-Silicon-Mac verwenden Sie `install --host claude`.
Für Antigravity wählen Sie einen bestehenden Arbeitsbereich mit absolutem Pfad;
ohne `--workspace` gilt die Installation global. Vermeiden Sie doppelte aktive
Installationen für dieselbe Aufgabe. Unter Windows verwenden Sie einen lokalen
Laufwerkspfad in Anführungszeichen, etwa `"C:\Work\Reading Workshop"`.

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

Exportieren Sie den Konto-Skill an einen absoluten ZIP-Dateipfad in einem
bestehenden Ordner. Laden Sie ihn anschließend in Claude unter **Customize →
Skills** hoch und aktivieren Sie ihn. Sichern Sie vor einem Austausch den bisherigen
OpenSocrates-Skill und seinen Aktivierungszustand. Der Export beweist weder Upload
noch Aktivierung oder automatische Auswahl. Ergänzen Sie unter **Settings →
General → Instructions for Claude** diese Anweisung; bestehende Anweisungen bleiben erhalten:

```text
Laden Sie bei Aufgaben, die Interpretation oder Urteil erfordern, etwa beim
Zusammenführen von Quellen, Vergleichen von Optionen, Entscheiden oder Schreiben
von Nachrichten, den aktivierten OpenSocrates-Skill und befolgen Sie seine
Anweisungen, auch wenn ich ihn nicht nenne. Lesen Sie vor der Anwendung einer
Denkmethode das vollständige Verfahren und prüfen Sie die Anwendungsbedingungen.
Ergänzen Sie mechanische Aufgaben wie Formatierung nicht um unnötige Verfahren.
```

Ältere Cowork-Oberflächen verwenden **Settings → Cowork → Global instructions**.
Richten Sie verschiedene Web-/Desktop-Konten getrennt ein und starten Sie eine
neue Unterhaltung. Die Auswahl erfolgt durch das Modell und kann ausbleiben;
es gibt keinen neuen nativen Hook oder garantierten Einsatz bei jeder Nachricht.
Standardwert und `--host all` wählen weiterhin nur Codex.

## Sprache der Anweisungen wählen

Deutsch lässt sich anhand der lateinischen Schrift nicht zuverlässig von den
anderen unterstützten Sprachen unterscheiden. Wählen Sie daher eine ausdrückliche
oder gespeicherte Präferenz. Im Stammverzeichnis des installierten Codex-Pakets auf Mac:

```sh
bin/launch.sh locale codex set de
bin/launch.sh locale codex get
bin/launch.sh locale codex reset
```

Unter Windows verwenden Sie `node bin/launch.mjs locale codex set de`.
`set follow` oder `reset` löscht nur die Sprachpräferenz. Sie gilt für den
beibehaltenen Selektor. Zustandslose Entscheidungsanfragen benötigen ein explizites
JSON-Feld `locale` und lesen keine Einstellungen. Konto-/Inhaltspakete verwenden
den passenden Sprachleitfaden und die vollständigen Referenzen.

Die Reihenfolge lautet: vertrauenswürdige explizite Sprache, gespeicherte Präferenz,
dann Schriftzeichen der aktuellen Eingabe. Kana haben Vorrang für Japanisch;
sonst wählen überwiegende Thai-, Hangul- oder Han-Zeichen Thai, Koreanisch oder
Chinesisch. Bei Gleichstand, leerer Eingabe oder unbekannter Schrift gilt Englisch.
Japanisch ohne Kana ist mehrdeutig und benötigt `ja`. Portugiesisch verwendet
brasilianische Schreibweise unter `pt`; separate Regionalvarianten werden nicht
beansprucht. Anweisungssprache, Antwortsprache, Host-Oberfläche und npm-Ausgaben
sind getrennt. Der npm-Installer besitzt keine Option `--locale`.

## Quellenangabe, Datenschutz und Grenzen

Die genaue Schlusszeile `Powered by OpenSocrates` erscheint nur, wenn eine
geeignete kanonische Methode vollständig gelesen und tatsächlich auf die Antwort
angewendet wurde. Lesehinweise allein und mechanische Arbeit reichen nicht aus.
Die Zeile beweist weder native Anwendung noch bessere Ergebnisse.

Der standardmäßige Entscheidungsweg ruft kein zusätzliches Auswahlmodell auf
und speichert keine Rohprompts, Unterhaltungen, Screenshots oder verborgenen
Gedankengänge. Der native Claude-Einstieg liest keine Unterhaltungen und legt
keine Datenbank an. Normale Host-Anfragen unterliegen dessen Anmeldung,
Berechtigungen, Aufbewahrung und Bedingungen. Installation, Laden, vollständiges
Lesen, Anwendung und Nutzen bleiben getrennte Nachweisstufen. Allgemeine Vorteile
bei Qualität, Kosten oder Geschwindigkeit werden nicht behauptet.

Weitere Angaben: [Sprachleitfaden](docs/v1.5.2.md), [Einstellungen](docs/settings.md),
[Einrichtung](docs/setup-guide.md) und [Sicherheitsrichtlinie](SECURITY.md).
Die historischen [Mac](docs/macos-v1.5.md)- und [Windows](docs/windows-v1.5.md)-Leitfäden
behalten ihre damaligen Nachweise; aktuelle Befehle stehen hier für Version 1.5.2.

OpenSocrates ist ein unabhängiges Projekt unter der [MIT-Lizenz](LICENSE), ohne
Zugehörigkeit zu oder Empfehlung durch OpenAI, Anthropic oder Google.
[Änderungsprotokoll](CHANGELOG.md).
