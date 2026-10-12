# Native installation, migration and updates — v1.6.0 candidate

[한국어](native-v1.6.ko.md) · [Setup](setup-guide.md) · [Security](../SECURITY.md)

This is the unreleased Go implementation. Commands describe candidate behavior;
passing source checks does not qualify a production release. Actual results,
commit, environment and remaining gates belong in the implementation handoff.
The current Mac has a verified Developer ID identity and canonical Team ID.
Actual candidate ZIP and standalone installer notarization has received Apple
acceptance; exact source/file identities belong in the release handoff.
Bare CLI trust uses the pinned Developer ID, team and notarization code
requirement. Protected signing runners, final merged-tag notarization, Windows
signing, the production update root and clean-machine download/activation
remain separate gates; see the release preparation/handoff.
Do not install this candidate over an active installation without authorization.

## Download and first-install trust

The distribution channel is [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases),
with native `opensocrates`/`opensocrates.exe` and the matching bundle:

| Target | Bundle |
| --- | --- |
| macOS ARM64 | `opensocrates-v1.6.0-darwin-arm64.zip` |
| Windows x64 | `opensocrates-v1.6.0-windows-x64.zip` |
| Windows ARM64 | `opensocrates-v1.6.0-windows-arm64.zip` |

The bundle includes `bundle-manifest.json`, the management/runtime executable,
Go update helper, schemas/content identity and host packages. Windows has no
native Claude Code package. Go, Python, Node.js and npm are unnecessary on the
user's machine. External host executables/login are still needed for native
host registration and normal host use.

Before execution, authenticate the installer using the published platform
signing/delivery instructions and independently trusted update root. A checksum
beside a download only detects corruption; it does not establish authenticity.
The candidate cannot claim production first-install trust until macOS
signing/notarization, Windows signing policy and production root/signing custody
are established. Development root fixtures are for isolated testing only.

## Manual lifecycle

Use absolute package paths. On Mac, `./opensocrates` below names the native
executable. On Windows use `.\opensocrates.exe` and quoted local-drive absolute
paths such as `"C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"` or its
`windows-arm64` counterpart. Global/workspace
scope must remain the same for status, updates, disable/enable and removal.

```text
./opensocrates verify --host codex --package /absolute/path/to/bundle.zip
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates manage diagnose --host codex
./opensocrates update --host codex --package /absolute/path/to/new-bundle.zip
./opensocrates remove --host codex
```

Codex enabled state belongs to the host's own controls. Go management preserves
that state during installation/adoption/update; `enable`/`disable` management
commands support Claude and Antigravity, and return unsupported for Codex.

The default and `--host all` mean Codex only. They do not install, update or
remove every integration. Additional profiles require explicit selection:

```text
./opensocrates install --host claude --package /absolute/path/to/bundle.zip
./opensocrates install --host antigravity --package /absolute/path/to/bundle.zip --workspace /absolute/path/to/existing/workspace
./opensocrates status --host antigravity --workspace /absolute/path/to/existing/workspace
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

Native Claude is Mac-only. Omit `--workspace` for Antigravity global scope; never
register workspaces through automatic discovery. Account `verify` and `export`
validate content without host hooks, account login or upload. Back up the old
account skill and enabled state before manually replacing/uploading it. Local
operations do not activate account content.

Verification covers package inventory/identity and local registration, not
agent reading/application or live host delivery. Unknown, modified, foreign,
linked/reparse or unsafe targets are preserved as conflicts rather than deleted.
Ordinary removal touches the selected owned integration. Do not infer broad
purge, trust-reset or npm-uninstall behavior from `remove`.

## One-time adoption of npm installations

Use the released v1.5.0 installation as the migration baseline. Confirm exact
ownership, version, desired state, inventory, registration, disabled state and
old update scheduler before adoption. The Go manager adopts only the explicitly
selected existing owned integration:

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
```

Adoption stages native state/bundles separately, captures verified old state and
scheduler recovery data, coordinates the previous update owner and commits only
after registration/integrity checks. If exclusive ownership cannot be acquired,
stop with the old installation intact. Never run old and new updater jobs
against the same installation. Preserve previous opt-in policy, host settings,
trust decisions and intentionally disabled integrations. Unknown retired
multi-host state is not silently reinterpreted. Do not indiscriminately uninstall
npm packages or delete caches/user content; the old package can remain after its
updater stops owning this installation.

On failure, recovery must restore verified files/state/registration and the old
scheduler, or report incomplete rollback while retaining recovery bytes. Verify
this on real native machines before claiming adoption supported in production.

## Automatic updates and activation

```text
./opensocrates auto-update enable --host codex
./opensocrates auto-update status --host codex
./opensocrates auto-update run --host codex
./opensocrates auto-update disable --host codex
```

