# First experiment results — 2026-10-30

## Case and setup

Each of 81 roles was invoked in an independent Codex CLI session for one fictional handover of an internal workshop. The nine capabilities ran in parallel; each capability's nine agents received the earlier results from that same capability in sequence. One separate call synthesized all 81 reviews. The comparison was a single CLI call given the same fictional request and source material. Both conditions also received a list of unknowns.

- Of 81 agent calls, 81 completed and none failed. One baseline response and one synthesis response also completed separately.
- Twenty-four agents marked their own results as needing information. No tool use was detected in CLI events, and no real execution or storage was performed.
- Total elapsed time was about 193 seconds. The baseline response took about 12.2 seconds. Subtracting the baseline call from the total leaves about 181 seconds for the other 81 agents and synthesis.
- CLI-reported input tokens totaled 1,771,139 for the 81 agents and synthesis (the CLI separately reported 450,816 cached input tokens), versus 16,498 for the baseline response. Output tokens were 33,323 and 406, respectively. Cache billing rules and actual cost were not checked.
- The model name and reasoning level were not recorded in the run results and cannot be confirmed. The CLI version checked immediately after the experiment was `codex-cli 0.166.0-alpha.5.1`.
- All 81 role results and both final responses are in the local `results/run.json`, which is excluded from Git. After the code had been loaded for the experiment, only two path-handling details were changed: separating the default dry-run output file and normalizing temporary paths. The 81 calls, inputs, and synthesis approach were unchanged.

## Comparison

Both the baseline and the response synthesized from 81 results incorporated the schedule, attendance, venue capacity limit, budget, program-review status, and next items to confirm into a report draft. The synthesized response more explicitly stated the 20-person capacity shortfall, availability on the event date, and the unconfirmed status of the overall budget fit. The baseline read naturally as a report from the person taking over the work.

Claude compared the fictional request, source material, and final responses without being told how the responses were generated. Claude judged them **substantially equivalent in practical use**. It saw explicitness as the synthesized response's strength and the handover recipient's perspective as the baseline's strength. It also noted that both provided one report draft rather than separate lists of the current situation and next tasks. Evaluation conversation: [Anonymous A/B comparison](https://claude.ai/chat/54bd4ad1-ea3e-426e-a210-d8112582f903). A passage in Claude's evaluation that could be read as implying that an alternative venue would also cost at least KRW 2 million is unsupported. KRW 2 million was candidate A's quote.

This is one AI evaluator's judgment, not a human usefulness evaluation. Because only the final responses were compared, the evaluation also did not fully assess error propagation through the 81 intermediate results or omissions during synthesis.

## What this experiment cannot establish

- Whether it is superior to a single response from one case, whether the nine capabilities or particular questions caused an effect, or whether it helps general office workers broadly.
- The separate effects of generating and synthesizing multiple responses, dividing the questions, and passing results forward in sequence.
- The quality of real email or document search, information storage and updates, actions such as sending or booking, or behavior in other hosts.
- The model name and version, exact billed cost, or variation across repeated runs.

In a separate review of the experiment design, Claude recommended additional conditions: checking the same questions in one call, multiple sessions with generic questions, no sequential handoff, separate simple and complex tasks, and blinded human evaluation. That review is in the [planning conversation](https://claude.ai/chat/eb5d4235-64a9-4a6c-9b13-21ec6d53bbe5). Those additional conditions were not run in this single experiment.
