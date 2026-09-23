# Bounded v1.5 synthetic pilot execution receipt

- Frozen task/source/prompt/rubric/arm manifest: `evals/v1.5/pilot-execution-freeze.json`, commit `72e054b3fdfd7e162dacd777ef2b68fdbb3ae177`, before any outcome call. Source head: `efeb436aeb80dabd9a3df9571e66a3de280eadad`.
- Client: `/Applications/ChatGPT.app/Contents/Resources/codex`, `codex-cli 0.155.0-alpha.16.3`; existing ChatGPT login, disposable `CODEX_HOME` and fixture directory for each cell. Each command requested the manifest model and medium effort.
- Intervention: explicit prompt-delivered v1.5 guidance proxy. The candidate plugin, native hooks, optional memory, and accepted model profiles were not activated or validated. All calls used `--disable hooks` and `--ignore-user-config`.
- These are one-replicate synthetic pilot observations, not held-out evidence, noninferiority, savings, or a general quality claim. No stronger-model call helped a Luna arm.

## Commands

`python3 evals/v1.5/pilot_runner.py --lane EVAL-03`
`python3 evals/v1.5/pilot_runner.py --lane EVAL-02`
`python3 evals/v1.5/pilot_runner.py --lane EVAL-05` (three attempt batches; first two preserved below)

Initial CLI form: `codex exec --sandbox workspace-write --skip-git-repo-check -C <disposable fixture> --json --ignore-user-config --disable hooks -m <frozen model> -c model_reasoning_effort=medium -`.
Final follow-up CLI form: `codex exec resume --last --skip-git-repo-check -c sandbox_mode=workspace-write --json --ignore-user-config --disable hooks -m gpt-6-sol -c model_reasoning_effort=medium -`.

## Final batch, exact per-cell receipts

Columns: checks show passed/total deterministic artifact checks; wall is all calls in the cell; token order is input/cached input/output/reasoning output. Cached input is a subset of input, not an additional amount. Tool and retrieval counts come from completed JSONL items.

| Lane | Task | Locale | Arm | Checks | Calls | Wall s | Tools | Retrieval | Policy | Tokens in/cache/out/reasoning |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| EVAL-02 | coding | en | luna_alone | 5/5 | 1 | 25.642 | 5 | 2 | 0 | 87370/81408/620/102 |
| EVAL-02 | coding | en | luna_v15 | 5/5 | 1 | 35.813 | 6 | 2 | 0 | 111093/101632/1040/231 |
| EVAL-02 | coding | en | sol_alone | 5/5 | 1 | 27.610 | 8 | 4 | 0 | 91671/86656/869/76 |
| EVAL-02 | planning | en | luna_alone | 6/6 | 1 | 15.384 | 3 | 3 | 0 | 58042/53248/378/41 |
| EVAL-02 | planning | en | luna_v15 | 6/6 | 1 | 16.755 | 3 | 3 | 0 | 62082/56320/480/45 |
| EVAL-02 | planning | en | sol_alone | 6/6 | 1 | 18.681 | 3 | 1 | 0 | 59054/55168/562/47 |
| EVAL-03 | mechanical | en | astra_ablation | 1/1 | 1 | 22.255 | 3 | 2 | 0 | 48129/39936/270/0 |
| EVAL-03 | mechanical | en | astra_alone | 1/1 | 1 | 21.467 | 3 | 2 | 0 | 60392/56704/286/0 |
| EVAL-03 | mechanical | en | astra_v15 | 1/1 | 1 | 19.790 | 3 | 2 | 0 | 64417/59776/267/0 |
| EVAL-03 | mechanical | en | sol_ablation | 1/1 | 1 | 19.922 | 4 | 2 | 0 | 78467/73472/570/40 |
| EVAL-03 | mechanical | en | sol_alone | 1/1 | 1 | 23.305 | 4 | 1 | 0 | 74340/70016/691/31 |
| EVAL-03 | mechanical | en | sol_v15 | 1/1 | 1 | 20.232 | 4 | 3 | 0 | 78652/73856/494/27 |
| EVAL-05 | developer | en | alone | 2/2 | 2 | 40.141 | 9 | 3 | 0 | 244256/227072/1761/236 |
| EVAL-05 | developer | en | v15 | 2/2 | 2 | 51.997 | 8 | 3 | 0 | 263528/240768/2783/398 |
| EVAL-05 | developer | ko | alone | 2/2 | 2 | 49.798 | 13 | 6 | 0 | 251812/235392/2772/557 |
| EVAL-05 | developer | ko | v15 | 2/2 | 2 | 51.390 | 15 | 8 | 0 | 304416/289408/2840/408 |
| EVAL-05 | nondeveloper | en | alone | 2/4 | 2 | 65.203 | 9 | 5 | 0 | 253191/234496/3796/704 |
| EVAL-05 | nondeveloper | en | v15 | 2/4 | 2 | 45.893 | 5 | 4 | 0 | 179099/166528/2599/569 |
| EVAL-05 | nondeveloper | ko | alone | 4/4 | 2 | 57.906 | 7 | 3 | 0 | 216985/200192/2867/628 |
| EVAL-05 | nondeveloper | ko | v15 | 2/4 | 2 | 60.606 | 7 | 3 | 0 | 267455/243456/3456/594 |

