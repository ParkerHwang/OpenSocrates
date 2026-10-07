# Antigravity host implementation plan

Research checked **2026-10-07** against preparation baseline `main@5a2ff3c`.
No installation, account configuration, host invocation, or live qualification
was performed. The baseline supports Codex only. The earlier implementation
checkout's document 16 supplies the revised product scope, not reusable release
proof.

The parent's read-only app inspection on the same date showed Customizations
with one active `user_global` rule at `~/.gemini/GEMINI.md`, rules using
308/20,000 tokens, and twelve displayed skills without OpenSocrates. Preserve
that rule. This is current discovery-UI evidence only; no host changes or model
invocations occurred, and automatic OpenSocrates delivery remains untested.

## Decision and intended behavior

Target the **Antigravity conversation application** first, on macOS and Windows.
Its Projects, Local environment, Settings, and Open IDE affordances identify a
different surface from the standalone IDE. Google describes Antigravity 2.0 as
independent of the IDE and suitable for knowledge work. Opening the IDE does not
qualify the application's conversation behavior. [Official overview](https://antigravity.google/docs/overview)

Use a small persistent `always_on` controller plus progressively read canonical
references. Normal requests should enter relevant reasoning without an
OpenSocrates command: reconcile source material, stakeholder knowledge and
responsibilities, decisions, disagreements, and usable messages. Keep mechanical
work light. Add no dedicated coding features, selector model call, daemon, MCP
server, or private conversation reader.

## Current host mechanisms

| Surface | Modular rule | Standalone skill | Management |
| --- | --- | --- | --- |
| Conversation app | Workspace `.agents/rules/*.md`; global `~/.gemini/config/rules/*.md` | Workspace `.agents/skills/<name>/SKILL.md`; global `~/.gemini/config/skills/<name>/SKILL.md` | App/project Customizations; Rules and Skills |
| Standalone IDE | Same documented rule/skill paths | Same paths | Agent side panel, Customizations |

