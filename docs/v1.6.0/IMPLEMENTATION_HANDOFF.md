# v1.6.0 implementation handoff

Tracking: implementation issue #111; preparation PR #110 and issue #109 remain separate. Base: `9572db2c71a455d4ada24c78402d0f874002cec9`. Worktree branch: `codex/v1.6-go-native`.

## Progress

| Package | State | Ownership |
| --- | --- | --- |
| V0 | Recorded | Released v1.5.0 baseline in CONTENT_BASELINE.json; latest main has no newer canonical input changes |
| V1–V2 | In implementation | Typed contracts, domain, content, decision, runtime CLI and persistence |
| V3 | In implementation | OS security and external pinned Codex app-server compatibility |
| V4–V5 | In implementation | Lifecycle journals, transport, registrations, native management, npm adoption |
| V6 | In implementation | TUF trust, scheduling, shared activation and self-update |
| V7 | In implementation | Go generation, package/release tooling, validation, CI and bilingual documentation |
| V8 | Pending integration | Final checks, native evidence, code/security review and release handoff |

The parent owns integration, shared module pins, release identities, profiles and final evidence. Workers own distinct packages and defer validation until integration. Canonical methods, teacher questions, response policies and shared guides remain frozen.

## Decisions

- Source starts at current main, not the planning branch or withdrawn PR #95.
- The v1.5.0 annotated tag resolves to `cf6634310afcf5d5ce58484e67a73151bb4c5999`; the tag object's different SHA is not the content source commit.
- Go toolchain is pinned to 1.27.2, checked against the official release list on 2026-10-12. Users do not require it.
- Production update root and signing credentials must be provisioned through the documented release gate. Test keys cannot become production trust.
- Production releases, tags, merging and active-installation replacement are outside this authorization.

## Evidence

Repository status and GitHub issue/PR history were read. No implementation tests or validation builds have run yet. macOS ARM64 execution is available locally; Windows x64 execution availability will be established in V8. Cross-compilation will not count as Windows runtime evidence. Existing tagged release evidence remains scoped to v1.5.0.
