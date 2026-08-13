# OpenSocrates contributor and agent protocol

This file is the repository-level operating contract for humans and automated agents. It applies from the repository root. More specific `AGENTS.md` files may add rules for a subtree, but may not weaken the privacy, evidence, generated-source, or protected-main rules here.

## Authority and shared state

Use durable repository and GitHub state, not local chat memory, as the source of truth:

1. tagged release documentation and versioned source;
2. the active issue and pull request, including their latest commit SHA;
3. `CONTRIBUTING.md`, `SECURITY.md`, and this file;
4. required GitHub Actions results;
5. the OpenSocrates Development project for portfolio status;
6. the Wiki for conceptual and operational orientation.

The Wiki and Project are helpful coordination surfaces, but they do not override tagged release documentation, source, or security policy.

## Before changing anything

1. Read this file, `CONTRIBUTING.md`, and the relevant source and tests.
2. Search open and closed issues and pull requests for the same work.
3. Confirm the user need, acceptance criteria, affected host surfaces, and evidence level.
4. Work from current `main` on a focused branch. Never push directly to protected `main`.
5. Use or create an issue when practical. Security vulnerabilities must use the private process in `SECURITY.md`.
6. If you can edit the GitHub Project, move accepted work to `Ready` or active work to `In Progress`. If you cannot, proceed through the issue/PR workflow and let repository automation add the item.

Do not start implementation from an unverified local branch, stale transcript, or another agent's unsupported summary. Reconcile against GitHub first.

## Change rules

- Runtime code belongs under `src/opensocrates/`.
- Canonical reasoning content belongs under `content/methods/`.
- Canonical schemas belong under `schemas/source/`.
- Host templates belong under `plugin-src/claude/` and `plugin-src/codex/`.
- Do not hand-edit generated files in `schemas/v1/`, `content/compiled-*.json`, `build/`, or `dist/`.
- Run `make generate` after changing canonical generated inputs and commit canonical and generated changes together.
- Keep English and Korean user-facing content semantically aligned.
- Do not add telemetry, credential collection, raw prompt or transcript logging, workspace-content retention, or hidden reasoning capture.
- Preserve fail-open behavior, bounded selection, cleanup, transactional rollback, and explicit unknown/unavailable states.
- Distinguish implemented, locally validated, release-validated, and live-probe evidence. Never upgrade a claim because implementation or offline CI exists.

## Validation

Run focused tests while iterating. Before requesting review, run the complete source-level suite described in `CONTRIBUTING.md` when the environment permits it.

Never claim a command passed unless you ran that exact command against the reported commit. Record:

- the last verified commit SHA;
- exact commands and results;
- checks not run and why;
- required authenticated or clean-machine evidence still missing.

Platform-dependent work must state its environment. Native release and packaging claims require the documented Apple-silicon macOS gates. A green offline suite does not prove live host delivery or answer-quality improvement.

## Pull requests and handoff

1. Open incomplete work as a Draft pull request.
2. Complete every required PR-template section. Link the issue with `Closes #N`, `Fixes #N`, or explain why no issue exists.
3. Move reviewable work to `In Review` if permitted; otherwise Project automation will track the PR.
4. Keep the PR description current when scope, validation, or limitations change.
5. Do not mark ready for review until the reported local checks pass or every unavailable check is explicitly documented.
6. Do not merge while required checks are pending or failing, required live evidence is missing, or the PR remains Draft.

Every handoff must be recoverable from GitHub without access to the previous machine or conversation. Put this in the issue or PR:

```text
Current commit: <sha>
Completed: <bounded list>
Verified: <exact commands and results>
Not verified: <commands/evidence and reasons>
Next: <ordered next actions>
Known limitations: <explicit boundaries>
```

## Completion

Work is complete only when requested behavior is implemented, canonical and generated outputs agree, required checks pass, documentation and claim boundaries are accurate, privacy and rollback properties are preserved, and GitHub contains a durable handoff. Merge through the protected branch workflow. Closed or merged items move to `Done`; stable behavior begins with the corresponding tagged release, not merely a Project card or Draft PR.
