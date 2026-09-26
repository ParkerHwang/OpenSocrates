# Stronger-claim study readiness (not a release-candidate blocker)

The user's [2026-09-26 practical completion standard](../../docs/v1.5.0/PRACTICAL_COMPLETION.md)
replaces earlier requirements that made held-out studies, power calculations,
numerical noninferiority margins or human recruitment prerequisites for v1.5.0.
The [practical comparison](practical/RESULTS.md) is complete: six matched scenarios,
20 model invocations and 12/12 artifact/state episode passes. Version metadata can
now identify an unpublished 1.5.0 RC, subject to required final source/native gates.

No held-out study or numerical margin is claimed. The [original protocol](protocol.json),
[expanded pilot](expanded/RESULTS.md), [provisional review](expanded/reviews/astra-xhigh-v4/REPORT.md)
and its [frozen readiness assessment](expanded/reviews/astra-xhigh-v4/readiness-assessment.json)
retain their historical results and limitations. None is rewritten as a new study.

## Limits attached to their claims

| Claim | Current limit | Effect on practical RC |
| --- | --- | --- |
| General quality gain, equivalence or noninferiority | Selected tasks, one matched episode per version and no justified population/tolerance | No such claim; not a completion prerequisite |
| Incremental memory causality | Account-side isolation unproven; note and memory workflows differ | Describe observed operations/state and task results; no isolated causal claim |
| General efficiency or monetary savings | Memory-backed examples used more work; billing unavailable | Report all available usage/time/actions and regressions; no savings claim |
| Independent human quality | No human review or recruitment performed | Unblinded integrator assessment is labelled; no recruitment gate |
| Exact backend model identity | Client requests are pinned; independent echo unavailable | Record requested tuple and completed calls; no hidden substitution |
| Live Windows Codex | No connected live host | Claim native CI package coverage separately from live-host qualification |
| Destructive account-home lifecycle | Separate explicit authorization absent | Do not run it; disposable acceptance remains valid within scope |
| Publication or activation | Not authorized by RC preparation | Keep Draft; merge/tag/publish/install are separate actions |

A future stronger-claim study should define a task population, calibrate its
quality measure and judge, justify practical tolerance, and freeze its own
sampling/analysis protocol before outcomes. That optional research does not defer
completion of the implemented and practically qualified product. Model-specific
profiles remain experimental; the task-based fallback is the normal working path.
