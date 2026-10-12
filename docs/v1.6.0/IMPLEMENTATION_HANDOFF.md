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

Historical native evidence for the resumed large-payload fix: **bc151afdb9a9d6845906b05ec2efb022961fd45f**. [CI 38239135183](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38239135183) passed source and actual macOS ARM64, Windows x64 and Windows ARM64 execution after the resumed large-payload fix. Git tree `29d6306880d0e09f42b59bdbc78cfbe816ad02c4` matches all three native provenance receipts. The documentation/evidence follow-up does not relabel these observations as a new execution.

Earlier [CI 38219463804](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38219463804) passed source and actual macOS ARM64, Windows x64 and Windows ARM64 execution. The first Windows x64 attempt reached the outer lifecycle acceptance deadline after 30.006 seconds during install, with empty output; the same commit passed when only that failed job was rerun, with unchanged deadlines. This observation does not establish the cause of the initial timeout. Earlier complete native runs [38218166860](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38218166860) at 6011249 and [38216709561](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38216709561) at d156c27 also passed. [Retained receipts](evidence/README.md) keep their original revisions; documentation does not relabel old results.

Commands/results:

- make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check: all passed at bc151af on macOS ARM64 with Go 1.27.2. make release-check exited 2 (Make), failed closed with production platform signature required; this is not a release-check pass.
- The actual v1.5 Windows archive contains a 341,142,832-byte Codex executable, exceeding the initial Go 256 MiB lifecycle cap. bc151af corrects the per-file cap to 512 MiB while retaining 2 GiB/10,000-entry bounds, and streams guarded hashes/recovery copies. The exact-size synthetic copy regression, over-limit rejection and streaming security tests passed in all native source suites. Bounded final code/security reviews found no actionable findings; the evidence audit classified release acceptance PARTIAL.
- [Windows ARM64 actual-payload adoption](evidence/native-npm-adoption-windows-arm64-bc151af.json): Go adopt/status/recover exited 0 at bc151af using the authentic v1.5 Windows x64 ZIP and an integrity-matched actual npm TGZ installed under a private prefix. Disabled state, settings/trust/unknown JSON fields, npm bytes and exact payload/registration rollback passed. Overall qualification remains **PARTIAL** because the original unchanged v1.5 installer exited 1 with `Foreign owner refused` in this elevated VM's owner environment. The legacy layout was explicitly initialized from the verified release with its source-equivalent schema. The [frozen reproducer](evidence/qualification/windows-actual-payload/README.md) and [artifact receipt](evidence/native-npm-adoption-artifacts-windows-arm64-bc151af.json) bind source, native ARM64 PE identity and actual transferred bytes. Local cross-built and CI-built artifacts retain separate hashes.
- make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check smoke installer-check: preparation/static/generated/content/docs/governance/package passed at 6498fd6. A new package test compared an in-memory typed array using JSON-only helpers; it was corrected to inspect serialized output. The affected runtimecli/devtools go test and make installer-check passed after correction. Complete source/behavioral CI passed at d156c27.
- make package TARGET=windows-arm64: artifacts assembled. Cross-build alone is not runtime evidence; native ARM64 CI subsequently executed the binaries.
- Native CI ran go test ./src/opensocrates/..., build, package, check package, acceptance lifecycle, acceptance timing and acceptance scheduler. Lifecycle covers install/status/update/disabled-state/removal/interruption/recovery/rollback and synthetic npm adoption. Windows runs actual packaged Go helpers for manager/helper replacement and interrupted activation.
- Exact generated hooks passed Unicode/space/dollar/backtick paths, 20 startup and 20 compact samples, each below two seconds and p95 at most one second. The development-test executable has separate checked Windows shell setup; packaged timing has no warmup, retry or excluded sample.
- Actual per-user Mac LaunchAgent and Windows Task Scheduler registration/Go execution/owned cleanup passed. Windows captured XML export/import restoration passed. Go encodes OS imports as UTF-16 while state remains UTF-8; defaults/durations/OS-resolved aliases do not authorize foreign changes.
- [Differential comparison](evidence/go-v1.5-compatibility.json): 1,055 synthetic decision responses, all 48 methods/locales, nine rigor commands, 21 control cases and ten affected control-root rechecks passed at c5a822c6. Unchanged runtime sources support reuse; four intentional differences remain documented.
- [Authentic npm payload adoption](evidence/native-npm-adoption-darwin-arm64.json) passed on Mac at c5a822c6 using the actual v1.5.0 ZIP and original entry installer with isolated HOME/Go host fixture. Exact bytes/modes/state/trust/disabled state were preserved and restored; the legacy scheduler was disabled.
- [Enabled legacy-updater takeover](evidence/native-npm-enabled-updater-darwin-arm64.json) passed on macOS ARM64 at 3724bf8. The original installer and actual release ZIP registered a real unique disposable LaunchAgent; Go adoption replaced its legacy arguments with the native updater and retained one update owner. Recovery restored the live legacy identity, original policy/plist/desired-state/payload bytes, settings, trust, key and disabled integration. The fixed label was mapped to a unique test label and RunAtLoad suppressed only in its OS copy; Codex/npx were Go fixtures. Actual updater execution, login/network triggers and the production fixed-label installation are outside this observation.
- Five-second Go fuzz runs passed for archive paths, trust reset and safe relative transport. Bounded final reviews found no remaining actionable findings after fixes.
- Read-only gh api repos/ParkerHwang/OpenSocrates/immutable-releases --jq '{enabled}' returned enabled:true. This does not provision the publication environment's separate Administration-read credential.

