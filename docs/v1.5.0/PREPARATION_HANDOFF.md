# v1.5.0 preparation handoff

Prepared on 2026-10-07. Current branch: `prep/v1.5-product-refocus`.
Runtime baseline: released main
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`. Preparation changes documentation
and developer navigation only; implementation of the revised hosts has not begun.

## GitHub work order

Parent tracker: [#94](https://github.com/ParkerHwang/OpenSocrates/issues/94).
Preparation review: [#96](https://github.com/ParkerHwang/OpenSocrates/issues/96).
Historical candidate: [Closed PR #95](https://github.com/ParkerHwang/OpenSocrates/pull/95),
`f04d57fa84a82fbb0e3feb6894ec1210f135b3a8`; preserve source and frozen outcomes.

| Order | Issue | Dependency |
| --- | --- | --- |
| W1 Reader-useful original reasoning | [#97](https://github.com/ParkerHwang/OpenSocrates/issues/97) | Prepared scope and baseline |
| W2 Native Claude Code | [#98](https://github.com/ParkerHwang/OpenSocrates/issues/98) | W1 shared contract |
| W3 Claude account delivery | [#99](https://github.com/ParkerHwang/OpenSocrates/issues/99) | W1 shared contract |
| W4 Antigravity application | [#100](https://github.com/ParkerHwang/OpenSocrates/issues/100) | W1 shared contract |
| W5 Distribution, lifecycle and CI | [#101](https://github.com/ParkerHwang/OpenSocrates/issues/101) | W2-W4 surface contracts |
| W6 Reader and claimed-host qualification | [#102](https://github.com/ParkerHwang/OpenSocrates/issues/102) | W1-W5 |

Each issue contains acceptance criteria and links to the corresponding contract.
No implementation or final outcome is marked complete by creating an issue.
Use the [kickoff](IMPLEMENTATION_KICKOFF.md) to start W1, then assign independent
host work against the agreed shared contract. One integrator owns shared changes.

## Completed preparation

- Accepted original reasoning focus, dedicated coding exclusion, and exact host
  families. Antigravity means the conversation application, not Gemini web/CLI.
- Current primary-source host research, concrete source seams, default transports,
  compatibility distinctions, preservation and migration contracts.
- Read-only local inspection of Claude 2.26454.0 and Antigravity 2.19.1. The enabled
  Claude account skill's configured text names 1.1.2, not current v1.4.0. Existing
  Antigravity global rule and displayed skill state remain unchanged.
- Ordered issues, synthetic reader-case seeds, host acceptance, source checklist
  and a self-contained implementation kickoff.
- A local locked Python 3.12 environment was initialized for this checkout.
  No global application settings, active plugin, private memory or projects changed.

## Verification performed

On the unchanged v1.4.0 runtime/source baseline in this preparation checkout:

```text
make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check
```

Result: PASS, exit 0. This includes strict typing/lint, byte-identical canonical
generation, original 48 content, committed adjudication and mutations, package
launcher/docs, security, decision/runtime smoke, and **248/248** Node
installer/lifecycle/release-gate tests plus npx packaging. It is baseline source
readiness, not v1.5 host or usefulness validation. Locked runtime dependencies
remain unchanged. Final documentation links and PR governance are checked after
the preparation documents are complete and reported in its PR.

Not run: native release rebuild (no runtime/package-input change), new Claude or
Antigravity model-outcome calls, cloud Cowork hook execution, live Windows tests,
account-skill replacement, historical comparison reruns, destructive purge,
merge/tag/publication or deployment.

## Remaining evidence and next action

Start W1 now from the prepared scope and actual source. Inspect the concrete
reader cases before adding instructions. If the user's October 6 artifacts become
available, use them as the first authorized reference rather than inventing their
contents; implementation preparation does not depend on obtaining them.

The local Claude CLI is absent from PATH; Desktop's bundled runtime was not
inspected. Antigravity's standalone CLI is 1.0.6, so it is not assumed to validate
the currently installed desktop's schema. Current app rule loading, native Claude
payloads, account skill matching and each Windows/cloud cell need implementation
qualification. These have assigned issues and do not block the core work.

The selected transports reopen if ordinary entry, complete reference access,
permission scope, duplicate-controller handling or lifecycle fails. Reader
regression reopens the corresponding guide change. Preserve unavailable states
and narrow support claims to actual cells. Source/package tests do not prove
method application, universal benefit or savings.

The repository description and released support remain Codex-only until the new
support is implemented and qualified. PR #95 is closed historical reference. Its earlier
scores, failed versions and claim limits are preserved; no blanket candidate
merge, code/guide import or retroactive regrading is part of the revised implementation.
