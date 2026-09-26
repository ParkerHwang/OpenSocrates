# Maintainability review

Guide revision: 2

Use this guide before completing a non-mechanical code change. Scale the review
to changed behavior and affected contracts; do not turn a routine edit into an
architecture exercise.

1. Read the final diff and enough surrounding code to understand ownership and
   call sites. Check coherent responsibilities, duplicated domain rules,
   unnecessary abstractions or options, brittle coupling, failure behavior,
   testability, and fit with documented project conventions.
2. For each finding, name a location, a concrete consequence or likely follow-on
   change, the supporting source evidence, and a proportionate repair. A style
   preference without a project rule or consequence is not a defect.
3. Correct material findings within scope. Use behavioral tests, linters, type
   checks, and complexity or duplication signals for their distinct purposes.
   No score, line count, model opinion, or passing test certifies maintainability.
4. Verify the corrected behavior and relevant affected uses. Keep unrelated
   working code intact; propose larger refactors separately.

Connect a failed check to its exact input, expected/observed result, source version
and affected obligation before repairing it. Exercise that boundary after the
change; a green self-authored suite does not close an independent failure. Identify
supplied/protected tests from source provenance and task instructions, not merely
because a test existed before this turn. Keep unknown evidence unknown. Store raw
fixtures in the authorized test workspace, never in product memory.

Stop when material in-scope findings are addressed and required checks have run,
or when a concrete blocker is reported. Do not rerun unchanged checks, write
mirror tests for trivial edits, or seek unavailable proof that this guide was
applied. Complete with grounded findings and repairs, exact checks and results,
remaining limitations, and the changed behavior's completion status.