## Preserved failed EVAL-05 attempts

- Attempt 1: all eight initial turns ran. Four developer follow-ups exited 1 with zero JSON events because the resume command omitted `--skip-git-repo-check`. Four nondeveloper receipts were lost after a scorer `TypeError` on an accessibility object; their models were called, but their per-call usage and tool counts are missing. See `eval-05-pilot-attempt1-harness-failure.json`.
- Attempt 2: all eight initial and follow-up turns returned exit 0, but the resume command reverted to a read-only sandbox. No follow-up changed the required artifact, so all eight correction cells failed. See `eval-05-pilot-attempt2-readonly-followup.json`.
- Attempt 3: `--skip-git-repo-check` and `sandbox_mode=workspace-write` were both applied. All developer artifact corrections passed in English and Korean. Nondeveloper artifact checks passed only in Korean baseline (one of four cells). All initial nondeveloper cells correctly held booking while 28 guests exceeded the accessible venue capacity.
- A separate disposable Sol smoke established that workspace-write on resume permits a file edit. It was a harness diagnostic, not an EVAL-05 result.

## Interpretation and missingness

- EVAL-02: both Luna conditions and Sol baseline passed the frozen coding and planning artifact checks. The pilot shows no observable Luna quality gain or remaining Sol gap on these easy fixtures; no ratio or Sol-level claim applies. The v1.5 guidance proxy used more wall time and reported tokens than Luna alone on both tasks.
- EVAL-03: all six mechanical-edit cells passed. Single concurrent wall-time observations are not a stable efficiency estimate. The ablation and full guidance arms held the guide text, source, model, effort, tools, and disabled memory fixed; only the optional wrapper differed.
- EVAL-05: developer artifact correction passed 4/4 in the final batch. Nondeveloper final artifact checks passed 1/4, with English 0/2 and Korean 1/2. This is a strict machine check of stated JSON fields, not a bilingual human quality judgment. The `side_question_observation` field in JSON is a text heuristic only and was not counted as a human score.
- Manual bilingual dialogue quality scores, independent blind review, billing/cost per call, native plugin activation/application, native-memory isolation proof, and server-echoed model identity are unavailable (`null` or explicitly false in records). CLI commands requested exact models and effort and returned model turns, but the event stream did not independently echo them.
- Composed execution prompts, transcripts, tool text, and disposable synthetic outputs were removed with each temporary directory. The frozen manifest retains only the public synthetic task strings and guidance sources needed to reproduce the pilot. Persisted result files contain hashes, event types, exit codes, usage, checks, and bounded heuristic flags. Attempt 1 nondeveloper receipts have known missingness due to the scorer exception.
- The EVAL-05 fixture covered initial constraint conflict, correction, and a side question. It did not explicitly probe unavailable memory, all necessary/unnecessary clarification patterns, or independent bilingual communication quality. These remain untested protocol dimensions.