Scheduling is opt-in `stable`, every 24 hours, with a five-minute delayed login
check. It uses the logged-in user's LaunchAgent on Mac and Task Scheduler task
on Windows; no service, password or authentication token is stored. Hooks never
check the network or trigger installation. Offline checks leave the active
version intact. Status must distinguish configured policy, actual OS scheduler
state, candidate integrity and activation state; absence is not a successful
scheduler registration.

TUF root/timestamp/snapshot/targets verification checks signature thresholds,
expiry, monotonic metadata, consistent targets, permitted bounded transport,
platform, inventory and runtime/schema compatibility. Major versions or breaking
schema transitions are blocked from automatic activation. A verified local
rollback does not lower the persisted network rollback floor. Root rotation
requires existing/new-root authorization. Missing/expired/invalid metadata and
unprovisioned production root leave updates unavailable without weakening trust.

Codex macOS ARM64 and Windows x64/ARM64 are scheduled-update targets in v1.6.0.
Claude/Antigravity retain manual lifecycle until each registration, reload,
disabled-state, integrity and recovery gate is satisfied. Account ZIPs stay
manual export/upload; no account automation is claimed.

Runtime/content bundles are versioned separately from user settings/state under
`~/.opensocrates/` (`bundles`, `bin`, `native-state.json`, `transactions`). Started
processes retain their bundle identity. Manager/updater self-replacement belongs
to the same verified transaction; Windows uses a Go helper when an executable is
in use. Retain running/recovery bundles and safe rollback data. File activation
can be complete while host activation remains pending. Review changed hook
commands in the host and start a fresh session/reload where required; never
terminate or read a conversation to force activation.

## Recovery

```text
./opensocrates recover --transaction TRANSACTION_ID
```

Durable journals bind pre/post inventories and verified backups to owned targets.
Recovery checks actual files and registrations before replay/restore. Do not
manually delete a lock, journal, changed replacement or backup to bypass a
conflict. Interrupted staging keeps the active version; interrupted activation
must complete safely or restore the verified prior state. If neither is safe,
retain bytes and report `rollback_incomplete` with local recovery guidance.
Local diagnostic paths are private operational information; exclude workspace
paths/raw errors from public receipts. A rollback is not verified until files,
registrations, state and scheduler ownership all agree.

## Compatibility and intentional changes

Compatibility-preserving refactoring separates package transport,
transaction/recovery, host registration, OS protection, distribution profiles,
runtime adapters and typed services/errors. Preserve wire/stored state,
canonical bytes, Unicode, number precision, unknown-field handling,
omitted/null/empty distinctions and fail-open hook semantics. The legacy selector
uses an opt-in Go external Codex app-server adapter pinned to `0.144.4`;
availability checks do not establish authenticated operation. The normal decision path
continues without an extra model/authentication call.

Intentional changes are native direct distribution/adoption, Windows scheduled
updates and signed compatible stable updates with durable self-update recovery.
JSON input rejects duplicate keys and unpaired Unicode surrogates. Complete
decision requests are validated before changing context/scope: an invalid route
must not erase previous availability. Unsafe or unsupported newer settings are
never overwritten by fallback defaults. The 48 method-body upgrades are
excluded. The frozen v1.5.0 tag is
`cf6634310afcf5d5ce58484e67a73151bb4c5999`, content revision `3`. Hashes/complete
baseline inventory belong to V0's implementation record; guide/transport changes
do not authorize new method semantics.

## Qualification still required

The implementation handoff records exact final commands and evidence. Native
Mac and Windows install/adopt/remove/scheduling/self-update/interruption/rollback,
ACL/reparse/concurrency/modified-file regressions, offline behavior and signed
metadata mutation cases require actual results. Cross-compilation is not a
Windows pass. Separate clean-machine acceptance, authenticated host activation,
production metadata/key custody, platform signing and verified public assets
remain release gates until explicitly evidenced. Historical v1.5/v1.4 evidence
cannot be promoted to this Go release. This document authorizes no merge, tag,
publication or active-installation replacement.

## Hook command and trust configuration details

Installation diagnostics use `opensocrates manage diagnose --host HOST`; the
existing runtime `diagnose codex` wire behavior remains separate. macOS commands
use quoted OS environment references `$PLUGIN_ROOT`/`$CLAUDE_PLUGIN_ROOT`, avoiding
textual path macros. Windows Codex CLI/Desktop hooks are qualified only for the
normal inherited default PowerShell command context:

```text
& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" hook codex session_started
```

This is one command in external OS/host scheduling configuration, not a
first-party PowerShell wrapper. Custom/cmd fallback shells are unsupported and
fail open explicitly. ARM64 uses the corresponding `runtime/windows-arm64/`
path with the same command shape; this does not change the shell boundary.

