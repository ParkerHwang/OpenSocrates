# Per-cell observation and qualification tables

One episode per cell. All raw first-pass outcomes remain in qualification-v1; diagnostics are separate. Token categories below are reported CLI fields.

## Coding

| Tuple | Arm | Minutes | Input / cached | Output / reasoning | Tool items / failed | Qualification |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| gpt-6-sol-high | vanilla | 32.38 | 2,788,111 / 2,632,704 | 42,225 / 11,624 | 65 / 5 | burst transport failure; staged-body invariants pass |
| gpt-6-sol-high | v14 | 30.24 | 4,388,181 / 4,235,520 | 51,854 / 14,294 | 67 / 8 | original critical API + restart + readiness flow pass |
| gpt-6-sol-high | v15 | 15.64 | 3,811,383 / 3,702,272 | 39,727 / 6,401 | 66 / 8 | burst transport failure; staged-body invariants pass |
| gpt-6-luna-max | vanilla | 36.49 | 12,425,031 / 12,189,952 | 92,446 / 38,828 | 99 / 2 | login form remains visible |
| gpt-6-luna-max | v14 | 32.32 | 8,806,946 / 8,575,872 | 95,798 / 40,411 | 69 / 7 | burst transport failure; staged-body invariants pass |
| gpt-6-luna-max | v15 | 41.84 | 10,797,338 / 10,562,816 | 104,315 / 47,327 | 88 / 16 | burst transport failure; staged-body invariants pass |
| gpt-6-luna-high | vanilla | 15.32 | 2,608,306 / 2,492,672 | 34,440 / 7,095 | 49 / 8 | burst transport failure; staged-body invariants pass |
| gpt-6-luna-high | v14 | 17.98 | 4,616,826 / 4,455,680 | 49,313 / 14,258 | 67 / 13 | original critical API + restart + readiness flow pass |
| gpt-6-luna-high | v15 | 18.34 | 4,132,178 / 3,986,432 | 49,039 / 12,877 | 70 / 9 | original critical API + restart + readiness flow pass |
| gpt-5.6-luna-max | vanilla | 28.82 | 5,552,920 / 5,389,312 | 83,135 / 32,294 | 74 / 4 | burst transport failure; staged-body invariants pass |
| gpt-5.6-luna-max | v14 | 25.54 | 9,118,957 / 8,909,056 | 75,889 / 25,378 | 68 / 2 | burst transport failure; staged-body invariants pass |
| gpt-5.6-luna-max | v15 | 28.32 | 8,387,891 / 8,163,328 | 80,417 / 29,835 | 83 / 12 | original critical API + restart + readiness flow pass |
| gpt-5.6-luna-high | vanilla | 16.86 | 3,370,233 / 3,239,936 | 47,520 / 7,846 | 54 / 5 | burst transport failure; staged-body invariants pass; login form remains visible |
| gpt-5.6-luna-high | v14 | 19.13 | 5,087,800 / 4,934,912 | 45,539 / 8,233 | 59 / 7 | burst transport failure; staged-body invariants pass; mobile overflow |
| gpt-5.6-luna-high | v15 | 16.18 | 3,314,524 / 3,183,616 | 42,758 / 8,079 | 47 / 6 | burst transport failure; staged-body invariants pass; multi-line UI fails; price-field400 is contract ambiguity |
| gpt-6-astra-xhigh | vanilla | 39.81 | 1,246,449 / 1,152,768 | 53,309 / 9,805 | 44 / 2 | original critical API + restart + readiness flow pass |
| gpt-6-astra-xhigh | v14 | 64.13 | 1,576,443 / 1,453,568 | 57,833 / 9,604 | 40 / 2 | original critical API + restart + readiness flow pass |
| gpt-6-astra-xhigh | v15 | 55.53 | 1,822,802 / 1,714,176 | 61,130 / 13,249 | 49 / 3 | original critical API + restart + readiness flow pass |

## Consulting

