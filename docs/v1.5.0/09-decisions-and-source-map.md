# Decisions, alternatives, and source map

Reviewed source: v1.4.0, `5a2ff3c312e92aa8a44d0905465674d9a4e4f645`.
Review date: 2026-09-23. Repository main matched this commit when checked.
The original design branch added documents only; the separate implementation
branch now contains candidate source changes. Source inspection is not execution
evidence. Historical v1.3 and earlier evaluation artifacts remain historical.

## Decision register

All choices below are design decisions for implementation, not measured benefits.

| ID | Choice and decisive criteria | Alternative / cost accepted | Reopen when |
| --- | --- | --- | --- |
| D01 | Built-in optional local memory with explicit project enrollment; privacy and source-aware continuity are required | Host memories alone need less code but do not provide this freshness/identity contract | Host offers a verified equivalent portable contract |
| D02 | Keep `decision` stateless; add a separate memory protocol | Combining them would simplify one entrypoint but change a trusted existing boundary | A reviewed protocol migration has a demonstrated need |
| D03 | SQLite stores local record versions/checkpoints; readable exports are snapshots | Live Markdown plus DB synchronization creates competing authorities; choosing DB requires export/inspection tooling | Real team workflows require reviewed repository-native decision authoring |
| D04 | Private product-data-root projects subtree with explicit worktree bindings | Workspace DBs are easy to find but risk accidental Git inclusion and implicit trust | Portability needs justify a separately reviewed project-file format |
| D05 | Source/coverage fingerprints and conservative invalidation | TTL-only reuse is cheaper but cannot detect new callers or dirty changes | Measured cost demands incremental optimization without weaker correctness |
| D06 | Deterministic search and bounded structural adapters first | Remote vector retrieval adds infrastructure and may retrieve similar but unsuitable code | Held-out retrieval failures demonstrate useful semantic-search benefit |
| D07 | Separate coding guides, preserving 48 methods | Adding methods changes frozen catalog, teacher-question, and package contracts | A new independent canonical reasoning method is justified and evaluated |
| D08 | Explicit capture milestones and recall; hooks remain discovery-only | Automatic hook scanning could feel seamless but is incomplete and expands side effects | Host provides a reliable reviewed lifecycle capability |
| D09 | Rollback-journal SQLite initially; safe owned files and bounded locks | WAL can improve concurrency but adds sidecar/deletion complexity | Concurrency measurements justify it and lifecycle tests pass |
| D10 | Model-specific probes with common outcome contracts | Hardcoding a flagship may simplify testing but changes cost/capability roles | Actual model-specific failures justify scoped adaptations |
| D11 | Accepted project intent may cross enrolled worktrees; observations/checkpoints are scoped | Sharing all state would improve apparent recall but leaks incompatible code/task state | An explicit merge/import workflow can validate a broader transfer |
| D12 | Quality measured on a second change in a fresh session | Single-turn tests are cheaper but do not establish project continuity | User scope changes to purely local single-turn assistance |
| D13 | Preserve the general reasoning product; memory and coding support are additive capabilities | A coding-only narrative is simpler but loses the user's intended product identity | The user explicitly changes the product purpose |
| D14 | Treat useful text/context selection and delivery as the founding product mechanism | Optimizing memory size or method count alone does not establish better behavior | Matched-task evidence identifies a different causal mechanism |
| D15 | Separate stateless assistance policy with task-based fallback and evaluated model profiles | A single fixed prompt is simpler but cannot address differing observed failure/overhead patterns | Policy overhead outweighs benefit or a simpler rule meets all outcomes |
| D16 | Shared workspace identity for Git and bounded non-Git text projects | Git-only identity simplifies storage but excludes required general continuity | A new source type has explicit capability, identity, and privacy contracts |
| D17 | Natural collaboration is observable intent/action/correction/continuity behavior | Style-only scoring is cheaper but can reward pleasant incomplete work | Blinded outcome evidence shows the rubric misses a material user need |
| D18 | Separate inexpensive-model gain, capable-model efficiency, memory, collaboration, and coding studies | A single aggregate leaderboard is simpler but obscures regressions and attribution | A preregistered analysis demonstrates a valid combined claim |

