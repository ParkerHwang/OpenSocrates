# Office evaluation lab

[한국어](evaluation-lab.ko.md) · [Create another case pack](evaluation-lab-casepacks.md)

Use this local kit to compare whole office-work answers: whether the message,
tone, use of context, content, references and structure work for you together.
You run the actual apps and make the first practical judgment. The lab prepares
fictional tasks, keeps attempts separate and collects approved final answers.
It does not run models or decide which answer is better.

## First session: one app, six attempts

1. Install [Python 3.12 or later](https://www.python.org/downloads/) and the app
   you want to test. Sign in through that app normally. No API key is needed.
2. Extract the portable ZIP into your own writable folder. On Mac, open
   **Start Lab.command**; on Windows, open **Start Lab.cmd**. Follow any normal
   operating-system trust prompt. If Python is missing, use the official installer
   linked by the launcher and reopen it. Do not bypass security policy.
3. In the local browser page, choose **this OS and one app**. Start with the two
   calibration tasks and an attempt budget of six: two tasks × three conditions.
   Creating the study spends no model usage. Selecting all six app/OS cells would
   instead plan 36 calibration attempts; these are independent cells.
4. Read the fictional task pack and its common short instruction. Confirm that
   these are plausible office tasks before you see any generated answers.
5. Prepare one attempt, follow its app-specific setup, complete the preflight,
   then start the lab's attempt record **before** clicking Run in the app.
6. When the final answer arrives, preview it and approve only the requested final
   deliverable from the synthetic task. Repeat the remaining attempts, then make
   your first practical choices in the review view before revealing conditions.

The browser page connects only to a local address. Leave it open for status
refreshes. Closing the page does not stop a model running in another app.

## What is being compared

| Condition | Setup |
| --- | --- |
| A | The ordinary task, with OpenSocrates absent from the active environment. |
| B | The same task plus one fixed short instruction, shared across tasks. |
| C | The ordinary task with the pinned OpenSocrates 1.5.3 content prepared for that app. |

Each attempt uses a fresh conversation and its own actor folder. Use the supplied
prompt unchanged. If the app asks a clarification question, use the supplied
reply card and record the number of clarifications. Do not improve B for each
task or coach C after seeing its answer. Save a failed or blocked attempt as such;
a retry is a separate diagnostic attempt and never replaces the first attempt.
The budget counts started attempts, including failures. The lab never retries
or launches an app task automatically.

| App on macOS or Windows | Requested setting | Preflight observation |
| --- | --- | --- |
| Codex app Work | `gpt-6-luna max` | GPT-6 Luna, Max effort, in Work. |
| Claude Cowork | `haiku-5.5-medium` | Haiku 5.5, Medium effort, in Cowork. |
| Antigravity standalone app | `gemini-3.8-flash-mid` | Gemini 3.8 Flash Medium; explicitly confirm this label mapping. |

Record the actual model, effort, app version and execution mode visible to you.
If the requested combination cannot be selected, record it as unavailable or
unknown. Do not substitute another model, consumer chat, Claude Code or Codex CLI.
A Mac or Windows client does not establish where the task executes: cloud,
synchronized and unknown execution remain separate recorded states.

## App setup and environment checks

Give the app access to **only the prepared actor folder** shown by the lab.
Never grant the whole lab, source repository or another attempt's folder. The
actor folder contains this task's public materials, prompt, empty `out/` folder
and, for C, that app's content. Folder separation is not an operating-system
sandbox; use the app's normal access controls.

The prepared setup instructions are the authority for that attempt's files:

- **Work C:** the kit supplies an experimental content-only plugin adapter from
  the complete, unchanged 1.5.3 account skill. Import it through the Work UI if
  supported. It has no command hooks. This transport is under test; copied files
  do not prove Work discovered or applied the skill. Unsupported import blocks
  this cell rather than switching to a CLI.
- **Cowork C:** upload the supplied account skill through Claude's normal skill
  interface and enable it for the test. Complete any ordinary trust steps. An
  instruction saying a skill exists is not a substitute for enabling it. Check
  account-level skill state again before A or B because it may sync to other
  machines or surfaces. Preserve existing settings and restore only changes you
  intentionally made for this test.
- **Antigravity C:** open the new actor workspace containing the supplied
  workspace rules and skills. Do not install this content globally or reuse a
  workspace from another condition. The kit uses workspace rules/skills, not
  a workflow or the consumer Gemini website.

For every attempt, check account/global instructions, installed plugins and
skills, project or folder instructions, memory, connectors and parent-workspace
rules. A fresh OS installation or a new folder can still inherit account state.
The lab records your environment declaration; it cannot automatically certify
a clean machine. Existing OpenSocrates guidance in A/B is contamination. Known
contamination blocks starting. Unknown isolation requires an explicit exploratory
choice and stays labeled exploratory in the results.

Use an independently prepared OS environment or a clean snapshot when you need
stronger isolation. Do not copy login tokens between machines, erase global
settings, or remove unrelated plugins to make a test start. Use ordinary app
settings and record what you can establish. If native app discovery cannot be
observed, leave delivery/application unknown; an answer's claim or footer is not
proof of loading, a complete read, or application.

## Final answers and monitoring

The prompt asks for the deliverable at `out/final.md` inside the actor folder.
Monitoring checks only that file's existence, size and readiness. A file arrival
does not prove the model has finished or that OpenSocrates worked. Preview the
text, confirm it is the synthetic final deliverable, and approve that exact
version. If the file changes after preview, preview it again. After a restart,
preview approval must also be renewed.

If the app cannot write that file, paste its final deliverable through the lab's
manual intake and mark the source as manual. Keep the original wording,
structure, references and any footer. Do not paste an entire conversation,
thinking trace, tool log, account details or private work. Rejecting a preview
does not import it into the lab's approved answer collection; the lab does not
retain rejected text or a fingerprint of it. An app-created file remains in its
actor folder until you manage that folder yourself.

Collection is limited to approved synthetic final answers, approved human
comments/edits and explicit study metadata. No background screen recording,
transcript scraping, global host logs, credential capture or hidden reasoning
capture is enabled. Native hook monitoring is not included in this version.
Provider-side retention is controlled by each service, outside this local lab.
The local app makes no upload; even an export remains a local file.

## Your judgment comes first

Compare the three whole answers and choose the one you would actually use,
**tie**, or **all unusable**. A short free reaction is optional; “I cannot explain
why” is valid. Record confidence, whether you recognize a condition, and whether
the comparison reproduced the difference you normally feel. The first judgment
locks before condition identities and factual guardrails are revealed. Optional
human editing can help show the desired difference afterward.

The same person may operate and review, so this is partial blinding. Opaque answer
labels reduce cues but do not erase memory, an identifying footer or familiarity
with a condition. Review a completed batch later when practical. AI suggestions
about wording or causes belong after your first reaction; they do not override
your choice.

The supplied two calibration cases check the procedure. Four discovery cases
explore varied office situations, including a simple task where extra work may
hurt. Freeze human-approved criteria and the study setup before the two separate
confirmation examples. If these tasks miss your usual experience, change the
next pack or design a separate multi-turn study. More completed attempts do not
repair an irrelevant task sample.

## Resume, repeat and combine

- **Resume:** reopen the same launcher in the same extracted kit. Its `lab-data/`
  folder retains the study. Do not run two lab instances on the same data folder.
- **New study:** extract a clean copy of the original ZIP into another writable
  folder, or launch with `--data` pointing to a new, dedicated data folder. Do not
  copy an existing kit's `lab-data/` when you want an empty study. There is no
  automatic destructive reset of app or lab state.
- **Other OS or app:** prepare an independent clean kit copy and record that
  environment's actual settings. Do not move host login caches between copies.
  The same frozen pack and payload identities allow later comparison.
- **Export:** use the lab's export action. It includes allowlisted study metadata,
  approved answers, locked judgments and a descriptive report. Keep it private
  unless you deliberately share it. Unrevealed condition mappings remain hidden.
- **Combine:** run the bundled read-only merger, for example
  `python merge-exports.py mac-export.json windows-export.json --output combined.json`.
  It creates a new result, checks matching pack/content identities and rejects
  conflicting duplicates. It does not import studies for continued execution.

Results remain separate by OS, app, model and effort. Missing, blocked and failed
attempts remain visible; retries cannot improve the original denominator. The
report does not pool a win rate or infer savings from unavailable usage data.
One owner's preference is valuable personal evidence, not a general-user effect
claim. If B and C are similar on new varied tasks, added OpenSocrates utility
remains unconfirmed. Convenience and multi-turn benefits need their own evidence.

## For maintainers

From the source repository, start with `python tools/evaluation_lab.py`. Optional
`--data`, `--pack`, `--payloads`, `--no-browser` and `--port` select explicit local
paths and launch settings. Build a portable kit with
`python tools/build_evaluation_lab.py --payloads-dir PATH --output office-lab.zip`.
Use the exact published payloads required by the builder; it checks pinned hashes.
No model calls are part of building or starting the lab.

See the [design](evaluation-lab-design.md) and
[implementation contract](evaluation-lab-contract.md) in the source repository
for architecture and acceptance boundaries. Offline tests can establish local
workflow behavior. Actual authenticated Work/Cowork/Antigravity runs on each
Windows/Mac environment remain separate evidence; the kit itself does not qualify
all six cells or demonstrate better answers.
