# Native clean-machine acceptance

[한국어](clean-machine-acceptance.ko.md) · [Native guide](native-v1.6.md)

Use a separately configured macOS ARM64 or Windows x64/ARM64 machine that has never
had the managed installation, registrations, user state or scheduler. A used
machine or a temporary home is not clean-machine evidence. Bind approved
candidate assets, source commit, content baseline and successful native CI run
before mutation. End-user prerequisites are the native assets and the external
host app/login; no Go, Python, Node.js or npm is required.

Do not run against the user's active installation without authorization. First
record a content-free baseline with the platform, exact source/artifact hashes,
absence of managed state/registrations/scheduler and host version. Unknown or
foreign paths block installation. Install through the native commands in the
native guide, verify status/inventory/registration, restart the host where
required, review hooks through the host trust interface and inspect actual
activation. Never fabricate trust records or infer delivery from registration.

Test manual update, disabled-state preservation, selected owned removal,
opt-in scheduler enable/status/run/disable, offline behavior, interruption,
recovery and verified rollback. Keep state, registration and updater ownership
consistent after each completed transaction. Production update tests require
approved trusted root/signed metadata and platform signing policy. Development
fixtures do not establish public-release authenticity.

The Go developer harness can additionally run isolated native filesystem and
host fixtures:

```text
go run ./src/opensocrates/cmd/opensocrates-dev acceptance lifecycle --binary /absolute/path/to/opensocrates --package /absolute/path/to/bundle --report build/evidence/native-lifecycle.json
```

This harness is **fixture evidence**, not clean-machine or authenticated live
host evidence. Run it only after integration and on the reported native target.
Windows results must come from the reported x64 or ARM64 architecture; cross-compilation and x64 emulation on ARM64 are insufficient.

Public reports contain only exact commit, platform/artifact identities, command
names/results, bounded categorical observations and missing evidence. Exclude
prompts, transcripts, credentials, environment values, paths and raw process
output. Keep any recovery data private. Record CLI/Desktop activation and
account/Antigravity scope separately. No result asserts method understanding,
application or answer improvement.

Removal must preserve unrelated files, credentials/history, trust unless
explicitly reset through a supported operation, and unknown/modified payloads.
Incomplete recovery is a blocker with retained bytes, not success. Public
GitHub transport/signing verification is a separate postpublication gate.
