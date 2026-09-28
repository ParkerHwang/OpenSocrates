# S24 usage and timing from original receipts

Evidence state: **complete_original_receipts**. Scheduled episodes: **24**; terminal episodes: **24**; response receipts: **24**.

Observed model-role calls: **68**, including every returned status. Local native-check processes: **21**. The observer's all-marker count is the sum of these two kinds; native checks have no model-token usage.

Role-call statuses: completed 48, failed 1, invalid_output 19. Nonzero role process exits: 1; unknown process exits: 0. Native-check statuses: passed 21. Blocked dependency units: 9 (these are units whose downstream role calls were not made).
Native unit states (not call counts): S-design qualified_candidate 3, S-design unavailable 9, S-implementation blocked_dependency 9, S-implementation qualified_candidate 1, S-implementation unavailable 2.
Observed provider-error event items: 35; failed-turn event items: 1. Backend-attempt counts were null/unavailable for 68 role calls. These event items are not additional role calls.

| Exposed category | Cohort total | Missing calls | Accounting meaning |
| --- | ---: | ---: | --- |
| input_tokens | unavailable (known 13,601,914; 1 missing calls) | 1 | Input; additive across observed calls |
| cached_input_tokens | unavailable (known 10,678,144; 1 missing calls) | 1 | Included within input; do not add again |
| cache_write_input_tokens | unavailable (known 0; 1 missing calls) | 1 | Reported input attribute; kept separate from additive total |
| output_tokens | unavailable (known 1,036,472; 1 missing calls) | 1 | Output; additive across observed calls |
| reasoning_output_tokens | unavailable (known 417,587; 1 missing calls) | 1 | Included within output; count only, no reasoning content |

Reported input + output, without subset double counting: **unavailable**. Derived uncached input (input minus cached input): **unavailable**. These are token counters, **not billed cost**.

Observed extra producer invocations: **5**; additional version numbers after v1: **3**. The two measures are kept separate because a producer call need not yield a retained version.

Role elapsed time: n=68, p50=185.618s, p95=5234.198s; summed role-process time 45951.460s. Whole-episode elapsed time: n=24, p50=881.231s, p95=7351.299s. Cohort wall span: 12402.567s.
Observed peak overlap: 24 episodes and 24 role processes. These are measured intervals, not account/backend independence attestations.

| Role | Calls | Input | Cached input | Output | Reasoning-output subset | Role elapsed sum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| design | 15 | 2,545,981 | 1,907,200 | 327,341 | 116,454 | 14492.992s |
| execution_verification | 18 | 2,371,620 | 1,713,408 | 61,808 | 43,109 | 1638.317s |
| production | 17 | unavailable | unavailable | unavailable | unavailable | 26928.056s |
| review | 18 | 3,955,837 | 3,184,512 | 113,076 | 82,080 | 2892.096s |

| Arm | Calls | Input | Output | Missing input/output calls |
| --- | ---: | ---: | ---: | ---: |
| A | 6 | unavailable | unavailable | 1 |
| B | 6 | 2,189,723 | 247,558 | 0 |
| C | 18 | 2,565,748 | 198,862 | 0 |
| D | 38 | 7,722,818 | 435,074 | 0 |

| Model / effort | Calls | Input | Output |
| --- | ---: | ---: | ---: |
| gpt-5.6-luna/high | 8 | 852,668 | 71,036 |
| gpt-5.6-luna/max | 11 | 3,039,424 | 297,925 |
| gpt-6-astra/xhigh | 11 | unavailable | unavailable |
| gpt-6-luna/high | 12 | 1,306,386 | 81,917 |
| gpt-6-luna/max | 12 | 2,572,214 | 230,217 |
| gpt-6-sol/high | 14 | 1,581,674 | 88,004 |

External qualification variants: 39; its reported model calls: 0. Preparation dry-run reported model calls: 0; disposable memory setup receipts: 0, with reported role model calls unavailable. Neither category was added to subject-role tokens. Other helper usage outside these receipt roots is unobserved.

Integrity cross-check: **passed** (0 issues). Original input inventory: 159 files; manifest digest `sha256:7842fade6dd891f99ad6ac7f88b91f0aa22bc3e3ba855df47f8b90c6825bc21b`; freeze digest `sha256:3973a93cf491030d3aac47cfe4748c2a70b67d43ebed39b879d9253e4a92f815`.

The role-assignment IDs in response calls were compared with **role-only** start and terminal markers; native-check IDs were compared separately with check receipts. All-marker reconciliation therefore does not create a missing-model-call warning. Duplicate attempt identities are reported rather than silently deduplicated.

Limits: reported usage does not prove billed cost or internal backend retry count. The reasoning-output field is a count, not access to private reasoning. Completion, latency and token use do not establish answer quality. Concurrent episode durations must not be added to infer wall time.

S24-specific evidence: one Astra A process failed after an observed partial event stream. All five token fields for that call are null. Cohort and affected arm/model complete token totals therefore remain unavailable; the known sums in JSON cover only the other 67 calls. The partial stream's observed public items are reported separately in `s24_event_categories` and are not complete event totals. Provider-error counts do not exhaust the public error-item inventory. Native `qualified_candidate` describes a unit terminal state; external correctness and browser-transport decisions are separate.
