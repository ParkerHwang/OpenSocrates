# OpenCode support

OpenSocrates 1.2 adds a provider-neutral OpenCode integration built on the
stable `chat.message` plugin hook and OpenCode's native Agent Skill discovery.
The minimum live-verified host version is OpenCode 1.18.18.

## Architecture

OpenCode automatically loads the installed bridge from
`~/.config/opencode/plugins/opensocrates.js`. For bounded judgment-heavy user
requests, that dependency-free bridge selects one method locally and appends
one synthetic text part containing the method's complete authored procedure.
The mutation happens before message persistence and model dispatch, so the
grounded procedure is available in the same model turn. Mechanical requests,
explicit `/opensocrates` requests, unsupported parts, oversized inputs,
and exceptions leave the original request unchanged.

The native `opensocrates` Agent Skill is installed at
`~/.config/opencode/skills/opensocrates/SKILL.md`. It is always available as the
explicit content-first fallback. The generated bridge does not call a model,
make a network request, spawn a process, recursively invoke OpenCode, start a
session, read credentials, or depend on a provider/model identifier. In
particular, DeepSeek V4 Flash is a smoke-tested provider, not a hardcoded
dependency.

The beta V2 plugin package is not used. The bridge targets the stable V1
`@opencode-ai/plugin` `chat.message` contract.

## Grounding and fail-open contract

The bridge can inject at most one complete authored method. It never claims a
method merely from catalog metadata. This preserves the OpenSocrates grounding
contract: a method may be claimed only after its complete procedure has been
loaded in the current conversation.

Selection is a conservative, bounded local heuristic. The bridge accepts at
most 128 message parts, 64 KiB of public prompt text, and a 48 KiB injection.
Selection runs synchronously over that capped input using a fixed set of
linear, backtracking-free patterns, so the work is bounded by input size
rather than by a wall-clock deadline; OpenCode's stable `chat.message`
contract is awaited without a host-side deadline or cancellation signal. The
bridge marks its synthetic part and suppresses a duplicate injection. Any
parsing, selection, or mutation failure is caught so the original prompt
continues normally.

## Installation and ownership

Use the same lifecycle CLI as other hosts:

```sh
npx --yes opensocrates@1.2.0 install --host opencode
npx --yes opensocrates@1.2.0 status --host opencode
npx --yes opensocrates@1.2.0 verify --host opencode
npx --yes opensocrates@1.2.0 update --host opencode
npx --yes opensocrates@1.2.0 remove --host opencode
```

`--host all` includes OpenCode. The installer owns only these exact paths:

- `~/.config/opencode/plugins/opensocrates.js`
- `~/.config/opencode/plugins/.opensocrates-managed.json`
- `~/.config/opencode/skills/opensocrates/`

It never rewrites `opencode.json` and preserves every unrelated plugin, skill,
and config file. Existing exact paths must carry valid ownership metadata and
checksums; partial, unowned, symbolic-link, or unsupported filesystem entries
are refused. Install/update stage the skill, bridge, sidecar, and complete
installed inventory before activation. Existing owned files are moved to
unique backups and restored if any later host or desired-state step fails.
Remove uses the same reversible backup boundary before commit.

Package verification covers the outer checksum, safe and complete ZIP
inventory, package checksums, release manifest, OpenCode package manifest,
stable bridge/skill files, and absence of an unexpected native runtime. When an
OpenCode installation is present, `verify` additionally checks the ownership
marker, sidecar, bridge hash, and complete managed-skill inventory.

## Validation levels

| Behavior | Status | Basis |
|---|---|---|
| Deterministic package and archive inventory | Validated | Release gate and byte-identical generation tests |
| Bridge parsing, limits, duplicate prevention, exception fail-open | Validated | Offline Node tests against the generated bridge |
| Install/status/verify/update/remove and unrelated-file preservation | Validated | Isolated lifecycle tests |
| Global plugin and native skill discovery | Live validated | OpenCode 1.18.18 isolated invocation |
| Same-turn `chat.message` mutation with the production bridge | Live validated | `opencode run` and interactive TUI on OpenCode 1.18.18 |
| DeepSeek V4 Flash compatibility | Provider-specific live smoke | Existing OpenCode provider; no credential change |
| Interactive TUI receipt | Live validated | Production bridge, fixed probe prompt, and existing DeepSeek V4 Flash provider |
| Native skill invocation receipt | Unverified | Discovery validated; invocation was not claimed |
| Other providers and model versions | Unverified | The implementation is provider-neutral, but no matrix receipt exists |

The privacy-safe machine-readable receipt is
[`docs/evidence/opencode-compatibility-2026-08-13.json`](evidence/opencode-compatibility-2026-08-13.json).
The host contract was checked against the current primary
[plugin documentation](https://opencode.ai/docs/plugins/),
[skill documentation](https://opencode.ai/docs/skills/), and the
[OpenCode v1.18.18 source](https://github.com/anomalyco/opencode/tree/v1.18.18).
