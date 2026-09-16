# Installation and runtime reference

[한국어](advanced-usage.ko.md)

OpenSocrates 1.4.0 supports Codex only. Native packages are provided for
Apple-silicon macOS and Windows x64. Node.js 20 or later and an authenticated
Codex CLI are required; the packaged runtime does not require Python.

## Install and update

```sh
npx --yes opensocrates@1.4.0 install
npx --yes opensocrates@1.4.0 status
npx --yes opensocrates@1.4.0 update
```

`--host codex` is optional; `--host all` is a compatibility alias for Codex.
Other host names are rejected before lifecycle mutation. After installing,
start a new interactive Codex session and review the seven OpenSocrates hooks.
Untrusted hooks do not run in non-interactive `codex exec` sessions.
Previously disabled hooks stay disabled after an update; enable them through
Codex's `/hooks` view when you want automatic discovery.

The installer verifies the archive, closed checksum inventory, release identity,
native target, and runtime layout before staging it. Activation is transactional;
if registration fails, it attempts to restore the previous managed installation.
A failed restoration preserves recovery bytes and prints bounded recovery guidance.
Do not manually delete a reported backup before reviewing that guidance.

## Upgrade from 1.3.1

Codex-only installations can use `update` directly. For a multi-host installation,
first remove each retired integration with the version that installed it:

```sh
npx --yes opensocrates@1.3.1 remove --host claude --purge
npx --yes opensocrates@1.4.0 update --host codex
```

Replace `claude` with each retired host you installed. Version 1.4.0 refuses
multi-host desired state instead of silently deleting other integrations or
rewriting their state. Review pending cleanup from the old installer before
continuing. Retired hosts have no 1.4.0 packages, runtimes, or upload archives.

## Removal and hook trust

```sh
npx --yes opensocrates@1.4.0 remove
npx --yes opensocrates@1.4.0 remove --purge
npx --yes opensocrates@1.4.0 remove --purge --reset-trust
```

Ordinary removal unregisters the managed plugin. `--purge` additionally removes
verified OpenSocrates-owned payloads, caches, lifecycle state and updater files.
Unknown files, changed identities and live cache markers prevent a false success.
Close the named Codex process and rerun only when a live cache remains. Purge
preserves conversation history, authentication, unrelated plugins and files.
It does not restore the old cache contents.

Hook trust is separate from payload ownership. Only `--reset-trust` removes the
seven exact OpenSocrates trust sections; unrelated Codex configuration remains.
The reset validates candidate configuration in an isolated app-server process,
uses an atomic replacement, and preserves recovery bytes after unsafe rollback.

## Automatic updates on macOS

```sh
npx --yes opensocrates@1.4.0 auto-update enable
npx --yes opensocrates@1.4.0 auto-update status
npx --yes opensocrates@1.4.0 auto-update run --force
npx --yes opensocrates@1.4.0 auto-update disable
```

The optional user LaunchAgent checks the stable release channel. Updates retain
package verification and rollback. Major versions require explicit policy
consent. The updater records only lifecycle state and a concise result receipt;
it never terminates a running task. Windows uses manual `update` only.

## Verify a downloaded package

For macOS, download the exact version's Codex ZIP, checksum sidecar and installer
from its GitHub Release. Windows uses the `-windows-x64.zip` asset instead.

```sh
node opensocrates.mjs verify --host codex \
  --asset opensocrates-1.4.0-codex-plugin.zip \
  --checksum opensocrates-1.4.0-codex-plugin.zip.sha256
node opensocrates.mjs install --host codex \
  --asset opensocrates-1.4.0-codex-plugin.zip \
  --checksum opensocrates-1.4.0-codex-plugin.zip.sha256
```

A checksum sidecar is a file, not a digest argument. Integrity hashes detect
changed bytes; they are not code signing or an independent authenticity anchor.

## Runtime behavior

Codex receives lightweight discovery guidance at native hook boundaries. The
active agent chooses whether a judgment needs a method, retrieves the complete
authored procedure, and preserves the user's goals, permissions and output.
There is no separate selector-model call on the normal decision-point path.
A persistent `decision codex --stream` process keeps volatile retrieval state;
a new process or context cannot inherit an old full-read assertion.

The retained compatibility selector uses the pinned OpenAI Codex SDK and a
bounded, non-retrying request. This legacy path is distinct from normal hooks.
Timeout, unavailable host, invalid output or unsafe context fails open.
`diagnose codex` checks package identity and inventory without claiming actual
hook delivery, complete method reads or method application.

No OpenSocrates telemetry or raw prompt/transcript retention is added. Temporary
authored artifacts and categorical receipts use private storage and bounded
cleanup. See [SECURITY.md](../SECURITY.md) and
[decision-point retrieval](decision-points.md) for the exact boundaries.

## Development and acceptance

Canonical runtime code lives in `src/opensocrates/`, methods in `content/`,
schemas in `schemas/source/`, and templates in `plugin-src/codex/`. Regenerate
schemas and package output from those sources; do not edit generated files.

Run the source and native gates in [CONTRIBUTING.md](../CONTRIBUTING.md).
[Clean-machine acceptance](clean-machine-acceptance.md) and
[same-machine purge/reinstall acceptance](reinstall-cycle-acceptance.md) provide
different evidence. The latter never proves a separate clean-machine install.
[Windows validation](windows-support.md) remains a native Windows gate.
Publication also requires verification of the public npm and GitHub assets.
