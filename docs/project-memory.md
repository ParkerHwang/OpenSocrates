# Project continuity in the v1.5.0 release candidate

[한국어](project-memory.ko.md)

OpenSocrates can keep bounded public decisions and checkpoints for a project so
a fresh Codex session can continue useful work. It supports Git projects and
ordinary local text folders. Memory is optional and starts disabled; installing
or updating the plugin does not enroll a project.

For ordinary work, ask Codex to use OpenSocrates and give the task. A simple edit
needs no reasoning ceremony or memory lookup. For a code change, the guidance
helps inspect existing helpers, affected callers and the checks the change needs.
Normal assistance uses the task-based fallback; experimental model profiles are
not silently enabled and your model/effort is preserved.

## Enable only the project you intend

Ask Codex to show the proposed OpenSocrates memory enrollment for the selected
project: its root, what it retains, exclusions, and how to inspect, disable and
delete it. Authorize that scope if it fits your needs. Existing explicit permission
is sufficient; the agent should not repeatedly ask for the same permission.

After enrollment, useful requests include:

- “Continue this project from its accepted decisions, but check the current files
  before relying on old implementation details.”
- “The capacity figure is wrong. Forget that scoped fact while keeping the
  accessibility requirement and the other project decisions.”
- “Answer this side question, then continue the original task. Ask only if a
  missing answer changes what you can do next.”

The agent handles the memory operation details through the installed guidance.
Current source establishes current behavior. Accepted records express attributed
intent; a proposed idea is not accepted merely because it was saved. Missing
memory does not invent facts or authorize an action. A maintained project note
remains a reasonable alternative for small projects.

## Inspect and control it

For an enrolled task, the agent can save a milestone, inspect its current version,
and update it before continuing in a fresh session. The installed
[checkpoint guide](../plugin-src/shared/assistance/checkpoint.en.md) supplies the
complete request and recovery flow. Checkpoints remain reported progress, not
accepted intent or native proof that work happened; current sources still govern.

Ask to inspect or export the project's stored records. Disablement stops normal
context use/capture while preserving management access. Deleting a record removes
that exact record and its managed history/backups; if it mixes obsolete facts and
valid intent, the agent must preserve and accept the retained intent first.
Supersession alone preserves history and is not forgetting. An exact project
deletion removes only its owned store, never source files or unrelated projects.

The store may retain bounded public decisions, task state, relative source
references, digests and declared index metadata. It must not retain raw prompts,
transcripts, source-file copies, credentials, screenshots or hidden reasoning.
Logical deletion is not a promise of forensic erasure from SSDs, OS backups or
independent copies you exported. Project memory is preserved by ordinary updates
and uninstall by default.

If hooks are unavailable or not trusted, explicitly ask Codex to use the installed
controller skill. If memory is unavailable, the agent should state that limit and
continue independent authorized work rather than pretend it remembered something.

This branch is a release candidate, not a published installation. See the
[candidate handoff](v1.5.0/RELEASE_CANDIDATE.md), [bounded comparison](../evals/v1.5/practical/README.md)
and [technical protocol](project-memory-development.md) for exact support and limits.
