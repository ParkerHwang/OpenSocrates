# Previously used Mac purge and reinstall acceptance

[한국어](reinstall-cycle-acceptance.ko.md)

Use this procedure only for the focused `purged_same_machine` acceptance test on
an Apple-silicon Mac that already has the exact supported OpenSocrates baseline.
It is not a clean-machine test and must never be reported as one.

The harness uses the real authenticated account homes and the packed `npx`
entrypoint. It removes the admitted OpenSocrates installation, verifies exact
zero residue, and reinstalls Claude and Codex from the same candidate. This is a
destructive test of OpenSocrates-owned registrations, payloads, caches, data,
state, the LaunchAgent, and the seven OpenSocrates Codex trust entries. It does
not restore their prior contents. It must not inspect or delete unrelated host
configuration, history, plugins, or npm/npx caches.

## Required starting state

Run from the latest commit of the focused pull request after its Native package
CI job succeeds. The harness fails before lifecycle mutation unless all of these
conditions hold:

- macOS hardware and the Node process are `arm64`, the process is not root or
  under `sudo`, and the account home is canonical and owned by the current UID;
- Python 3.12 is available for the hermetic installed `SessionStart` timing
  driver;
- the current POSIX username is canonical, and Claude and Codex authentication
  succeeds in both the normal preflight and the closed lifecycle environment;
- Claude and Codex each have exactly one managed OpenSocrates 1.3.1
  registration at the canonical managed root;
- Claude and Codex managed roots and cache versions pass their complete
  checksum and closed-file-set checks;
- automatic updates are disabled, the LaunchAgent is unloaded, and the exact
  desired state names Claude and Codex only;
- Antigravity, Cursor, Grok, and OpenCode OpenSocrates roots or bridges are
  absent;
- no unsupported pre-1.0 Claude case-variant registration, installer
  transaction residue, trust-reset residue, or LaunchAgent temporary exists;
  and
- the checkout is clean and still matches the open pull-request head.

The candidate gate creates an exact nine-file `npm pack` tarball. It also pins
the successful CI repository, workflow, run ID, attempt, full head SHA,
immutable artifact ID, artifact name, raw ZIP digest and size, build-time commit
and tree receipt, both host payload manifests, and the canonical Python, Claude,
and Codex executables with their SHA-256 digests. The private execution identity
also pins the canonical POSIX username. Destructive lifecycle capsules pass the
exact host binaries and that username explicitly and do not depend on the
capsule's reduced shell `PATH`; final timing invokes the pinned Python directly.
The harness creates the private timing report as an exclusive owner-only file
before Python writes any observation bytes, and verifies that mode again before
reading it.
The unpublished candidate 1.4.0 uses the packed installer and exact PR CI artifact;
no public npm or GitHub release 1.4.0 download is assumed. Published 1.3.1
release bytes are used only to authenticate the initial payload, not the candidate.

The immediately pre-purge baseline recheck binds the exact managed roots,
stable cache payloads, desired state, and OpenSocrates Codex trust syntax. The
cache binding excludes only a validated, non-live per-process `.in_use`
transient, whose shape and liveness are checked separately. Any other byte or
topology change stops before the first purge command.

## Version transition and baseline provenance

This focused path admits **initialVersion 1.3.1 → candidateVersion 1.4.0** only.
It records `purged_same_machine` and `transition: purge_then_reinstall`; it is
neither clean-machine evidence nor in-place update/migration evidence. Do not
install 1.4.0 first to manufacture the baseline. The earlier issue #83 harness
reinstalled its same 1.2.1 candidate; its use of `PRODUCT_VERSION` for both
roles was not an upgrade path. The installer's pre-1.0 case-variant migration
instructions are a different, explicitly manual procedure.

Both active registrations, managed plugin/release manifests, marketplace
metadata, and desired state must agree on 1.3.1. The source and verified PR
artifact must agree on 1.4.0. The public baseline, private checkpoint, resume
checks, pre-purge byte bindings and sealed final result retain these separate
roles. Old checkpoints without this contract are rejected, never migrated or
replayed after changing source.

