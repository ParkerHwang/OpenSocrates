# continuity8 usage and timing from original receipts

Evidence state: **complete_original_receipts**. Scheduled episodes: **8**; terminal episodes: **8**; response receipts: **8**.

Observed model-role calls: **24**, including every returned status. Local native-check processes: **8**. The observer's all-marker count is the sum of these two kinds; native checks have no model-token usage.

Role-call statuses: completed 20, invalid_output 4. Nonzero role process exits: 0; unknown process exits: 0. Native-check statuses: passed 8. Blocked dependency units: 0 (these are units whose downstream role calls were not made).
Native unit states (not call counts): continuation qualified_candidate 4, continuation unavailable 4.
Observed provider-error event items: 0; failed-turn event items: 0. Backend-attempt counts were null/unavailable for 24 role calls. These event items are not additional role calls.

| Exposed category | Cohort total | Missing calls | Accounting meaning |
| --- | ---: | ---: | --- |
| input_tokens | 1,648,752 | 0 | Input; additive across observed calls |
| cached_input_tokens | 1,254,912 | 0 | Included within input; do not add again |
| cache_write_input_tokens | 0 | 0 | Reported input attribute; kept separate from additive total |
| output_tokens | 32,910 | 0 | Output; additive across observed calls |
| reasoning_output_tokens | 14,166 | 0 | Included within output; count only, no reasoning content |

Reported input + output, without subset double counting: **1,681,662**. Derived uncached input (input minus cached input): **393,840**. These are token counters, **not billed cost**.

Observed extra producer invocations: **0**; additional version numbers after v1: **0**. The two measures are kept separate because a producer call need not yield a retained version.

Role elapsed time: n=24, p50=39.898s, p95=60.226s; summed role-process time 962.134s. Whole-episode elapsed time: n=8, p50=122.835s, p95=153.346s. Cohort wall span: 159.930s.
Observed peak overlap: 8 episodes and 8 role processes. These are measured intervals, not account/backend independence attestations.

| Role | Calls | Input | Cached input | Output | Reasoning-output subset | Role elapsed sum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| execution_verification | 8 | 567,873 | 422,912 | 10,334 | 4,786 | 324.183s |
| production | 8 | 371,886 | 249,344 | 9,296 | 3,445 | 256.890s |
| review | 8 | 708,993 | 582,656 | 13,280 | 5,935 | 381.061s |

| Condition | Calls | Input | Output | Missing input/output calls |
| --- | ---: | ---: | ---: | ---: |
| disabled_memory_with_equivalent_note | 12 | 856,038 | 17,178 | 0 |
| scoped_disposable_memory | 12 | 792,714 | 15,732 | 0 |

| Model / effort | Calls | Input | Output |
| --- | ---: | ---: | ---: |
| gpt-6-luna/high | 12 | 745,335 | 16,376 |
| gpt-6-sol/high | 12 | 903,417 | 16,534 |

External qualification variants: 8; its reported model calls: 0. Preparation dry-run reported model calls: unavailable; disposable memory setup receipts: 8, with reported role model calls 0. Neither category was added to subject-role tokens. Other helper usage outside these receipt roots is unobserved.

Integrity cross-check: **passed** (0 issues). Original input inventory: 67 files; manifest digest `sha256:708d3e595ad2b5ee4ef9fb47c82082b1523f40b33afad3a6892e87d25e47a010`; freeze digest `sha256:637d63d7d5a06525f8a0b96f8f7ecd687557513c371c13a1e7b7f71b6d4cb4c9`.

The role-assignment IDs in response calls were compared with **role-only** start and terminal markers; native-check IDs were compared separately with check receipts. All-marker reconciliation therefore does not create a missing-model-call warning. Duplicate attempt identities are reported rather than silently deduplicated.

Limits: reported usage does not prove billed cost or internal backend retry count. The reasoning-output field is a count, not access to private reasoning. Completion, latency and token use do not establish answer quality. Concurrent episode durations must not be added to infer wall time.
