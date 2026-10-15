# Lab v1 implementation contract

Read with [design](evaluation-lab-design.md). Frozen before implementation.
Python 3.12, standard library. Public `LabError(code)` has `.code`; never expose
raw exceptions. `Lab(root, pack, payloads=None)` accepts Paths; `pack` is the pack
directory. `snapshot()` and `action(name, data)` return JSON objects.

## Storage and case pack

Owned data root: marker `.office-lab`, `state.json`, `actors/<opaque-run-id>/`,
`approved/`, `exports/`. Only actor folder is granted to a host; this is logical
input separation, not an OS sandbox. Never grant the whole study/source folder.
No arbitrary user-supplied paths in actions. State lock uses exclusive creation,
atomic state replacement, no automatic stale-lock deletion. Defaults preserve
existing state; create refuses replacement. Source/pack mutations cannot change
an existing study's frozen inputs. Actor source files are copied into study-owned
frozen inputs first. Evaluator fields never go to actor files.

`pack.json` object: `schema="opensocrates.office-pack/1"`, `id`, `version`,
`public_synthetic=true`, `b_instruction={en: string, ko: string}`, `cases=[...]`.
Case fields: `id`, `phase` (`calibration/discovery/confirmation`), `family`,
`title`, `locale`, `prompt`, `deliverable`, `materials` (relative .md path list),
`clarification_reply`, `evaluator_checks` (string list). Eight cases: 2+4+2.
Each case's input text is self-contained except its listed materials; no hidden
answer in prompt. Materials have no external file references or live data.

Payload directory has `manifest.json` with `schema="opensocrates.lab-payloads/1"`,
`version="1.5.3"`, `assets` list of `{name,sha256,host}`. Hosts `claude_cowork`
and `antigravity`; names are exact published `opensocrates-1.5.3-*.zip` basenames.
Manifest's expected hashes are fixed in source from public v1.5.3 receipts;
manifest cannot authorize arbitrary new bytes. Work is derived only from verified
account archive, preserving all skill bytes. No product binary in kit.

`hosts.py`: `prepare_content(actor: Path, host: str, payloads: Path | None) ->
dict[str, Any]`; `setup_guide(host: str, arm: str, actor: Path, payloads: Path |
None) -> dict[str, Any]`. Returned guide has `profile`, `status` (`manual_required`
or `unavailable`), `steps: list[str]`, `links: list[{title,url}]`. Preparation
returns the guide. C missing payload is unavailable, no silent content fallback.
Archive extraction validates containment, member types, byte/file caps and collisions;
only new owned actor folder is mutated, no global app settings or shell commands.

## Engine requests and response shapes

All requests reject unknown fields. IDs validated from stored assignments only.
Actions return current bounded object, not filesystem paths in exported metadata.
Operator responses may contain the known actor path for opening the actual app.

`snapshot`: `{schema, initialized, pack:{id,version,sha256}, cells:[...], phase,
budget, started_count, runs:[...], groups:[...], judgments:[...], warnings:[...]}`.
Before create, runs/groups empty and cells lists all six supported combinations.
Cell object `{id,os,host,requested_model,expected_model,expected_effort}`.
IDs: `macos-work`, `windows-work`, `macos-cowork`, `windows-cowork`,
`macos-antigravity`, `windows-antigravity`. Host values `desktop_work`,
`claude_cowork`, `antigravity`; requested literal model strings remain unchanged.
Expected model enums `gpt-6-luna`, `claude-haiku-5-5`, `gemini-3.8-flash-medium`;
effort `max/medium` (Antigravity medium). Unsupported observed value `unknown`
blocks start. App UI labels are explained to operator, not parsed from transcripts.
Run object `{id,group_id,cell_id,case_id,arm,attempt,status,preflight,started_at,
finished_at}` plus operator-only actor_path/prompt/setup after preparation.
Group `{id,cell_id,case_id,status,judged}`; packet uses first attempts only.

* `create`: `{phase,cells:[cell_id],budget:int,seed?:int}`; budget 1..180.
  Default UI: calibration, current OS + Work, budget6. Engine requires valid
  explicit cell list. Response snapshot. No preparation/model execution implicit.
