# Contributing to OpenSocrates

Thank you for helping improve OpenSocrates. Bug reports, documentation fixes,
new tests, implementation improvements, and carefully sourced reasoning-system
changes are welcome.

Humans and automated agents must also follow [AGENTS.md](AGENTS.md), the shared
cross-machine operating contract. GitHub issues, pull requests, commit SHAs, and
Actions are durable shared state; local chat history and unpushed branches are
not a substitute for a GitHub handoff.

## Before opening an issue

- Search existing issues and pull requests.
- Use the security process in [SECURITY.md](SECURITY.md) for vulnerabilities.
- Remove prompts, transcripts, OAuth data, local paths, and other sensitive
  material from examples and logs.
- Describe the observed behavior separately from the behavior you expected.

## Development setup

OpenSocrates uses Python 3.12 and a locked `uv` environment.

```bash
git clone https://github.com/ParkerHwang/OpenSocrates.git
cd OpenSocrates
uv python install 3.12
uv sync --locked --all-groups
make bootstrap
```

Node.js 20 or later is also required when changing the GitHub/npx installer.

## Make changes

- Runtime code belongs under `src/opensocrates/`.
- Canonical reasoning content belongs under `content/methods/` and must keep
  theory, public-output, evidence, stop-condition, and example boundaries
  explicit. Teacher questions for the injection voice belong in
  `content/teacher-questions.yaml` and must stay bilingual, three per method,
  unique within each locale, and addressed to the active agent rather than the
  user. Its overlay `content_revision` must match the canonical content
  revision; changing the overlay does not by itself rewrite an authored
  method's `content_revision`. Generated procedures plus `source_tree_hash` and
  `normalized_semantic_hash` bind the overlay into package identity.
- Canonical schemas belong under `schemas/source/`.
- Host package templates belong under `plugin-src/antigravity/`,
  `plugin-src/claude/`, `plugin-src/codex/`, `plugin-src/cursor/`,
  `plugin-src/grok/`, and `plugin-src/opencode/`. A controller, teacher-question,
  procedure, grounding, or package-wording change must be reviewed across all
  six trees. Preserve each host's delivery model: only Claude/Codex claim hidden
  trusted hook context; Antigravity/Cursor/Grok are skill/content paths; OpenCode
  injects one compiled procedure and uses the same procedure for native fallback.
- Do not edit generated files in `schemas/v1/`,
  `content/compiled-*.json`, `build/`, or `dist/` by hand.
- Keep English and Korean user-facing documentation semantically aligned.
- Do not add telemetry, credential collection, raw prompt logging, or hidden
  reasoning capture.

Regenerate canonical outputs when their sources change:

```bash
make generate
```

## Validate

Run the checks relevant to your change. Before requesting review, the complete
source-level suite should pass:

```bash
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

Native release work additionally requires Apple-silicon macOS:

```bash
make release-check
```

For Codex, this native check measures the generated package's configured
`SessionStart` command before the runtime version smoke. The exact process model,
one-second p95 margin inside the two-second host timeout, and privacy-safe evidence
contract are documented in [docs/codex-session-start-timing.md](docs/codex-session-start-timing.md).

Release candidates that change installation or host packaging should also use
the [clean-machine acceptance procedure](docs/clean-machine-acceptance.md) on a
separate Mac and attach its privacy-safe result bundle to the pull request.
For a previously used Mac that begins with the exact supported Claude and Codex
installation, use the separate
[purge and reinstall acceptance procedure](docs/reinstall-cycle-acceptance.md).
Its result is `purged_same_machine`, never clean-machine evidence.

If a platform-dependent check cannot be run, state that clearly in the pull
request instead of claiming it passed.

## Pull requests

Keep each pull request focused and include:

- what changed and why;
- user or developer impact;
- a linked issue or a specific explanation for why no issue exists;
- validation commands and results;
- the supported evidence level and missing evidence;
- privacy, security, compatibility, or generated-output effects;
- remaining limitations or follow-up work;
- a current-commit handoff that another contributor can resume on another
  machine.

Open incomplete work as Draft. Do not mark it ready for review until the stated
checks pass or every unavailable check is documented. Repository automation adds
open issues and pull requests to the OpenSocrates Development project; Project
edit access is not required to contribute.

By submitting a contribution, you agree that it is licensed under the
repository's [MIT License](LICENSE).
