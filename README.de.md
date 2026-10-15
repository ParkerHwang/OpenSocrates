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

## Native Migration v1.6.0

Dieser Zweig ist ein unveröffentlichter v1.6.0-Kandidat. Er übernimmt die zehn Sprachen aus v1.5.2. Native Go-Programme ersetzen Python, Node.js und npm; Nutzer benötigen auch kein Go. Windows ARM64 verwendet eigene native Dateien. Natives Claude Code bleibt auf macOS ARM64 beschränkt. Signatur, Notarisierung und Veröffentlichung sind getrennte Freigabebedingungen. Neue Methodeninhalte gehören zu v1.6.1 oder später.

## Anwendungen und Plattformen

[v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2) · [v1.6.0](docs/native-v1.6.md) · [Setup](docs/setup-guide.md) · [Security](SECURITY.md)

| Anwendung | Bereitstellung | Plattform und Aktivierung |
| --- | --- | --- |
| Codex | Bestehende Hooks und native Entscheidungsruntime | Apple-Silicon-Mac und Windows x64/ARM64; Vertrauen für 7 Hooks in einer interaktiven Sitzung prüfen |
| Claude Code CLI / lokaler Desktop-Code | Zustandsloser nativer Einstieg und vollständige Referenzen | Apple-Silicon-Mac; Claude CLI, Anmeldung und Plugin-/Hook-Berechtigungen |
| Claude Web / Desktop Chat / Cowork | Konto-Skill als ZIP ohne ausführbaren Code | Export auf Mac oder Windows; Upload und Aktivierung im Konto sind getrennte Schritte |
| Antigravity | Modulare Regel und Skill | Apple-Silicon-Mac und Windows x64/ARM64; Arbeitsbereich oder globaler Geltungsbereich |

## Installieren oder aktualisieren

Laden Sie das native Programm und das passende Paket aus einer freigegebenen Release. Vor Veröffentlichung sind Kandidatenpakete lokale Builds. Übernehmen Sie eine npm-verwaltete v1.5-Installation ausdrücklich mit `adopt`; Einstellungen, Berechtigungen und deaktivierte Integrationen bleiben erhalten. Verwenden Sie anschließend `update` mit einem geprüften Paket.

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates update --host codex --package /absolute/path/to/bundle.zip
```

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

Öffnen Sie `/hooks` im interaktiven Codex, prüfen Sie die 7 OpenSocrates-Hooks
und erteilen Sie erforderliche Freigaben über die Vertrauensfunktion des Hosts.
Starten Sie danach eine neue Unterhaltung. `status` prüft Installation und
Integrität, beweist jedoch keine Hook-Freigabe oder tatsächliche Anwendung.

Für Claude Code auf einem Apple-Silicon-Mac verwenden Sie `install --host claude`.
Für Antigravity wählen Sie einen bestehenden Arbeitsbereich mit absolutem Pfad;
ohne `--workspace` gilt die Installation global. Vermeiden Sie doppelte aktive
Installationen für dieselbe Aufgabe. Unter Windows verwenden Sie einen lokalen
Laufwerkspfad in Anführungszeichen, etwa `"C:\Work\Reading Workshop"`.

```text
./opensocrates install --host claude --package /absolute/path/to/claude-bundle.zip
./opensocrates install --host antigravity --package /absolute/path/to/antigravity-bundle.zip --workspace /absolute/path/to/workspace
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
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

Mit dem nativen Programm auf Mac:

```text
./opensocrates locale set de
./opensocrates locale get
./opensocrates locale reset
```

Unter Windows x64/ARM64 verwenden Sie `.\opensocrates.exe`. `locale` hat kein Hostargument.
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
beansprucht. Anweisungssprache, Antwortsprache, Host-Oberfläche und Verwaltungsausgaben
sind getrennt. Die Installation besitzt keine Option `--locale`.

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

Der [native Leitfaden](docs/native-v1.6.md) beschreibt automatische Updates, Wiederherstellung und fehlende Nachweise. v1.5.2- und npm-Anleitungen gelten nur für den veröffentlichten Wartungskanal.

OpenSocrates ist ein unabhängiges Projekt unter der [MIT-Lizenz](LICENSE), ohne
Zugehörigkeit zu oder Empfehlung durch OpenAI, Anthropic oder Google.
[Änderungsprotokoll](CHANGELOG.md).
