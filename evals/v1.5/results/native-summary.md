# Installed OpenSocrates native-plugin pilot receipt

- Native execution freeze: `evals/v1.5/native-plugin-execution-freeze.v1.json`, final pre-outcome freeze commit `b843b9d581d9fa94a563fa5ec49c1d4c4efd2645`. The earlier prompt-delivered proxy pilot remains separate and unchanged.
- Task bytes, prompts, follow-up corrections and deterministic rubric are inherited by hash from `evals/v1.5/pilot-execution-freeze.json` (`a1065c38474c345610740acbf45e95f78354a5332262fe3ca51cea44aed899a0`).
- Candidate package: `opensocrates-1.4.0-codex-plugin.zip`, SHA256 `c8cc308e757afafb5e5a076e45de096aa1f305e1168c926effe2d34d2a604201`, built from the pre-revision v1.5 candidate source. Later root-branch guide/WAL edits are not in these results.
- Client: `/Applications/ChatGPT.app/Contents/Resources/codex`, `codex-cli 0.155.0-alpha.16.3`. Every call requested the frozen model and medium effort. Subagents were disabled in every arm; no stronger-model help was used in Luna cells.
- Each cell used owner-only disposable HOME, CODEX_HOME and TMPDIR. Existing auth was copied with mode 0600 into that profile, not symlinked; profiles and extracted ZIP marketplace were removed after each lane. Baseline profiles confirmed no OpenSocrates installation; treatment/ablation profiles confirmed installed and enabled `opensocrates@os-eval` 1.4.0 before model calls.

## Commands

`python3 evals/v1.5/native_plugin_runner.py --lane EVAL-03`
`python3 evals/v1.5/native_plugin_runner.py --lane EVAL-02`
`python3 evals/v1.5/native_plugin_runner.py --lane EVAL-05`

All turns used `--disable multi_agent`, `-m <frozen model>`, `-c model_reasoning_effort=medium`, JSONL output, and workspace-write in disposable fixtures. Native arms used `--dangerously-bypass-hook-trust` only inside the isolated profile for the pinned ZIP. Ablation and alone arms used `--disable hooks`; ablation retained the installed package and same skill prompt as native. Resumed turns also used `--skip-git-repo-check -c sandbox_mode=workspace-write`.

## Exact per-cell observations

Checks are passed/total deterministic final artifact checks. Wall is summed model-turn time and excludes the separately recorded installation time. Tokens are input/cached input/output/reasoning output; cached input is included within input. Tool and policy counts are completed-event counts; policy count is a command-keyword heuristic and can include guide reads. Hook delivery/application was not visible in JSONL.

