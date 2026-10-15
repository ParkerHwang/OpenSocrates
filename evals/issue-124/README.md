# Issue #124: rejected native `select` requests

These are public synthetic fixtures and the source-level findings for
[#124](https://github.com/ParkerHwang/OpenSocrates/issues/124). They contain no
user conversations, credentials, screenshots, hidden reasoning or host data.

| File | Use |
| --- | --- |
| `select-faults.json` | One valid `select` envelope for the fictional Tessellate task plus 20 single-field faults. The faults are plausible ways an agent could build the envelope wrongly. `tools/check_decision_points.py` replays them. |
| `appendix-a.ko.txt`, `appendix-a.en.txt` | Fixed unprompted strategy-comparison inputs for live runs. Use them unchanged. |
| `appendix-b.txt` | Mechanical control. The expected output is only the two-row Markdown table. |

## Cause analysis (baseline `227a528`)

Reproduction: a single `DecisionSession` loaded from the canonical bundles.
`catalog` with `locale: ko` succeeded. Then each fixture case was sent as `select`.

| Hypothesis | Evidence | Verdict |
| --- | --- | --- |
| Parser defect: valid input is rejected | The packaged `request.json` and the valid Tessellate envelope both select (`critical-thinking`, `trade-off-analysis`). Every rejected case violates a rule already documented for contributors in `docs/decision-points.md`, or enforced as a closed value. | Rejected |
| The model sent a malformed request, and the guidance allowed it | The installed agent-facing files (decision guide, `request.json`, `features.json`) never state several rules. `context` must be exactly 32 lowercase hexadecimal characters. `decision` must be 1–64 ASCII letters or digits. `classification_confidence` must be `high`, `medium` or `low`. `strength` must be 1..3. At most 16 features are allowed. All five routing keys are required. The guide asks for a "fresh opaque context handle" without a format, so a UUID from `uuidgen` (or any hyphenated decision ID) is rejected. | Confirmed as a guidance gap |
| The error response blocks recovery | All 20 distinct faults returned the identical `{"reason": "invalid_decision_request"}`. The guide says "repair the input", but the response did not say which field to repair. Malformed JSON, such as a shell-quoting error, returned `decision_unavailable`. That label made a repairable input error look like a runtime outage. | Confirmed as a runtime response defect |
| Environment problem | Environment failures appear as launcher failure, `canonical_content_unavailable` or `decision_unavailable`, not as `invalid_decision_request`. The earlier `sandbox_apply` failure was a separate preparation problem. | Not the cause of this response |

The retained evidence does not show which field the two historical requests got
wrong. The cause above is shown only for synthetic inputs. The historical cause
of #124 remains unknown.

## Correction

- `invalid_decision_request` now also returns a closed `field` path, a predefined
  `error` code, a fixed `expected` description, and `repair: correct_field_once`.
  It never echoes submitted values or unknown key names. A rejected request no
  longer resets session state.
- Malformed JSON is reported as `invalid_decision_request` / `request` /
  `invalid_json`. `decision_unavailable` is now reserved for runtime or
  packaged-content faults after the request is accepted.
- `features.json` gains an `envelope` section with every field format.
- The Codex decision guide (all 10 locales, with English and Korean as the
  canonical pair) points to it. The guide also separates five states: input
  error, valid empty selection, native path unavailable, inapplicable candidate,
  and reader guidance sufficient. File fallback after an invalid request is
  permitted only after one correction attempt has failed. Fallback is optional,
  starts from the catalog, and reads the complete procedure for the exact locale
  and revision.

Validation rules, contraindications, prerequisites and method selection are
unchanged. Every fault in the fixture is still rejected.

## Appendix C public-output review (`critical-thinking@5`)

This review is based only on the public answer. It is not evidence that the run
applied the method.

| Required public output | Present in Appendix C | Assessment |
| --- | --- | --- |
| Strongest claim / claim map | A: "stars guarantee repeat use"; C: "host count is the main driver"; B's support | Present |
| Source assessment | "판단 근거는 제시된 가상 사실뿐입니다" (the judgment rests only on the supplied fictional facts). A and C are labelled 미검증 (unverified), not false. B's support is tied to the stated facts. | Sufficient for a stipulated case |
| Material framing or omission | 3/10 is the share of reports, not the abandonment rate. No demand or maintenance-cost data. | Present |
| Inference gap | No repeat-use data for A. Supporting two hosts does not imply that host count drives adoption. Improving B does not show an effect on repeat use. | Present |
| Strongest counterargument | Awareness or host coverage may be the larger barrier | Present (brief) |
| Verdict with evidence labels | B conditionally supported; A and C core claims unverified | Present |
| Flip condition and next check | Bring A forward if promotion is shown to convert into use. Bring C forward if specific host demand and a manageable support cost are shown. Measure installation completion, first response, repeat use and unsupported-host requests. | Present |

The source-assessment requirement is satisfied. The user stipulated the facts
and forbade external lookup. The procedure forbids fabricating source detail.
The answer names the only source (the stipulated case), labels nothing as
verified, and keeps "unverified" separate from "false". No guidance change is
made for this element.

## Live verification status

These live runs were **not performed** in this change. The change was prepared
in a cloud container. The linked computer's shell is a Linux VM without the
Codex CLI. A separate Codex profile would need its own login, and copying the
existing credentials is prohibited. Fill in the table below in a separate test
profile with fixed version, model and settings. Report every run.

| Run | Entry delivery | Reference access | Selection result | Complete canonical delivery | Public-output compliance | Task completion |
| --- | --- | --- | --- | --- | --- | --- |
| A-ko-1 | unknown | unknown | unknown | unknown | unknown | unknown |
| A-ko-2 | unknown | unknown | unknown | unknown | unknown | unknown |
| A-en-1 | unknown | unknown | unknown | unknown | unknown | unknown |
| B-control | unknown | unknown | unknown | n/a | n/a | unknown |

Record the selection result as one of: `selected`, `no_intervention`,
`invalid_decision_request` (with `field`/`error`), `decision_unavailable`, or
not attempted. Do not count a run without a fresh read as an omission when valid
reuse is possible. Keep any diagnostic run with an explicit method-use reminder
separate from these runs.
