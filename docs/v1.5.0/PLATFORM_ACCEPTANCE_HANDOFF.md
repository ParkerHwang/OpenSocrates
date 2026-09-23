# Platform acceptance handoff for the v1.5 candidate

This handoff is for a reviewer with a disposable macOS or Windows host. It is
not a release instruction. Use the exact Draft PR head being reviewed and
record the archive SHA-256, packaged runtime SHA-256, installed guide/schema
hashes, Codex client version, selected model and effort, and host architecture
before interpreting any result. The archive still reports product version
1.4.0 on the v1.5 candidate branch; its filename is not proof of release
identity. Reconcile the Git commit and built package bytes separately.

## Evidence already available

- PR #95 CI at `efeb436aeb80dabd9a3df9571e66a3de280eadad` passed native
  Windows x64 source/package fixtures, including linked worktrees, junction and
  copied-root rejection, frozen SQLite migration/backup/deletion, and owner ACL
  checks. The hosted Apple Silicon job passed frozen package checks and installed
  the candidate in a fresh runner. These are synthetic and package receipts.
- A disposable macOS `CODEX_HOME` probe using the ChatGPT desktop-bundled
  `codex-cli 0.155.0-alpha.16.3` requested `gpt-6-sol` at medium effort,
  retrieved an installed project-memory pack, and completed a dependent fixture
  with and without hooks. The installed ZIP and guides/schemas have recorded
  SHA-256 identities. The pack reports `application: unverified`; the artifact
  supplies the observed-behavior evidence. No live Windows Codex task was run.

## Non-destructive acceptance on a fresh host

1. Start from a clean temporary user profile or VM snapshot with no
   OpenSocrates registration. Record Codex client/account model access and
   supported effort before selecting a task tuple. Do not add a credential or
   paid service to bypass missing access.
2. Download or build the candidate archive from the exact reviewed commit.
   Compare its SHA-256 and member manifest with the reviewed artifact. Record
   package version separately from source commit. Keep the real Codex profile
   and active plugin installation untouched.
3. Point `CODEX_HOME` at an owner-only disposable directory and install the
   candidate archive only there. Check that the installed skill, memory request
   and context-pack schemas, and launcher match the archive hashes.
4. Create a disposable Git worktree and a separate local Markdown directory.
   Exercise enrollment preview/apply, one attributed public decision, snapshot
   freshness, cold recall, a source change, record deletion, and exact-project
   deletion. Assert no project data is written under either source root. Run
   `tools/check_frozen_memory.py` against the frozen runtime and
   `tools/check_windows.py --packages` on Windows, or the corresponding
   `make release-check` on Apple Silicon.
5. Where the exact model is available, run one fresh live task that explicitly
   retrieves the installed pack and depends on its accepted decision. Repeat
   with hooks disabled. Capture JSONL event types, tool exits, final artifact,
   per-run input/cache/output/reasoning usage, wall time, and all repairs.
   Compare the answer with current source and scoped intent; an emitted pack
   alone does not prove application.
6. Remove only the disposable profile and fixture roots after the evidence is
   secured. Verify the host's original plugin inventory and configuration are
   unchanged. A failed cleanup is reported, not silently broadened.

## Separate permission boundary

The existing previously-used-Mac purge/reinstall harness touches actual account
homes and is destructive. It is **not** part of the procedure above and has not
been authorized for this work. If a future review requires it, present the exact
target host, owned-file inventory, backup/rollback point, commands, expected
state changes, and stop conditions for a separate decision. A fresh disposable
profile or hosted CI runner cannot establish that destructive lifecycle path.

## Receipt and stop rules

Record every attempted command and its exit/status, including invalid requests,
lock/contention failures, missing models, and repairs. Keep usage and account
limits separate from model availability and billed cost. Secret canaries must
stay absent from the database, journal, backup, export, diagnostics, and packaged
evidence. Stop the acceptance lane on an owner, reparse, identity, or deletion
boundary failure; preserve the fixture for review without trying an unsafe
alternate path. Never infer release readiness or model-quality improvement from
these platform checks.
