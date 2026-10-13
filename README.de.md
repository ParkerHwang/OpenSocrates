<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**Nutzen Sie 48 Denkmethoden in Ihren KI-Gesprächen.**

OpenSocrates bietet wiederverwendbare Denkverfahren für **Claude, Codex und
Antigravity**. Vergleichen Sie Optionen, ordnen Sie widersprüchliche Informationen
ein und betrachten Sie einen Plan aus einem anderen Blickwinkel. Beschreiben Sie
Ihre Aufgabe mit Ihren eigenen Worten; die Methoden liefern Fragen, Prüfungen und
Schritte, auf die Sie zurückgreifen können.

[Mit Ihrer Anwendung starten](#start-with-your-app) · [Ein Beispiel ansehen](#see-it-in-a-task) · [Die Methoden entdecken](#a-method-for-the-question)

**48 Methoden · 10 Anweisungssprachen · MIT-Lizenz**

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · **Deutsch** · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## Ein Werkzeugkasten für Ihre aktuelle Aufgabe

- **Beginnen Sie mit Ihrer Aufgabe.** Jede Methode enthält bereits Fragen und Prüfungen, die Sie in weiteren Gesprächen wiederverwenden können.
- **Finden Sie einen hilfreichen Blickwinkel.** Nutzen Sie Methoden zum Vergleichen von Optionen, Bewerten von Belegen, Erkunden von Annahmen und Vorausplanen.
- **Passen Sie die Methoden an Ihre Arbeit an.** Lesen Sie jedes Verfahren, sehen Sie sich seine Beispiele an und nutzen Sie das offene Material für Ihre Aufgaben.

<a id="see-it-in-a-task"></a>

## So könnte eine Anfrage aussehen

Probieren Sie nach der Einrichtung eine Anfrage wie diese:

> Wir wollten gerade ein gehostetes Tool kaufen, aber der Arbeitsablauf muss jetzt offline funktionieren.
> Sollten wir ein Tool kaufen, selbst eines entwickeln oder vorerst manuell arbeiten?

Für eine solche Entscheidung bietet die [Zielkonfliktanalyse](content/methods/trade-off-analysis/procedure.de.md)
einen wiederverwendbaren Ablauf: Anforderungen bestimmen, umsetzbare Optionen
vergleichen, bekannte Fakten von Annahmen trennen und erklären, was die Empfehlung
ändern würde. Die Methode ergänzt Ihre alltägliche Anfrage um diese Struktur.

<a id="start-with-your-app"></a>

## Mit Ihrer Anwendung starten

Wählen Sie, wo Sie OpenSocrates nutzen möchten.
[v1.5.2 herunterladen](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

<details>
<summary><strong>Claude Chat und Cowork</strong> — einen Skill hochladen und ein Gespräch beginnen</summary>

Für Claude Web, Desktop Chat und Cowork:

1. Aktivieren Sie unter **Settings → Capabilities** die Option **Code execution and file creation**. Prüfen Sie bei einem von Ihrer Organisation verwalteten Konto, ob deren Richtlinien Skills und Codeausführung erlauben.
2. Laden Sie die [ZIP-Datei des Konto-Skills](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip) und die zugehörige [SHA-256-Datei](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip.sha256) herunter.
3. Öffnen Sie **Customize → Skills → + → Create skill → Upload a skill**, laden Sie die ZIP-Datei hoch und aktivieren Sie den Skill. Sichern Sie einen vorhandenen OpenSocrates-Skill, bevor Sie ihn ersetzen.
4. Ergänzen Sie in jedem verwendeten Claude-Konto die [einmalige Kontoanweisung](docs/setup-guide.md#claude-standing-instructions), ohne bestehende Anweisungen zu löschen. Beginnen Sie ein neues Gespräch und beschreiben Sie Ihre Aufgabe.

Die portable Skill-ZIP enthält die vollständigen Methoden und Beispiele.
[Bebilderte Einrichtungsanleitung](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Claudes offizieller Skills-Leitfaden](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Apple-Silicon-Mac</summary>

Sie benötigen [Node.js 20 oder neuer](https://nodejs.org/en/download), die Claude
CLI und ein angemeldetes Claude-Konto. Dies funktioniert mit Claude Code im
Terminal und lokalem Code in Claude Desktop. Führen Sie im **Terminal** aus:

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

Prüfen Sie `enabled: true`, `integrity: verified` und `registration: confirmed`.
Prüfen Sie gegebenenfalls die Vertrauensabfrage für das Projekt und beginnen Sie
danach eine neue lokale Sitzung.
[Bebilderte Einrichtungsanleitung](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Apple-Silicon-Mac oder Windows x64</summary>

Sie benötigen [Node.js 20 oder neuer](https://nodejs.org/en/download) und Codex.
Die native Laufzeitumgebung ist im Paket enthalten. Führen Sie im **Terminal auf
Mac** oder in **PowerShell unter Windows** aus:

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
```

Öffnen Sie Codex interaktiv und geben Sie `/hooks` in das Eingabefeld ein. Prüfen
Sie die sieben OpenSocrates-Hook-Definitionen und genehmigen Sie diejenigen,
denen Sie vertrauen. Beginnen Sie danach ein neues Gespräch.
[Bebilderte Einrichtungsanleitung](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

So aktualisieren Sie eine vorhandene Codex-Installation:

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Apple-Silicon-Mac oder Windows x64</summary>

Sie benötigen [Node.js 20 oder neuer](https://nodejs.org/en/download). Wählen Sie
einen Arbeitsbereich und ersetzen Sie den Beispielpfad durch den vollständigen
Pfad eines vorhandenen Ordners. Führen Sie im **Terminal auf Mac** oder in
**PowerShell unter Windows** aus:

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace "/absolute/path/to/workspace"
```

Verwenden Sie unter Windows einen lokalen Laufwerkspfad in Anführungszeichen,
etwa `"C:\Work\Reading Workshop"`. Lassen Sie für eine globale Einrichtung
`--workspace` weg. Wählen Sie für ein bestimmtes Projekt entweder eine globale
Installation oder eine im Arbeitsbereich und beginnen Sie danach ein neues Gespräch.
[Skill und Regel prüfen](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**Soll ein Agent die Einrichtung übernehmen?** Nutzen Sie die [Einrichtungsanfrage](docs/setup-guide.md#ask-an-agent-to-finish-setup)
oder die [aktuelle Installationsanleitung](docs/agent-discovery.md). Wählen Sie jede
Anwendung mit ihrer benannten `--host`-Option; der Standardwert und `--host all`
wählen Codex.

<a id="a-method-for-the-question"></a>

## Eine Methode für die Frage

| Ihre Aufgabe | Eine Methode zum Erkunden |
| --- | --- |
| Zwischen Optionen mit konkurrierenden Prioritäten wählen | [Zielkonfliktanalyse](content/methods/trade-off-analysis/procedure.de.md) |
| Verstehen, was ein Plan als selbstverständlich voraussetzt | [Annahmenkartierung](content/methods/assumption-mapping/procedure.de.md) |
| Die Belege hinter einer Behauptung abwägen | [Kritisches Denken](content/methods/critical-thinking/procedure.de.md) |
| Sich auf mögliche Schwierigkeiten eines Plans vorbereiten | [Premortem-Analyse](content/methods/premortem-analysis/procedure.de.md) |

Jede Methode enthält ihren Zweck, Anwendungsbedingungen, ein vollständiges
Verfahren, Beispiele und Fragen an den Assistenten. Lesen Sie den Text, folgen
Sie den Denkschritten und verwenden Sie die Methoden für weitere Aufgaben.

[Alle 48 Methoden ansehen](content/methods/)

## Vollständige Methodentexte in zehn Sprachen

Englisch, Koreanisch, vereinfachtes Chinesisch, Japanisch, Französisch, Deutsch,
Italienisch, Spanisch, Portugiesisch und Thai. Jede Sprache enthält die
vollständigen Verfahren und Beispiele aller 48 Methoden.

Dies sind die Sprachen der Methodentexte, die Ihr Assistent liest.
[Sprachleitfaden](docs/v1.5.2.md) · [Codex-Anweisungssprache einstellen](docs/settings.md)

## Open Source zum Entdecken

Lesen Sie die vollständigen Methoden und den Quellcode, passen Sie sie an Ihre
Arbeit an oder steuern Sie ein neues Beispiel bei. OpenSocrates ist ein
unabhängiges Projekt unter der [MIT-Lizenz](LICENSE).

[Releases](https://github.com/ParkerHwang/OpenSocrates/releases) · [Einrichtungsanleitung](docs/setup-guide.md) · [Datenschutz und Sicherheit](SECURITY.md) · [Mitwirken](CONTRIBUTING.md) · [Issues](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [Änderungsprotokoll](CHANGELOG.md)