`tools/reinstall_baseline_provenance.json` pins checksum-inventory and manifest
digests extracted from downloaded official releases whose archive bytes matched
the GitHub asset digests. The 1.3.1 release is immutable. The legacy 1.2.1 release
is not immutable, so its exact observed archive/inventory digests are pinned in
source rather than trusting its mutable tag on a later run. Full checksum and
closed-file-set verification still runs; self-consistent but unknown/rehashed
payloads fail. This is a repository/release provenance anchor, not code signing.

Only the pinned 1.3.1 caches and an optional pinned **inactive Claude 1.2.1 cache**
are admitted. An old cache does not change `initialVersion` or prove an active
mixed-version installation. Unknown versions, host/version mismatches, altered
manifests, extra files, and unrecognized cache markers remain blocking. Purge
removes these admitted old caches as part of the recorded destructive cycle.

## Codex inventory diagnostics

All OpenSocrates warnings, all hook inventory errors and unclassified warnings
block acceptance. One exact diagnosed external warning is counted separately:
Codex Companion `openai-codex/codex/1.0.6` configures SessionEnd at five seconds,
and Codex reports clamping it to its three-second limit. This is an unrelated
plugin's configuration diagnostic, not an observed OpenSocrates execution
failure. The exact message and canonical default-home source path must match;
other messages/paths remain blocking. No unrelated setting is changed.
`otherPluginTimeoutWarningCount` preserves the count in baseline and final
first-review evidence without publishing the raw path/message. The seven-hook,
namespace, trust and fixed SessionStart timeout checks are unchanged.

There is no `--preflight` or `--dry-run` CLI. The no-argument command proceeds
from its gates into real mutation. Read-only preparation must inspect code and
use only its read-only inventory functions; it must not start the cycle.

## Start the automated cycle

From the clean pull-request checkout, run:

```bash
node tools/reinstall_cycle_acceptance.mjs
```

Keep both printed locations. The public directory contains only sanitized
evidence. The owner-only private directory contains the exact checkpoint,
candidate inputs, lifecycle journal, command ledger, and later the recording.
Do not publish, move, edit, or delete the private directory while the cycle is
active.

Every lifecycle operation uses the locally pinned tarball explicitly through
an operation-bound `npx --package` invocation. Purge is one combined command
with `remove --host all --purge --reset-trust`; reinstall is one atomic
`install --host all` command with both exact host assets. The harness refuses to
install until registration and the closed exact residue inventory are empty.

## Resume and the one bounded host-close retry

Never start a second initial run after purge may have begun. Resume only the
printed private checkpoint so the original baseline and exact candidate remain
authoritative:

```bash
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY
```

If the sanitized result is `paused`, it names only the host apps whose live
`.in_use` marker is the sole remaining blocker. Close exactly those apps,
confirm they are no longer running, and then use the single explicit retry:

```bash
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY \
  --confirm-host-apps-closed
```

The confirmation does not authorize the harness to terminate an app. Before
retrying, it requires the checkpointed registration, root, data, state, trust,
LaunchAgent, transaction, candidate, and desired-state bindings to be unchanged;
only the named live marker may have disappeared. A mixed purge defect or a
second live-cache failure is terminal and receives no further automatic retry.

A claimed lifecycle without a verified terminal receipt is
`blocked_unverifiable` and cannot be replayed. A nonzero atomic install terminal
cannot be promoted to success from filesystem appearance. Once one-shot Codex
review verification enters `finalizing`, it is not replayed; a complete matching
sealed receipt can only finish publication.

## Record and review the app observations

When capture is authorized, start Record & Replay before the first manual Codex or Claude app interaction.
The recorder asks for confirmation before capture starts. Perform the checks,
stop the recording, and review its returned event stream privately. Do not copy
raw accessibility events, prompts, transcripts, sidebar text, account details,
credentials, or local paths into the public result.

Record these five categorical checks in order:

1. Codex presents exactly seven `opensocrates@opensocrates` hooks as new and
   untrusted on first review.
2. After the user approves those exact hooks, all seven are trusted; do not
   approve unrelated hooks.
3. A fresh Codex task has no OpenSocrates `SessionStart` timeout at the fixed
   two-second host limit.
4. A fresh Claude Code Local task runs
   `/opensocrates:opensocrates status` and reports 1.4.0. A bare
   `/opensocrates` is not Local plugin evidence.
5. The private Record & Replay event stream was stopped and reviewed.

