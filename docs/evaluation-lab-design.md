# Reusable office evaluation lab: implementation design

Status: reviewed design; corrections recorded in [review](evaluation-lab-review.md),
2026-10-15. Tracking: GitHub issue #134. Base: main
`d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`. No actor calls or effect results.

## Need and evidence

The owner reports that OpenSocrates improves office answers as a whole: intended
message, tone, situation, content selection, structure and references together.
This is a personal experience report, not a reproduced or general quality claim.
The scoped need is to try comparable work without repeatedly assembling test
environments, and express practical preference before AI supplies explanations.
The lab must not require the owner to invent all cases or articulate a rubric first.

Three considered concepts: a copy/paste workbook (easy but poor resumption and
provenance); a fully automated CLI/API benchmark (repeatable but wrong requested
surfaces and privacy/spending risks); a local guided lab with manually operated
real apps (chosen: repeatable preparation, bounded observation and human judgment).

The initial prototype question is whether two authored office tasks reproduce the
owner's meaningful differences and whether setup/review is easy. Participant:
the owner, also operator, with partial blinding only. Exposure: public synthetic
fixtures and reviewed final deliverables; no real recipients or production data.
If the owner says the comparison misses their normal experience, revise the case
pack or add a separately designed multi-turn study before expanding or claiming
effect. Completion or consultant agreement is not evidence of benefit.

## Product and evidence scope

Six independent cells: macOS/Windows × desktop Work, Claude Cowork, standalone
Antigravity. Preserve requested strings `gpt-6-luna max`, `haiku-5.5-medium`,
`gemini-3.8-flash-mid`. Observe actual UI model and effort separately. The last
maps to documented Gemini 3.8 Flash Medium only after explicit operator mapping
confirmation. Never substitute another model, host, or CLI. Record host version,
OS, architecture and actual execution mode (local/cloud/sync/unknown). Mac/Windows
clients do not establish native OS inference, particularly for current Cowork.

Condition A: normal task. B: the same task plus a fixed strong short instruction,
identical across tasks. C: the same normal task with pinned full OpenSocrates
content installed through that surface's documented UI/workspace integration.
No per-case method hint. Cowork uses its account skill; Antigravity uses only
workspace rules/skills. Work uses an explicitly experimental content-only plugin
adapter with complete unchanged v1.5.3 account skill content, no command hooks.
It is a new transport under test, not qualified Codex-native behavior. Missing
supported import or discovery remains blocked/unknown, never replaced by CLI.

New folders do not disable account/global instructions, plugins, skills, memory,
connectors or parent-workspace rules. Each trial requires an independent new
conversation and operator preflight of these influences. Clean OS/VM snapshots
are recommended for strong isolation; self-attestation is labeled operator
attestation, not automatically observed clean-machine qualification. Known
contamination blocks starting. Unknown isolation permits preparation only until
operator resolves it or explicitly chooses an exploratory run. Exploratory
evidence cannot silently become a clean comparison. Do not reset global settings,
copy login state, disable unrelated plugins or remove user files automatically.

## Architecture and contracts

Python 3.12 or newer, standard library only; repository development stays on the
locked Python 3.12 toolchain. Reusable runtime under
`src/opensocrates/evaluation/`, portable launch/build tools under
`tools/evaluation-lab/`, pack under `evals/office-work-v1/`, EN/KO user guides.
No runtime dependency on uv, npm, API keys or provider command-line clients.
Mac `.command` and Windows `.cmd` launch the local browser UI, diagnose a missing
Python prerequisite and link the official installer; no execution-policy bypass
or privileged automatic installation. A source build produces a portable ZIP
containing lab code/assets, synthetic cases, guides and pinned content archives.
No production release version bump or reasoning-content change.

`Lab(root: Path, pack: Path, payloads: Path | None = None)` owns a marked dedicated
data directory. Core public calls: `snapshot() -> dict[str, Any]` and
`action(name: str, data: dict[str, Any]) -> dict[str, Any]`. All mutation validates
closed input fields and uses a lock plus atomic writes. Errors are closed public
codes without raw paths, exception text or submitted content. Source code must
remain compatible with repository strict typing, lint and import contracts.

