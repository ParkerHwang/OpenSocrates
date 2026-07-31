# Contributing to OpenSocrates

Thank you for helping improve OpenSocrates. Bug reports, documentation fixes,
new tests, implementation improvements, and carefully sourced reasoning-system
changes are welcome.

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
  explicit.
- Canonical schemas belong under `schemas/source/`.
- Codex package templates belong under `plugin-src/codex/`.
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
make docs-check
make security-scan
make smoke
npm test
npm pack --dry-run
```

Native release work additionally requires Apple-silicon macOS:

```bash
make release-check
```

If a platform-dependent check cannot be run, state that clearly in the pull
request instead of claiming it passed.

## Pull requests

Keep each pull request focused and include:

- what changed and why;
- user or developer impact;
- validation commands and results;
- privacy, security, compatibility, or generated-output effects;
- remaining limitations or follow-up work.

By submitting a contribution, you agree that it is licensed under the
repository's [MIT License](LICENSE).
