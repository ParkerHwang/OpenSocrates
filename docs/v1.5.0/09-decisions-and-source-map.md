# Decisions, alternatives, and source map

Reviewed source: v1.4.0, `5a2ff3c312e92aa8a44d0905465674d9a4e4f645`.
Review date: 2026-09-23. Repository main matched this commit when checked.
The local design branch adds documents only. Source inspection is not execution
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
| D14 | Treat useful text/context selection and delivery as the founding product mechanism | Optimizing memory size or method count alone is easier to describe but does not establish better model behavior | Matched-task evidence identifies a different causal mechanism or the user changes the thesis |

Criteria come from the user's stated reuse, dependency-understanding, code-quality,
and continuity goals plus the verified repository privacy/evidence contracts.
Storage limits/retention periods are explicit engineering defaults in 03/05, not
user preference measurements. No numeric weighted score was invented.

## Existing implementation map

Links point to real baseline files; line references are review anchors.

| Source | Verified behavior / implementation implication |
| --- | --- |
| [AGENTS.md](../../AGENTS.md), lines 34–45 | Codex-only, canonical/generated ownership, no workspace retention, distinct evidence levels; requires scoped policy amendment |
| [SECURITY.md](../../SECURITY.md), lines 19–35 | Default decision has no persistent state; legacy selector is separate |
| [CONTRIBUTING.md](../../CONTRIBUTING.md), setup and validation sections | Python 3.12, locked SDK, canonical generation and source/native check requirements |
| [CLI dispatcher](../../src/opensocrates/cli/main.py), `_parser` and `main` dispatch | New memory command belongs in explicit parser/dispatch rather than host-only control payloads |
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
performance on bounded fixture repositories. Those are verifiable engineering
tasks with cases in 06, not permission to assume success or wait indefinitely.
