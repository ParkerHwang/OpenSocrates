# Decision-point retrieval and migration

Status: v1.3.0 release work; content revision 3, router 1.1.0. Canonical method bodies retain the v1.2.1 wording.
Experimental content revision 2, method variants, language rewrites and Compact
policies have not been promoted. Method IDs remain unchanged.

## Use in the current turn

Keep task goals, permissions, constraints and completion conditions available.
Activate the controller when a materially changed judgment needs help; do not
wait for another user message. It links locale-specific decision guides, compact
routing metadata and exact complete canonical instructions. Do not load a method
for mechanical steps. Upstream constraints must be read before they affect a choice.

When the packaged runtime and shell are available, Claude/Codex use native
`catalog` and `select` first. Include known missing prerequisites in the closed
features, use a separate decision identity for a distinct question, and leave
`explicit_method` null unless the user explicitly requested a method. An empty
eligible set is valid, not a reason to bypass eligibility with file lookup.
Runtime/shell unavailability or failure permits the existing complete-reference
fallback with the same contraindications and global constraints. Other hosts
retain their file path. This is guided host behavior; the selector does not
verify feature classification, freeform semantics or actual method application.

For multiple questions, retain a separate public conclusion, missing inputs and
reopening evidence for each, using the user's requested format. Conditions are
shared only when an explicit dependency justifies sharing them. Reading a method
to establish that it cannot apply does not activate its output requirements for
another question or justify citing it as applied.

The installed Claude/Codex package exposes:

```sh
cat skills/opensocrates/references/decision/request.json | ./bin/launch.sh decision codex
```

Replace the example's closed features and opaque context handle with the current
judgment; do not insert prose, paths or instructions into routing fields. Use
`claude` for its package. The source checkout supports:

```sh
PYTHONPATH=src .venv/bin/python -m opensocrates decision --stream
```

The installed launcher also supports `./bin/launch.sh decision codex --stream`
(or `claude`). Keep that one process open for acknowledgments; repeated one-shot
launcher calls cannot share availability state. The stream accepts one JSON object per line. `select` uses the existing routing
feature schema; one judgment uses its established primary/optional-complement
pair (0/1/2). Multiple distinct judgment needs can be evaluated successively
within the same request; file-directed lookup can select the smallest sufficient
set without an artificial one-method restriction. Do not model every tool call as
a new judgment. `catalog` with `locale` returns metadata only. `reset` clears all
volatile availability assertions. Closing or losing the process has the same effect.

After actually reading emitted content, an agent may submit `acknowledge` with
`context`, `epoch` and `digests`. Each digest identifies the exact method, locale,
revision and bytes in that process's emitted inventory. The result is expressly
`agent_reported`, not authenticated host evidence. `applied` remains `unverified`.
Repeated unchanged selections reuse routing; acknowledged available content is
not re-emitted. Without an acknowledgment, a repeat emits again rather than claiming
an unobserved read. No separate model selector is called by this path.

Use a new random 32-character lowercase hexadecimal context handle for each agent
or handoff; increment the nonnegative epoch after compaction. Required references
must then be reread. Reset does not remove already-consumed context tokens. Retain
public decisions, evidence references, unresolved assumptions and remaining work
in the host's normal task record, never private reasoning. The content-only decision process
writes no runtime files and starts no network/authentication or telemetry flow.

One-shot mode accepts exactly one JSON document, including a pretty-printed
multi-line document, and reads it through EOF. The 16,384-character input limit
still applies to the complete document. `--stream` is different: it accepts one
complete JSON object per line, retains the same per-line limit, and may return
multiple responses from one volatile session. Multiple JSON documents supplied
to one-shot mode are malformed rather than silently treated as a stream.

## Host evidence and compatibility

| Host | New in-turn delivery | Evidence level |
| --- | --- | --- |
| Codex | Native CLI first with scoped reference fallback | v1.3.0 P11 observed one in-request native selection and complete reference delivery; submit-hook delivery, semantic classification, application and GUI remain unverified; see the versioned matrix below |
| Claude | Agent CLI where shell is available; reference lookup otherwise | Package/runtime contracts; new live flow unverified |
| Antigravity | Agent reference lookup | Generated package contracts only |
| Cursor | Agent reference lookup | Generated package contracts only |
| Grok | Agent reference lookup | Generated package contracts only |
| OpenCode | Agent reference lookup; existing initial bridge preserved | Package/bridge regression only; no new automatic decision hook |