| Tuple | Arm | Minutes | Input / cached | Output / reasoning | Tool items / failed | Qualification |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| gpt-6-sol-high | vanilla | 15.47 | 3,208,066 / 3,094,144 | 42,509 / 9,459 | 66 / 2 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-6-sol-high | v14 | 24.13 | 2,209,937 / 2,105,856 | 32,718 / 6,089 | 44 / 3 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-6-sol-high | v15 | 29.58 | 4,065,252 / 3,957,504 | 44,552 / 8,949 | 60 / 6 | core values match; 44/44 pair cases match; frozen score 17/17 |
| gpt-6-luna-max | vanilla | 43.56 | 14,138,054 / 13,869,952 | 111,268 / 54,228 | 101 / 9 | core values match; 44/44 pair cases match; frozen score 15/17 |
| gpt-6-luna-max | v14 | 52.52 | 16,943,439 / 16,581,248 | 134,813 / 59,047 | 117 / 7 | core values match; 44/44 pair cases match; frozen score 17/17 |
| gpt-6-luna-max | v15 | 37.05 | 9,053,317 / 8,826,880 | 111,251 / 54,180 | 85 / 7 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-6-luna-high | vanilla | 19.44 | 3,526,016 / 3,393,024 | 57,273 / 10,931 | 43 / 2 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-6-luna-high | v14 | 28.94 | 9,988,939 / 9,721,984 | 82,706 / 29,108 | 84 / 12 | core values match; 44/44 pair cases match; frozen score 17/17 |
| gpt-6-luna-high | v15 | 52.01 | 9,201,750 / 8,979,328 | 77,246 / 21,062 | 83 / 6 | effective-date cost error; 44/44 pair cases wrong; frozen score 13/17 |
| gpt-5.6-luna-max | vanilla | 26.93 | 5,870,379 / 5,671,296 | 80,442 / 20,041 | 62 / 11 | core values match; 44/44 pair cases wrong; frozen score 16/17 |
| gpt-5.6-luna-max | v14 | 28.95 | 10,794,182 / 10,557,824 | 79,581 / 24,079 | 84 / 10 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-5.6-luna-max | v15 | 25.22 | 8,278,519 / 8,040,704 | 74,556 / 21,604 | 69 / 12 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-5.6-luna-high | vanilla | 12.76 | 2,374,240 / 2,245,888 | 38,309 / 6,476 | 42 / 7 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-5.6-luna-high | v14 | 16.64 | 4,753,014 / 4,557,696 | 47,893 / 10,614 | 42 / 6 | core values match; 44/44 pair cases match; frozen score 16/17 |
| gpt-5.6-luna-high | v15 | 14.94 | 4,193,780 / 4,040,192 | 41,219 / 8,220 | 55 / 13 | core values match; 44/44 pair cases match; frozen score 14/17 |
| gpt-6-astra-xhigh | vanilla | 68.91 | 1,597,119 / 1,477,376 | 55,748 / 10,487 | 39 / 1 | core values match; 44/44 pair cases match; frozen score 17/17 |
| gpt-6-astra-xhigh | v14 | 69.39 | 2,829,786 / 2,659,584 | 66,061 / 12,703 | 48 / 1 | core values match; 44/44 pair cases match; frozen score 17/17 |
| gpt-6-astra-xhigh | v15 | 63.71 | 1,918,997 / 1,725,184 | 57,372 / 11,085 | 47 / 3 | core values match; 44/44 pair cases match; frozen score 17/17 |

## Serial local performance at concurrency 8

Read workload500 requests; write workload200 unique draft orders. Fresh store per concurrency. No concurrent benchmark. All32 measured workload batches returned only2xx. First-pass burst transport failures keep10 servers ineligible.

| Tuple | Arm | Read req/s | Read p95 ms | Write req/s | Write p95 ms |
| --- | --- | ---: | ---: | ---: | ---: |
| gpt-6-sol-high | v14 | 3,444 | 3.39 | 1,926 | 10.56 |
| gpt-6-luna-max | vanilla | 3,059 | 3.99 | 1,717 | 10.58 |
| gpt-6-luna-high | v14 | 3,397 | 3.62 | 2,015 | 10.08 |
| gpt-6-luna-high | v15 | 3,530 | 3.42 | 1,637 | 9.46 |
| gpt-5.6-luna-max | v15 | 3,369 | 3.58 | 2,096 | 10.87 |
| gpt-6-astra-xhigh | vanilla | 2,694 | 4.27 | 1,523 | 11.72 |
| gpt-6-astra-xhigh | v14 | 2,610 | 4.24 | 1,627 | 10.86 |
| gpt-6-astra-xhigh | v15 | 2,079 | 5.12 | 1,354 | 21.32 |

All per-request latencies/status/errors and concurrency1 results are retained in qualification-v1/results and the two declared runtime-correction results. These short local workloads do not establish production capacity or power-loss durability.
