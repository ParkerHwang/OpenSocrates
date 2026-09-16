# Clean Apple-silicon Mac acceptance

[한국어](clean-machine-acceptance.ko.md)

This procedure tests Codex on a real newly configured Mac. It uses the actual
account's default Codex home. It is not an isolated fixture or same-machine
reinstall. Existing OpenSocrates state, registrations, managed roots or updater
files block the clean baseline.

Install Node.js 20+, Codex CLI, Git and GitHub CLI. Sign in to Codex and GitHub.
Check out the current pull request and wait for successful native macOS CI at
its exact head. The checkout must be clean.

```sh
gh repo clone ParkerHwang/OpenSocrates
cd OpenSocrates
gh pr checkout YOUR_PR_NUMBER
node tools/clean_machine_acceptance.mjs
```

The harness verifies architecture, authentication and the unused baseline;
binds the PR, CI run and native artifact to the exact commit; checks the Codex
archive against the combined manifest; and packs the nine-file npm installer.
It installs Codex from these candidate bytes, checks desired state, registration,
managed layout and status, and writes a privacy-safe report. It does not enable
automatic updates or prove the public npm/GitHub download path. After publication,
that path needs a separate check.

Complete the two categorical fields in the printed `manual-observations.md`:
Codex plugin recognition and host runtime loading. Use a fresh interactive Codex
task, review its OpenSocrates hooks, and record observed results only. Change
`PENDING` to `PASS` or `FAIL`; add no free-form text, raw output, prompts,
transcripts, identities, credentials or local paths. Run the printed `--pack`
command. The ZIP contains only `result.json`, `result.md` and
`manual-observations.md`.

A checksum or baseline failure blocks installation. Registration failure attempts
rollback; a post-install assertion failure leaves state available for diagnosis.
A failure bundle is produced automatically. A package check alone is not live
hook or method-application evidence.

To remove the test installation after collecting the result, close Codex and run:

```sh
node installer/opensocrates.mjs remove --host codex --purge
# Only when resetting the seven exact OpenSocrates hook approvals is intended:
node installer/opensocrates.mjs remove --host codex --purge --reset-trust
```

A live cache keeps purge incomplete. Do not report success until the named
process is closed and the command completes. Authentication, user history and
unrelated configuration remain intact. Purge does not restore removed caches.
