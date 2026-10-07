# Claude host plan

Status: implementation proposal; official sources checked **2026-10-07**. Baseline:
`main@5a2ff3c`; prior candidate `f04d57fa` is reference-only. No installation,
configuration mutation, or model-outcome test was performed for this plan.

## Recommendation and contract

Deliver general reasoning assistance for understandable synthesis, stakeholder
context, decisions, and messages. Preserve all 48 canonical methods, bilingual
controller, contraindications, dependencies, stops, public outputs, grounding,
and `DecisionSession` contracts. Add no coding-specialist entry or selector-model
call. Generate two distribution profiles from identical canonical content:

1. **Account content package:** a standalone `opensocrates` skill ZIP for ordinary
   Chat and Cowork, matching the inspected Customize > Skills route. A binless
   account plugin is an optional later transport after qualification.
2. **Native Code package:** local macOS/Windows plugin with deterministic hook
   bootstrap and packaged `decision` runtime. An installation using both
   profiles must expose only one discovery controller; the native companion
   profile supplies hooks/runtime and internal references without advertising
   another controller.

The standalone account package is the first complete portable path, paired with
an opt-in standing instruction. A binless account plugin or Cowork hook profile
is a subsequent gated extension, not an assumed property of this package.

## Host boundaries

| Surface | Ordinary-request entry | Guarantee and limit |
| --- | --- | --- |
| Claude Code CLI, macOS/native Windows | Trusted, enabled `SessionStart` and `UserPromptSubmit` hooks inject the controller entry | Deterministic event delivery under the tested host configuration; application remains unverified. Skills alone are selected by the model. [Hooks guide](https://code.claude.com/docs/en/hooks-guide) |
| Desktop **local Code** | Same local configuration/hook route; GUI plugin management | Test separately from CLI. Desktop cloud/SSH/WSL are separate configurations; Desktop WSL sessions do not support plugins. [Desktop Code](https://code.claude.com/docs/en/desktop) |
| Web Chat / Desktop ordinary Chat | Enabled account skill, matched from its description | No documented every-message enforcement: Chat ignores plugin hooks. No repeated slash command is required for matching tasks, but selection can be missed. [Platform support](https://claude.com/docs/plugins/platform-support), [Use skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude) |
| Cowork / merged Claude experience | Account skill; account plugin hooks are supported on the documented Cowork surface | Cloud-specific hook execution and payloads need fresh evidence. A local Code install does not install an account plugin. [Plugin loading](https://code.claude.com/docs/en/plugins/loading) |

On October 6, new Pro/Max Cowork tasks moved to cloud execution; older local
tasks remain local. The Chat/Cowork merge rolls out by account, starting with
Pro/Max; Team/Enterprise cloud availability remains beta. Desktop connectivity
is needed for local resources, even when the task runs remotely. Record plan,
surface, rollout variant, task origin, and version separately. Do not infer
capability from an absent mode selector. [Cowork across surfaces](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile),
[Merged experience](https://support.claude.com/en/articles/16761823-claude-cowork-and-chat-are-one-claude).

## Entry, payload, and lifecycle

Implement explicit Claude normalization in proposed
`src/opensocrates/hosts/claude/{events,native,responses,adapter,capability,commands}.py`;
extend `hosts/registry.py` and host enums only after contract fixtures exist.
Reuse shared `HostAction`/selector interfaces, not the Codex parser wholesale.
The historical `v1.3.1` Claude adapter, commands, and
`docs/claude-payload-receipts.md` identify seams; their stub-backed/macOS receipts
are historical evidence, not current Claude or Windows validation.

For native Code, parse bounded stdin JSON containing `hook_event_name`,
`session_id`, optional `prompt_id`, and event-specific fields. Never open
`transcript_path` or retain raw `prompt`/assistant text. Missing identity degrades
evidence. Emit `hookSpecificOutput` with the exact event name and
`additionalContext` for bootstrap. Observe successful full `Read` deliveries
through `PostToolUse` only where the supported callback exposes them. Default
`Stop` is fail-open/no-op or owned metadata cleanup. Missing native read receipts
or `application: unverified` never trigger a repair. A separately qualified
repair for a confirmed incomplete canonical read may occur at most once and
must respect `stop_hook_active`. `SessionEnd` only cleans up and cannot block exit.
Use a cleanup target below its shared default 1.5-second budget. [Hook reference](https://code.claude.com/docs/en/hooks).

Hooks deliver standing controller rules before ordinary requests; the active
agent still recognizes later materially changed judgments. Reconsider changes
in objective, alternatives, evidence, assumptions, or consequential risk, not
every tool call. Native `decision` stays deterministic, network-free, and
volatile. Context handoff creates a fresh handle; compaction increments epoch;
task end closes the stream. Cleanup must also cover interruption/crash through
bounded expiry of any adapter-owned receipt metadata. Do not persist reasoning,
workspace contents, or a hidden method cache.

## Minimal complete loading

Discovery metadata must name concrete everyday tasks. After entry, load the
complete canonical controller and decision guide once per available context,
then routing metadata, then the smallest eligible set of **complete** procedures
and explicitly required dependencies. Preserve method IDs, locale, revision,
and digests in both profiles. Do not replace procedures with summaries or load
all 48 into every prompt. Mechanical work and an empty eligible selection need
no method.

Native Code uses `decision` first. Account delivery uses packaged catalog and
full method files when that runtime is unavailable; it performs the same
eligibility checks. Partial/truncated/missing reads prohibit method application.
Only actually applied, fully read methods appear in the grounding line. A native
tool result proves delivery only; an acknowledgment is an agent assertion;
neither proves application or improved usefulness. Recheck availability after
compaction rather than assuming all content survived. Skill selection and
progressive disclosure are host behavior, not an activation guarantee.
[Code skills](https://code.claude.com/docs/en/skills),
[Custom skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills).

## Package and installer seams

Add reviewed `plugin-src/claude/` profiles and `tools/build_plugins.py` support;
the current builder explicitly accepts only Codex. Generate controller and
references from canonical sources and retain content/semantic hashes. Account
plugin: `.claude-plugin/plugin.json`, one `skills/opensocrates/SKILL.md`, internal
references, notices, and release manifest; **no top-level `bin/` executables**,
which cause Chat/Cowork to reject the package. Standalone ZIP has one root skill
directory, uses standard frontmatter, and needs code execution enabled.
[Platform support](https://claude.com/docs/plugins/platform-support),
[Custom skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills).

Native profile uses exec-form launcher arguments and separate verified
`darwin-arm64`/`windows-x64` assets. Windows must cover PowerShell without Git
Bash, spaces, Unicode, stdin/stdout encoding, private ACLs, reparse-point rejection,
and interrupted transactions. Do not require WSL, administrator privileges, or
shell installation. Claude Code supports native Windows; that does not certify
our runtime. [Code setup](https://code.claude.com/docs/en/setup).
Initial native targets are Apple-silicon macOS and Windows x64; Intel macOS and
Windows ARM64 need separately approved build/test cells before support claims.

Extend `installer/opensocrates.mjs` host layout, registration, status, diagnose,
update, rollback, and ownership checks; adapt native build/launcher tests.
Use Claude's supported plugin operations and merge only owned registration
keys. Preserve unrelated settings/hooks/plugins and existing disabled state.
Never overwrite `CLAUDE.md`, remove Claude itself, or reset global trust.
Disable before removal; delete only verified owned files. Reload/restart and
verify effective loaded origin/version after each lifecycle action.
[Code plugin management](https://code.claude.com/docs/en/plugins/install).

Account upload/update/disable/remove stays in Customize and requires account
verification. Marketplace synchronization and Code synchronization are separate
update paths; never edit downloaded synced files. Avoid duplicate local/account
origins. Account plugins sync into signed-in Code from 2.1.273, not API-key
sessions. [Account plugin management](https://claude.com/docs/plugins/overview),
[Plugin loading](https://code.claude.com/docs/en/plugins/loading).

Parent UI inspection found an enabled user-created `opensocrates` skill dated
August 11 whose `SKILL.md` status instruction names **1.1.2**, content revision 1,
and 48 systems. The UI label `opensocrates v1` is an account revision, not product
1.4. Desktop bundle is 2.26454.0; `claude` is absent from PATH. These observations
prove availability/configured text, not execution or exact package hash.
Qualify the replacement in an approved isolated account/project test scope first;
creating another account is not required. Before migration, export only
the owned old skill and preserve its bytes/enabled state; stage a distinctly
named disabled candidate, then reversibly switch one controller on, verify, and
retain the old archive. Never delete the existing skill before qualification.

## Bounded first tests and closure

Use disposable host homes/workspaces and an approved account test scope: CLI macOS/Windows,
Desktop local Code macOS/Windows, Web Chat, Desktop Chat, and current cloud
Cowork. Keep older local Cowork a separate historical-compatibility cell.
Run two ordinary judgment prompts and one mechanical control per cell, then
one second-turn change and one fresh-session lifecycle check. Use synthetic
stakeholder notes and a decision/message task; no unrelated account changes or sends.
One repair per failed case, then record failure and stop that cell.

Record four distinct fields: capability/origin/version; complete canonical-read
evidence or unknown; application evidence (`unverified` unless independently
supported); requested artifact/result rubric. Check synthesis fidelity,
stakeholder distinctions, actionable choice/message, uncertainty, and grounding.
Record missed automatic selections separately from answer quality.

Close a host cell only after current payload fixtures where hooks apply,
otherwise account loading observations; complete content identity,
ordinary-entry observations; bounded repair/fail-open behavior;
update/disable/remove/rollback, unrelated-settings preservation, and clean
restart pass at the exact candidate digest. Close release only when every claimed
cell passes; mark inaccessible cells `BLOCKED`, not passed. This plan proves no
live activation or answer improvement. Every-message Chat enforcement is
unavailable under documented hooks; portable cloud Cowork hook/runtime behavior
remains unverified. Alternatives are explicit invocation for missed selection,
opt-in project instructions for stronger standing context, or a separately
qualified account hook profile; none silently upgrades the guarantee.
