# Installation and runtime reference

[한국어](advanced-usage.ko.md) · [Native commands](native-v1.6.md)

The unreleased v1.6.0 candidate uses native Go execution and direct GitHub
Release distribution. Users need their chosen host application and approved
native assets, without Python, Node.js, npm or Go. See the native guide for
install/adopt/update/verify/export/remove, automatic updates and journal recovery.
The default and `--host all` select Codex only. Native Windows Claude Code and
additional platforms remain excluded.

## Trust, disable and activation

Review the seven Codex hook commands in an interactive session through `/hooks`.
Non-interactive `codex exec` can skip untrusted hooks. Adoption/update must
preserve host trust and intentionally disabled integrations; enable through the
explicit host controls when desired. Account ZIP export is separate from account
upload/activation. Antigravity global/workspace registrations remain explicit.
A new installed version may require a fresh session or reload. `status` and
`manage diagnose` report local inventory/registration, not live method application.

## Runtime behavior

Codex hooks provide lightweight discovery. The active agent determines whether
a materially changed judgment needs help and retrieves the complete eligible
canonical procedure. The normal decision path makes no additional model or
authentication call. `decision codex --stream` retains volatile retrieval state
only in that process; a new process/context cannot inherit a full-read assertion.
See [decision-point retrieval](decision-points.md) for the wire contract.

Legacy selector compatibility is a distinct Go adapter using the pinned external
Codex app-server protocol, isolated authentication/context, bounded read tools,
deadlines, cancellation and cleanup. Unsafe/unavailable/version-incompatible
conditions fail open. It is not silently removed or called by normal hooks.
Windows retains the explicit unavailable credential-copy/POSIX context boundary.

The v1.5.0 revision-3 content baseline preserves all 48 methods, English/Korean
semantics, teacher questions and response/shared guides. No method-body upgrades
are included. Intentional validate-before-scope behavior rejects a malformed
route before clearing availability; refactoring does not change other wire or
stored-state semantics.

## Ownership and recovery

A closed verified inventory binds package bytes before activation. Installation,
update and removal share journaled transaction/recovery; transport, registration
and OS protection remain separate. Preserve foreign/modified files, unknown
locks and verified backups when safe recovery is unavailable. Do not bypass
ownership, ACL/reparse or concurrency checks to force a successful command.
One update owner manages each installation; explicit npm adoption coordinates
the old scheduler rather than uninstalling unrelated packages/data.

Codex opt-in stable updates use a per-user Mac LaunchAgent or Windows Task
Scheduler outside hook execution. Signed metadata must satisfy trusted-root,
expiry, rollback, platform/inventory and compatibility checks. Major/breaking
schema releases are not automatic. Production trust/signing are still release
gates for this candidate. Other profiles retain manual lifecycle.

## Evidence and development

Source code is under `src/opensocrates/`, methods under `content/methods/`, schemas
under `schemas/source/` and templates under `plugin-src/`. Regenerate outputs;
never hand-edit them. Follow [CONTRIBUTING.md](../CONTRIBUTING.md): implement and
integrate fully before final checks. Native platform, clean-machine,
same-machine reinstall, authenticated host and public-release evidence are
separate. Historical releases remain version-scoped. The no-retention and
fail-open boundaries are described in [SECURITY.md](../SECURITY.md).

JSON parser hardening intentionally rejects duplicate keys and unpaired Unicode
surrogates. Complete requests are validated before context/scope mutation; unsafe
or unknown newer settings are never overwritten by fallback defaults. Compiled
content changes only release `product_version` to `1.6.0`, preserving revision-3
method/projection/policy identities. Legacy compatibility is opt-in and pinned
to external Codex `0.144.4`; availability is not authenticated live evidence.
Installation diagnostics are `manage diagnose --host HOST`; existing runtime
`diagnose codex` semantics remain separate.
