# Native installation, migration and updates — v1.6.0 candidate

[한국어](native-v1.6.ko.md) · [Setup](setup-guide.md) · [Security](../SECURITY.md)

This is the unreleased Go implementation. Commands describe candidate behavior;
passing source checks does not qualify a production release. Actual results,
commit, environment and remaining gates belong in the implementation handoff.
No production signing credentials or trusted production root are provisioned.
Do not install this candidate over an active installation without authorization.

## Download and first-install trust

The distribution channel is [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases),
with native `opensocrates`/`opensocrates.exe` and the matching bundle:

| Target | Bundle |
| --- | --- |
| macOS ARM64 | `opensocrates-v1.6.0-darwin-arm64.zip` |
| Windows x64 | `opensocrates-v1.6.0-windows-x64.zip` |

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
paths such as `"C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"`. Global/workspace
scope must remain the same for status, updates, disable/enable and removal.

```text
./opensocrates verify --host codex --package /absolute/path/to/bundle.zip
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates manage diagnose --host codex
./opensocrates update --host codex --package /absolute/path/to/new-bundle.zip
./opensocrates disable --host codex
./opensocrates enable --host codex
./opensocrates remove --host codex
```

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

Only Codex macOS ARM64/Windows x64 are scheduled-update targets in v1.6.0.
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
fail open explicitly. No shell change or new platform is implied.

Canonical production trust data is `config/update/root.json` and
`config/update/identities.json`, embedded by Go generation under
`internal/update/trustconfig`. The candidate has no approved production root or
platform publisher identities. Mutable update policy, categorical receipts and
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
Codex app-server pinned to `0.144.4` before journaled replacement. Do not use this
flag when you want existing approvals preserved; trust is never auto-approved.
Actual native removal/rollback and host trust evidence remain required.