## Implementation decisions and deviations

These entries document choices made after the design-only review. They do not
upgrade the evidence for any target outcome.

| ID | Choice and reason | Verification boundary / reopen condition |
| --- | --- | --- |
| I01 (revised 2026-09-26) | Prepare synchronized 1.5.0 metadata and RC artifacts after functional qualification under the user's practical completion standard. PR stays Draft until separately authorized publication work. | Update Python/npm/version/lock/docs together and run exact-version package checks. Historical 1.4.0-labelled candidates keep their original identities. |
| I02 | Author v1.5 closed JSON Schemas in `schemas/source/v15_contracts.py` with a separate checked manifest. The existing 48-method schema generator remains intact and emits the added schemas into the generated package. | Runtime operation checks still enforce per-operation required/allowed fields. Revisit if a compatible discriminated schema generator can express those rules without weakening the existing schema family. |
| I03 | Keep Luna/Sol/Astra profiles at `candidate` and normal CLI use on task fallback. The three scoped candidates carry no observed failure categories yet; a declared evaluation harness may inject them explicitly. | A separately declared practical criterion and exact-tuple evidence is needed to enable a model-specific profile. No profile promotion is needed for this release; the working task fallback is the default. |
| I04 | Add explicit development-only fixture data-root selection behind `OPENSOCRATES_MEMORY_FIXTURE=1`, `OPENSOCRATES_DEVELOPMENT_MANIFEST=1`, and `OPENSOCRATES_DATA_DIR`; ordinary requests use the owned product root. | The frozen native test checks only disposable roots. Any broader data-root override requires separate review. |
| I05 | Use existing owner-only paths and locks around rollback-journal SQLite. The journal file is created owner-only before a content transaction and SQLite uses `TRUNCATE` rollback mode so the checked ACL remains stable on Windows. POSIX source reads use descriptor-relative no-follow opens; the Windows reader pins local-drive roots and components with non-reparse handles. UNC/device roots are rejected. Unexpected WAL/SHM sidecars fail closed rather than being silently converted. | Hosted Windows x64 run `35878192625` at `efeb436` passed local-drive/reparse, linked-worktree, owner ACL/journal, frozen SQLite migration/deletion, and package fixtures. The later WAL rejection has focused macOS fixture coverage; exact-head native rerun remains required. No WAL or network filesystem guarantee is made. |
| I06 | The installer preserves project memory by default and delegates an explicit exact-project deletion to the verified installed memory command before host purge. | Native Windows lifecycle fixture passed at `efeb436`; clean-machine live installation and destructive account-home purge are separate unverified conditions. |
| I07 | Git metadata reads resolve a regular installed Git executable outside the enrolled root, strip inherited `GIT_*` configuration, disable fsmonitor and optional locks, and use fixed argument vectors. A project-controlled `git` executable is rejected before execution. | Git metadata may still reside in the registered common directory outside a linked worktree. Native linked-worktree fixture passed at `efeb436`; broader hostile host configurations remain a bounded coverage limit. |
| I08 | Internal SQLite schema 2 adds a migration audit. Existing enrolled schema-1 stores upgrade on the next explicit memory command. A fixed owner-only backup and manifest are checked before the transactional schema change and retained seven days after verification. Delete/prune remove the backup first so a retained copy cannot revive deleted content. | Disposable process-exit, expiry, and deletion fixtures and native frozen Apple Silicon/Windows checks passed at `efeb436`. The later WAL-sidecar guard needs exact-head native rerun. Automatic restore is intentionally excluded because later writes could be lost. |
| I09 | A linked worktree must have reciprocal Git pointer metadata: its `.git` file points to its Git directory and that directory's `gitdir` points back to the same file identity. This rejects a copied worktree that otherwise appeared to share the original common directory. | Disposable POSIX and hosted Windows linked-worktree, reparse, and replacement fixtures passed at `efeb436`. Clean-machine behavior remains unverified. |
| I10 | A live EVAL-01 pilot exposed repeated invalid `recall` envelopes: one omitted required `need`, while others added unsupported `query`. Revise the optional assistance guide in EN/KO to state the exact closed recall fields and response check, without changing the stateless decision envelope or memory schema. | The initial pilot and its failed memory attempts remain immutable. The bilingual disposable recall fixture checks equivalent EN/KO need behavior; a separately frozen paired replay on the revised packaged guide is required to measure whether agent retrieval improves. |
| I11 | A new frozen EVAL-04 continuation completed its artifact but reported failed removal of a withdrawn fact from a mixed decision record. Assistance guide revision 3 links conditional EN/KO mutation guidance: supersession preserves history; explicit forgetting needs exact-record deletion after preserving the remaining accepted intent. Closed mutation payloads and actual versions are documented. No runtime/schema/model-profile change is needed. | The source fixture executes the documented payloads in both locales and proves supersession alone retains the old fact while deletion removes it and preserves intent. The original expanded pilot stays on guide revision 2; any live mutation repair is a separately frozen condition. Exact rejected requests from the original turn were not retained, so the guide gap is verified but the original failure cause remains provisional. |
| I12 | A later retained diagnostic trace identified prose in `acceptance_basis`, which the runtime already rejects in favor of bounded references. The published memory request schema used a broader short-string field. Align `authorization_basis` and `acceptance_basis` schema constraints with the existing runtime rule and add exact EN/KO acceptance examples in assistance guide revision 4 / mutation guide revision 2. Preserve the accepted-value set and privacy restriction. | Source and frozen-runtime negative/positive fixtures check prose rejection before mutation, then `user:current-request` with agent-reported attribution. Old guide-2/3 results and two parser-lost usage receipts remain unchanged. A separate guide-4 live diagnostic checks the actual persisted state; no performance claim follows from this repair. |

