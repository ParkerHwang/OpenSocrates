# O24 usage and timing from original receipts

Evidence state: **complete_original_receipts**. Scheduled episodes: **24**; terminal episodes: **24**; response receipts: **24**.

Observed model-role calls: **54**, including every returned status. Local native-check processes: **23**. The observer's all-marker count is the sum of these two kinds; native checks have no model-token usage.

Role-call statuses: completed 37, invalid_output 17. Nonzero role process exits: 0; unknown process exits: 0. Native-check statuses: failed 2, passed 21. Blocked dependency units: 10 (these are units whose downstream role calls were not made).
Native unit states (not call counts): O-analysis qualified_candidate 2, O-analysis unavailable 10, O-document blocked_dependency 10, O-document qualified_candidate 1, O-document unavailable 1.
Observed provider-error event items: 20; failed-turn event items: 0. Backend-attempt counts were null/unavailable for 54 role calls. These event items are not additional role calls.

| Exposed category | Cohort total | Missing calls | Accounting meaning |
| --- | ---: | ---: | --- |
| input_tokens | 22,604,903 | 0 | Input; additive across observed calls |
| cached_input_tokens | 19,301,120 | 0 | Included within input; do not add again |
| cache_write_input_tokens | 0 | 0 | Reported input attribute; kept separate from additive total |
| output_tokens | 1,129,228 | 0 | Output; additive across observed calls |
| reasoning_output_tokens | 430,962 | 0 | Included within output; count only, no reasoning content |

Reported input + output, without subset double counting: **23,734,131**. Derived uncached input (input minus cached input): **3,303,783**. These are token counters, **not billed cost**.

Observed extra producer invocations: **2**; additional version numbers after v1: **2**. The two measures are kept separate because a producer call need not yield a retained version.

Role elapsed time: n=54, p50=242.827s, p95=3167.556s; summed role-process time 34595.769s. Whole-episode elapsed time: n=24, p50=1119.649s, p95=3879.523s. Cohort wall span: 4455.472s.
Observed peak overlap: 24 episodes and 24 role processes. These are measured intervals, not account/backend independence attestations.

| Role | Calls | Input | Cached input | Output | Reasoning-output subset | Role elapsed sum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| execution_verification | 13 | 2,047,727 | 1,639,552 | 58,345 | 37,889 | 1454.038s |
| production | 28 | 17,443,560 | 15,176,064 | 965,743 | 339,239 | 30753.581s |
| review | 13 | 3,113,616 | 2,485,504 | 105,140 | 53,834 | 2388.150s |

| Arm | Calls | Input | Output | Missing input/output calls |
| --- | ---: | ---: | ---: | ---: |
| A | 6 | 4,608,688 | 261,191 | 0 |
| B | 6 | 3,299,662 | 162,652 | 0 |
| C | 17 | 7,559,254 | 328,771 | 0 |
| D | 25 | 7,137,299 | 376,614 | 0 |

| Model / effort | Calls | Input | Output |
| --- | ---: | ---: | ---: |
| gpt-5.6-luna/high | 11 | 3,457,776 | 186,864 |
| gpt-5.6-luna/max | 8 | 7,558,342 | 330,485 |
| gpt-6-astra/xhigh | 8 | 2,842,367 | 152,414 |
| gpt-6-luna/high | 4 | 661,282 | 24,131 |
| gpt-6-luna/max | 12 | 4,031,092 | 300,410 |
| gpt-6-sol/high | 11 | 4,054,044 | 134,924 |

External qualification variants: 28; its reported model calls: 0. Preparation dry-run reported model calls: 0; disposable memory setup receipts: 0, with reported role model calls unavailable. Neither category was added to subject-role tokens. Other helper usage outside these receipt roots is unobserved.

Integrity cross-check: **passed** (0 issues). Original input inventory: 145 files; manifest digest `sha256:925fd9b81dd4dbb8d91f9174d7985ae812ce6566331babc09228bea121773af6`; freeze digest `sha256:730847ffea5ff543f8eac7af8e2bf356663aa568a024b063239270ce67aea21e`.

The role-assignment IDs in response calls were compared with **role-only** start and terminal markers; native-check IDs were compared separately with check receipts. All-marker reconciliation therefore does not create a missing-model-call warning. Duplicate attempt identities are reported rather than silently deduplicated.

Limits: reported usage does not prove billed cost or internal backend retry count. The reasoning-output field is a count, not access to private reasoning. Completion, latency and token use do not establish answer quality. Concurrent episode durations must not be added to infer wall time.
