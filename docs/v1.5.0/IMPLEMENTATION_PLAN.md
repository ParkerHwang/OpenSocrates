# Revised v1.5.0 implementation plan

The root question is how to make the revised product implementable from the
working v1.4.0 foundation. Organize work by deliverable: shared behavior,
host integration, distribution lifecycle, and practical qualification. Host
adapters may proceed independently only after their shared content contract is
fixed. One primary integrator owns shared files and final verification.

## Fixed initial decisions

1. Start from released main `5a2ff3c312e92aa8a44d0905465674d9a4e4f645`, with
   this preparation package. Preserve the original 48 procedures and all
   applicability, stop, evidence, grounding, privacy, and fail-open contracts.
2. Keep selection task-based, with no extra selector-model call, hidden model
   switch, default capture, or automatic project enrollment. Project memory and
   broad orchestration from the old candidate are excluded from this release,
   together with dedicated coding-specialist content. Do not import old v1.5
   candidate code or guides into the new implementation.
3. Make a standalone account skill ZIP the first Claude Chat/Cowork transport,
   matching the existing Customize > Skills path. Supply a small opt-in persistent
   instruction. A binless account plugin is a later distribution option; local
   native Code hooks/runtime form a separate companion. Avoid duplicate public
   controllers when account content syncs into Code.
4. Make a modular workspace rule plus skill the first Antigravity conversation
   app route. Qualify global installation afterward with preservation checks.
   Plugin-contained rules are an optional transport after current app validation;
   a manifest inconsistency is not a blocker for the modular route. Native
   Antigravity hooks are deferred unless rule delivery proves insufficient.
5. Native runtime targets are Apple-silicon macOS and Windows x64. Antigravity's
   content package also needs explicit Windows 11 x64 acceptance. Other native
   architectures, WSL, remote Code sessions and standalone Antigravity CLI are
   outside the initial support claim. Web account delivery is a separate surface.
6. Support normal requests without repeated OpenSocrates commands. Deterministic
   hook/rule delivery and model-selected Chat skills have different guarantees;
   never promise every-message Chat enforcement. Cowork cloud hook/runtime work
   requires current evidence and is optional after the account-content path.

These defaults settle implementation choices without asking the user to manage
the setup. Reopen a transport only if its actual loading, complete reference
access, duplicate origin, permissions, or lifecycle checks fail.

## Work packages and owners

| Package | Dependencies and ownership | Work and completion |
| --- | --- | --- |
| W0 Preparation | Primary; documentation and GitHub only | Scope, research, source map, starter fixtures and GitHub handoff are reviewable. Runtime remains v1.4.0. |
| W1 Reader-useful original reasoning | W0; primary owns shared controller and EN/KO guidance | Preserve the methods; improve reader-purpose/context/action connections against concrete cases from the v1.4 baseline. No old v1.5 code/guide imports. Mechanical work stays light. Generate and check affected content together. |
| W2 Claude native Code | W1 contract; sole owner of Claude host adapter and fixtures | Explicit Claude event/response normalization, short entry hooks, platform-safe launchers, deterministic decision support and bounded cleanup. CLI and Desktop local Code on macOS/Windows are separate cells. |
| W3 Claude account delivery | W1 contract; sole owner of account export and migration guide | Binless complete skill export, normal matched requests, standing instruction, old enabled 1.1.2-text skill preserved until replacement qualifies. Ordinary Chat and cloud Cowork are separate cells. Runtime hooks are not bundled into the first account export. |
| W4 Antigravity application | W1 contract; sole owner of Antigravity rules/skill templates and fixtures | Current always_on syntax, complete references, modular owned workspace route, then global route. Qualify conversation app on macOS/Windows. IDE observations cannot substitute for application acceptance. |
| W5 Distribution and lifecycle | W2-W4 surface contracts; primary owns generator, installer, native builds and shared CI | Separate content-only and native profiles; checksum/source identity; transactional install/update/disable/remove and rollback; preservation of unrelated user rules/settings. Unsupported targets remain explicit. |
| W6 Practical qualification and release preparation | W1-W5; primary owns final outcome review and support claims | Run the bounded reader cases and each claimed host lifecycle. Report improvement, tie, regression and unavailable cells separately. Version/release preparation follows functional qualification; publication is separately authorized. |

Do not give multiple writers ownership of host IDs, generator routing, version
metadata, installer registration, lockfiles, or CI at the same time. A host owner
proposes shared contract changes to the primary before implementing against them.

## Concrete source seams

| Area | Files and required reconciliation |
| --- | --- |
| Core entry/content | `src/opensocrates/selector/entry.py`, `selector/decision.py`, `cli/decision.py`, `plugin-src/codex/skills/opensocrates/SKILL.md.tmpl`, `plugin-src/shared/decision/`, `content/response-policy/` |
| Native host composition | `hosts/registry.py`, `domain/enums.py`, `cli/main.py`, `cli/runtime.py`, `hooks/entrypoint.py`, `hosts/codex/` contracts; add an explicit Claude adapter rather than assuming Codex envelopes |
| Generation and profiles | `tools/build_plugins.py`, `plugin-src/`, `tools/build_runtime.py`, `tools/release_check.py`; current Codex-only guards must become separate distribution and runtime capability lists |
| Platform launch | `packaging/launchers/launch.sh`, `packaging/launchers/launch.mjs`, Windows runtime build/check tools; native profiles must not leak into account or Antigravity content packages |
| Installer/lifecycle | `installer/opensocrates.mjs`, Windows helper, installer/lifecycle tests; preserve exact ownership markers, conflicts, rollback and unrelated registration |
| Governance and CI | `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CLAUDE.md`, `tools/check_pr_governance.py`, Makefile, package-doc mutation checks, Windows/macOS/release workflows |

Governance currently requires literal Codex-only phrases. Change the contract and
its mutation checks together when new runtime/package behavior is implemented.
Do not rename the installed support statement merely because a plan exists.
Do not remove the current checks to make a new host appear supported.

## Withdrawn candidate and retained history

The earlier v1.5 coding/memory/orchestration candidate is withdrawn in full.
PR #95 is closed, unmerged, and retained only for historical source and frozen
results. It is not an implementation baseline, future optional feature backlog,
or planned source of code or guide imports. Do not merge, cherry-pick, or copy its
implementation into this release. Develop new improvements from the v1.4 source
against the current user need.

Older pre-v1.4 multi-host records can identify past host-contract pitfalls, but
current vendor APIs and new surface-specific qualification govern restoration.
Dedicated coding specialists, coding benchmark targets, new project-memory
storage and broad maker/reviewer/verifier orchestration are outside this version.
Original results and failures are retained without regrading or deleting history.
Unrequested Gemini web/mobile/CLI and unsupported native architectures also remain
outside the requested host scope.

## First execution and reopening conditions

Start W1 by freezing original canonical/source hashes and creating the explicit
cases in [practical acceptance](PRACTICAL_ACCEPTANCE.md). Inspect concrete failed
reader outcomes before rewriting guidance. Host development can start with
synthetic contract fixtures even when a live Windows host is not connected.

The first native checks must verify launcher/event delivery and complete content
identity before interpreting a result as an OpenSocrates treatment. A missed
entry, partial read, unsupported cloud executable or modified unrelated rule
reopens only that host/transport. A worse or needlessly longer result reopens
the corresponding guidance change. Correct metadata alone never proves benefit.