Actions (server delegates, does not reimplement study logic):

* `create`: phase (`calibration`, `discovery`, `confirmation`), cells, budget,
  optional scheduling seed. Default calibration: two cases, three arms, one cell,
  six planned runs, zero model calls. All six cells are available independently;
  explicitly selecting all yields 36 planned calibration runs.
* `prepare`: run ID. Creates a fresh opaque actor folder with only this task's
  public materials, prompt and empty outbox, plus C content when applicable.
  No rubric, other answers, arm ledger, study root or evaluator files in it.
* `preflight`: run ID, observed model/effort/host version, execution mode,
  isolation status, clean-environment attestation, plugin state and mapping
  confirmation. Explicit enum fields; no account IDs, free error text or paths.
* `start`: run ID. Durable reservation before the operator clicks the host Run.
  Budget counts attempts, including later failures. No automatic actor launch.
* `monitor`: run ID. Reads only owned `out/final.md` existence/size/readiness;
  metadata observed here is local outbox metadata, not host/model completion.
* `preview`: run ID. Bounded UTF-8 final text returned in memory for approval;
  no persisted candidate or rejected-content hash. Reject links/reparse paths.
  An ephemeral approval token binds the exact preview bytes; changed files or a
  restarted lab require a new preview. Finish cannot approve unseen replacement.
* `finish`: run ID, terminal status, synthetic-only approval, optional allowed
  aggregate usage and bounded evidence enums. Completed requires approved final
  text; no footer/agent claim is proof of application. Failed/aborted/blocked/
  timed_out retain denominator and timestamps. Never overwrite original attempt.
* `retry`: terminal run ID. New attempt ID and independent folder, subject to
  remaining budget. Original remains visible. Retry never starts automatically.
  Primary comparison always uses first assigned attempts; retries are diagnostic
  and cannot replace an unsuccessful or less preferred answer in that comparison.
* `packet`: case/cell group ID. Answers labeled with randomized opaque aliases;
  no arm/run/model/install metadata. Preserve exact deliverable text and structure,
  including any identity-revealing footer; record recognition, don't rewrite it.
* `judge`: group ID, choice (alias/tie/all_unusable), free first reaction (optional,
  synthetic-only approval), confidence, recognition, reproduced-experience enum,
  optional approved final edit. Lock the first judgment immutably before reveal.
* `reveal`: group ID. Available only after judgment; disclose mapping and private
  evaluator fact checks. No AI judge or automatic explanation before human input.
* `freeze`: human-confirmed criteria text, prior discovery reference. Required
  for confirmation. Freeze prompt/pack/content/model assignments before starting.
* `export`: explicit local export of allowlisted metadata, reviewed final texts,
  locked judgments and per-cell descriptive report. No network/public upload.
  A separate read-only merge command validates exported schema and exact study/
  pack/version identities, rejects conflicting duplicate attempts, retains source
  study IDs and renders six cells separately. No arbitrary ZIP extraction/import.

The server binds `127.0.0.1` on an OS-assigned port, checks Host and Origin,
uses a per-launch token and strict JSON size limits. No arbitrary file/path APIs,
remote scripts, shell execution, Markdown HTML execution, request/body logging or
raw exception output. UI polls only while open. Shutdown/resume preserves ledger.
Outbox arrivals never start another run or approve/import content automatically.

## Case-pack format and workflow

`pack.json`: schema `opensocrates.office-pack/1`, id/version, `public_synthetic:
true`, fixed B instruction EN/KO, and cases. Each case has id, phase, family,
title, locale (`ko` initially), prompt, deliverable boundary, materials (relative
`.md` files), and evaluator-only checks. All authoring content is fictional and
safe to share. Pack changes produce a new hash/version; immutable study snapshots
bind their copies and assignments. No arbitrary real-work folder import.