Criteria are task quality, efficient completion, continuity, natural collaboration,
appropriate reuse, dependency understanding, and the verified privacy/evidence
contracts. Product choices below are self-contained implementation decisions.
Storage limits/retention periods are explicit engineering defaults in 03/05, not
user preference measurements. No numeric weighted score was invented.

## Existing implementation map

Links point to real baseline files; line references are review anchors.

| Source | Verified behavior / implementation implication |
| --- | --- |
| [AGENTS.md](../../AGENTS.md), lines 34–45 | Codex-only, canonical/generated ownership, no workspace retention, distinct evidence levels; requires scoped policy amendment |
| [SECURITY.md](../../SECURITY.md), lines 19–35 | Default decision has no persistent state; legacy selector is separate |
| [CONTRIBUTING.md](../../CONTRIBUTING.md), setup and validation sections | Python 3.12, locked SDK, canonical generation and source/native check requirements |
| [CLI dispatcher](../../src/opensocrates/cli/main.py), `_parser` and `main` dispatch | New assistance/memory commands belong in explicit parser/dispatch rather than host-only control payloads |
| [Decision CLI](../../src/opensocrates/cli/decision.py), lines 1–39 | Installed canonical loading, volatile session, bounded input, no CWD-controlled fallback |
| [DecisionSession](../../src/opensocrates/selector/decision.py), lines 18–24, 147–214 | Closed select envelope, deterministic routing, zero model calls, applied unverified |
| [TaskStore](../../src/opensocrates/persistence/task_store.py), lines 39–85 | Typed public-event repository, reducer preflight and concurrency handling; not general project memory |
| [Record events](../../src/opensocrates/domain/record_event.py), module contract | Closed event union; do not append arbitrary memory dictionaries |
| [Atomic storage](../../src/opensocrates/persistence/atomic.py), bounded write helpers | Reuse reviewed patterns for canonical/bounded writes |
| [Locks](../../src/opensocrates/persistence/locks.py), FileLock | Cross-process ownership/lock pattern; validate fit with SQLite transactions |
| [Paths](../../src/opensocrates/persistence/paths.py), DataRootLayout and initialization | Known directory layout requires deliberate projects subtree support |
| [Permissions](../../src/opensocrates/persistence/permissions.py) | Platform-aware owned filesystem helpers; include all SQLite sidecars |
| [Windows security](../../src/opensocrates/windows_security.py) | Existing reparse/identity/ownership boundary must not be weakened |
| [Content schema](../../src/opensocrates/content/schema.py), lines 801–817 | Canonical catalog requires exactly 48 methods |
| [Domain models](../../src/opensocrates/domain/models.py), teacher-question validation | Additional fixed 48-method/closed-model constraints |
| [Plugin generator settings](../../plugin-src/codex/generator.json) | Shared reference-copy and public discovery configuration |
| [Plugin builder](../../tools/build_plugins.py), semantic projection and manifest generation | Standalone guide identity must be deliberately represented and verified |
| [Controller template](../../plugin-src/codex/skills/opensocrates/SKILL.md.tmpl) | Selective guidance entry; preserve grounding and completion contracts |
| [Decision guide](../../plugin-src/shared/decision/guide.en.md) | Goals/constraints, eligibility, availability reset, no reasoning retention |
| [Selector worker](../../src/opensocrates/selector/sdk_worker.py), lines 29–30, 609–624 | SDK/CLI 0.144.4 pins, medium effort, isolated retained path |
| [Makefile](../../Makefile) | Bootstrap dependency assertions, schema/content/plugin generation, verification targets |
| [Frozen runtime spec](../../packaging/pyinstaller/opensocrates-runtime.spec) | Explicit data/native closure; SQLite availability needs frozen-runtime tests |
| [POSIX launcher](../../packaging/launchers/launch.sh) | Extend only the documented explicit command allowlist |
| [Decision checks](../../tools/check_decision_points.py), hook/compaction cases | Bounded discovery and selector avoidance; add no-repository-scan assertion |
| [Installer lifecycle tests](../../installer/lifecycle.test.mjs), purge cases | Unknown files, ownership ambiguity, and incomplete cleanup must remain protected |
| [Local link checker](../../tools/check_links.py) | Documentation validation without network access |

