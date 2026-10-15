# Frozen Windows ARM64 actual-payload adoption qualification

This inactive historical reproducer records the observed run at implementation
commit `bc151afdb9a9d6845906b05ec2efb022961fd45f`. The `.txt` files are not
supported installation tools or active Go build/test inputs. Node and PowerShell
here reproduce the old v1.5 installation and disposable test setup; they are not
dependencies of the Go product.

The [receipt](../../native-npm-adoption-windows-arm64-bc151af.json) is **PARTIAL**:
Go adoption/status/recovery and exact payload rollback passed, but the original
v1.5 npm entry installer did not complete. Its elevated VM environment creates
Administrators-owned files that the original current-user-SID guard rejects.
No ownership guard, account setting, privilege or OS policy was weakened to
make that installer pass. The legacy layout was explicitly initialized from
the checksum-verified official ZIP using the released three-field marker and
marketplace schema. This is actual-payload evidence, not original-installer
adoption success or live Codex evidence.

## Source and artifact identity

The environment was the user's Windows 11 ARM64 VM. The new management binary
is native ARM64; only the legacy Node/v1.5 x64 components use emulation.
Source and package identity remain separate from the native CI build of the
same revision.

- Native bundle manifest SHA-256:
  `3a9f14f6ed52c8e45cfad0faecea4b9596cfc915ff93d0dfca261786c20597f7`.
- Native manager SHA-256:
  `5fbbf573ca299e2dda000e2a42f7af090a37539fcbef87776e00ba9c24b9d1a3`.
- Public v1.5 Windows x64 ZIP SHA-256:
  `f16360daaabb7e1d66084afcb50257d9ac395e561d72b7a630d4136ac19f2425`.
- Public npm `opensocrates@1.5.0` TGZ SHA-256:
  `76a60761b3c0cafcec95fd158f6751b097aab5d9294b8a8be330e28c97a8e11b`.
  Its recorded registry SHA-512 integrity and SHA-1 both match the downloaded
  bytes. The private-prefix npm install used that TGZ offline with scripts
  disabled; no active global npm installation was changed.
- Frozen `verify-windows.mjs.txt` SHA-256:
  `fc48366022e6cffdae82b866f11b177b569ed0bf33aa3c19a3905c0134bd4000`.
- Frozen `source-layout-v3.ps1.txt` SHA-256:
  `4b2aae28b6b930eb18317b9b8241d94e2c5ad5caf1133f6f91cf5a3137babc88`.
- Frozen `seal.ps1.txt` SHA-256:
  `af07d2ac194f01d92ee768742a12f9a5dd389175675ae20d95b9b3fab1ad7c53`.
- Frozen `hostfixture.go.txt` SHA-256:
  `0dc7382867d2fc49b4240cf8f49bb626bdb4b6ce0decaadef8461cee9e93497d`.

## Recorded execution and reproduction

The Mac build ran `make package TARGET=windows-arm64` at the source commit
above. Metadata-free transfer used `ditto -c -k --norsrc --noextattr
--keepParent dist/native/windows-arm64 <transfer-zip>`; its ZIP SHA-256 was
`78e325c2017f3223f9a913247aade8e7eeeb03f6e13ceb5852fb0aa8f3be7599`.
The guest launched the isolated runner with `powershell -NoProfile
-ExecutionPolicy Bypass -File <isolated-runner>`, then ran `node
verify-windows.mjs` from the disposable fixture. The receipt preserves the
actual inner command templates, exits and bounded preservation checks without
personal paths or raw process output.

To reproduce, use a disposable checkout at the recorded revision and an
isolated current-user-owned Windows ARM64 directory whose name contains
`npm-adoption-`. Copy the frozen sources to their executable filenames; preserve
the UTF-8 BOM in `source-layout-v3.ps1`. Create `fixture-owner.json` with schema
`opensocrates.private-verification/1.0.0`, id `20261012-pinWPO-interactive` and a
disposable qualification purpose. Do not use an existing user's installation
or registry settings.

Supply the checksum-verified official v1.5 ZIP/checksum, npm TGZ, published
`opensocrates.mjs`/`windows.ps1`, official Node 24.21.0 Windows x64 archive and
its bundled npm CLI. Extract Node under `node-v24.21.0-win-x64`, copy `node.exe`
to the fixture root, and build the frozen Go fixture as `codex-fixture.exe`
with `GOOS=windows GOARCH=arm64`. Extract the native bundle under
`candidate/windows-arm64`. Seal only this explicitly owned disposable fixture,
then run the frozen Node harness. These are reproduction instructions, not
additional executions claimed here. Write a new receipt for any rerun; never
relabel the historical receipt as evidence for a newer revision.

## Observed behavior and boundaries

Go adoption, status and transaction recovery exited 0. Disabled integration,
one native update owner, settings/trust/unknown-field bytes, unrelated npm
files and the complete original payload were preserved. Recovery restored the
legacy payload, desired-state bytes and fixture registration exactly. Status
reported deferred activation: installed 1.6.0 while the fixture observed 1.5.0
until a fresh session or host reload.

The exact 341,142,832-byte legacy Codex executable previously exceeded the Go
256 MiB limit. The corrected implementation accepts it under a 512 MiB file
bound with streamed hashing/copying. Native CI separately runs the exact-size
synthetic regression, limit rejection, ownership/ACL/reparse, scheduler,
interrupted recovery and helper replacement tests.

Early setup attempts stopped at UTF-8 parsing or missing fixture sidecar
initialization. The final run used a fresh Codex fixture and uniquely named
transfer scripts; no production source or guard was changed for these setup
corrections. Disposable diagnostic directories were retained rather than
deleting unverifiable contents.

Original-installer completion, production signing/public updates,
clean-machine acceptance and real host trust/activation remain release gates.
Released Windows v1.5 had no supported scheduled updater to take over. Enabled
legacy-updater takeover is the separately recorded macOS qualification.
