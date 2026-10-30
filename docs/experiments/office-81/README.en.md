# Office-work experiment with 81 agents

This early research experiment tests nine work capabilities × nine questions as 81 independent AI calls on one fictional office task. It is not an OpenSocrates product or released feature. It uses Codex CLI as its execution environment and does not establish behavior in Claude, ChatGPT web, or other hosts.

## Contents

- `agents.json`: Each of the 81 agents' questions and roles.
- `case.json`: A fictional work case containing no personal or company information, plus the outcomes to check.
- `run.py`: The experiment coordinator, which runs independent calls within a concurrency limit and generates a baseline response and a synthesized response.
- `test_harness.py`: Tests for the coordinator's basic behavior and failure handling.
- `FIRST_RUN.en.md`: The first run's results, Claude's anonymous comparison, and the limits of the observations.
- `results/`: A local-only folder for run results, excluded from Git.

Within each capability, nine agents pass their results forward in sequence. Different capabilities run in parallel within the concurrency limit. This is not a single 81-step flow that passes through every capability in a fixed order. A final synthesis call combines the responses that actually succeeded into a result for the user. The experiment examines each question's distinct perspective; the collaboration benefits of independent calls and their effect on real work require separate evaluation.

## Run

Codex CLI and an account that can use it are required. The experiment can affect model-call counts, elapsed time, and usage limits. Codex CLI uses the existing login; the experiment does not collect a separate API key.

```sh
cd docs/experiments/office-81
python3 run.py --dry-run
python3 run.py --output results/run.json --concurrency 6
```

Use fictional data only. Do not add real emails, messages, customer information, or confidential work content. Execution requests and conversation transcripts are not saved; local results contain only public responses about the fictional case and their statuses. The experiment does not perform external actions such as sending mail or making reservations. Failures and timeouts are not filled in as successes. Tool use is detected after the fact in output events, and the corresponding result is rejected. This detection does not prevent the tool action itself, and the read-only setting does not block all file reads or network access. Using real material requires separate isolation and policy validation.

When evaluating the baseline and the response synthesized from 81 agents, consider fitness for purpose, priorities, context, factual accuracy, understandable communication, and the effort needed to revise the result, alongside the checks in `case.json`. One fictional case does not establish benefits across general office work or prove that the 81-agent structure is superior. A person must judge whether the result is useful.
