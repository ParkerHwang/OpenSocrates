# Reuse suitability

Guide revision: 2

Use this guide when adding behavior, a shared function or component, a dependency,
or an abstraction, or when existing implementations appear to overlap. Skip it
for a mechanical edit whose behavior and contracts do not change. This guide
supports the ordinary coding task; it is not a canonical reasoning method.

1. State the required behavior, inputs and outputs, failure handling, ownership,
   and the reason it may change later.
2. Recall relevant project decisions as leads, then check them against the
   current checkout. Search the relevant source, standard facilities, and
   installed dependencies. Record the searched scope; a search miss does not
   establish that no implementation exists anywhere.
3. Read promising implementations, actual callers, tests, and public contracts.
   Check semantics, version and configuration compatibility, error behavior,
   and ownership, including returned mutable values. Preserve each operation's
   preconditions and defaults when sharing a transition. A matching name or shape
   alone is insufficient evidence.
4. Choose direct reuse, a narrow extension or adaptation, or a separate
   implementation. Explain why material candidates were accepted or rejected.
   Separate code when its behavior or reasons to change differ; avoid an
   abstraction or new library whose cost exceeds the shared benefit. For repeated
   state transitions, inspect the transaction and copying boundary with a representative
   batch; preserve correctness before optimizing copies.
5. Implement the choice and verify the new behavior plus affected existing uses.

Stop exploring when the current evidence supports a choice and further search is
unlikely to change it. If tools or source access limit inspection, state the
covered scope and unresolved candidates instead of inventing structural proof.
Complete with the chosen location and option, source evidence for the decision,
relevant verification and results, and any remaining uncertainty. A passing test
does not by itself establish long-term reuse suitability.
