# Grok Build support

OpenSocrates uses a dedicated, content-first native Grok Build plugin. The
package exposes exactly one user-visible `opensocrates` skill and keeps all 48
authored reasoning procedures as internal references. Grok Build can select
the skill in the current turn, and the user can always invoke
`/opensocrates` explicitly.

## Verified boundary

The compatibility probe used installed Grok Build
`1.0.3 (1a29d5bc12d4) [stable]` on 2026-08-13. The closest public source
revision inspected was Git commit `e5fd4816d43260c15ba785f103990c1ed6cea230`,
whose `SOURCE_REV` was `ea094a8c369475f97c85540d01730baec0dce5d6`.
The installed build revision is not present in the public repository history,
so source-only conclusions are identified separately from live observations.

Primary sources:

- [Skills, plugins, and marketplaces](https://docs.x.ai/build/features/skills-plugins-marketplaces)
- [Hooks](https://docs.x.ai/build/features/hooks)
- [Grok Build source](https://github.com/xai-org/grok-build)
- The source-tree user guide under
  `crates/codegen/xai-grok-pager/docs/user-guide/`

Live observations on 1.0.3:

- A native plugin at `~/.grok/plugins/opensocrates` is discovered and enabled
  without adding an installed-marketplace registration.
- Automatic native skill selection produced the probe marker in headless
  `grok -p` in the same model turn.
- Explicit `/opensocrates` invocation produced the probe marker in headless
  mode.
- Hook execution was visible in both the TUI and headless mode for a temporary
  global diagnostic hook.
- `UserPromptSubmit` included the current prompt, but plain stdout and
  Claude-compatible `hookSpecificOutput.additionalContext` did not become
  model-visible. Passive hook output is therefore not an injection mechanism.
- A trusted, CLI-installed native probe plugin advertised hooks in inspection,
  but its hook definitions were not merged into the active 1.0.3 hook registry.
- `SubagentStart` and `SubagentStop` fired during a live child-agent probe.
  OpenSocrates skill propagation and duplicate activation inside subagents were
  not independently proven, so no subagent capability is claimed.
- TUI native skill activation itself was not independently marker-tested; TUI
  host hook execution was. Headless native automatic and explicit invocation
  were marker-tested.
- Compaction was not triggered in a live session. Its payload shape is
  source-inspected only.
- `PostToolUse` included tool name, tool input/result, truncation flags, tool
  use ID, and background state. That host payload is structurally sufficient
  to recognize a read result, but installed 1.0.3 did not activate plugin hooks
  and the shipped package has no observer, so grounding observation remains
  unavailable.
- A temporary one-second `UserPromptSubmit` timeout was enforced at 1006 ms;
  Grok logged the timeout and continued the same request successfully. Passive
  hook timeout is therefore fail-open for this observed surface.
- A temporary `Stop` hook returned the documented blocking decision once. Grok
  made a second model turn with the supplied reason and then stopped, proving
  that `Stop` can request bounded continuation rather than observation only.

The CLI lifecycle probe also established these ownership details:

- `grok plugin install <path>` without `--trust` refused the local plugin and
  left no installation. Adding `--trust` installed it enabled.
- `grok plugin disable`, `enable`, and `uninstall` worked for that CLI-managed
  installation. `grok plugin list --json` reported installation but not the
  enabled bit; `grok inspect --json` reported enabled/disabled state and the
  component inventory.
- A direct user plugin was visible to `inspect` but not to `plugin list`, and
  the enable/disable commands could not address it. The installer therefore
  owns the exact direct path and uses inspection for state, without writing
  Grok's unrelated configuration. A user-level disabled entry is reported and
  must be cleared by the user rather than silently edited.

The privacy-safe compatibility record is
[`docs/evidence/grok-build-1.0.3-compatibility.json`](evidence/grok-build-1.0.3-compatibility.json).

## Architecture decision

The selected architecture is a dedicated native Grok content package with no
runtime hooks. This is the smallest design that gives Grok correct host
identity, native same-turn selection, an explicit fallback, deterministic
packaging, and independent lifecycle ownership.

The alternatives were rejected as follows:

- Reusing the Claude package would share lifecycle ownership, expose a
  Claude-specific selector and hook contract, and make one host's removal
  affect the other.
- A native package that reused hook templates would claim behavior absent in
  installed 1.0.3: plugin hooks were not activated and passive prompt-hook
  output was ignored.
- A Grok-specific runtime adapter would add executable surface without a
  verified injection or continuation path.
- A nested `grok -p` selector was not used. Its recursion, plugin isolation,
  latency, cost, and session side effects were not all provable, and native
  skill selection already supplies same-turn activation without a second model
  request.

## Capability profile

| Capability | Classification | Evidence |
| --- | --- | --- |
| Prompt context injection | Degraded | Native skill context is available; passive hook output is ignored |
| Automatic method selection | Supported | Live headless native-skill probe |
| Explicit method skill invocation | Supported | Live headless slash invocation |
| Tool-event observation | Unavailable in shipped package | Host payload observed, but package has no hooks/runtime |
| Local record writes | Unavailable | Content-only package |
| Grounding/read observation | Unavailable | No `PostToolUse` runtime |
| Completion interception/continuation | Unavailable in shipped package | Host continuation live-probed; package has no `Stop` hook/runtime |
| Compaction lifecycle | Unavailable | No runtime; source shape only, no live compaction receipt |
| Subagent propagation | Unknown | Lifecycle events observed; skill propagation not proven |
| Deterministic trace rendering | Unavailable | No renderer/runtime |
| Rich card/widget rendering | Unavailable | No widget surface |

The grounding rule remains strict: OpenSocrates may apply, name, or cite a
method only after the complete authored procedure was read in the current
conversation.

## Installation and coexistence

Install and manage the Grok package with:

```bash
npx --yes opensocrates@1.2.0 install --host grok
npx --yes opensocrates@1.2.0 status --host grok
npx --yes opensocrates@1.2.0 verify --host grok
npx --yes opensocrates@1.2.0 update --host grok
npx --yes opensocrates@1.2.0 remove --host grok
```

The installer owns only `~/.grok/plugins/opensocrates` and its exact ownership
marker. It rejects symlinks, unowned roots, unsafe archive entries, incomplete
inventories, and mismatched host/name/version metadata. Installation and
updates stage before atomic activation; removal and activation retain a
rollback backup until the operation commits. Both transient directories, the
staging tree and the rollback backup, are created directly under the Grok home
rather than inside its scanned `plugins/` directory, so neither an in-flight
nor an interrupted operation can leave a second discoverable copy of the
plugin. No unrelated Grok config, marketplace, skill, plugin, or hook entry is
edited.

Install and update require the `grok` command, because activation is confirmed
against `grok inspect --json`. Status and removal do not: the managed files are
host-independent content, so a user who has uninstalled Grok Build can still
inspect and remove them. When inspection is unavailable in those read-only and
removal paths, the installer says so and reports the managed files alone
instead of claiming host-confirmed state.

Grok also discovers Claude-compatible plugins. A native user plugin with the
same `opensocrates` name takes precedence; an isolated live inspection showed
one native plugin and one native skill rather than two activations. The Grok
installer path never deletes, disables, or rewrites the Claude installation.

## Next acceptance test

On the minimum supported Grok Build version, install the generated release ZIP
through the installer into a clean profile, open the TUI, and use a judgment
prompt whose answer can include a privacy-safe marker proving native skill
activation. Then delegate the same task to a subagent and record only
categorical activation counts. This would close the remaining TUI native-skill
and subagent-propagation gaps without retaining prompts or transcripts.
