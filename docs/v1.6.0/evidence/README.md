# Retained migration evidence

These content-free receipts record completed observations, not production or
live-host qualification. Their recorded source/binary revisions are deliberate;
later documentation commits do not relabel old evidence as a new execution.

- [Behavioral comparison](go-v1.5-compatibility.json): 1,055 synthetic decision
  responses, all 48 methods in both locales, nine rigor commands, 21 control
  cases, and the ten affected control-root rechecks. The baseline implementation
  at main `9572db2` has no runtime-source differences from released v1.5.0
  `cf66343`. Only command path names are redacted; script and binary hashes are
  retained. The one-off historical Python comparison is an observed migration
  experiment, not active first-party validation tooling. Current repeatable
  contract tests are Go tests under `src/opensocrates/`.
- [Released npm payload adoption](native-npm-adoption-darwin-arm64.json): actual
  public v1.5.0 ZIP and original release entry installer, isolated HOME and
  external Go host fixture, exact byte/mode rollback and disabled-state
  preservation. Its `baseline_commit` is the public asset's embedded build
  revision, not the canonical content tag commit. No global npm installation,
  live host, enabled legacy scheduler, production signature, or user installation
  replacement is claimed.
- [Enabled legacy updater takeover](native-npm-enabled-updater-darwin-arm64.json):
  original v1.5 installer/payload, actual macOS ARM64 launchd registration,
  native adoption with one update owner, and exact live-identity/byte rollback.
  A fixed logical label maps to one unique disposable OS label; RunAtLoad is
  suppressed only in the mapped OS copy. Codex and npx are Go fixtures; actual
  scheduled execution, network updates and production fixed-label installation
  are outside this observation. The [frozen reproducer](qualification/macos-enabled-legacy/README.md)
  records exact commands, hashes and boundaries.

Native CI evidence is linked from the [implementation handoff](../IMPLEMENTATION_HANDOFF.md).
Each workflow uploads receipts and build artifacts with exact source provenance.
Production trust, platform signing and live activation remain separate gates.

The resumed fix at **bc151afdb9a9d6845906b05ec2efb022961fd45f** passed all
source/macOS ARM64/Windows x64/Windows ARM64 jobs in
[CI 38239135183](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38239135183).
Retained lifecycle receipts: [Mac](native-lifecycle-darwin-arm64-bc151af.json),
[Windows x64](native-lifecycle-windows-x64-bc151af.json), and
[Windows ARM64](native-lifecycle-windows-arm64-bc151af.json).
The native tests include an exact 341,142,832-byte synthetic legacy-runtime
copy and rejection above the corrected finite 512 MiB file bound.

[Actual Windows v1.5 payload adoption](native-npm-adoption-windows-arm64-bc151af.json)
is explicitly **PARTIAL**: native Go adoption/status/recovery, disabled-state,
settings/trust/npm preservation and exact payload rollback passed; original
v1.5 installer completion did not. Its elevated VM owner mismatch required
source-equivalent initialization from the authentic release ZIP. This does not
claim successful original-installer adoption. The
[artifact identities](native-npm-adoption-artifacts-windows-arm64-bc151af.json)
and [frozen reproducer](qualification/windows-actual-payload/README.md) preserve
the native ARM64 manager and transferred source hashes. CI and VM artifacts
are separate builds of the same source revision.

The retained native receipts and package provenance are from
[run 38216709561](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38216709561)
at d156c27feefa64dd57ae7e64a0ee114456c0ebd7: actual macOS ARM64, Windows x64
and Windows ARM64. Each platform ran the native lifecycle, exact-command hook
timing and OS scheduler gates. Windows also executed packaged Go helper
replacement/recovery probes and captured scheduler XML restoration.

Final source/native CI [run 38219463804](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38219463804)
passed at 3724bf803661b34cd2b8c54e1d5852dbc4f3e457. Its first Windows x64
lifecycle attempt reached the outer 30-second install deadline with empty
output; the unchanged failed job passed on rerun. Both the
[first attempt](native-lifecycle-windows-x64-3724-first-attempt.json) and
[rerun](native-lifecycle-windows-x64-3724-rerun.json) are retained. No deadline
or acceptance requirement changed, and the timeout's cause remains unestablished.

The user's Windows 11 ARM64 VM supplies separate
[native lifecycle](native-vm-windows-arm64-lifecycle.json) and
[native scheduler](native-vm-windows-arm64-scheduler.json) observations.
Earlier x64 binaries executed through ARM64 emulation are supplemental only;
they are never relabeled as native x64 or native ARM64 release qualification.

## Additional preparation at 306b74c

- [Development HTTPS update](development-https-update-306b74c.json): successful real TLS exchange and shared lifecycle activation/rollback under ephemeral development trust; production signing/public delivery/native self-update are false.
- [Authenticated legacy selector](authenticated-legacy-selector-306b74c.json): actual pinned external CLI and protected existing login; synthetic request, content-free success within 8.5 seconds; no live conversation/quality claim.
- [Actual Codex private registration](real-codex-registration-darwin-arm64-306b74c.json): real installed CLI and disposable configuration; supported lifecycle PASS, active auth/config unchanged; host-disabled/different-version/live activation explicitly not verified.
- [Mac Developer ID signatures](macos-developer-id-signature-306b74c.json): actual user-authorized identity on manager/helper copies with hardened runtime/timestamps; notarization/production release remain false. Private keys/keychain credentials stay outside source and public evidence.

Exact commands, account-resource boundaries and remaining prerequisites are in
[release preparation](../RELEASE_PREPARATION.md) and the updated handoff.
