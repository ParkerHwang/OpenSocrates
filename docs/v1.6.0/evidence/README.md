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

Native CI evidence is linked from the [implementation handoff](../IMPLEMENTATION_HANDOFF.md).
Each workflow uploads receipts and build artifacts with exact source provenance.
Production trust, platform signing and live activation remain separate gates.

The retained native receipts and package provenance are from
[run 38216709561](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38216709561)
at d156c27feefa64dd57ae7e64a0ee114456c0ebd7: actual macOS ARM64, Windows x64
and Windows ARM64. Each platform ran the native lifecycle, exact-command hook
timing and OS scheduler gates. Windows also executed packaged Go helper
replacement/recovery probes and captured scheduler XML restoration.

The user's Windows 11 ARM64 VM supplies separate
[native lifecycle](native-vm-windows-arm64-lifecycle.json) and
[native scheduler](native-vm-windows-arm64-scheduler.json) observations.
Earlier x64 binaries executed through ARM64 emulation are supplemental only;
they are never relabeled as native x64 or native ARM64 release qualification.
