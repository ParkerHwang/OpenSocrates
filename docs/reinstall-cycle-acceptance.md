# Same-machine native removal and reinstall acceptance

[한국어](reinstall-cycle-acceptance.ko.md) · [Native guide](native-v1.6.md)

This procedure records **same-machine reinstall**, never clean-machine evidence.
It is also separate from preserving an existing v1.5 installation through
`adopt`. Historical 1.3.1→1.4.0 purge/trust-reset evidence remains
[version-pinned](https://github.com/ParkerHwang/OpenSocrates/blob/v1.4.0/docs/reinstall-cycle-acceptance.md)
and is not the Go candidate's active procedure.

On macOS ARM64 or Windows x64, use approved exact-commit native assets and a
selected verified owned profile/scope. Capture the pre-operation inventory,
state, registration, enabled/trust status and scheduler ownership in private
recovery state. Confirm that the selected installation can be safely removed
and that active host use is stopped by the user where required. A removal/reinstall
cycle changes real state and requires explicit authorization.

Use the native manager's `remove --host <profile>` with the exact scope, verify
owned registration/files are removed, then `install --host <profile> --package
<absolute-bundle>` and verify the new inventory, state and registration. For
Antigravity retain the explicit workspace or global selection. Do not infer
purge/trust-reset/npm deletion from ordinary removal. Preserve unrelated files,
host configuration/history/credentials, unknown data and intended disabled state.

Use opt-in scheduler controls to ensure a single owner throughout. Test an
interrupted transaction through its original journal and `recover --transaction
<ID>`; never erase locks/backups/checkpoints to restart blindly. Modified/foreign
replacements or unverified recovery bytes require a safe conflict/unavailable
result, not a forged completion.

Record exact commit, asset hashes, native environment, commands/results,
rollback/removal/reinstall outcomes, scheduler and categorical host observations.
Separate plugin registration, hook review, fresh-session loading, actual delivery,
agent reading/application and useful results. Do not publish raw output,
transcripts, credentials or paths. State missing production signing, clean-machine,
Windows/macOS-native and live-host evidence explicitly. Isolated Go lifecycle
fixtures in the clean-machine guide cannot substitute for this actual cycle.
