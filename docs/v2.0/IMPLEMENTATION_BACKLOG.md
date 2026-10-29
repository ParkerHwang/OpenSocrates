# OpenSocrates 2.0 implementation backlog

This backlog is a proposed sequence of implementable work, not a record that any feature is complete. Read [the master plan](MASTER_PLAN.md), [product cases](PRODUCT_AND_EVALUATION.md), [host research](HOSTS_AND_BOTS.md), and [architecture](ARCHITECTURE_AND_MIGRATION.md). Each item should become a focused issue or PR when its prerequisite contracts and current-main source are reconciled; do not start implementation from historical branches blindly.

| ID | Work | Deliverable and acceptance | Dependencies |
| --- | --- | --- | --- |
| B01 | Freeze actual release baseline | Inventory v1.5.3 host packages and ten language content; inspect initial guidance and actual delivered tokens per accessible host; retain unknowns and exact versions. | None |
| B02 | Prepare evaluation | Freeze synthetic inputs, actual prompts, model and host settings, blinded reader rubric, all attempted runs, timing and error capture. Include long-session and language cases. No user or private transcript retention. | B01 |
| B03 | Define task contract | Version objective, audience, artifacts, user permissions, facts and constraints, material uncertainty and completion conditions. Tests distinguish accepted/proposed and important/nonimportant missing inputs. | B01, B02 |
| B04 | Logical lifecycle | Define start, changed judgment, artifact preparation and continuation semantics independently of host hook names. Empty method selection and unavailable host events continue ordinary work. | B03 |
| B05 | Reader artifact | Implement artifact versus user work-note boundary. Test multiple recipients, missing facts, recipient-relevant uncertainty, requests and no fabricated commitments. | B02, B03 |
| B06 | Language policy | Separate conversation, source, output and instruction language; explicit user scope wins. Test ambiguous, mixed, unsupported and changing language; preserve quotations and identifiers. | B03 |
| B07 | Localized delivery | Keep 48 methods in ten locales; load relevant complete methods and instruction locale on demand where host allows. Verify source/package inventory, correctness and actual context, not only templates. | B01, B06 |
| B08 | Host capability contract | Map logical lifecycle to actual host event inputs, allowed outputs and timing. No inferred pre-answer hook; measure registration, emission and application separately. | B04 |
| B09 | Codex adapter | Preserve current profiles and trust behavior, handle prompt, compaction and completion with real supported receipts. Reproduce or characterize issue 124 without presuming cause. | B04, B07, B08 |
| B10 | Claude adapter | Qualify Code and account Chat/Cowork independently. Respect host-selected skills and account upload boundary; verify locale and ordinary requests. | B04, B07, B08 |
| B11 | Antigravity adapter | Preserve scoped rules/skills; consider documented hooks only after local tests. Avoid per-invocation duplication and respect host permissions. | B04, B07, B08 |
| B12 | Cursor adapter — mandatory | Build supported Cursor package, rules, localized skill and event adapter. Test local and cloud separately, prompt and no-tool flows, disable/remove and ordinary user installation. | B04, B07, B08 |
| B13 | Memory policy | Design user-facing enrollment, scope, location, retention, data minimization, inspect/correct/delete, host separation and export semantics. Do not retain raw conversation or hidden reasoning under current policy. | B03 |
| B14 | Working memory | Implement bounded checkpoints with versioning, freshness, accepted/proposed state and safe recovery. Verify compaction/resume, concurrency, missing data and stale authority. | B04, B13 |
| B15 | History | Implement project-level consequential decision/change records with provenance and lifecycle, distinct from temporary checkpoints. Verify correction, deletion, scope and no new authority. | B13 |
| B16 | Independent review | Implement opt-in or task-qualified parallel source review where useful; final-artifact checks follow artifact availability. Bound waits, verify findings and continue on unavailable reviewer. | B02, B03, B04 |
| B17 | Bot profile | Research and prototype distinct fast-interaction and substantive-task profiles for Dot, Grok Bot and Claude Duet; independently observe install, activation, update, storage and quality. No unsupported auto-install claims. | B02, B04, B07, B08 |
| B18 | Native lifecycle | Review preserved Go draft, independently port eligible work onto current main, preserve existing ownership, disabled state, fail-open behavior and release evidence. Do not reuse the withdrawn v1.5 candidate. | B01, B08 |
| B19 | Natural-language onboarding | Agent discovers official versioned installation, identifies host and existing state, installs what is permitted and guides only necessary human trust/upload actions. Qualify normal user and offline/retry paths. | B08, B18 |
| B20 | Update and 1.x migration | Decide automatic and major-version policy; implement signed staged activation, safe failure recovery and authentic v1.5.3 adoption per host/platform. Account-only manual steps are explicitly documented. | B18, B19 |
| B21 | Product qualification | Compare no product, v1.5.3, v2 base, sequential review and parallel review with reader-blind evaluation; report per-task latency, slow cases, failures and token categories. Set thresholds before outcomes. | B02, B05–B17 |
| B22 | Release qualification | All selected claimed host/OS cells, existing-user migration, security, privacy, full source checks and aligned EN/KO public docs. Explicitly preserve untested cells and blocking failures. | B09–B21 |

## Required dependency and security boundaries

- Work and tests never treat generated schemas/content as canonical; generate outputs from their sources and follow repository validation.
- Keep closed 1.6 PR heads and evidence discoverable. Inspect them for design lessons and permissible ports without treating old checks as proof of changed code.
- The prior 1.5 memory candidate is expressly withdrawn under repository governance; do not merge, cherry-pick or copy its code or guides.
- Closing the standalone 1.6 work does not resolve independent application-coverage or office-evaluation issues.
- Do not change the live installation, publish, deploy, weaken trust or approve external effects as part of preparation or unqualified test runs.