The user VM is Windows 11 ARM64. Its [native lifecycle](evidence/native-vm-windows-arm64-lifecycle.json) and [native scheduler](evidence/native-vm-windows-arm64-scheduler.json) passed with verified ARM64 artifacts, including packaged helper replacement/recovery. Earlier x64-emulation observations are supplemental. A contaminated disposable Mac transfer ZIP was rejected for 465 AppleDouble extras; the unchanged payload passed after metadata-free transfer into fresh staging. All temporary scheduler tasks were removed. Older diagnostic folders without a byte-identity sidecar were retained intentionally; modified/unverifiable files are never deleted indiscriminately. Existing installations, accounts, settings and trust decisions were preserved.

## Additional release preparation at 306b74c

[CI 38247473916](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38247473916)
passed source and native macOS ARM64/Windows x64/Windows ARM64 at
306b74cdf0efa4000dcee8a5656e287890d8a45d. The exact full local Make suite also
passed at that revision. New explicit Go acceptance commands are documented in
[release preparation](RELEASE_PREPARATION.md); ordinary tests do not call models.

- [Development HTTPS update](evidence/development-https-update-306b74c.json): real verified HTTPS through production transport/repository, authentic development metadata/archive, bounded synthetic extraction, shared lifecycle commit/rollback; tamper/expiry/metadata rollback/offline preserve payload. Production public delivery/native self-update remain separate.
- [Authenticated legacy selector](evidence/authenticated-legacy-selector-306b74c.json): actual official external Codex 0.144.4, existing protected login, one synthetic request with transcript off, completed valid catalog selection in 8.5 seconds. Post-success observation: zero matching processes/temporary selector directories. This qualifies authenticated adapter operation, not live host delivery/answer quality.
- [Real Codex private lifecycle](evidence/real-codex-registration-darwin-arm64-306b74c.json): installed actual CLI 0.162.0-alpha.17.2, private install/status/diagnose/same-version update/remove/final status PASS; active auth/config unchanged. Codex toggle state belongs to host controls; unsupported manager toggle examples are corrected in EN/KO. Host-disabled/different-version/live activation are not claimed by this probe.
- [Actual Mac Developer ID signature](evidence/macos-developer-id-signature-306b74c.json): user-authorized certificate issuance after direct agreement acceptance, public/private pair and Apple chain verified, dedicated owned keychain, manager/helper copies signed with verified hardened runtime, matching team and secure timestamp. Private signing material never entered source or left the Mac. Local signing does not establish notarization or protected release runner qualification.
- Canonical/embedded Mac Team ID now matches that approved account. Production TUF root remains `{}`; Windows publisher pin is empty. Existing protected-tag/publication guards were not bypassed. No release/active-installation replacement was performed.

