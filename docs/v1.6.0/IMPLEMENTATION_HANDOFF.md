# v1.6.0 implementation handoff

Tracking: [implementation issue #111](https://github.com/ParkerHwang/OpenSocrates/issues/111) and [Draft PR #112](https://github.com/ParkerHwang/OpenSocrates/pull/112). Preparation PR #110 and issue #109 remain separate. Base: `9572db2c71a455d4ada24c78402d0f874002cec9`. Branch: `codex/v1.6-go-native`.

## Progress

| Package | State | Ownership |
| --- | --- | --- |
| V0 | Recorded | Released v1.5.0 baseline in CONTENT_BASELINE.json; latest main has no newer canonical input changes |
| V1–V2 | Implemented; source/Mac validated | Typed contracts, domain, content, decision, runtime CLI and persistence |
| V3 | Implemented; Windows fixes in verification | OS security and external pinned Codex app-server compatibility |
| V4–V5 | Implemented; Mac adoption/rollback validated | Lifecycle journals, transport, registrations, native management, npm adoption |
| V6 | Implemented; production trust blocked | TUF trust, scheduling, shared activation and self-update |
| V7 | Implemented; review fixes in verification | Go generation, package/release tooling, validation, CI and bilingual documentation |
| V8 | In final verification | Windows native rerun, review fixes and durable release handoff |

Canonical methods, teacher questions, response policies and shared guides remain frozen. Distribution command references are specialized for native Go without changing the canonical guide inputs. The compiled bundle's release-only product version changes to 1.6.0; content revision remains 3.

## Decisions

- Source starts at current main, not the planning branch or withdrawn PR #95.
- The v1.5.0 annotated tag resolves to `cf6634310afcf5d5ce58484e67a73151bb4c5999`; the tag object's different SHA is not the content source commit.
- Go toolchain is pinned to 1.27.2, checked against the official release list on 2026-10-12. Users do not require it.
- Production update root and signing credentials must be provisioned through the documented release gate. Test keys cannot become production trust.
- Production releases, tags, merging and active-installation replacement are outside this authorization.

## Evidence

Last complete source verification: `c5a822c6d97779d507f38d8344ec82ebe591bd8e`, macOS ARM64, Go 1.27.2.

- `make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check smoke installer-check` — passed.
- `make package` — native macOS bundle assembled; Windows cross-build/assembly passed separately without a runtime claim.
- Go SBOM/security scan — passed; `make release-check` failed closed at production platform signing.
- Configured zsh hook: 20 startup + 20 compact samples passed the 2-second host limit and p95 1-second gate. Isolated per-user macOS scheduler registration, native Go entry and exact cleanup passed.
- Native Mac lifecycle: install/status/update/disabled-state/removal/recovery/rollback and synthetic npm adoption passed. The authentic v1.5.0 public ZIP and original release installer additionally passed adoption and exact rollback in an isolated HOME with a Go external-host fixture. Actual npm global installation and live host activation are not claimed.
- Differential Python v1.5/Go comparison: 1,055 decision responses, all 48 methods in both locales, nine rigor commands and 21 control cases passed, with four documented intentional differences. Ten affected control-root cases passed after correcting array/null/scalar error categorization.
- Five-second fuzz runs passed for archive paths, trust reset and safe relative transport paths.

Hosted run [38203175201](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38203175201) passed source and native macOS checks at that SHA. Actual Windows x64 execution failed and identified permission, lease, temporary-owner, archive-mode and pipe issues. Their fixes and regression tests are in final integration; cross-compilation does not replace the required native rerun. Repository governance run [38203175319](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38203175319) passed; review subsequently found and fixed missing PR-event wiring.

Read-only runtime/security reviews found no exploitable issue at their reviewed revisions. Tooling review found four concrete defects: Windows ZIP modes, immutable-release API credentials, PR-event wiring and embedded-asset checking. Fixes retain the existing gates and add regression coverage. A focused security follow-up also identified filename-dependent Windows EXE snapshot modes; recovery snapshots are now independent of staging/backup aliases.

## Remaining release gates

1. Finish native Windows x64 CI, including ACL/reparse/lease, actual process death, executable replacement, installation, exact hook timing and per-user scheduling.
2. Review and verify final changes; record the final checked SHA and retain content-free CI/compatibility evidence.
3. Provision an independently approved threshold-signed TUF root and publisher identities, production signing/notarization resources, and the narrowly scoped `Administration:read` credential for immutable-release settings. Unsigned preparation builds cannot enable production trust.
4. Obtain clean-machine and live host/account/workspace/global evidence separately. Authenticated legacy app-server selection remains unqualified.

No merge, tag, publication or active-installation replacement is authorized. Existing v1.5 release evidence remains scoped to that release. GitHub SSH upload works; the CLI workflow scope was also added through the user's separate setup chat.
