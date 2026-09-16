# Security Policy

## Supported versions

Security fixes are provided for the latest `1.x` release. OpenSocrates 1.4.0
supports Codex only. Pre-1.0 builds and retired host integrations are unsupported.

## Report a vulnerability

Do not publish credentials, private prompts, transcripts, workspace data, or
exploit details in a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/ParkerHwang/OpenSocrates/security/advisories/new).
Include the affected version and platform, a minimal reproduction, the observed
impact, whether private user data is exposed, and any suggested mitigation.
If private reporting is unavailable, request a private contact channel in an
issue without vulnerability details. Response timing depends on reproducibility,
severity, safe fixes, and maintainer availability.

## Security boundary

The default Codex submission entry emits discovery guidance only. It starts no
selector-model request and creates no initial method artifact. The decision
command loads fixed canonical content and retains only volatile, context-scoped
delivery identities and agent availability assertions. It never treats an agent
assertion as proof of applied reasoning. Missing fixed package/source content
does not authorize a CWD-controlled fallback. This command adds no disk state,
raw prompt logging, conversation retention, screenshot capture, authentication
call, or telemetry.

The retained legacy Codex selector is a separate compatibility path. It uses the
pinned SDK and existing Codex authentication in an isolated worker, with bounded
read-only context access, disabled recursive hooks/plugins, a deadline, and
fail-open cleanup. Its temporary method artifacts contain authored content only.
A native read receipt is limited to the supported callback and exact artifact;
it cannot prove model understanding, method application, or improved answers.
Legacy SDK credential-copy and POSIX context access are unavailable on Windows.

OpenSocrates has no backend, telemetry, separate account, or API-key requirement.
Ordinary model requests remain subject to Codex service terms. Host-managed policy
and hook approvals remain part of the host trust boundary. Installation and
synthetic fixtures do not establish live hook delivery.

Release and package SHA-256 inventories detect corruption and enforce complete
closed payloads. `diagnose` checks the installed package against its manifest.
Unsigned checksums cannot authenticate bytes against an attacker who can replace
both the payload and its metadata. Release publication requires exact source
identity, verified asset transport, and immutable GitHub releases.

The installer validates managed-path ownership and preserves unrelated files.
Installation and removal are transactional; a failed activation restores verified
prior state. If rollback cannot safely restore a backup, it preserves the backup
and reports its exact recovery path. Purge refuses unknown, changed, linked, or
in-use payloads. Codex trust is preserved unless the explicit `--reset-trust`
option requests removal of the seven exact OpenSocrates trust entries through a
validated transactional configuration update. Conversation history is preserved.
Retired-host installation state must be cleaned up with the installer version
that owned it; 1.4.0 does not reinterpret it as Codex state.

The optional macOS LaunchAgent uses the verified installer and the selected npm
channel. It does not read or terminate active Codex sessions. Its owner-only
receipt contains version, timestamp, host result, and an error category, without
prompts, transcripts, credentials, workspace paths, or raw errors. Automatic
updates and automatic major upgrades are opt-in. Windows scheduled updates are
unavailable; use manual updates.

Windows x64 packages use real owner/DACL checks, binary I/O, file locks, and ZIP
path validation. Signing, notarization, SmartScreen reputation, Windows ARM64,
and separate clean-machine or GUI behavior are not inferred from package tests.
See [Windows support](docs/windows-support.md) and the version-specific release
record for measured evidence.
