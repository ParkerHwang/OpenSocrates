# Reuse the lab with another case pack

[한국어](evaluation-lab-casepacks.ko.md) · [Operator guide](evaluation-lab.md)

A case pack is an authored set of public, fictional office tasks. It lets a new
study reuse setup, final-answer collection and human review without carrying over
old answers or changing conditions mid-comparison. This version does not import
private work folders, conversations, screenshots or real client records.

## Decide what the next study needs

Write the practical question first: for example, “Can I send this update without
misrepresenting the change or damaging the relationship?” Include the situation,
audience, intended message, useful references and competing constraints. Do not
reduce the task to polished sentences if the desired benefit concerns all of
these together.

Keep the first two tasks for checking the procedure, then use varied discovery
tasks to learn what matters to the human reviewer. Include a simple task that
can expose unnecessary elaboration. Reserve separate confirmation examples for
after the human-approved criteria are frozen. The supplied 2 + 4 + 2 structure
is a starting sample, not a statistical sample-size recommendation. If the owner
has read or helped design a confirmation example, record that limitation; a
different filename does not make a case genuinely unseen.

Use one clear task and the same materials for A, B and C. Put common length or
format needs in the ordinary prompt. The fixed B instruction is common across
tasks and is approved before outputs; do not tune it to an individual case or
weaken it to favor C. Do not give C a method name or a more helpful context brief.
The current study compares fixed inputs. A scripted follow-up or natural ongoing
conversation needs a separate study design.

## Author the files

Make a new pack directory by copying `evals/office-work-v1/` from the source
repository. Give it a distinct `id` or new `version`. Keep `pack.json` and the
listed Markdown materials together. Use UTF-8 and relative material paths within
the pack. Do not use parent paths, links to external files, symlinks, live web
sources or executable files.

The pack contract is:

| Field | Meaning |
| --- | --- |
| `schema` | Exactly `opensocrates.office-pack/1`. |
| `id`, `version` | Public stable identifiers for this authored pack. |
| `public_synthetic` | Exactly `true`; an authoring declaration, not automatic anonymization. |
| `b_instruction.en`, `.ko` | Semantically aligned fixed short B instruction. |
| `cases` | Case records, with unique IDs and phases. |

Each case contains:

| Field | What to write |
| --- | --- |
| `id`, `family`, `title` | Stable ID, office-task family and human-readable title. |
| `phase` | `calibration`, `discovery` or `confirmation`. |
| `locale` | The task language; the initial pack uses `ko`. |
| `prompt` | The shared ordinary request with enough context to act. |
| `deliverable` | The final deliverable boundary, defined before generation. |
| `materials` | Relative `.md` file paths containing the same supplied evidence for all conditions. |
| `clarification_reply` | A fixed reply card if an unsolicited question occurs. |
| `evaluator_checks` | Private-to-evaluator factual/reference guardrails shown after the first judgment. |

Write all names, events, amounts and references as explicitly fictional. Avoid
real addresses, accounts, correspondence or proprietary details, even if partly
redacted. Materials should stand alone, including any prior-context brief that
the task needs. Keep language versions semantically aligned when adding bilingual
content. Do not place a preferred answer, scoring rubric or condition-specific
instruction inside actor materials.

Factual checks should identify concrete constraints: an update not yet approved,
a conflicting date, an unsupported claim, or a reference that concerns another
audience. They are guardrails after the practical choice, not an answer key that
forces a particular tone or replaces the reviewer's judgment.

## Freeze before running

Review the entire pack for plausible tasks, public fictional content, matched
inputs and the fixed B instruction before collecting any answers. Start a new
data directory with the new pack, for example:

```text
python tools/evaluation_lab.py --pack PATH_TO_PACK --data PATH_TO_NEW_STUDY
```

In an extracted portable kit, use `python start-lab.py --pack PATH_TO_PACK
--data PATH_TO_NEW_STUDY` instead. Keep the authored pack directory available;
the lab copies its frozen inputs into the new study. The standard ZIP builder
ships the initial pack, so an alternate pack uses this explicit launch option.

The lab freezes the pack and assignment identities for that study. Editing the
original pack later must not alter an existing study. Give changed content a new
version and a fresh study rather than replacing a failed case or modifying an
instruction after seeing the result. A scheduling seed changes ordering only;
it does not control the model's randomness.

Before confirmation, freeze the human-approved criteria and identify the prior
discovery study. This records what the human learned before confirmation tasks
run. It does not by itself prove those examples were unseen. Keep first-attempt
outcomes, failed attempts, recognition and exploratory-environment declarations
in the report. Export identities must match before the read-only merger can
combine independently run environments.

## What to change after a small pilot

Ask the human first whether the comparison reproduced the difference they usually
feel. If not, record what situation, context or interaction was missing and
change the next pack accordingly. A short reaction or a later human edit can
guide revision without forcing a premature scoring system. Preserve the original
pilot and label the next version as a revised study.

If the comparison does reproduce useful differences, expand task coverage before
claiming broad effect. If B and C remain similar on new varied cases, added
framework utility is unconfirmed for those settings. Do not rename the outcome
as a convenience benefit without a separate observation of setup burden or
repeatability. Each OS/app/model combination and each human population needs
evidence appropriate to the claim.
