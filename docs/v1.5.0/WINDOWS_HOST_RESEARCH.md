# Windows host research, 2026-10-07

Research baseline: `9eb2d2f90c9a17a7eee6db41a1c7f7c234ad761b`, the revised
Mac implementation. This document verifies current documented mechanisms and
the installed Antigravity application bundle. It does not qualify an installed
OpenSocrates Windows candidate. Build, lifecycle and ordinary-request findings
belong in the Windows observation record, with their own exact candidate digest.

## Evidence boundary

The inspected system is Windows 11 Pro, version `10.0.26300`, build `26300`,
x64. Inspection read only the installed application's executable metadata and
shipped bundle under its program directory. No user conversation, trajectory,
authentication, account configuration, app storage, or log file was read.
No screenshot, raw private output, or bundled executable was copied into this
repository. Program paths below use `%LOCALAPPDATA%` to avoid publishing the
machine's user identifier.

The browser automation tool exposes no native Windows API. A separate installed
Computer Use plugin provides `@oai/sky` native window control; its skill and
guidance were read before preparing any app interaction. Thus native UI testing
is potentially available, but this research itself performs no app invocation,
conversation, installation, permission change or account mutation. A missing
live receipt is unknown, even when a supported tool or executable exists.

## Antigravity conversation application

Google identifies Antigravity 2.0 as a standalone desktop application for
knowledge and coding tasks, independent of the IDE. Qualify the conversation
application's Local project, rather than substituting an IDE, Gemini CLI, web,
mobile, or Antigravity CLI result. [Official application overview](https://antigravity.google/docs/overview)

| Intended scope | Owned controller | Owned standalone skill |
| --- | --- | --- |
| Workspace | `<workspace>/.agents/rules/opensocrates.md` | `<workspace>/.agents/skills/opensocrates/SKILL.md` |
| Global | `<home>/.gemini/config/rules/opensocrates.md` | `<home>/.gemini/config/skills/opensocrates/SKILL.md` |

The app's Rules UI is in Customizations. Modular rules require valid YAML
frontmatter; use `trigger: always_on`, with a description. Missing or camelCase
triggers are discarded. Immediate Markdown children are scanned; nested rules
need `.agents/rules.json`. Existing `AGENTS.md`, `GEMINI.md` and unrelated modular
rules remain user-owned. Active rules accumulate, with more specific directory
rules winning conflicts. Files have a 24,000-byte expanded limit and active
global/always-on rules share 20,000 tokens. [Official rules](https://antigravity.google/docs/rules)

```yaml
---
trigger: always_on
description: "Use grounded reasoning for synthesis, decisions, and stakeholder communication."
---
```

The table's skill folders contain `SKILL.md` with YAML metadata. Keep explicit
`name: opensocrates` and a concrete `description`; description is required.
The app discovers metadata at conversation start and reads the full skill when
relevant. This model-selected activation is distinct from the always-on rule.
The current primary paths use plural `.agents`; do not create a second legacy
`.agent` copy. [Official skills](https://antigravity.google/docs/skills)

An optional app plugin transport uses `.agents/plugins/<name>` or
`~/.gemini/config/plugins/<name>`. CLI plugin staging uses
`~/.gemini/antigravity-cli/plugins/<name>`. Cross-surface synchronization is
documented, but a CLI listing does not establish this candidate's app entry.
Keep the modular route until separately qualified plugin behavior warrants a
route change. [Official plugins](https://antigravity.google/docs/plugins)

Windows currently uses the documented previous permission system. Workspace
files are normally accessible; outside-workspace reads can require approval.
Test global canonical references under the actual project permissions, and
record a denied or missing read as unavailable. Do not broaden access or change
security settings to manufacture a pass. [Official Windows permissions](https://antigravity.google/docs/permissions)

### Installed bundle findings

The program at
`%LOCALAPPDATA%/Programs/Antigravity/Antigravity.exe` reports FileVersion
`2.19.1` and ProductVersion `2.19.1.0`. Its
`resources/app.asar:package.json` independently reports package version `2.19.1`,
product name Antigravity and an agentic desktop application description.

The ASAR header was parsed in memory, then only these shipped code members were
read: `package.json`, `dist/paths.js`, `dist/languageServer.js`,
`dist/services/settingsService.js`, and `dist/ipcHandlers.js`. The wrapper's
`getSettingsPbPath()` derives `.gemini/config/config.json` using `os.homedir()`
and the platform path API. Its packaged Windows service path selects
`resources/bin/language_server.exe`. These findings support deriving the home
directory through the platform API; they do not prove that an individual rule
was discovered.

Targeted literal searches of the shipped language-server binary found embedded
customization documentation for `.agents/rules/*.md`, `.agents/skills`,
`.agents/plugins`, global `config/skills`, and `always_on`/`model_decision`.
The embedded text describes progressive skill loading, path deduplication and
the documented rules budgets. No full binary dump or user data was retained.
Literal presence and embedded documentation are corroboration, not a dynamic
loader trace or successful current installation.

| Public shipped artifact | SHA-256 |
| --- | --- |
| `resources/app.asar` | `341234faf45bd1776fd5418a3c288dedc5487ebfcf153f53d75de17cfe15c1de` |
| ASAR `dist/paths.js` | `43eeac76c59932cbcb398321a2802d9bb2d779155c035ef4895791e54bee769f` |
| ASAR `dist/languageServer.js` | `5c781d05050506d7643a88b1eeadc9bb4f320d7133f84b075e6338a6ce158d26` |
| `resources/bin/language_server.exe` | `d569b7a0fb5c2e3eb6dc867be17e6cde1ad1fac94c7dcda2909d6612c7c31532` |

## Claude Windows surfaces and version boundaries

Current user scope includes only Claude account Web/Desktop Chat and Cowork.
Both terminal Code and Desktop local Code are excluded from new Windows support;
existing Mac implementation remains historical/retained work. Native details
below are host research and version context, not a Windows deliverable or
mandatory installation, authentication or acceptance step. Do not restore
native Code support requirements from older plans.

Claude Desktop's local Code tab shares the CLI engine, project instructions,
settings, skills and hooks. Its plugin browser can install and manage plugins
for local sessions; cloud and WSL sessions have different plugin behavior.
Keep local Desktop Code, terminal Code, account Chat and Cowork distinct.
`claude --desktop` requires Code `2.1.285+`, macOS or x64 Windows, and a Claude
subscription sign-in; API-key sessions cannot use that transfer route. Record
Desktop and CLI engine versions separately rather than inferring one from the
other. [Official Desktop Code reference](https://code.claude.com/docs/en/desktop)

Native Windows Code can use PowerShell without Git Bash. Git for Windows is
optional and enables its Bash tool; native host availability does not qualify
OpenSocrates's launcher. This stage supplies no native Code Windows candidate.
[Official setup](https://code.claude.com/docs/en/setup)

The Code hook guide documents command hooks and `SessionStart`/
`UserPromptSubmit` delivery. Preserve host trust requirements and observe the
candidate's actual hook entry; do not treat an enabled skill as deterministic
ordinary-request delivery. [Official hook guide](https://code.claude.com/docs/en/hooks-guide)

Account skills are managed in Customize; standalone skill ZIPs contain one
root skill folder and require code execution enabled. Upload acceptance proves
format acceptance only. [Official custom skill packaging](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)

Cowork/cloud skills come from the account rather than the machine's ordinary
`~/.claude/skills/` directory. Signed-in terminal skill synchronization is
documented for Code `2.1.273+`; API-key or supplied-token sessions and sessions
without required feature-flag access do not establish that route. Synced files
are downloaded caches; change the account origin rather than editing those
files. Check the displayed origin to detect duplicate local/account controllers.
[Official skills and account synchronization](https://code.claude.com/docs/en/skills)

Account plugins also synchronize into eligible signed-in terminal sessions from
`2.1.273+`. Synchronization can finish after startup and need `/reload-plugins`
or a fresh session. This boundary is independent of the newer Desktop-transfer
boundary. [Official plugin loading](https://code.claude.com/docs/en/plugins/loading)

Chat ignores hooks, while Cowork and Code support hooks under their respective
host conditions. Account Chat/Cowork reject a plugin with top-level `bin/`
executables; a content-only account ZIP cannot establish local native hook or
runtime support. [Official platform support](https://claude.com/docs/plugins/platform-support)

The web reader returned unavailable for plugin-loading/platform-support pages.
Read-only HTTPS requests to the same official URLs returned HTTP 200; research
used their rendered article text, with scripts omitted. This was a research
transport fallback, not an authenticated account or host probe.

## Windows fixture and qualification use

[Fixed EN/KO cases](../../evals/v1.5-windows/fixtures/cases.json) cover workshop
synthesis and separate stakeholder drafts, a changed-capacity continuation,
an exact mechanical table, a settled private-draft decision, and a changed-date
side question while drafting continues. Stage only the source files in a
disposable host folder; keep rubrics, research and parent plans outside its
source scope. Ordinary prompts do not name OpenSocrates or use its command.

The new definitions preserve [Mac findings](../../evals/v1.5-macos/REPORT.md):
Claude's photography absence/assignment claims and draft promise remain partial
outcomes; Antigravity's extra parent-plan read remains a source-isolation limit.
They are regression targets, never retroactive passes or replaced results.

Required new host cells are Claude Web Chat, Desktop Chat and current Cowork,
plus Antigravity conversation-app workspace and global scopes. Codex regression
keeps its existing boundary. Native Windows Claude Code, including Desktop's
local Code tab, is outside this stage's support claim and acceptance matrix.

For each actual cell, retain the candidate digest, app/engine version, selected
scope and origin, ordinary entry, complete canonical reads or unknown, artifact
rubric result, and lifecycle/settings preservation separately. A successful
draft with unknown method application is a valid bounded artifact observation.
Missing native application proof is neither automatic failure of that artifact
nor proof of improved reasoning. Keep failed attempts and any one bounded
repair. Stop unchanged access blockers and continue independent checks.
