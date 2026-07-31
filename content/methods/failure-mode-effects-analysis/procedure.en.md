## Purpose

Use this procedure to identify how a planned process, product, or control could fail before relying on it. It connects a failure mode to its effect, plausible cause, existing detection, and preventive or detective control. The result is an ordinal priority and an owned action list, not a fake risk score. It makes uncertainty visible and focuses effort on failures whose consequences or weak controls deserve attention first.

## Use when

Use it for a launch, workflow change, service design, handoff, safety barrier, data pipeline, or product feature with a defined sequence and failure surface. It is useful before commitment, after a meaningful design change, or when a recurring incident reveals a class of unexamined failures. Use available incident data, tests, service records, and domain expertise. Keep the analysis bounded to the process or component that can be described and acted upon.

## Do not use when

Do not use it as a substitute for an emergency response, legal compliance review, hazard analysis required by a specialist, or a causal diagnosis of an already recurring incident. Do not assign severity, occurrence, or detectability numbers when the scale, calibration, and source are absent. Do not treat a long list as thoroughness, and do not rank a failure above another solely because it is easier to imagine. If the process boundary or intended function is unknown, establish it first or hold the assessment.

## Inputs to establish

Name the process, product, or component, its boundary, intended function, users, operating conditions, and current controls. Map the main steps or interfaces and identify known hazards, constraints, incidents, test results, and owners. Define the ordinal priority language before ranking—for example, urgent, material, watch, or low attention—and explain what each label means in this context. Ask at most two questions that could change the ranking, such as “Which failure could cause irreversible harm?” or “What control would detect this before release?”

## Procedure

1. **Set the analysis boundary.** Describe the intended function, operating context, interfaces, and exclusions; split a large process into a workable sequence. **Visible output/state change:** publish the boundary and step list, with unknown functions or conditions marked unverified.
2. **Name failure modes and effects.** For each step, state what could go wrong and the immediate, downstream, user, or safety effect. Keep modes distinct enough that different controls could address them. **Visible output/state change:** publish a failure-effect register linked to each step.
3. **Trace causes and current controls.** Record plausible causes, preventive controls, detection controls, and evidence that a control actually operates. Separate observed failures from hypothetical possibilities. **Visible output/state change:** add cause and control fields with verified, inferred, assumed, or unverified states.
4. **Set ordinal priority.** Apply the predeclared qualitative priority rule using consequence, plausible exposure, and control weakness. If quantitative inputs are not defensible, do not calculate a product or risk-priority number; explain the comparison in words. **Visible output/state change:** publish an ordered shortlist with the reason each item is urgent, material, watch, or low attention.
5. **Assign control actions.** Prefer prevention that removes a cause, then detection that catches a failure before harm, then containment that limits impact. Name the owner, trigger, evidence of completion, and residual uncertainty. **Visible output/state change:** publish a control plan tied to each prioritized mode.
6. **Reassess after change.** State what observation or test would show that the control reduced exposure or improved detection, and what would reopen the mode. **Visible output/state change:** publish a supported, provisional, or held priority assessment and a flip condition; do not close a mode merely because an action is planned.

## Public output contract

Return the boundary, failure modes, effects, causes, current controls, ordinal priority, owner, and verification signal. Show whether each material item is observed, inferred, assumed, unverified, or conflicted. Never present fabricated severity/occurrence/detectability scores or a precise ranking when provenance is absent. The Conclusion Card may summarize the highest-attention failure and the condition that would change its priority; the trace can contain the complete register.

## Evidence and uncertainty rules

A hypothetical failure is not an observed rate. An existing control is not effective merely because it is documented; evidence must show operation, coverage, or a bounded test. Keep consequence, likelihood, and detectability as separate judgments. Use ordinal language only with a local definition and a stated basis. If a safety or regulatory threshold is binding, defer to the authoritative requirement and mark any unverified interpretation. If two credible assessments disagree, label the priority conflicted and hold the action order where the conflict is material.

## Stop conditions

Stop when the intended function, boundary, or operating condition cannot be established, when a high-consequence mode lacks any safe containment, or when ranking would depend on invented numbers. For immediate hazards, follow the applicable incident or safety process first. Hold a release recommendation when a decisive control has not been tested or assigned an owner.

## Complement handoff

Hand off to premortem-analysis when a chosen plan needs a human failure narrative and early warning signals before commitment. Pass the bounded plan, prioritized failure modes, effects, and controls; the complement should add plausible scenarios without converting ordinal priority into false precision.
