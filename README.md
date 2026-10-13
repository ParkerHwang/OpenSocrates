<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**Put 48 reasoning methods to work in your AI conversations.**

OpenSocrates brings reusable reasoning procedures to **Claude, Codex and
Antigravity**. Compare choices, make sense of conflicting information, and explore
a plan from another angle. Describe your task in your own words; the methods
provide questions, checks and steps to draw on.

[Start with your app](#start-with-your-app) · [See an example](#see-it-in-a-task) · [Explore the methods](#a-method-for-the-question)

**48 methods · 10 instruction languages · MIT licensed**

**English** · [한국어](README.ko.md) · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## A toolkit for the work in front of you

- **Start with your task.** The questions and checks are already written into each method, ready to reuse across conversations.
- **Find a useful angle.** Draw on methods for comparing options, evaluating evidence, exploring assumptions and planning ahead.
- **Make it your own.** Read every procedure, study its examples and adapt the open-source material to your work.

## See it in a task

Try a request like this after setup:

> We were about to buy a hosted tool, but now the workflow has to run offline.
> Should we buy, build our own, or handle it manually for now?

For a decision like this, [trade-off analysis](content/methods/trade-off-analysis/procedure.en.md)
provides a reusable sequence: identify the requirements, compare viable options,
separate known facts from assumptions, and explain what would change the
recommendation. The method supplies that structure alongside your everyday request.

## Start with your app

Choose where you want to use OpenSocrates.
[Get v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2).

<details>
<summary><strong>Claude Chat & Cowork</strong> — upload a skill and start a conversation</summary>

For Claude web, Desktop Chat and Cowork:

1. In **Settings → Capabilities**, enable **Code execution and file creation**. For an organization-managed account, confirm that your organization's policy allows Skills and code execution.
2. Download the [account skill ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip) and its [SHA-256 file](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip.sha256).
3. Open **Customize → Skills → + → Create skill → Upload a skill**, upload the ZIP and enable it. Back up an existing OpenSocrates skill before replacing it.
4. Add the [one-time account instruction](docs/setup-guide.md#claude-standing-instructions) to each Claude account you use, preserving your existing instructions. Start a fresh conversation and describe your task.

The portable skill ZIP contains the complete methods and examples.
[Visual setup guide](docs/setup-guide.md#2-claude-account-skill-enable-it-and-add-account-instructions) · [Claude's Skills guide](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Apple-silicon Mac</summary>

You need [Node.js 20+](https://nodejs.org/en/download), the Claude CLI and a
signed-in Claude account. This works with terminal Claude Code and local Code
in Claude Desktop. Run in **Terminal**:

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

Confirm `enabled: true`, `integrity: verified` and `registration: confirmed`.
Review any project trust prompt, then start a fresh local session.
[Visual setup guide](docs/setup-guide.md#3-claude-code-check-the-local-mac-plugin)

</details>

<details>
<summary><strong>Codex</strong> — Apple-silicon Mac or Windows x64</summary>

You need [Node.js 20+](https://nodejs.org/en/download) and Codex. The native runtime
comes with the package. Run in **Terminal on Mac** or **PowerShell on Windows**:

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
```

Open interactive Codex and enter `/hooks` in its input field. Review and approve
the seven OpenSocrates hook definitions you trust, then start a fresh conversation.
[Visual setup guide](docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks)

To update an existing Codex installation:

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Apple-silicon Mac or Windows x64</summary>

You need [Node.js 20+](https://nodejs.org/en/download). Choose a workspace and
replace the example with the full path of a folder that already exists. Run in
**Terminal on Mac** or **PowerShell on Windows**:

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace "/absolute/path/to/workspace"
```

On Windows, use a quoted local-drive path such as `"C:\Work\Reading Workshop"`.
For a global setup, omit `--workspace`. Pick global or workspace installation
for a given project, then start a fresh conversation.
[Confirm the skill and rule](docs/setup-guide.md#4-antigravity-check-both-the-skill-and-rule)

</details>

**Setting up with an agent?** Use the [setup request](docs/setup-guide.md#ask-an-agent-to-finish-setup)
or the [current installation guide](docs/agent-discovery.md). Select each app
with its named `--host` option; the default and `--host all` select Codex.

## A method for the question

| What you're working on | A method to explore |
| --- | --- |
| Choosing between options with competing priorities | [Trade-off analysis](content/methods/trade-off-analysis/procedure.en.md) |
| Understanding what a plan takes for granted | [Assumption mapping](content/methods/assumption-mapping/procedure.en.md) |
| Weighing the support behind a claim | [Critical thinking](content/methods/critical-thinking/procedure.en.md) |
| Preparing for what could go wrong with a plan | [Premortem](content/methods/premortem-analysis/procedure.en.md) |

Each method includes its purpose, use conditions, complete procedure, examples
and questions for the assistant. Explore the text, follow the reasoning steps,
and reuse the methods across your work.

[Browse all 48 methods](content/methods/)

## Complete method text in ten languages

English, Korean, Simplified Chinese, Japanese, French, German, Italian,
Spanish, Portuguese and Thai. Every language includes the full procedures and
examples for all 48 methods.

These are the languages of the method text your assistant reads.
[Language guide](docs/v1.5.2.md) · [Codex instruction-language settings](docs/settings.md)

## Open source, ready to explore

Read the complete methods and source, adapt them to your work, or contribute a
new example. OpenSocrates is an independent project, available under the
[MIT license](LICENSE).

[Releases](https://github.com/ParkerHwang/OpenSocrates/releases) · [Setup guide](docs/setup-guide.md) · [Privacy and security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Issues](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [Changelog](CHANGELOG.md)
