# Complete numeric readout

All values are descriptive for one generated artifact per cell. Three load repetitions are not model replications. Prose scores are provisional unblinded primary-agent assessments; human ratings are unavailable. The source of each value remains in summary.json and the locked result/review files.

## Episodes

| Task | Tuple | Condition | API/artifact groups | Own Go tests | CLI end | Seconds | Tool actions | Failed / unresolved actions | Prose /20 |
| --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| coding | sol-medium | vanilla | 28/28 | pass | complete | 562.342 | 33 | 1 / 0 | n/a |
| coding | sol-medium | v14 | 28/28 | pass | complete | 768.192 | 49 | 3 / 0 | n/a |
| coding | sol-medium | v15 | 28/28 | pass | complete | 414.792 | 29 | 1 / 0 | n/a |
| coding | luna-medium | vanilla | 12/28 | pass | complete | 207.197 | 19 | 1 / 0 | n/a |
| coding | luna-medium | v14 | 27/28 | pass | complete | 443.063 | 46 | 4 / 0 | n/a |
| coding | luna-medium | v15 | 27/28 | pass | complete | 395.386 | 46 | 3 / 0 | n/a |
| coding | luna-max | vanilla | 28/28 | pass | timeout | 1200.011 | 56 | 4 / 0 | n/a |
| coding | luna-max | v14 | 28/28 | pass | timeout | 1200.035 | 46 | 0 / 0 | n/a |
| coding | luna-max | v15 | 28/28 | FAIL | timeout | 1200.026 | 48 | 6 / 0 | n/a |
| office | sol-medium | vanilla | 27/27 | n/a | complete | 257.718 | 16 | 2 / 0 | 20 |
| office | sol-medium | v14 | 27/27 | n/a | complete | 316.249 | 34 | 3 / 0 | 20 |
| office | sol-medium | v15 | 27/27 | n/a | complete | 291.143 | 29 | 6 / 0 | 19 |
| office | luna-medium | vanilla | 27/27 | n/a | complete | 399.938 | 20 | 2 / 2 | 15 |
| office | luna-medium | v14 | 27/27 | n/a | complete | 547.123 | 18 | 3 / 0 | 18 |
| office | luna-medium | v15 | 27/27 | n/a | complete | 526.087 | 54 | 8 / 0 | 18 |
| office | luna-max | vanilla | 27/27 | n/a | complete | 1169.133 | 21 | 4 / 0 | 20 |
| office | luna-max | v14 | 27/27 | n/a | complete | 1045.581 | 28 | 4 / 0 | 20 |
| office | luna-max | v15 | 27/27 | n/a | complete | 1113.594 | 28 | 3 / 0 | 19 |

Failed actions use the client exit/status projection. Unresolved actions lack a completed event and are not silently assigned success or failure. Original command stdout is not comprehensively retained. A successful CLI turn is separate from correctness; a timeout may still leave a correct program.

## Client usage

Null means unavailable. Cached input is a subset of input; reasoning output is a subset of output. All reported cache-write values are explicit zeros, while the three timeout rows remain null. Do not turn these into billed cost or pool incomplete Max usage as if it were complete.

| Cell | Input | Cached input | Cache write | Output | Reasoning output |
| --- | ---: | ---: | ---: | ---: | ---: |
| coding-sol-medium-vanilla | 1,193,874 | 1,113,088 | 0 | 22,103 | 7,271 |
| coding-luna-medium-v14 | 1,506,912 | 1,424,384 | 0 | 18,784 | 4,747 |
| coding-luna-max-v15 | null | null | null | null | null |
| office-luna-medium-v14 | 706,712 | 615,936 | 0 | 12,226 | 2,681 |
| office-luna-max-v15 | 2,044,915 | 1,883,136 | 0 | 59,475 | 39,479 |
| office-sol-medium-vanilla | 407,722 | 354,304 | 0 | 11,985 | 1,386 |
| coding-luna-max-vanilla | null | null | null | null | null |
| coding-sol-medium-v14 | 2,002,797 | 1,860,992 | 0 | 31,882 | 11,415 |
| coding-luna-medium-v15 | 1,384,342 | 1,300,480 | 0 | 17,575 | 3,026 |
| office-sol-medium-v14 | 692,998 | 625,920 | 0 | 14,122 | 1,833 |
| office-luna-medium-v15 | 1,950,760 | 1,835,520 | 0 | 25,637 | 8,002 |
| office-luna-max-vanilla | 1,422,780 | 1,280,000 | 0 | 54,281 | 34,185 |
| coding-luna-medium-vanilla | 510,297 | 458,496 | 0 | 9,406 | 1,138 |
| coding-luna-max-v14 | null | null | null | null | null |
| coding-sol-medium-v15 | 900,547 | 827,776 | 0 | 18,831 | 3,969 |
| office-luna-max-v14 | 1,704,515 | 1,555,200 | 0 | 56,398 | 30,059 |
| office-sol-medium-v15 | 696,873 | 624,128 | 0 | 12,843 | 2,150 |
| office-luna-medium-vanilla | 603,580 | 533,504 | 0 | 16,860 | 4,445 |

