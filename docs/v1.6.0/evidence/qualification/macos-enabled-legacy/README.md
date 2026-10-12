# Frozen macOS enabled legacy updater qualification

This is an inactive historical reproducer for the observed qualification at source and package commit `3724bf803661b34cd2b8c54e1d5852dbc4f3e457`. It is not a supported installer, recurring automation, current validation gate, or claim that a later commit has been qualified. The `.txt` sources are not compiled by the repository's active Go build or test paths.

`main.go.txt`, `go.mod.txt`, and `go.sum.txt` preserve the exact bytes used for the recorded run. The source SHA-256 is `430e821151aa8fff6724d3f268171aa30ba5ef764fc8efb19b69310989da81c6`, matching the content-free enabled-updater receipt. The observed executable SHA-256 was `3a2919323482fe8b65a12c7f3fc2c84aba7705e6985952b7b6b377ec07d3ee97`. Freezing these files did not rerun the qualification.

## Recorded commands and results

Run from the historical checkout, the following commands downloaded the original public v1.5 assets, built the one-off harness, and ran it:

```text
gh release download v1.5.0 --repo ParkerHwang/OpenSocrates --dir build/qualification/macos-enabled-legacy/release --pattern opensocrates-1.5.0-codex-plugin.zip --pattern opensocrates-1.5.0-codex-plugin.zip.sha256 --pattern opensocrates.mjs
go -C build/qualification/macos-enabled-legacy build -mod=mod -o qualification .
build/qualification/macos-enabled-legacy/qualification "<checkout>"
```

`<checkout>` replaces the recorded machine's absolute checkout path. The command otherwise matches the observed invocation. No personal path, account identifier, or raw OS output is retained here.

The final harness command exited **0** and emitted these bounded results:

```text
original v1.5 installer installed isolated payload
real unique legacy job enabled and identity observed
native owns the one real unique job; previous policy retired
rollback restores actual legacy job identity and original bytes
enabled legacy updater adoption and rollback qualification PASS
```

The official v1.5 ZIP SHA-256 was `49852b3887d350e858b0d7ba77f5799bad83af10f8d211135cd21dde06d8a7c0`; the original published installer SHA-256 was `ceab84379b6889d621b41b6e6de7f4bb7f7d61cd4fac7b706491d5f91048bfbe`. The locally built native archive SHA-256 was `61d9d34447882d2e81e3a6c81fbe9af41c77da20455622ed8d55275f3e02fb9c`.

## Reconstructing the historical run

Use a disposable checkout and an actual macOS ARM64 GUI user session. The recorded environment used Go **1.27.2**, the GitHub CLI, and Node **24.21.0** at `/opt/homebrew/opt/node@24/bin/node`. Node is used only to execute the authentic historical installer. It is not a dependency of the v1.6 supported installation path. The frozen harness keeps this recorded executable path; changing it changes the source hash and creates a different qualification input.

From a checkout containing these frozen records, choose an unused absolute path for the disposable checkout. The following commands leave the current working checkout undisturbed and restore the `.txt` files to their original ignored build directory:

```sh
qualification_record="$PWD/docs/v1.6.0/evidence/qualification/macos-enabled-legacy"
qualification_checkout="/absolute/path/to/disposable-checkout"
git worktree add --detach "$qualification_checkout" 3724bf803661b34cd2b8c54e1d5852dbc4f3e457
mkdir -p "$qualification_checkout/build/qualification/macos-enabled-legacy/release"
cp "$qualification_record/main.go.txt" "$qualification_checkout/build/qualification/macos-enabled-legacy/main.go"
cp "$qualification_record/go.mod.txt" "$qualification_checkout/build/qualification/macos-enabled-legacy/go.mod"
cp "$qualification_record/go.sum.txt" "$qualification_checkout/build/qualification/macos-enabled-legacy/go.sum"
cd "$qualification_checkout"
```

The original `build/qualification/macos-enabled-legacy` location is required: `go.mod` resolves the repository module through `replace ... => ../../..`.

If the exact historical local native package is unavailable, build the historical source's local unsigned package before executing the harness:

```sh
go run ./src/opensocrates/cmd/opensocrates-dev build --target darwin-arm64 --output dist/runtime
go run ./src/opensocrates/cmd/opensocrates-dev package --target darwin-arm64 --runtime-root dist/runtime --output dist/native/darwin-arm64
gh release download v1.5.0 --repo ParkerHwang/OpenSocrates --dir build/qualification/macos-enabled-legacy/release --pattern opensocrates-1.5.0-codex-plugin.zip --pattern opensocrates-1.5.0-codex-plugin.zip.sha256 --pattern opensocrates.mjs
go -C build/qualification/macos-enabled-legacy build -mod=mod -o qualification .
build/qualification/macos-enabled-legacy/qualification "$PWD"
```

These are reproduction instructions, not additional commands claimed to have run while freezing this record. A fresh build may have different binary or archive hashes. A rerun writes a new content-free receipt under that disposable checkout's `build/evidence/native-npm-enabled-updater-darwin-arm64.json`; it must not replace or relabel the historical receipt as evidence for newer source.

## Observed behavior and limits

The original published v1.5 installer installed its authentic release ZIP under an isolated HOME. Its original `auto-update enable --host codex` command registered a real per-user LaunchAgent. A bounded Go adapter mapped only the exact logical `com.opensocrates.auto-update` identity and its owned canonical plist to one generated disposable OS label. Direct `launchctl print` observations verified the complete legacy npx arguments, configured timer interval, and zero executions.

The Go Manager adopted the installation through its normal lifecycle engine. The same unique OS label then contained the native management CLI updater arguments and native timer interval. The old enabled policy was retired and the native policy had the sole update owner. The deliberately disabled Codex integration, host configuration and trust settings, application settings, installation key, and isolated original-installer npm fixture retained their bytes.

Recovering the committed transaction restored the exact canonical legacy plist, desired-state JSON, payload snapshot, and live legacy argument identity. Final cleanup booted out only the unique owned job and directly confirmed its absence. The final receipt records this cleanup.

The following boundaries are part of the evidence:

- The production fixed-label job and the user's active installation were untouched. Initial read-only checks found no production fixed-label job or plist on the recorded Mac. This is not a production fixed-label installation qualification.
- Only owned target print/bootstrap/bootout operations reached launchctl. The adapter's broad-domain fallback projected solely from the actual owned target's observed presence or absence; unrelated jobs were not enumerated.
- RunAtLoad was suppressed only in the transient mapped OS plist. Authentic canonical installer and rollback documents retained their original bytes. No scheduled updater, login trigger, timing behavior, or update network request executed.
- Codex authentication and registration responses came from a disposable Go fixture. No actual account login, live-host delivery, model call, or host trust approval is claimed.
- The legacy scheduler npx executable was a disposable Go fixture that failed on unexpected execution. Scheduler ownership and command identity were observed; actual npm execution was not qualified.
- npm preservation covered an isolated copy of the original published installer, not a globally installed registry package.
- Native activation used the locally built unsigned package through the Manager qualification API. Production publisher signing credentials were not used or qualified.
- Earlier observation attempts stopped because this macOS exposed the timer as `run interval`, rather than `event triggers`. The final successful harness checks `run interval` against the mapped owned plist's StartInterval. This was an observation-parser correction, not a production source change.