Before implementation, verify anchors against the actual branch. Reconcile a newer
main rather than assuming these lines remain unchanged. Do not reuse another
branch's green CI as validation of the new memory feature.

## Official external references

These pages were read during design research. They support specific host/tool
capabilities; they do not validate the proposed OpenSocrates architecture.

- [OpenAI: GPT-6 model guidance and prompting](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md): model-specific behavior and compatibility; verify again before a dependency/API migration.
- [OpenAI: Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra): selective loading, clear discovery boundaries, and proportionate verification.
- [Codex model capabilities](https://learn.chatgpt.com/docs/models): exact model IDs, effort availability, and experimental context management; account/client availability can differ.
- [Codex Memories](https://learn.chatgpt.com/docs/customization/memories): host-owned memories, background update timing, and required guidance in repository documentation.
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) and [GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol): current API model positioning and controls, checked 2026-09-23. API information does not establish Desktop account access or task-quality equivalence.
- [SQLite FTS5](https://www.sqlite.org/fts5.html): local full-text search capabilities; frozen-runtime support must be checked.
- [OpenSocrates v1.4.0 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.4.0): Codex-only release scope and recorded limitations.

Research context, not a product claim: [What to Retrieve for Effective
Retrieval-Augmented Code Generation?](https://arxiv.org/abs/2503.20589) distinguishes
the utility of repository context/APIs from similar snippets on its evaluated
benchmarks. [Human-Written vs. AI-Generated Code](https://arxiv.org/abs/2508.21634)
reports different defect/complexity profiles in its evaluated models/languages.
Neither establishes GPT-6 or OpenSocrates v1.5 performance.

## Remaining implementation checks

No unanswered product question blocks W0/W1. Defaults and scope have been chosen
above. Implementation still needs to determine the exact safe SQLite/native
closure, supported host adapter receipts, actual available model tuples, and
performance on bounded general and coding tasks. Those are verifiable engineering
tasks with cases in 06, not permission to assume success or wait indefinitely.

## 2026-09-26 completion revision

The user explicitly replaces statistical-release prerequisites with
[practical qualification](PRACTICAL_COMPLETION.md), while retaining functional,
privacy, lifecycle, packaging and honest-support gates. Human recruitment, billing
proof, backend echo, account-side isolation and broad superiority are not universal
release blockers. Frozen studies and their claim limitations are unchanged.