Reported totals from15/18 calls: input17,729,624 (cached subset16,292,864), output382,408 (reasoning subset155,786), cache-write0. Missing usage:3 calls in every category. Total observed tool actions620, failed58, unresolved2; summed call wall time12,057.610 seconds includes overlapping calls and is not elapsed study time. Three preparation-agent turns and primary integration have unavailable separate usage.

## Backend performance

Each entry is median [minimum, maximum] of three repetitions. RPS credits successful start-and-end pairs inside the five-second window. p99 uses the start cohort including drain. CPU seconds cover server warmup, measurement and drain; RSS is sampled server MiB, not guaranteed peak. Both scopes exclude the client/model/whole-machine cost.

| Artifact | Qualification | Workload | Concurrent | RPS | p99 ms | Server CPU s | Sampled RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| coding-sol-medium-vanilla | eligible | read | 1 | 192.20 [191.60, 197.60] | 6.23 [5.46, 6.56] | 5.81 [5.77, 5.82] | 24.78 [24.42, 24.78] |
| coding-sol-medium-vanilla | eligible | read | 16 | 189.20 [179.20, 190.20] | 215.30 [213.87, 227.41] | 6.10 [6.09, 6.11] | 25.89 [25.20, 26.25] |
| coding-sol-medium-vanilla | eligible | write | 1 | 1833.40 [1786.60, 1900.00] | 0.87 [0.80, 0.87] | 4.56 [4.50, 4.58] | 28.00 [27.88, 28.02] |
| coding-sol-medium-vanilla | eligible | write | 16 | 2188.60 [2141.00, 2231.40] | 30.33 [30.22, 31.39] | 6.09 [6.05, 6.09] | 28.69 [28.47, 28.84] |
| coding-sol-medium-v14 | eligible | read | 1 | 104.80 [96.60, 114.00] | 15.53 [11.80, 27.35] | 5.80 [5.55, 5.85] | 25.00 [24.62, 25.52] |
| coding-sol-medium-v14 | eligible | read | 16 | 261.40 [260.00, 277.20] | 140.12 [134.51, 147.90] | 23.78 [23.74, 23.80] | 48.02 [46.59, 48.14] |
| coding-sol-medium-v14 | eligible | write | 1 | 2096.80 [2027.80, 2147.20] | 2.40 [2.30, 2.53] | 5.41 [5.37, 5.56] | 28.50 [28.44, 28.92] |
| coding-sol-medium-v14 | eligible | write | 16 | 2639.60 [1900.40, 2704.80] | 57.23 [56.51, 83.54] | 9.58 [8.27, 9.72] | 28.72 [28.42, 29.72] |
| coding-sol-medium-v15 | eligible | read | 1 | 147.80 [106.20, 148.20] | 9.21 [8.92, 20.77] | 5.75 [5.66, 5.79] | 24.88 [24.28, 24.91] |
| coding-sol-medium-v15 | eligible | read | 16 | 141.60 [140.00, 146.00] | 469.68 [430.31, 537.28] | 6.19 [6.14, 6.19] | 25.80 [25.61, 25.86] |
| coding-sol-medium-v15 | eligible | write | 1 | 1164.60 [1116.00, 1217.60] | 1.86 [1.49, 2.18] | 4.85 [4.79, 4.89] | 28.09 [27.70, 28.11] |
| coding-sol-medium-v15 | eligible | write | 16 | 1364.20 [1158.00, 1391.60] | 53.13 [53.04, 70.27] | 5.96 [5.94, 6.01] | 28.83 [28.67, 29.38] |
| coding-luna-medium-vanilla | **diagnostic** | read | 1 | 156.60 [137.00, 157.20] | 8.38 [7.54, 18.44] | 6.12 [6.07, 6.13] | 24.38 [24.31, 24.41] |
| coding-luna-medium-vanilla | **diagnostic** | read | 16 | 296.80 [281.80, 320.00] | 114.11 [97.07, 117.15] | 23.38 [23.30, 23.42] | 37.02 [36.11, 37.16] |
| coding-luna-medium-vanilla | **diagnostic** | write | 1 | 2225.20 [2071.80, 2301.20] | 0.88 [0.85, 0.94] | 4.77 [4.70, 4.81] | 27.66 [27.59, 27.94] |
| coding-luna-medium-vanilla | **diagnostic** | write | 16 | 0.00 [0.00, 0.00] | 3004.45 [3004.26, 3004.82] | 0.01 [0.01, 0.01] | 20.14 [20.09, 20.30] |
| coding-luna-medium-v14 | **diagnostic** | read | 1 | 168.40 [158.60, 173.20] | 13.60 [8.01, 13.68] | 5.70 [5.65, 5.75] | 23.45 [23.28, 23.91] |
| coding-luna-medium-v14 | **diagnostic** | read | 16 | 168.00 [126.60, 174.60] | 257.85 [240.97, 409.73] | 6.13 [6.04, 6.13] | 24.31 [24.31, 25.19] |
| coding-luna-medium-v14 | **diagnostic** | write | 1 | 2350.60 [2191.60, 2361.40] | 2.26 [2.10, 2.35] | 4.84 [4.71, 4.91] | 27.95 [27.64, 28.31] |
| coding-luna-medium-v14 | **diagnostic** | write | 16 | 2757.80 [1854.60, 2935.00] | 25.81 [24.92, 43.53] | 8.44 [7.35, 8.52] | 29.14 [28.95, 29.38] |
| coding-luna-medium-v15 | **diagnostic** | read | 1 | 109.80 [108.00, 114.80] | 13.59 [12.67, 13.99] | 5.78 [5.78, 5.79] | 24.50 [24.34, 24.66] |
| coding-luna-medium-v15 | **diagnostic** | read | 16 | 130.40 [116.80, 131.40] | 974.23 [475.96, 1377.23] | 6.19 [6.15, 6.23] | 36.86 [29.75, 36.98] |
| coding-luna-medium-v15 | **diagnostic** | write | 1 | 2469.80 [1914.20, 2486.40] | 2.30 [2.27, 2.71] | 4.52 [4.51, 4.70] | 27.95 [27.80, 28.38] |
| coding-luna-medium-v15 | **diagnostic** | write | 16 | 3124.60 [2973.00, 3313.80] | 41.32 [37.87, 42.42] | 8.46 [8.20, 8.49] | 28.05 [27.41, 28.88] |
| coding-luna-max-vanilla | **diagnostic** | read | 1 | 134.60 [130.20, 135.60] | 16.50 [9.90, 20.75] | 5.64 [5.50, 5.79] | 24.41 [24.14, 24.42] |
| coding-luna-max-vanilla | **diagnostic** | read | 16 | 283.00 [270.60, 324.80] | 182.21 [138.48, 194.00] | 22.83 [22.57, 23.87] | 58.47 [57.30, 59.52] |
| coding-luna-max-vanilla | **diagnostic** | write | 1 | 1006.00 [925.80, 1047.60] | 2.40 [2.10, 2.55] | 5.49 [5.42, 5.49] | 28.67 [28.19, 28.80] |
| coding-luna-max-vanilla | **diagnostic** | write | 16 | 993.20 [965.40, 1005.20] | 329.88 [231.98, 330.23] | 5.59 [5.49, 5.71] | 30.88 [30.67, 31.34] |
| coding-luna-max-v14 | eligible | read | 1 | 226.80 [218.60, 228.80] | 5.68 [5.48, 6.39] | 6.05 [6.05, 6.06] | 25.23 [24.86, 25.36] |
| coding-luna-max-v14 | eligible | read | 16 | 471.80 [469.20, 478.00] | 83.60 [78.18, 84.52] | 23.50 [23.46, 23.53] | 53.89 [53.86, 53.91] |
| coding-luna-max-v14 | eligible | write | 1 | 2794.40 [2768.80, 2890.20] | 2.45 [2.40, 2.51] | 5.03 [5.03, 5.05] | 28.77 [28.47, 28.80] |
| coding-luna-max-v14 | eligible | write | 16 | 2603.60 [2598.40, 2644.60] | 96.78 [88.12, 103.59] | 6.99 [6.93, 7.02] | 29.94 [29.78, 31.03] |
| coding-luna-max-v15 | **diagnostic** | read | 1 | 114.20 [99.60, 121.40] | 13.70 [11.85, 19.35] | 5.80 [5.75, 5.81] | 25.11 [24.83, 25.31] |
| coding-luna-max-v15 | **diagnostic** | read | 16 | 276.20 [266.20, 278.20] | 136.08 [135.21, 139.39] | 23.82 [23.81, 23.89] | 47.81 [46.67, 47.91] |
| coding-luna-max-v15 | **diagnostic** | write | 1 | 1834.20 [1567.40, 2008.60] | 3.48 [2.93, 3.62] | 4.99 [4.98, 5.06] | 27.83 [27.61, 28.05] |
| coding-luna-max-v15 | **diagnostic** | write | 16 | 2587.00 [2383.40, 2632.40] | 54.96 [54.17, 58.95] | 9.01 [8.99, 9.22] | 30.30 [29.61, 30.38] |

108 load cells and709,858 raw requests (including warmup) are retained. There are111 failed requests:63 warmup and48 measured starts. Seven cells fail the all-attempt/conservation gate: three Luna-medium-vanilla write/c16 cells (32 request timeouts each, plus unavailable final-state reads), three Luna-medium-v15 read/c16 cells (6/2/6 warmup timeouts), and one Luna-max-vanilla write/c16 cell (one warmup timeout). The remaining101 cells pass that per-cell gate; artifact-level eligibility still requires all28 API groups and own tests.

Only Sol medium in all three conditions and Luna max/v14 satisfy the full frozen performance gate. Every other artifact remains diagnostic, including fast measurements from a program with a known API defect. No failed load cell was rerun.

## Delivery and memory observations

All18 disposable native-memory output/job tables are empty in the read-only receipts. That is local evidence, not account-side isolation proof. Adapter receipts contain zero calls; direct native decision invocations are separately identifiable by lexical command evidence. A zero captured response count is not proof of zero native activity or failed application. No fresh-session memory effect is isolated by this one-session task.
