## Purpose

Use this procedure to determine whether a conclusion follows necessarily from explicit premises and a rule, while separating validity from the truth of the premises. It standardizes the argument, exposes hidden premises, checks the form, and identifies the premise whose failure would invalidate the conclusion. A valid form does not by itself make a real-world argument sound.

## Use when

Use it for rule application, formal argument checking, contract or policy interpretation, and claims that say a result must follow from stated conditions. It fits cases where the relevant premises can be made explicit and the question is entailment rather than empirical generalization.

## Do not use when

Do not use it when premises are uncertain and the real task is to estimate, diagnose, generalize, or update confidence. Do not treat a likely premise as a proved premise, confuse `P(E|H)` with entailment, or call an invalid form valid because its conclusion happens to be true. Do not invent a rule that the user or governing source did not provide.

## Inputs to establish

Establish the proposed conclusion, premises, governing rule or implication, scope, definitions, and source of each premise. Mark hidden premises explicitly and identify whether the task requires validity, soundness, or only a conditional result. Ask at most one decisive question when a missing rule or premise changes the form; otherwise state the conditional assumption.

## Procedure

1. Publish the conclusion and standardize the argument into numbered premises, rule, and conclusion. Mark hidden premises as `[implicit]`; this creates the visible formalization state.
2. Publish the argument form, such as modus ponens, modus tollens, a valid syllogism, affirming the consequent, or denying the antecedent. If no recognized form fits, show the relevant structural relation without forcing a label.
3. Publish the validity verdict: assuming the premises true, must the conclusion be true? State the counterexample pattern when the form is invalid.
4. Publish a premise-status table with source, scope, and evidence state for each premise and rule. Separate a valid form from a sound argument; this is a visible judgment update.
5. Publish the invalidating premise or rule condition. State exactly what would break entailment and distinguish an exception to the rule from a false premise.
6. Publish the conclusion as sound, valid-but-unsound, invalid, or conditional, with the smallest missing check. Do not upgrade the state because the conclusion is plausible.
7. Publish the current conclusion and an observable flip condition. If a decisive premise or rule is absent, hold the real-world claim while preserving the conditional implication.

## Public output contract

Return `premises`, `hidden_premises`, `rule`, `rule_or_form`, `conclusion`, `validity_verdict`, `premise_status`, `invalidating_premise`, `soundness_verdict`, and `flip_condition`. The result must state whether the form is valid and whether the premises are supported; it must not collapse those into one confidence label. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels.

## Evidence and uncertainty rules

Validity is a structural relation and does not verify premises. A source can support a premise without proving that the rule applies to this scope. Hidden premises remain assumptions until supported. If a premise is disputed, preserve the conditional result and lower or hold the applied conclusion. Do not use a single true conclusion to validate an invalid inference.

## Stop conditions

Stop and ask one blocking question when the governing rule or conclusion is missing and possible forms lead to different results. Hold when a material premise cannot be checked, while reporting the valid conditional if one exists. Stop when the task is probabilistic, causal, or comparative rather than entailment.

## Complement handoff

Hand off to `conceptual-analysis` when the formal dispute depends on an ambiguous term or scope definition. Pass the standardized premises, disputed term, and affected rule. The complement should clarify the concept without redoing the validity verdict.