Local notarization authentication was completed on 2026-10-12 at checkout
3b0ed4ec334f34549677af3c0baf72a703784c3d on macOS ARM64. After direct user
authentication, a dedicated app-specific password was registered as
`opensocrates-notary` in the local login keychain. `notarytool store-credentials`
with `--validate` exited 0; private account arguments and the secure password
input are intentionally omitted from this public handoff. The exact check
`xcrun notarytool history --keychain-profile opensocrates-notary --output-format json`
exited 0 with a valid history response. Temporary credential transfer was
removed and iCloud synchronization was not enabled. Actual archive notarization,
Gatekeeper and isolated release-runner qualification remain separate gates.

The actual native Mac ZIP and standalone installer at c9da20d each received
Apple `Accepted`, with zero issues, exact submitted ZIP hashes and code hashes
matching the returned tickets. The installer was submitted after payload
acceptance. [Candidate receipt](evidence/macos-candidate-notarization-c9da20d.json)
retains the source/file identities and the initial release-check failure:
all five distributed files pass notarized `codesign` requirements, but the
former `spctl` app assessor exits 3 for valid bare CLI code. The shared native
trust/release path now retains Apple Developer ID/team/notarized pinning, adds
online notarization checking, and removes that app-only assessor. Both manager
and helper authenticate before version execution. Changed bytes must be rebuilt,
re-signed and re-notarized; later evidence must retain its own source identity.

[Release environment observation](evidence/release-environment-c9da20d.json)
confirms source/native CI PASS at c9da20d (run 38265091598), active main ruleset
protection with obsolete required-check names, and absent release runners,
environments, Actions variables/secrets and final tag. The
[environment review](RELEASE_ENVIRONMENT_REVIEW.md) records the exact Go-check
migration proposal, runner choices and cloud-secret/reviewer decisions. No
production pipeline or cloud credential transfer was performed by these checks.

Additional original-Windows qualification at 001c75a used an isolated restricted
current-user primary token. The new file owner matched the user and original
owner/groups/privileges/default DACL remained unchanged. The original installer
still exited 1 at its Windows private-helper call; no fallback initialization
or adoption occurred. [Receipt](evidence/windows-original-installer-restricted-001c75a.json)
and [inactive reproducer](evidence/qualification/windows-restricted-owner/README.md)
retain this unavailable result. A compatible normal user environment is still
needed; do not weaken guards or change account/system/desktop policies.

## Remaining release gates

Available implementation acceptance passes; this candidate is **not production-release validated**.

1. Provision an independently approved threshold-signed TUF root, Windows publisher identity and protected signing runners, Windows hosted signing, metadata service/key custody and scoped Administration-read publication credential. Local Mac Developer ID issuance, signature checks and saved-profile notarization authentication now pass; the isolated runner and actual archive notarization remain unqualified. Test trust cannot become production trust. Release-check fails closed without production platform signatures.
2. Qualify public signed network updates and complete production installer/manager/updater self-update/rollback with production trust, security prompts and timestamps.
3. Complete Windows adoption beginning with a successfully executed original v1.5 installer in a compatible user environment. Actual-payload Go adoption/rollback now passes, but its source-equivalent initialization does not meet that original-installer gate. Also complete macOS production fixed-label/updater-execution qualification. Released v1.5.0 explicitly supported automatic updates only on macOS ARM64; its Windows installer reports them unavailable, so there is no supported enabled Windows legacy scheduler to adopt. Enabled macOS takeover and rollback now have integrated real-OS evidence under the disclosed unique-label and suppressed-execution fixture boundaries.
4. Obtain clean-machine and real host trust/activation, account/workspace/global and CLI/Desktop evidence. Authenticated macOS legacy adapter operation now has a synthetic live-account receipt; actual delivery/answer quality remain distinct. Local updates cannot modify account content or running conversations. External host ARM64 availability/loading remains host-specific qualification.

Next: complete these release gates, then protected review/release workflow. No merge/tag/production publication/active-installation replacement is authorized. PR remains Draft. SSH upload and workflow editing access are verified; production signing/trust is a separate requirement.