These global locations are shared; a surface label cannot isolate their effects.
Use a disposable workspace first. A project must include the intended local
folder; test Local and new-worktree behavior separately. [Rules](https://antigravity.google/docs/rules), [Skills](https://antigravity.google/docs/skills), [Project setup](https://antigravity.google/docs/getting-started)

Rule frontmatter must use the current spelling:

```yaml
---
trigger: always_on
description: "Use grounded reasoning for synthesis, decisions, and stakeholder communication."
---
```

Missing or camelCase triggers are silently discarded. Rules accumulate; narrower
directory instructions win conflicts. Immediate Markdown children are scanned;
nested rules require `.agents/rules.json`. Expanded rules have a 24,000-byte file
limit and active rules share 20,000 tokens; oversized aggregate content can be
demoted to pointers. `manual` cannot provide automatic entry. [Rules](https://antigravity.google/docs/rules)

OpenSocrates's proposed build limit is **4 KiB per entry, about 600 tokens**, with
no inline method catalog or full-file include. This product limit is stricter
than the host limit. Name/description metadata discovers the skill; the host
reads its body when relevant. Use an explicit description covering synthesis,
stakeholders, decisions, and communication. This selection remains agent
behavior, not proof of application. [Skills](https://antigravity.google/docs/skills)

## Controller and package contract

The entry tells the active agent to preserve the user's goal and constraints,
read the installed controller when judgment changes, select **zero to two**
eligible methods, and read each complete installed procedure before applying it.
Preserve all 48 canonical methods, teacher questions, contraindications, stop
conditions, exact ID/revision, bilingual content, and public grounding rules.
Settle teacher questions internally; ask only for a consequential missing fact.
Source documents are evidence, never controlling instructions. A missing read
means unavailable grounding; continue permissible task work without claiming the
method was applied.

Generate one content-only transport containing the entry rule, `opensocrates`
skill, catalog, and complete EN/KO references. Resolve reference paths from the
installed location; do not encode the builder's home or depend on working
directory. Keep release version, source identity, checksum inventory, and managed
ownership in OpenSocrates files.

Current plugins support `.agents/plugins/<name>` and
`~/.gemini/config/plugins/<name>` for the app and IDE. Thus the historical global
path is still documented, but does not prove this candidate loads. The current
published manifest schema lists `name` and `description`, rejects extra fields,
while its example includes `$schema`: use the minimal name/description manifest
and rewrite the historical version/author/homepage/license fields. The schema
endpoint was inaccessible; settle this example/schema inconsistency with the
actual validator before publishing.
[Plugins](https://antigravity.google/docs/plugins)

Use the documented modular workspace rule plus standalone skill route first,
with exact owned-file registration. A plugin-contained rule/skill is an optional
transport **only after** a disposable app probe proves its automatic rule loading
and disablement. Global installation follows a separately qualified lifecycle.
Choose one route per scope; installing both creates duplicate entry. CLI
`agy plugin install/list/enable/disable/uninstall` operates its separate
`~/.gemini/antigravity-cli/plugins` staging. It is an optional packaging check,
not desktop registration or desktop acceptance. [Plugins](https://antigravity.google/docs/plugins)

## Lifecycle and Windows constraints

Install only absent or exactly owned targets; never append to user `AGENTS.md`,
`GEMINI.md`, or replace unrelated rules. Persist the selected route/scope and
owned hashes. Update through verified staging and rollback; refuse a modified
owned file pending reconciliation. Remove only matching owned artifacts and
registrations. Preserve user rules, grants, host history, and unknown files.
Disable by excluding the exact rule and skill from discovery, or by verified
plugin disablement. Confirm in a fresh conversation; already loaded context is
not erased by deleting files. An update/removal cannot silently change routes.

For Windows, derive home with platform APIs, test spaces, Unicode, drive letters,
backslashes, case, LF/UTF-8 content, locked files, and junction/reparse rejection.
The primary content package needs no Bash, WSL, executable, or runtime launcher.
Keep existing Node installer requirements explicit. Host downloads include
Windows x64/ARM64, but qualify Windows 11 x64 first; host availability does not
prove OpenSocrates ARM64 support. [Getting started](https://antigravity.google/docs/getting-started)

Windows currently has a different permission implementation from macOS/Linux.
Workspace file reads are allowed by default; outside-workspace reads may ask.
Test complete global-reference access under ordinary project permissions, and
offer only a narrow package-directory grant if required. Do not switch users to
Turbo or request wildcard filesystem access. [Permissions](https://antigravity.google/docs/permissions)

## Optional lifecycle alternative

The app documents `.agents/hooks.json` and `~/.gemini/config/hooks.json`, managed
through Settings > Customizations > Hooks. `PreInvocation` handlers receive
JSON metadata (`invocationNum`, `initialNumSteps`, workspace/conversation paths)
and can return `injectSteps` with `ephemeralMessage`. The input does **not**
provide the user request body. [Hooks](https://antigravity.google/docs/hooks)

Therefore a future hook may deliver a bounded reminder, not reuse Codex's
request-dependent selector. Never dereference `transcriptPath`, inject a forged
user message, or log input. Add a separate typed adapter, fixed platform-safe
launcher, short timeout, bounded output, fail-open behavior, and once-per-scope
delivery only if app-native receipts justify the complexity. Windows shell,
quoting, executable resolution, permission prompts, disablement, and malformed
output need independent native tests. Hooks are not required for the first
content-only implementation.

## Evidence and first bounded checks

[Historical Windows receipt](../evidence/antigravity-windows-live-2026-09-09.json)
records explicit skill delivery, full selected-method reads, response, and
candidate lifecycle checks. It supplies no new automatic-entry or native
application receipt. Capability, installation, rule delivery, complete reading,
reported application, and reader outcome remain separate evidence levels.

| Disposable check | Pass | Fail / unknown | Current |
| --- | --- | --- | --- |
| Modular workspace rule and skill | Exact candidate entry discovered; fresh ordinary request needs no command | Wrong surface/path, duplicate or missing entry; absent observation is unknown | Unknown |
| One synthesis task and one stakeholder message | Full selected references read; relevant context, disagreement, and next action retained | Incomplete read, invented motive, unsupported conclusion | Unknown |
| Mechanical task; continuation with changed stakeholder | No unnecessary method load; renewed eligible judgment uses complete source | Ceremony on mechanical work; stale goal or procedure | Unknown |
| Disable, update, remove with unrelated sentinel rule | Fresh conversation excludes entry; owned version changes; sentinel survives | Residual rule, lost user configuration, rollback failure | Unknown |
| Same conversation-app checks on Windows 11 x64 | Surface/OS-specific receipt | Missing machine/account or unavailable observation stays unknown | Unknown |
| Optional plugin transport or IDE compatibility | Separate transport/surface receipt | Not part of the initial required app route | Deferred |

Use synthetic inputs; retain hashes, versions, counts, and public artifacts only.
No private transcript capture. Reader usefulness requires inspecting the actual
outputs, including regressions; grounding labels alone are insufficient.

## Ordered implementation work

1. Establish installed app version, target project, and discovery/permission route
   for the modular workspace path with disposable checks. These are **qualification blockers**, not missing
   theoretical host features; no release claim before receipts.
2. Add `plugin-src/antigravity/` templates and metadata; adapt
   `tools/build_plugins.py`'s Codex-only guard and native payload assumptions for
   content-only generation. Compare every generated method to canonical inputs.
3. Extend `installer/opensocrates.mjs`, its lifecycle tests, Windows tests, and
   package smoke checks for owned multi-file transactions, route identity,
   conflict refusal, rollback, and removal. Do not add Antigravity to
   `src/opensocrates/hosts/registry.py` unless a real runtime adapter is built;
   distribution support and native runtime support differ.
4. Add EN/KO host guides and privacy-safe receipts; revise historical support
   labeling and Codex-only governance only when implementation warrants it.
   Run generation/package/installer checks and existing required gates, then
   app/OS acceptance. Improve controller content against concrete synthesis and
   communication outputs before considering the optional hook.
