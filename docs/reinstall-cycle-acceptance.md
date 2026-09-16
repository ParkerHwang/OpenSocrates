# Previously used Mac purge and reinstall acceptance

[한국어](reinstall-cycle-acceptance.ko.md)

This destructive acceptance cycle records `purged_same_machine` and
`purge_then_reinstall`: **Codex 1.3.1 → Codex 1.4.0**. It is neither a separate
clean-machine test nor an in-place migration. It uses actual account homes and
removes the admitted OpenSocrates registration, payloads, caches, lifecycle state,
updater and seven exact Codex trust entries. Removed contents are not restored.
Unrelated plugins, configuration, authentication, history and npm caches remain
outside its ownership. Other host integrations are outside the 1.4.0 contract.

## Starting state and candidate identity

Use a clean checkout of the open PR after its exact-head macOS CI succeeds.
Hardware and Node must be arm64 on macOS; run as the canonical home owner,
without root or sudo. Python 3.12, authenticated Codex CLI and authenticated
GitHub CLI are required. The default Codex managed registration, payload and
desired state must agree on 1.3.1; automatic updates must be disabled and the
LaunchAgent unloaded. Unknown payloads, unsafe ownership and transaction residue
block the cycle before mutation.

If 1.3.1 desired state still lists retired hosts, remove those integrations with
1.3.1 first. The 1.4.0 harness does not implement their cleanup. Do not install
1.4.0 first to manufacture a baseline.

`tools/reinstall_baseline_provenance.json` pins the official immutable Codex 1.3.1
archive, inventory and manifest digests. Full closed-file-set and checksum
verification still runs; rehashed or unknown payloads fail. Only that version's
Codex cache is admitted. Old multi-host checkpoints are rejected.

The candidate gate binds the nine-file npm tarball, successful CI run/attempt,
head SHA, immutable artifact ID/name/digest/size, source commit/tree receipt,
Codex package inventory, canonical Python/Codex executables and their digests.
The pre-purge recheck binds the exact baseline bytes and target trust syntax.
Only validated non-live `.in_use` transient markers are excluded from cache byte
binding. Any other change blocks the first purge.

All OpenSocrates hook warnings, errors and unknown warnings block acceptance.
The exact Codex Companion 1.0.6 SessionEnd clamp warning is counted separately
only when its known message and canonical source match. No other plugin setting
is changed. A packaged timing test does not establish actual automatic delivery.

## Run and resume

The no-argument command proceeds into real mutation; there is no dry-run option.
Close Codex host sessions before the destructive cycle and run it in an independent
Terminal so its controller survives the plugin removal.

```sh
node tools/reinstall_cycle_acceptance.mjs
```

Keep the printed public and owner-only private directories. The private directory
holds candidate bytes, checkpoints, command ledger and lifecycle journal. Do not
move or edit it while active. Purge uses exact packed `npx` with
`remove --host all --purge --reset-trust`; `all` means Codex only. After a closed
zero-residue inventory succeeds, one atomic install uses the exact Codex asset.

Never restart the initial command after mutation may have begun. Resume its
original private checkpoint:

```sh
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY
```

Only a recorded live-cache pause permits one bounded retry. Close the named host,
confirm it is closed, then use:

```sh
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY \
  --confirm-host-apps-closed
```

The flag never terminates an app. All checkpoint bindings must remain unchanged
except the named live marker. Mixed residue or another live-cache failure is
terminal. A claimed operation without its durable terminal receipt is
`blocked_unverifiable` and cannot replay. Nonzero install cannot become success
from filesystem appearance. Once finalization starts, only its exact complete
seal can finish publication; one-shot review checks do not replay.

## Observations and packing

When raw capture is authorized, start Record & Replay before manual interaction,
stop it afterwards, and privately review the event stream. Never publish raw
accessibility events, prompts, transcripts, account details or paths. Record
these four categorical fields:

1. Seven exact OpenSocrates hooks appear new and untrusted on first review.
2. Those seven hooks are approved and trusted.
3. A fresh Codex task has no OpenSocrates SessionStart timeout at its fixed two-second limit.
4. The private Record & Replay capture was stopped and reviewed.

Use `PASS`, `FAIL`, `NOT_OBSERVED` or `BLOCKED`; never infer an approval or bypass
authentication. Bind a reviewed owner-only recording to this test when available:

```sh
node tools/reinstall_cycle_acceptance.mjs --bind-recording \
  PRIVATE_EVIDENCE_DIRECTORY RECORDING_FILE_INSIDE_PRIVATE_EVIDENCE TEST_ID
```

If raw capture is prohibited, do not create a substitute recording. Fields without
the qualifying recorded observation remain `NOT_OBSERVED` or `BLOCKED`. An
unrecorded direct observation does not meet the recorded PASS requirement.
Automatic success may be packed with unknown manual fields, but the overall
result is not a complete acceptance pass.

Edit only the four categorical lines, then run:

```sh
node tools/reinstall_cycle_acceptance.mjs --pack RESULT_DIRECTORY \
  --private-evidence PRIVATE_EVIDENCE_DIRECTORY
```

The final ZIP contains only `result.json`, `result.md` and `manual-observations.md`.
Its automated bytes, final seal, installed checkpoint, source/artifact identity,
recording receipt when present and ZIP digest remain linked. A diagnostic ZIP
from a pause or failure never occupies the final ZIP name or implies success.

## Retention and final state

Retain private evidence until the public bundle and digest are safely handed off.
Cleanup permanently removes only the exact authorized private run directory:

```sh
node tools/reinstall_cycle_acceptance.mjs --cleanup-private \
  PRIVATE_EVIDENCE_DIRECTORY --test-id TEST_ID --public-zip-sha256 BUNDLE_SHA256
```

For a moved bundle add `--public-bundle MOVED_BUNDLE_FILE`; for an intentionally
removed bundle whose digest was retained, use `--allow-missing-public-bundle`.
A durable tombstone makes interrupted cleanup repeatable without broad deletion.
Never clean an active run or bypass owner, mode, link, identity or digest checks.

A failed preflight performs no lifecycle action. Partial purge blocks reinstall.
After mutation, failures record the actual partial state or `unknown_unverified`,
never a claim that removed data or trust were restored. Success ends with Codex
1.4.0 installed from the exact candidate and automatic updates disabled. Do not
purge that final installation again as part of this cycle.
