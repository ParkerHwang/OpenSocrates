# Security Policy

## Supported versions and reporting

Security fixes apply to the latest released `1.x` version. v1.6.0 is an
implementation candidate until its release gates, approval and publication are
complete. The requested supported scope is Codex on macOS ARM64 and Windows
x64/ARM64, native Claude Code on macOS ARM64, Antigravity workspace/global on
these platforms and
Claude account content verification/export. Native Windows Claude Code,
additional platforms and retired integrations are excluded.

Do not post credentials, private prompts, transcripts, workspace data or exploit
details in public issues. Use GitHub's
[private vulnerability reporting](https://github.com/ParkerHwang/OpenSocrates/security/advisories/new).
Provide the version/platform, minimal reproduction, impact and suggested
mitigation. If private reporting is unavailable, request a private channel in an
issue without vulnerability details.

## Runtime and host trust

Default native entry emits discovery guidance without an additional model or
authentication request. Decision services load fixed packaged canonical content
and retain only volatile context-scoped delivery identities and agent assertions.
An assertion is not proof of applied reasoning. Missing fixed content does not
authorize a CWD-controlled fallback. Hooks fail open with content-free diagnostic
codes; they do not perform network update checks or installation.

Claude's stateless native adapter normalizes bounded JSON, ignores private
prompt/transcript fields, resolves complete references within the installed
package and never reads transcripts or initializes a database. Stop/SessionEnd
do not add a repair or native-application claim. Account ZIPs and Antigravity
rules/skills contain authored content without executable or credential access.
Local export never uploads or activates account content.

The retained legacy Codex selector is an explicit, separate Go compatibility
adapter for the external Codex app-server protocol pinned to `0.144.4`. It is opt-in and
protocol availability does not establish authenticated operation. It uses
existing host authentication, an isolated temporary environment, bounded
read-only context tools, disabled recursive hooks/plugins, deadlines,
cancellation and process cleanup. It is not invoked by the normal decision
path. Legacy credential-copy/POSIX context capability remains unavailable on
Windows. Any unavailable/version-incompatible path must fail open rather than
silently enabling broader access. Temporary method artifacts contain authored
content only; supported read receipts do not prove understanding, application
or answer improvement.

There is no OpenSocrates backend, telemetry, separate account, API-key
requirement, raw prompt/transcript logging, screenshot retention,
workspace-content retention or hidden reasoning capture. Host model calls,
conversation storage, permissions, authentication and retention remain governed
by the host. Host trust approvals and intentionally disabled integrations remain
user decisions. Installation/offline fixtures do not establish live delivery.

## Lifecycle and filesystem boundary

Package transport, lifecycle transaction/recovery, host registration and OS
filesystem/process protection are separate boundaries. Before mutation, validate
exact owned targets, inventories, release identities, supported profile/scope
and platform. Preserve foreign registrations, modified files, settings,
conversation history, credentials and disabled state. Unknown ownership is not
permission to adopt or delete. New state and journals use private per-user
storage; local registered paths are operational state, not public diagnostics.

macOS protection includes ownership, links, exclusive locks and durable writes.
Windows protection additionally includes actual owner/protected DACL checks,
reparse ancestors, protected directory handles, local-drive requirements and
running executable replacement. Do not weaken those contracts to portable mode
bits or path-only checks. Unsafe ACLs or conflicting files require an explicit
unavailable/conflict result, not silent permission normalization. Archives reject
traversal, links, special entries, aliases/streams, case collisions and
file/directory conflicts before extraction. Content-only archives contain no
executables. Conflicting export files are preserved.

Transactions record verified prior state, stage candidates, apply host-specific
registration, verify the result and complete or restore verified backups.
Recovery checks actual files/registrations against pre/post identities, not
journal claims alone. Unknown locks and modified backups/replacements are
preserved. If safe rollback is unavailable, retain recoverable bytes and report
`rollback_incomplete`; never claim success after a partial restore.

Adoption of a v1.5 npm installation is explicit and one-time. Coordinate its
previous scheduler under a shared exclusive ownership boundary before giving
the Go manager update ownership. Restore the old scheduler if adoption rolls
back. Do not uninstall unrelated npm packages or broadly delete user data.
`--host all` continues to select Codex only. Retired state is reconciled with its
owning version, not reinterpreted as a new profile. Trust reset/purge are separate
explicit capabilities; absence of a supported capability must be reported.

## Signed updates and first-install trust

SHA-256 inventories detect corruption and bind closed payloads. Checksums beside
an archive cannot authenticate an attacker-controlled archive and metadata.
First-install authenticity requires the approved delivery and platform signing
policy plus an independently bootstrapped trusted update root. Never trust a root
just because the update server supplied it.

The Go updater uses signed metadata with trusted-root verification, expiry,
monotonic metadata versions, snapshot/target consistency, bounded permitted
transport, target hashes and platform/profile/schema compatibility. Stable
compatible minor/patch releases are eligible; major or breaking-schema updates
require a separate manual decision and are not automatically applied. Root
rotation must be authorized by the existing root and the replacement root.
Production private signing keys must never enter source, assets, journals or
logs. Development trust fixtures cannot qualify production update trust.

Codex scheduling is opt-in through a per-user macOS LaunchAgent or Windows Task
Scheduler task, outside hook execution, with stable-channel checks at a 24-hour
interval. It stores no password/token and manages only the user's registered
installation. Offline/invalid/expired metadata preserves the active version.
Only one update owner may mutate an installation. Additional host scheduling is
withheld until registration, disabled-state, reload, integrity and recovery
qualification succeeds for that profile/scope.

User state is outside versioned executable/content bundles. Processes retain
started bundle identity. Executable/CLI/updater replacement uses verified
transaction recovery, including the Go helper where Windows replacement requires
it. Retain running and recovery bundles. New files do not imply an already
running conversation loaded them; report deferred activation where reload or a
fresh session is required. Never terminate/read conversations to force updates.

## Release evidence

Require exact source/content identity, deterministic generation, native macOS
ARM64 and Windows x64/ARM64 lifecycle evidence, authenticated host observations where
claimed, clean-machine acceptance, verified public GitHub transport and immutable
release policy. Platform signing/notarization, Authenticode/SmartScreen,
production root/signing custody and metadata publication remain independent
release gates. Cross-compilation, fixtures and old release evidence do not meet
these gates. See [native installation and qualification](docs/native-v1.6.md)
and the exact-commit implementation handoff. No production release is authorized
by this policy or by passing local checks.

Input hardening explicitly rejects duplicate JSON keys and unpaired Unicode
surrogates. Validate complete decisions before context/scope mutation. Never
overwrite unsafe or newer settings with fallback defaults. Canonical production
trust inputs are `config/update/root.json` and `config/update/identities.json`,
generated into the runtime under `internal/update/trustconfig`.

Native Windows Codex hooks are qualified only for normal inherited default
PowerShell; custom/cmd fallback shells are unsupported and fail open. The
configured command uses `$env:PLUGIN_ROOT` to invoke the Go executable, with no
first-party PowerShell wrapper. Mac uses quoted OS environment references rather
than textual plugin-path macros. Installation `manage diagnose --host HOST` and
existing runtime diagnostics have separate contracts.