Claude Chat standalone uses `/opensocrates`, but the exact public Chat 1.4.0
artifact remains pending. Do not infer Chat evidence from the Claude Local
plugin.

If authentication, 2FA, approval, or safe app control prevents a check, stop
that interaction. Do not bypass it or mark it `PASS`. Use only `PASS`, `FAIL`,
`NOT_OBSERVED`, or `BLOCKED` for each manual field.

Place the reviewed recording file inside the printed private evidence directory
as a new owner-only `0600` regular file, then bind it to the printed test ID:

```bash
node tools/reinstall_cycle_acceptance.mjs --bind-recording \
  PRIVATE_EVIDENCE_DIRECTORY RECORDING_FILE_INSIDE_PRIVATE_EVIDENCE TEST_ID
```

Edit only the five `PENDING` manual lines. Packing rejects free-form notes,
unknown enums, tampered automated fields, links, extra files, or privacy-sensitive
values. A `PASS` recording-review field requires its verified same-test receipt;
missing linkage is not an unconditional prohibition on packing unknown results.

### When raw capture is prohibited

Do not start Record & Replay or collect screenshots, prompts, transcripts,
accessibility events, account details, credentials or hidden reasoning. Do not
fabricate a recording or bind a substitute file. Leave every manual check that
lacks its qualifying recorded observation `NOT_OBSERVED`; use `BLOCKED` when
login, approval, capture authorization or safe control prevented it. A direct
unrecorded observation or an approval receipt does not meet the recorded `PASS`
requirement. The automatic hook inventory is distinct from manual review,
automatic hook delivery, full canonical reads and native application receipts.

After automatic checks pass, the unchanged pack contract allows all five final
enums, including unknown/blocked fields, with the recording linkage still
pending. It retains `automatedResult: passed`, but `manualResult` and
`overallResult` are `not_observed` or `blocked` (or `failed` if any field failed),
never a complete acceptance pass. Automatic-only evidence is useful for
installation/topology assessment but leaves the manual acceptance requirement
open. Authentication and trust approvals are user actions; never infer them.

## Create and retain the public handoff

After all five fields have a final categorical value, run:

```bash
node tools/reinstall_cycle_acceptance.mjs --pack RESULT_DIRECTORY \
  --private-evidence PRIVATE_EVIDENCE_DIRECTORY
```

The final ZIP contains exactly `result.json`, `result.md`, and
`manual-observations.md`. Its automated bytes must match the sealed result, and
the seal, final verification, installed checkpoint, source commit, CI artifact,
recording receipt when present, and ZIP digest remain linked in the private manifest.

A paused or failed run may create a separately named `.diagnostic.zip`. That
bundle does not occupy the final `.zip` name and does not seal a paused result as
an automated pass.

Retain private evidence until the public bundle and its SHA-256 digest are safely
handed off. Cleanup permanently deletes exactly one owner-controlled private run
directory. With the bundle still at its original path, use:

```bash
node tools/reinstall_cycle_acceptance.mjs --cleanup-private \
  PRIVATE_EVIDENCE_DIRECTORY --test-id TEST_ID \
  --public-zip-sha256 BUNDLE_SHA256
```

If the exact bundle was moved, add `--public-bundle MOVED_BUNDLE_FILE`. If it was
intentionally removed only after its digest was retained elsewhere, add
`--allow-missing-public-bundle` instead. Cleanup first writes a durable
authorization tombstone, so an interrupted deletion can safely repeat the same
exact command. Never use cleanup on an active run or a directory whose owner,
mode, canonical path, link count, prefix, test ID, or bundle digest differs.

## Failure boundaries and final state

- A preflight failure performs zero lifecycle commands and leaves the admitted
  installation unchanged.
- No reinstall follows a partial purge or nonempty exact residue inventory.
- After mutation starts, a failure reports the observed categorical partial
  state or `unknown_unverified`; it does not claim to restore the previous
  cache, data, trust, content, or version.
- Raw lifecycle output, candidate paths, recordings, accessibility snapshots,
  and private evidence paths stay private and must not be attached to the issue
  or pull request.
- A successful cycle ends with Claude and Codex installed from the exact
  candidate commit, automatic updates disabled, and the other supported hosts
  absent. This is the intended final state; do not purge it again as part of
  this acceptance.

The valid success claim is limited to the categorical final topology and the
exact candidate installation on this previously used Mac.