* `prepare`: `{run_id}` -> `{run,actor_path,prompt,setup,clarification_reply}`.
* `preflight`: `{run_id,observed_model,observed_effort,host_version,
  execution_mode,isolation,environment,opensocrates,model_mapping_confirmed,
  exploratory,pack_approved}` -> `{run,can_start,blockers,warnings}`.
  execution_mode `local/cloud/sync/unknown`; isolation `clear/contaminated/unknown`;
  environment `fresh_os/clean_snapshot/new_user/new_folder/unknown`;
  opensocrates `absent/enabled/unknown`; booleans actual JSON bool. `host_version`
  bounded ASCII version or `unknown`, no account/device identifiers. `clear`
  is explicitly operator-attested. A/B require absent, C enabled. Contamination
  always blocks; unknown isolation only permits explicit exploratory. AG mapping
  requires confirmation. Pack approval includes fixed B/common task boundaries.
* `start`: `{run_id}` -> `{run}`; prepared + eligible preflight only, increments
  durable attempt reservation. One running run at a time per data directory.
* `monitor`: `{run_id}` -> `{exists,bytes,ready,source:"local_outbox",overdue}`.
* `preview`: `{run_id}` -> `{text,approval_token}`; max64KiB UTF8, text only,
  no persisted candidate bytes/digest. Ephemeral token invalid if bytes change.
* `finish`: `{run_id,status,synthetic_approved?:bool,approval_token?:str,
  final_text?:str,intake?:"file"|"manual",clarification_count?:int,
  delivery?:"observed"|"operator_reported"|"unknown",
  application?:"self_reported"|"unknown",tokens?:int|null,elapsed_seconds?:int|null}`.
  Terminal statuses completed/failed/aborted/blocked/timed_out. Completed from
  running requires explicit approval and exact preview token or explicitly
  approved bounded manual text. Finish failed/blocked from prepared/planned also
  allowed with no reservation; never invent invocation. No raw error strings.
* `retry`: `{run_id}` -> `{run}`; terminal only, next attempt, no implicit start.
* `packet`: `{group_id}` -> `{group_id,title,prompt,deliverable,materials:[{name,text}],
  answers:[{alias,text}],judged,judgment?:object,partial_blinding:true}`.
  All three first attempts completed or `group_incomplete`; never substitute retry.
  Stable randomized aliases, no arm/cell/model/setup/actor path in this response.
* `judge`: `{group_id,choice,first_reaction?:str,confidence,recognition,
  reproduced_experience,synthetic_approved,edit?:str}` -> `{judgment}`.
  choice actual alias or `tie/all_unusable`; confidence low/medium/high;
  recognition unknown/guessed/known; reproduced_experience yes/no/uncertain.
  Free reaction max4000chars; optional approved edit max64KiB. Once stored cannot
  overwrite. Empty/cannot-explain valid; first reaction precedes reveal/AI analysis.
* `reveal`: `{group_id}` -> `{mapping,evaluator_checks,judgment}`; requires judged.
* `freeze`: `{criteria,discovery_reference,synthetic_approved}` -> `{frozen:true}`.
  Required before confirmation prepares/starts. Criteria immutable once frozen.
* `export`: `{}` -> `{filename,report,export}`; fixed owned exports directory.
  `export` object schema `opensocrates.office-export/1`, source study ID, frozen
  identities, closed metadata, first judgments and approved answers only. Report
  retains missing/failed counts per cell; no pooled score. Export may include
  explicit mapping only for judged groups, never unrevealed group mappings.

Read-only merger accepts exported JSON files, validates closed schema/size,
requires matching pack hash/contentversion, deduplicates same source study/run
records exactly, rejects conflicts, preserves IDs/cell denominators. It does not
resume imported studies, unpack archives or silently overwrite reports.

## Ownership and validation

Core worker: evaluation/__init__.py, engine.py, storage.py, model.py (can add
internal modules except hosts.py/server.py/assets/); core behavioral tests in
`tools/check_evaluation_lab.py`. Server/UI worker: server.py and assets only.
Payload/packaging worker: hosts.py, `tools/evaluation_lab.py`,
`tools/build_evaluation_lab.py`, `tools/evaluation-lab/`, payload manifest; read-only
merge utility there too. Content worker: evals/office-work-v1/ only. Docs worker:
user guides EN/KO, reusable case extension instructions only. Root owns design,
contract, review record, repo registration/Makefile/CI and final integration.
All workers defer tests/lint/review until stable integrated final state.
