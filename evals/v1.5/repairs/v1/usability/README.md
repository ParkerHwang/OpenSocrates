# Prospective checkpoint usability retest

This new repair boundary is prepared, not executed. Exactly four planned fresh,
ephemeral `gpt-6-sol` / `medium` CLI sessions: English create/update then fresh
continuation, and the equivalent Korean pair. No resume, stronger subagents,
model substitution, outcome retries, or favorable-result reruns. Each call has
300 seconds. A setup failure stops before further calls; a model/save failure is
counted and the already planned continuation still exposes the failed boundary.
This is a usability retest, not an effect study or release claim.

The operator seeds only enrolled, source-independent accepted project intent via
existing native `seed_memory`; no checkpoint or answer is seeded. Stage 1 sources
have Cedar64/Bay80, both step-free. Stage 2 changes Cedar to40 while preserving
accepted48/step-free/no-booking intent. Stage 1 must create after its first milestone
and update after artifact validation. The fresh continuation receives only its
metadata, guide/schema references, current sources and exact JSON contract. Its
previous plan.json is removed. Neither checker nor expected answers are supplied.

The imported `practical.runner` install/capture/seed/command helpers and
`expanded.harness_v4.profile` are reused without edits. Execution alone calls the
profile helper that copies existing authorized auth into the disposable profile;
selfcheck and preflight never read/copy credentials or create profiles. No raw
model event stream or hidden reasoning is retained. Outputs contain only public
synthetic prompts/messages/commands, native operation/state receipts, artifacts,
usage, hashes and checks. Auth copies are removed in finally; all temporary
profiles are deleted at context exit. Native hooks, native memories, memory import
and multi-agent execution are disabled in config and invocation.

The existing `practical/memory_tool.py` and its full configuration are copied
unchanged. It injects no envelope IDs and repairs no payload. Every agent request
must supply project/workspace/task identities itself. Adapter request/response
ID/status audits count failed calls. Native post-inspection checks the actual saved
task/version/action shape and unchanged accepted intent. The adapter lacks task
and checkpoint-payload audit fields, so ordering, first-milestone meaning, actual
source reads, and absence of extra model calls remain explicit integrator review
items; automated state/artifact success alone is not a final usability pass.

Primary must create and freeze the manifest before outcomes:

- `schema`: `opensocrates.repair-usability-manifest/1`; model/effort above.
- `client`: path, sha256, version; `availability_evidence`: exact current tuple
  availability evidence, without claiming backend echo.
- `limits`: `initial_model_invocations:4`, `per_invocation_seconds:300`.
- `permissions`: sandbox `workspace-write`, approval `never`; hooks,
  native_memories, memory_import, subagents, outcome_retries all false.
- `tasks`, `source_transition`, `artifact_contract`: exactly fixtures.json fields.
- `rubric`: exactly rubric.json. `usage_fields`: input_tokens,
  cached_input_tokens, cache_write_input_tokens, output_tokens,
  reasoning_output_tokens. Missing fields stay null; no billing proof.
- `arm`: archive_path, archive_sha256, package_version, `members` mapping installed
  package-relative paths to sha256; include native runtime, request schema and
  both `skills/opensocrates/references/assistance/checkpoint.{en,ko}.md` guides.
- `hashes`: repo-relative paths/digests for all local Python, README, fixture,
  rubric, four prompt files, imported practical runner/memory adapter, expanded
  harness_v4/runner_v2/harness_v3, practical/checks.py and
  evals/v1.5/native_plugin_runner.py and pilot_runner.py, product schemas/guides and relevant package inputs.
  Record source commit/provenance and package qualification separately.

Do not reuse a historical empty checkpoint template or edit old manifests.
The manifest digest must be recorded externally by primary; passing it explicitly
prevents silent local manifest changes. Execute creates a new exclusive output
root, and every call start is written before launching. An exclusive
`MANIFEST.execution-started.json` sidecar prevents executing the same freeze again
under another output directory. No unfinished-run resume.

```bash
python3 evals/v1.5/repairs/v1/usability/runner.py selfcheck
python3 evals/v1.5/repairs/v1/usability/runner.py preflight --manifest /absolute/frozen-manifest.json --manifest-sha256 PRIMARY_RECORDED_SHA256
python3 evals/v1.5/repairs/v1/usability/runner.py execute --manifest /absolute/frozen-manifest.json --manifest-sha256 PRIMARY_RECORDED_SHA256 --output /absolute/new-results-directory
```

Primary reviews deterministic checks together with public command/operation traces
against rubric.json. Count every failed transport/tool attempt; diagnose failures
without extending the four-session study. Assertions for own actions require
`agent_reported`, and checkpoints remain reported state rather than native proof
that those actions happened. Product guide/schema example execution is covered by
primary's deterministic package gates; this harness does not silently count them
as model usability evidence.
