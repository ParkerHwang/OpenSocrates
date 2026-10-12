# v1.6.0 implementation and release handoff

Tracking: [implementation issue #111](https://github.com/ParkerHwang/OpenSocrates/issues/111) and [Draft PR #112](https://github.com/ParkerHwang/OpenSocrates/pull/112). Preparation PR #110 and issue #109 remain separate. Reconciled main base: 9572db2c71a455d4ada24c78402d0f874002cec9. Branch: codex/v1.6-go-native.

## Completed implementation

| Package | Completed scope |
| --- | --- |
| V0 | Frozen released v1.5.0 baseline, 48 methods, EN/KO, revision 3 |
| V1–V2 | Typed Go contracts, services, content, domain, decision, runtime CLI and persistence |
| V3 | Native OS protection and pinned external Codex app-server compatibility |
| V4–V5 | Shared lifecycle journals, transport, host registration, native management and npm adoption |
| V6 | TUF trust, opt-in stable scheduling, versioned bundles and journaled self-update/recovery |
| V7 | Go generation, package/release tooling, governance/validation, CI and bilingual documentation |
| V8 | Source checks, compatibility comparison, native acceptance, specialist review and durable handoff |

The user subsequently added **Windows ARM64** to v1.6.0. It has separate native binaries, PE/build checks, signed target selection, helper/installer paths, publication assets and native CI. This is a material user-directed adjustment to the original two-platform plan. Codex and Antigravity retain their profile boundaries; native Windows Claude Code is excluded and --host all still means Codex. Claude account upload/activation remains separate.

Methods, teacher questions, response policies and shared guides remain frozen at tag source cf6634310afcf5d5ce58484e67a73151bb4c5999. Only compiled release metadata changes to 1.6.0; revision remains 3. The separate method-body session was not modified. See [baseline](CONTENT_BASELINE.json) and [intentional changes](DECISIONS.md).

## Exact evidence

Last fully native-checked implementation: **60112493fddef889058bb028d2f396586b0486a2**. [CI 38218166860](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38218166860) passed source and actual macOS ARM64, Windows x64 and Windows ARM64 execution. The previous complete [CI 38216709561](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38216709561) passed at d156c27; 6011249 adds content-free failure reporting only. [Retained receipts](evidence/README.md) keep their original revisions; documentation does not relabel old results.

Commands/results:

- make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check smoke installer-check: preparation/static/generated/content/docs/governance/package passed at 6498fd6. A new package test compared an in-memory typed array using JSON-only helpers; it was corrected to inspect serialized output. The affected runtimecli/devtools go test and make installer-check passed after correction. Complete source/behavioral CI passed at d156c27.
- make package TARGET=windows-arm64: artifacts assembled. Cross-build alone is not runtime evidence; native ARM64 CI subsequently executed the binaries.
- Native CI ran go test ./src/opensocrates/..., build, package, check package, acceptance lifecycle, acceptance timing and acceptance scheduler. Lifecycle covers install/status/update/disabled-state/removal/interruption/recovery/rollback and synthetic npm adoption. Windows runs actual packaged Go helpers for manager/helper replacement and interrupted activation.
- Exact generated hooks passed Unicode/space/dollar/backtick paths, 20 startup and 20 compact samples, each below two seconds and p95 at most one second. The development-test executable has separate checked Windows shell setup; packaged timing has no warmup, retry or excluded sample.
- Actual per-user Mac LaunchAgent and Windows Task Scheduler registration/Go execution/owned cleanup passed. Windows captured XML export/import restoration passed. Go encodes OS imports as UTF-16 while state remains UTF-8; defaults/durations/OS-resolved aliases do not authorize foreign changes.
- [Differential comparison](evidence/go-v1.5-compatibility.json): 1,055 synthetic decision responses, all 48 methods/locales, nine rigor commands, 21 control cases and ten affected control-root rechecks passed at c5a822c6. Unchanged runtime sources support reuse; four intentional differences remain documented.
- [Authentic npm payload adoption](evidence/native-npm-adoption-darwin-arm64.json) passed on Mac at c5a822c6 using the actual v1.5.0 ZIP and original entry installer with isolated HOME/Go host fixture. Exact bytes/modes/state/trust/disabled state were preserved and restored; the legacy scheduler was disabled.
- Five-second Go fuzz runs passed for archive paths, trust reset and safe relative transport. Bounded final reviews found no remaining actionable findings after fixes.
- Read-only gh api repos/ParkerHwang/OpenSocrates/immutable-releases --jq '{enabled}' returned enabled:true. This does not provision the publication environment's separate Administration-read credential.

The user VM is Windows 11 ARM64. Its [native lifecycle](evidence/native-vm-windows-arm64-lifecycle.json) and [native scheduler](evidence/native-vm-windows-arm64-scheduler.json) passed with verified ARM64 artifacts, including packaged helper replacement/recovery. Earlier x64-emulation observations are supplemental. A contaminated disposable Mac transfer ZIP was rejected for 465 AppleDouble extras; the unchanged payload passed after metadata-free transfer into fresh staging. All temporary scheduler tasks were removed. Older diagnostic folders without a byte-identity sidecar were retained intentionally; modified/unverifiable files are never deleted indiscriminately. Existing installations, accounts, settings and trust decisions were preserved.

## Remaining release gates

Available implementation acceptance passes; this candidate is **not production-release validated**.

1. Provision an independently approved threshold-signed TUF root/publisher identities, platform signing/notarization/Authenticode resources, metadata service/key custody and scoped Administration-read publication credential. Test trust cannot become production trust. Release-check fails closed without production platform signatures.
2. Qualify public signed network updates and complete production installer/manager/updater self-update/rollback with production trust, security prompts and timestamps.
3. Obtain authentic Windows npm-install adoption and integrated takeover from an **enabled** old scheduler. Current Windows adoption is synthetic; authentic Mac adoption used a disabled scheduler. Independent real scheduler checks plus mocked migration rollback do not prove enabled-updater takeover.
4. Obtain clean-machine and real host trust/activation, authenticated legacy app-server, account/workspace/global and CLI/Desktop evidence. Local updates cannot modify account content or running conversations. External host ARM64 availability/loading remains host-specific qualification.

Next: complete these release gates, then protected review/release workflow. No merge/tag/production publication/active-installation replacement is authorized. PR remains Draft. SSH upload and workflow editing access are verified; production signing/trust is a separate requirement.