Canonical production trust data is `config/update/root.json` and
`config/update/identities.json`, embedded by Go generation under
`internal/update/trustconfig`. The candidate has no approved production root or Windows publisher identity.
The Mac Team ID is bound to the user-authorized Developer ID certificate; local
signing evidence does not replace notarization and production qualification. Mutable update policy, categorical receipts and
accepted TUF trust state remain separate in installation-private storage.

The compiled content bundle changes only release metadata `product_version` to
`1.6.0`; method, projection and response-policy identity remains revision `3`.
This packaging metadata change is not a method-body upgrade.

## Explicit Codex purge and trust reset

```text
./opensocrates remove --host codex --purge
./opensocrates remove --host codex --purge --reset-trust
```

Purge preflights all removable payloads before mutation, unlike historical
sequential partial cleanup. It removes only proven owned integration/legacy
state and disables the owning scheduler; shared native manager/bundles, npm
packages, conversations/history and unrelated files remain. Unknown, modified,
linked or in-use `.in_use` caches block/pause completion safely.

`--reset-trust` explicitly removes only the seven exact OpenSocrates hook-state
entries. Preserve unrelated TOML bytes, comments, BOM/newlines and host settings.
Validate original/candidate configuration through an isolated no-authentication
Codex app-server with bounded version/stdio capability probes and required
`--strict-config` support before journaled replacement. This management probe is
separate from the legacy selector's `0.144.4` pin; unknown capabilities are
unavailable rather than allowing invalid configuration to fall back to defaults. Do not use this
flag when you want existing approvals preserved; trust is never auto-approved.
Actual native removal/rollback and host trust evidence remain required.

Trust reset is a separately verified transaction under the same lifecycle lock,
completed before purge snapshots/register changes because the host unregister
operation can also modify its configuration. A later purge failure does not undo
the explicitly completed trust reset; report its `trust_transaction` separately.

Production publication additionally requires protected-environment secret
`OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN`, scoped to this repository with
Administration:read solely for the exact GitHub `/immutable-releases` GET.
Release mutations still use the ordinary contents:write workflow token. Missing
or insufficient read permission blocks publication without weakening the
immutable-release check. This credential is a release prerequisite alongside
production root/identity/signing resources, not evidence of release validation.

## User-directed Windows ARM64 scope adjustment

The original preparation limited Windows to x64. The user's subsequent explicit
instruction adds native Windows ARM64 to v1.6.0 Codex CLI/Desktop integration,
Antigravity global/workspace lifecycle, native installation/adoption/removal,
Go helper self-replacement and per-user scheduled updates. It does not change
`--host all`, add native Windows Claude Code, automate account upload or alter
the frozen 48-method v1.5.0 content baseline. Account content verification/export
remains content-only on all supported targets.

Download standalone `opensocrates-v1.6.0-windows-arm64.exe` and matching
`opensocrates-v1.6.0-windows-arm64.zip`. Bundle binaries remain
`bin/opensocrates.exe` and `bin/opensocrates-update-helper.exe`; host runtime is
`runtime/windows-arm64/opensocrates.exe`. TUF target
`stable/windows-arm64/opensocrates.archive` has independent platform identity.
For first installation from the standalone ARM64 executable:

```text
.\opensocrates-v1.6.0-windows-arm64.exe install --host codex --package "C:\Downloads\opensocrates-v1.6.0-windows-arm64.zip"
.\opensocrates-v1.6.0-windows-arm64.exe status --host codex
```

Examples using `.\opensocrates.exe` refer to the bundle's extracted native
`bin/` executable; use the actual downloaded filename when running standalone.

The scheduler remains per-user, opt-in stable/24-hour/delayed-login, preserving
trust/disabled state and one update owner. Native ARM64 CI installation,
ACL/reparse/locks, helper replacement, interruption, rollback and scheduler
results are recorded in the implementation handoff. Production signing,
clean-machine and actual host activation remain separate evidence gates.

The official [Codex 0.144.4 release](https://github.com/openai/codex/releases/tag/rust-v0.144.4)
provides `aarch64-pc-windows-msvc` CLI/app-server executables. These upstream
assets establish distribution availability, not authenticated CLI/Desktop live
delivery. GitHub's [runner documentation](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
lists `windows-11-arm` for native CI. Antigravity's native app architecture and
actual ARM64 loading remain separately unverified; supported OpenSocrates owned
rule/skill lifecycle does not establish native external-host availability.

The previously used Windows VM is ARM64. Any x64 execution there used emulation
and remains supplementary; it cannot qualify native Go ARM64 behavior. Missing
production signing/root/publisher credentials and clean-machine/live evidence
remain release gates for this target too.