| Lane | Task | Locale | Arm | Checks | Turns | Wall s | Tools | Retrieval | Policy heuristic | Tokens in/cache/out/reasoning |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| EVAL-02 | coding | en | luna_alone | 5/5 | 1 | 50.772 | 6 | 2 | 0 | 119760/107520/1423/174 |
| EVAL-02 | coding | en | luna_native | 5/5 | 1 | 30.185 | 6 | 3 | 1 | 98723/88576/976/195 |
| EVAL-02 | coding | en | sol_alone | 5/5 | 1 | 28.099 | 9 | 4 | 0 | 91008/86144/781/104 |
| EVAL-02 | planning | en | luna_alone | 6/6 | 1 | 18.207 | 2 | 2 | 0 | 43343/38144/451/37 |
| EVAL-02 | planning | en | luna_native | 6/6 | 1 | 52.530 | 7 | 7 | 6 | 236674/210432/1888/332 |
| EVAL-02 | planning | en | sol_alone | 6/6 | 1 | 18.707 | 2 | 2 | 0 | 43987/37632/593/43 |
| EVAL-03 | mechanical | en | astra_ablation | 1/1 | 1 | 29.641 | 3 | 2 | 1 | 68591/61952/542/0 |
| EVAL-03 | mechanical | en | astra_alone | 1/1 | 1 | 18.753 | 3 | 2 | 0 | 44940/36480/262/0 |
| EVAL-03 | mechanical | en | astra_native | 1/1 | 1 | 27.792 | 3 | 2 | 1 | 68244/56320/487/0 |
| EVAL-03 | mechanical | en | sol_ablation | 1/1 | 1 | 36.101 | 5 | 3 | 1 | 99965/92928/734/84 |
| EVAL-03 | mechanical | en | sol_alone | 1/1 | 1 | 25.671 | 4 | 1 | 0 | 73990/66816/646/42 |
| EVAL-03 | mechanical | en | sol_native | 1/1 | 1 | 35.594 | 5 | 2 | 1 | 82233/62336/692/104 |
| EVAL-05 | developer | en | alone | 2/2 | 2 | 52.880 | 8 | 3 | 0 | 245236/233472/2625/410 |
| EVAL-05 | developer | en | native | 2/2 | 2 | 97.363 | 15 | 10 | 5 | 526374/471424/6208/1700 |
| EVAL-05 | developer | ko | alone | 2/2 | 2 | 67.265 | 13 | 6 | 0 | 255797/232960/3593/395 |
| EVAL-05 | developer | ko | native | 2/2 | 2 | 86.018 | 13 | 8 | 4 | 531744/492800/4418/1186 |
| EVAL-05 | nondeveloper | en | alone | 3/4 | 2 | 63.758 | 7 | 3 | 0 | 251296/233344/3647/871 |
| EVAL-05 | nondeveloper | en | native | 3/4 | 2 | 83.792 | 14 | 10 | 5 | 460902/424320/5106/1587 |
| EVAL-05 | nondeveloper | ko | alone | 3/4 | 2 | 69.818 | 9 | 5 | 0 | 283786/269952/3844/510 |
| EVAL-05 | nondeveloper | ko | native | 3/4 | 2 | 130.195 | 14 | 10 | 6 | 587365/539264/9120/1493 |

## Interpretation and incomplete evidence

- EVAL-02: all six coding/planning cells passed deterministic artifact checks. Luna native and Luna alone both passed both tasks; Sol alone also passed both. There is no observed quality gain or Sol gap on these easy fixtures. Luna native had lower coding wall time and tokens in this one attempt, but substantially higher planning wall time, tool/policy activity and tokens. No cost-per-accepted-outcome claim is possible.
- EVAL-03: all six mechanical-edit cells passed. Native and ablation conditions used more wall time than same-model baseline for both Sol and Astra in this one matched pilot. The ablation/native pair differs by hooks enabled versus disabled, but the JSONL exposed zero explicit hook events in either native cell. The effect of native hook delivery is unverified.
- EVAL-05: both developer language pairs passed initial and corrected code behavior in both arms (4/4 cells). All four nondeveloper cells held the initial impossible booking, then selected venue A, attendance 20 and accessibility after the correction. Every nondeveloper cell failed the strict `next_booking_action` string check, which requires availability and step-free access in one field. Synthetic artifact outputs were discarded, so semantic adequacy beyond that field cannot be adjudicated from these records. English and Korean failures remain visible.
- Treatment profiles verified package installation and enabled state. Model-initiated policy/guide command activity occurred in installed arms, but skill use, hook delivery and method application are not independently proven. Zero explicit hook events were exposed by Codex JSONL. A grounding-line self-claim, if any, is recorded separately and never treated as application evidence.
- Billing, independent blinded bilingual dialogue scores, exact native hook application, server-echoed model identity, and subscription cost attribution are unavailable. Their per-call fields are null. Installation wall time and every model-turn token/tool/failure receipt remain in the lane JSON files.
- These are one-replicate synthetic pilot episodes, not held-out tests or validated capability profiles. No noninferiority, superiority, general collaboration, or savings claim follows. The EVAL-05 fixtures did not explicitly test unavailable memory or all necessary/unnecessary clarification patterns; human dialogue review remains needed.
- Raw composed prompts, transcripts, tool text and disposable artifact bytes were not persisted. Frozen synthetic task strings and pinned source identities remain in the manifests; result JSON contains hashes, status, counts, usage, and deterministic checks.