### Versioned v1.3.0 verification matrix

This matrix is the single status reference for the v1.3.0 Codex/Chat evidence.
Do not promote evidence from one row into another.

| Layer | Exact version/source | Observed status | Boundary |
| --- | --- | --- | --- |
| Published packaged example | v1.3.0, `45bc788`, public Codex ZIP | **Failed.** The 22-line packaged `request.json` returned `decision_unavailable` with exit 0; compact one-line input selected `critical-thinking`, and two NDJSON lines returned two responses. | Confirms a one-shot parser defect, not a selector or stream failure. See the [post-release observation](evidence/v1.3.0-post-release-review.json). |
| Native/package integrity | v1.3.0 release run and 19 published assets | Runtime, package, checksums and point-in-time public byte comparison passed. The prior gate did not execute the pretty-printed example and therefore missed the defect above. | Native package execution is not live Codex host behavior. GitHub reports this release as `immutable: false`. |
| Submission/discovery hook | v1.3.0 Codex package | Hook declarations, launcher behavior, timing and seven locally approved command hashes were checked; no live Codex hook-delivery receipt was captured. | A configured or approved hook is not proof that Codex delivered its output into a task. |
| In-request decision path | P11 source `32d0322`, native Codex archive `sha256:f51be7c9ce4df606e8df98ed4446377e490d2894c8efaa80ed87e6888044031e` | One actual native invocation selected `critical-thinking`; complete `critical-thinking` and `socratic-questioning` references and final delivery were observed. | No complete request literal remained, so feature classification is unverified. Selection, delivery, `agent_reported` reading and application are distinct; `applied` is `unverified`. Final delivery was 384.58s, so the primary 300s result remains a deadline. See [P11 limits](../evals/v1.3/release-guided-20260908/native-verification/observation-limits.json). |
| Codex Desktop GUI | v1.3.0 | Unvalidated. | CLI/package evidence does not establish GUI behavior. |
| Claude Chat cloud upload/activation | v1.3.0 Chat ZIP | Export, layout and reference integrity validated; upload and activation unvalidated. | Local package state cannot establish account-level cloud activation. |

A user-submission hook observes initial submission, not every later decision.
No tool hook can guarantee detection of reasoning-only transitions. The v1.3 default
submission/compact hook delivers discovery only and creates no initial method
obligation for Stop. The existing selector/receipt adapter is retained for legacy
embedders; its stronger native read observations do not transfer to this new
agent-directed path.
The normal discovery hook avoids full content/store composition and never creates
an installation key or product data tree. For migration cleanup only, it reads a
safe existing owner-only key and preserves the existing 24-hour artifact sweep
and session cleanup. Missing, unsafe or read-only roots skip that cleanup fail-open;
they are not created or repaired by discovery. Product data roots are OS-home
based: CODEX_HOME alone is not sufficient test isolation. Verify OS home, temp and
workspace artifact roots before any isolated hook test. Legacy control/diagnostic
commands retain their existing storage contract.

Skill metadata identifies a method but does not establish grounding. Finish the
requested artifact and retain the authored method's evidence, stop, public-output
and grounding requirements. A failed lookup does not erase a global constraint.

Codex previously advertised 48 method skills plus controller/rigor/trace. In this
candidate only the latter three are discoverable. Invoke `opensocrates` with the
same method name or use the decision command; compatibility references are at
`skills/opensocrates/references/methods/<id>.md`, and complete bodies are at
`skills/opensocrates/references/decision/methods/<locale>/<id>.md`. The identifiers themselves are unchanged.
This avoids spending discovery context on all 48 procedures. The host's current
[skill documentation](https://learn.chatgpt.com/docs/build-skills) describes a
2%-of-context initial metadata budget (8,000 characters if context size is unknown),
with truncation/omission possible. We do not infer live discovery from file counts.

## Local preparation and rollback

Use `make bootstrap`, `make generate` and the full `CONTRIBUTING.md` validation
suite. `make release-check` builds isolated local native packages; it does not
install them in the active host. Missing release-specific Claude Chat evidence
must remain a failed gate. Clean-machine installation and held-out independent
quality evaluation remain release conditions, not claims made by local tests.
The original worktrees are preserved and the new branch is isolated. Do not replace
an active host mid-task; use a separate approved profile or a later normal installer
transaction, whose rollback contract is unchanged.
