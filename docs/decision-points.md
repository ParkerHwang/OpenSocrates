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

## Host evidence and compatibility

| Host | New in-turn delivery | Evidence level |
| --- | --- | --- |
| Codex | Native CLI first with scoped reference fallback | Normal installed reference delivery and completed turns observed on named candidates; latest native-first actor validation pending; GUI unvalidated |
| Claude | Agent CLI where shell is available; reference lookup otherwise | Package/runtime contracts; new live flow unverified |
| Antigravity | Agent reference lookup | Generated package contracts only |
| Cursor | Agent reference lookup | Generated package contracts only |
| Grok | Agent reference lookup | Generated package contracts only |
| OpenCode | Agent reference lookup; existing initial bridge preserved | Package/bridge regression only; no new automatic decision hook |

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