Author two procedure-calibration cases, four diverse discovery cases (including
a simple negative control), and two separate confirmation examples. Cover
relationship/tone, conflicting updates, synthesis/decision, reference relevance,
audience changes and simple work. Existing workshop fixtures may inspire discovery
but cannot be labeled fresh held-out evidence. Keep evaluator guidance outside
actor workspaces. Confirmation criteria freeze precedes exposing confirmation
cases. The same scheduling seed affects order only, not model randomness.

Operator flow: choose this machine/cell → prepare → use displayed native-app
setup checklist and verified content files → confirm model and inheritance →
start recording → run copied prompt in fresh actual app work → view local file
arrival → preview/approve final synthetic artifact → repeat remaining conditions.
Manual paste/save into that exact outbox is a fallback if the app cannot write
local files; mark manual intake, not an automatic export capability.
Before the first start, approve the pack as a plausible public synthetic office
sample and its common fixed B instruction. No condition outputs are required for
this approval. Each case includes a fixed reply card for an unsolicited question;
record clarification count, not the exchanged text. An optional scripted follow-up
pack is a separate study, not mixed with fixed-input primary comparisons.

Reviewer flow: compare whole answers → choose practical use/tie/all unusable →
optional free reaction, confidence and recognition → save first judgment →
reveal condition/fact guardrails → optional human edit and later analysis.
"Cannot explain" is valid. Ask whether this reproduced the normally felt
difference and what was missing, without forcing dimension scores first.
The same operator knows condition assignments; the UI reduces cues but is not
double blind, cryptographic concealment or independent evaluation.
Recommend reviewing a completed batch later, rather than immediately after each
run. Alias display is frozen per group, not reshuffled each time a page loads.

Summaries retain unattempted/blocked/failed runs, retries and incomplete groups.
Report separately by host/model/settings/OS; no pooled win rate, causal claim,
token/cost savings from missing metrics, or general-user conclusion from one owner.
B≈C on new diverse tasks means additional framework utility is unconfirmed.
Convenience, repeatability and multi-turn collaboration require their own evidence.

## Privacy, collection and acceptance

No capture of private prompts/transcripts, global host logs, tool arguments,
screenshots, credentials or hidden reasoning. Do not enable provider OTel by
default: currently it can include sensitive fields and has account/host limits.
MVP monitoring is dedicated-outbox observation plus explicit operator metadata;
native hook observation is deferred, not a promised universal capability.
Never retain rejected input bytes or fingerprints. Human-approved synthetic
final outputs and comments remain local until the owner explicitly exports.
Provider-side retention is outside this lab's control.

Acceptance: repeatable Mac/Windows launchers; valid six-cell exact-model plan;
safe marked storage and resume; immutable source/fixture identities; isolated
actor files; supported content preparation or explicit unavailable; model mismatch
blocks start; unknown-versus-attested evidence visible; attempt cap/retries;
bounded final-only monitor/intake; locked first human judgment before reveal;
per-cell report and allowlist export; reusable pack extension guide. Test synthetic
engine/server/package scenarios after integration. Do not claim real Windows or
authenticated GUI qualification until actually run. Deliver prepared kit even
when those live tests remain for the owner, with missing evidence explicit.

## Review and follow-up

Before runtime implementation, obtain bounded plan review and actual Claude/Gemini
consultation. Record decisions and unresolved limits, not raw conversations.
After stable integration run repository checks and independent code, security and
acceptance review; repair defects then rerun affected checks. The owner operates
and makes practical judgments; Codex authors cases, prepares/isolation-checks
inputs, collects allowed artifacts, reports evidence and proposes revised cases.

Source review: official [Work plugins](https://learn.chatgpt.com/docs/plugins),
[Work models](https://learn.chatgpt.com/docs/models),
[Cowork architecture](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview),
[Claude plugins](https://support.claude.com/en/articles/13837440-use-plugins-in-claude),
[Claude effort](https://support.claude.com/en/articles/8664678-change-the-model-effort-and-thinking-settings),
[Antigravity rules](https://www.antigravity.google/docs/rules/),
[Antigravity models](https://www.antigravity.google/docs/models/),
[Antigravity hooks](https://www.antigravity.google/docs/hooks/).
