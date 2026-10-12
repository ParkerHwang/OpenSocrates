# Contributing to OpenSocrates

Read [AGENTS.md](AGENTS.md), the shared operating contract, and
[SECURITY.md](SECURITY.md) before changing the project. GitHub issues, pull
requests, exact commit SHAs and Actions are durable shared state. Search open
and closed issues/PRs first; report vulnerabilities privately and remove private
prompts, transcripts, credentials and user paths from reproductions.

## Development setup

Active first-party implementation uses Go. The module pins Go 1.27.2 through
`go.mod`; contributors need that toolchain, Git, and the documented external
host tools for host-specific work. End users need only the native release assets
and their host application: Python, Node.js, npm and Go are not installation or
runtime requirements. Make is an optional task runner; its recipes delegate to
Go commands.

```text
git clone https://github.com/ParkerHwang/OpenSocrates.git
cd OpenSocrates
go mod download
make bootstrap
```

Work on a focused branch from reconciled current `main`. Never push directly to
protected `main`. Read the [v1.6.0 preparation](docs/v1.6.0/README.md) and current
implementation handoff. PR #110 is planning reference, not an implementation
base to reuse blindly; issue #109 tracks preparation only.

## Canonical sources and compatibility

- Runtime, CLI, lifecycle and active development tools belong under
  `src/opensocrates/`; OS filesystem/process protection and host registration
  remain separate from transaction/recovery and package transport.
- Canonical reasoning content belongs under `content/methods/`. v1.6.0 freezes
  the released v1.5.0 baseline. The separate 48 method-body upgrades belong to
  v1.6.1 or later. Preserve English/Korean methods, teacher questions,
  applicability, evidence/stop conditions, response policy and shared guides.
- Teacher questions belong in `content/teacher-questions.yaml`: bilingual,
  three per method, unique within each locale, addressed to the active agent.
  The overlay revision must match the canonical content revision; changing it
  does not rewrite an authored method's revision.
- Schemas belong under `schemas/source/`. Preserve wire formats, persisted
  state, unknown-field policy, Unicode, numeric precision, omitted/null/empty
  distinctions and canonical serialization. Document intentional changes
  separately from refactoring.
- Distribution templates belong under `plugin-src/<host>/`; shared reader and
  decision guidance belongs under `plugin-src/shared/`. Distribution profiles
  and runtime adapters have separate capability lists. `--host all` means
  Codex only. The supported native targets are macOS ARM64 and Windows x64/ARM64.
  Windows ARM64 is an explicit user-directed expansion; native Windows Claude
  Code and other additional platforms remain excluded.
- Do not hand-edit generated files in `schemas/v1/`,
  `content/compiled-*.json`, `build/`, or `dist/`. Commit canonical and generated
  changes together. Regenerate with `make generate`.
- Keep EN/KO user-facing documents semantically aligned. Add no telemetry,
  credential collection, raw prompt/transcript logging, screenshot retention,
  workspace-content retention or hidden reasoning capture. Preserve fail-open
  hooks, bounded selection, cleanup, ownership checks and verified rollback.

## Implementation and final verification

Understand contracts, implement the full scope, integrate delegated changes,
then verify stable files. During ordinary implementation, defer tests, lint,
validation builds and code/security reviews. Reading/writing tests and generating
outputs may happen earlier. A concrete blocking error permits the smallest
relevant diagnostic. Do not test after every edit by default.

Once integration is complete, run the complete source-level suite:

```text
make bootstrap
make format-check
make lint
make generated-check
make content-check
make adjudication-check
make docs-check
make governance-check
make package-check
make security-scan
make smoke
make installer-check
```

Native distribution work additionally runs `make release-check` on the required
native platforms. Use [the native guide](docs/native-v1.6.md) for supported
profiles, installation/adoption, scheduler, recovery and release gates. Exact
commands, results, environment and the verified commit belong in the PR and
handoff. Run Windows x64 and ARM64 gates on their respective native targets.
The user's existing Windows VM is ARM64: previous x64-emulated observations are
supplementary, not native ARM64 qualification. Missing evidence remains missing;
cross-compilation does not validate
Windows ACLs, reparse points, Task Scheduler, running executable replacement or
native host registration. Existing v1.5 evidence is historical and does not
qualify the Go release.

Final verification must cover native install/adoption/remove, offline behavior,
interrupted transactions, rollback, updater/management executable replacement,
signed metadata, expiry/rollback rejection, disabled state, modified foreign
files, host reload boundaries and deterministic generated outputs. Mac
LaunchAgent and Windows Task Scheduler evidence must come from their respective
OS and executable architecture. Windows ARM64 requires its own native binaries,
helper/self-replacement, ACL/reparse, adoption, removal, interrupted recovery and
signed-update checks. Native CLI/Desktop/Antigravity observations are separate. Separate fresh-machine acceptance from reinstalling on a used machine.
Signing credentials, trusted production root, notarization/Authenticode and
public transport verification are release gates, not consequences of a local
build. Do not replace an active installation to gather evidence without the
user's authorization.

Review stable integrated changes with bounded code/security/verifier specialists
where useful. Serialize tests sharing mutable resources. Fix found defects and
rerun affected checks; reuse successful unchanged evidence.

## Pull requests and handoff

Open incomplete work as a Draft PR and complete every template section. Include
the problem/result, compatibility and intentional behavior changes, issue link,
exact verification, evidence level, missing native/live/signing evidence,
privacy/ownership/generated-output effects and remaining limitations. Keep the
PR description current. Do not mark ready until checks pass or unavailable
checks are explicitly documented. Repository automation can add the item to the
OpenSocrates Development project when direct Project access is unavailable.

```text
Current commit: <sha>
Completed: <bounded list>
Verified: <exact commands and results with environment>
Not verified: <commands/evidence and reasons>
Next: <ordered next actions>
Known limitations: <explicit boundaries>
```

Do not merge with pending/failing required checks, missing required live
qualification or a Draft PR. Merge/tag/publication require separate release
approval. Stable behavior begins with the tagged release. Contributions use the
repository's [MIT License](LICENSE).
