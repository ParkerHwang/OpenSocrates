# Security Policy

## Supported versions

Security fixes are provided for the latest `1.x` release. Version 1.5.0 preserves
the v1.4 Codex foundation and adds native Mac Claude
Code, content-only Claude account delivery, and modular Antigravity content.
The Windows continuation supports content-only Claude account verification/export
and Antigravity modular lifecycle on x64; native Windows Claude Code is excluded.
Live account selection and conversation-app loading require separate observations.
Pre-1.0 builds and retired
host integrations are unsupported; they are not silently adopted by a new profile.

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

The default native submission entry emits discovery guidance only. It starts no
selector-model request and creates no initial method artifact. The decision
command loads fixed canonical content and retains only volatile, context-scoped
delivery identities and agent availability assertions. It never treats an agent
assertion as proof of applied reasoning. Missing fixed package/source content
does not authorize a CWD-controlled fallback. This command adds no disk state,
raw prompt logging, conversation retention, screenshot capture, authentication
call, or telemetry.

The Claude adapter has its own bounded JSON normalization and native response
shape. It drops private prompt/transcript fields, resolves complete controller
locations only inside the installed package, and never opens a transcript or
initializes a database. Stop and SessionEnd do not require a repair or assert a
native application receipt. Unavailable native entry fails open with empty output.

Claude account exports and Antigravity modular packages contain complete authored
content without hooks, runtimes, or credential access. An Antigravity standing
rule links the owned controller; it never authorizes unrelated account or file
actions. Workspace/global origins and existing user instructions remain separate.

Windows addon operations refuse junctions/reparse ancestors, foreign ownership,
untrusted writable DACLs, unknown files and changed inventories. New directories
are created with the current user's explicit owner and protected DACL. A held
directory lease blocks ancestor rename during mutations; an exclusive operation
lock is never removed as stale automatically. Rollback preserves changed
replacement content and its recovery backup. Local drive paths are required;
network shares are not qualified. Existing settings are not normalized by
rewriting permissions. ZIP paths reject aliases, streams, links, special entries,
case collisions and file/directory conflicts before extraction. Portable content
archives carry fixed regular-file modes and no executables. Account exports use
verified captured bytes and refuse conflicting output files.

The retained legacy Codex selector is a separate compatibility path. It uses the
pinned SDK and existing Codex authentication in an isolated worker, with bounded
read-only context access, disabled recursive hooks/plugins, a deadline, and
fail-open cleanup. Its temporary method artifacts contain authored content only.
A native read receipt is limited to the supported callback and exact artifact;
it cannot prove model understanding, method application, or improved answers.
Legacy SDK credential-copy and POSIX context access are unavailable on Windows.

OpenSocrates has no backend, telemetry, separate account, or API-key requirement.
Ordinary model requests and host conversation storage remain subject to the
chosen host's authentication, privacy settings, permissions, and service terms.
The product's no-retention contract does not replace the host's retention policy.
Host-managed policy
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
Retired-host installation state must be reconciled with the installer version
that owned it; the new profiles do not reinterpret it as Codex or addon state.
The additive Mac driver verifies exact package inventories and owned markers,
preserves disabled state, and rejects unknown or modified collisions. Native
Claude registration uses supported host operations; Antigravity touches only its
owned rule/skill files. New profiles support exact owned removal, without purge,
trust reset, or automatic updates. Account export never activates an account
skill; preserve the old skill and its backup until replacement qualification.

The optional macOS LaunchAgent uses the verified installer and the selected npm
channel. It does not read or terminate active Codex sessions. Its owner-only
receipt contains version, timestamp, host result, and an error category, without
prompts, transcripts, credentials, workspace paths, or raw errors. Automatic
updates and automatic major upgrades are opt-in. Windows scheduled updates are
unavailable; use manual updates.

Those scheduler controls remain in the existing Codex lane. `--host all` does
not expand it to the additional profiles. Local archive installation
requires paired `--asset` and `--checksum`; checksum matching does not create a
published release or establish live host trust.

Windows x64 packages use real owner/DACL checks, binary I/O, file locks, and ZIP
path validation. Signing, notarization, SmartScreen reputation, Windows ARM64,
and separate clean-machine or GUI behavior are not inferred from package tests.
See [Windows support](docs/windows-support.md) and the version-specific release
record for measured evidence.
