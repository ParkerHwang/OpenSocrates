# Structural revision and official-document reference guidance

Authorized on 2026-09-27 after the combined pilot, practical, GearDesk and
QueueForge review. Baseline: `b70d9f1a60b7256febe0e62498a46f8cd0cd2507`.
This specification defines a bounded revision of the unpublished 1.5.0 candidate.
It does not relabel historical artifacts, promote model profiles or authorize
publication, global settings changes, active installation replacement or enrollment
of a real project.

## Outcome and architecture

Help the selected model preserve meaningful distinctions, obtain relevant official
documentation, and close the user's actual obligations. Keep general reasoning,
coding, planning and English/Korean collaboration. Existing decision selection,
48 canonical methods, optional memory and task fallback remain.

1. A stateless `documentation codex` command emits a trusted packaged EN/KO
   reference prompt plus separately typed reference metadata. It performs no
   network/model call, document execution, memory initialization or persistence.
   The active agent uses existing authorized host tools to discover/read sources.
2. The prompt triggers for an external API/behavior question, a version change,
   conflicting documentation or an explicit official-source request. Mechanical
   work and no documentation need emit no extra prompt. Reuse a current reference
   until relevant input changes; missing access only limits dependent conclusions.
3. A packaged publisher catalog identifies known official documentation origins.
   URL matching establishes catalog membership only. Reading, source version,
   applicability, freshness and actual application remain separately attributed.
   Unlisted publishers use the same guide with explicit unresolved authority;
   they are not silently treated as unofficial or as verified official sources.
4. Do not accept page bodies or arbitrary prompt instructions in this command.
   Documentation is evidence, never an override of user intent, permissions,
   system policy or the selected model. Keep fixed instructions separate from
   caller metadata. Read actual documents, cite precise pages/sections, and test
   the affected behavior; a search snippet, URL, emitted prompt or claimed read is
   insufficient proof of use or correctness.

This follows the separation of skills and supporting resources in the
[official plugin skill documentation](https://developers.openai.com/plugins/build/skills)
and the untrusted-data boundary described in
[OpenAI's agent safety guidance](https://developers.openai.com/api/docs/guides/agent-builder-safety).
These references inform the design; they do not change task permissions or model
selection, and do not prove resistance to every prompt-injection attack.

## Versioned interfaces

Preserve all existing v1.0 schema bytes. Add separate v1.1 assistance and memory
request schemas and a v1.1 context projection. Existing requests retain their
response shape. No SQLite layout or migration change is needed.

- Memory `prepare` is read-only and operates only on explicit enrolled project,
  workspace and task identities. Before any migration/backup-maintenance path,
  read the current schema and checkpoint version. Return a checkpoint draft with
  mechanical identifiers and neutral defaults plus semantic fields to complete.
  Do not infer acceptance, task authority or completion. Actual submission retains
  current CAS, idempotency, privacy and authorization checks.
- Recall applies the requested path scope to delivered source references and the
  primary snapshot. Retain every applicable accepted intent. Revalidate each old
  source snapshot against its own original scope, including broader negative
  claims; expose that broader verification scope separately in v1.1. Required
  constraints/unknowns are never silently dropped to fit a budget. `need` ranks
  projections; it is not represented as a byte-reduction mechanism.
- v1.1 recall tags decision/checkpoint provenance and carries a bounded checkpoint
  summary/version. Source freshness is not acceptance or execution verification.
  The projection is ephemeral; no new cache can survive a scoped deletion.
- Contract diagnostics expose only known field paths and fixed reason codes,
  never rejected values or unknown field names.
- v1.1 assistance connects bounded public obligations and dependencies to existing
  completion semantics. Required missing/unverified/conflicting obligations prevent
  conditional finish. Independent work and question-specific blockers are returned
  separately. Reported completion/evidence remains an assertion, not native proof.

## Verification and stop rule

The integrator owns shared schemas, runtime, generated assets, packaging and final
evidence. Verify closed JSON/URL inputs, EN/KO parity, no stateless writes, old
schema compatibility, no preparation mutation/migration, CAS/replay, scope/negative
claims, provenance, overflow and scoped deletion. Reproduce changed semantic
boundaries with independent expected outcomes and genuine old-producer fixtures.

New failure feedback must include its own input, expected/observed result, source
identity and reproduction reference. Retain historical missing evidence and
scores; never insert a stronger model's repair inside a Luna treatment. Reuse
existing zero-price, seat-domain, public-message and operation-receipt fixtures.
Any live usability calls require a new bounded manifest frozen before calls, with
exact tuple/package/guide identities and every attempt/null usage counted.

Run focused checks, then the required source and native package gates for this
revision, verify generated/embedded guide/schema bytes and exact-head CI. Live
Windows Codex remains unavailable unless a connected host actually changes; hosted
Windows checks are separate evidence. Stop after the bounded acceptance and Draft
PR handoff. No broad matrix, held-out power study or human recruitment is required.

`plan_objective_measure`: fewer protocol errors and correctly scoped source and
completion handling against the observed baseline; efficiency gains are hypotheses.
`do_scope`: reversible native/interface/guidance changes and disposable fixtures.
`check_rule`: independent negative controls, compatibility, privacy and actual
artifact/state results; preserve failures and unverified behavior.
`act_standardize_decision`: accept only verified behavior in the RC; keep broader
quality/efficiency/application claims unverified and publication separate.
