# Claude hook payload receipts

The Claude adapter reuses the Codex native parser on purpose. That reuse is only
safe while the live Claude Code envelope still agrees with the shared mapping,
and repository or schema documentation cannot establish that. This document
records what a supported Claude Code runtime actually sends, how the sanitized
fixtures were produced, and which differences from Codex are intentional.

Scope covered here is the v1.1.2 hook lifecycle: `SessionStart`,
`UserPromptSubmit`, `PostToolUse`, `Stop`, and `SessionEnd`. `PostToolUse` joined
the lifecycle in v1.1.2 with the grounding read receipt, so it is verified with
the same standard as the four events named in the original scope.

- Captured host: Claude Code CLI 2.1.226 (macOS, `darwin/arm64`).
- Captured on: 2026-08-11.
- Fixtures: `src/opensocrates/hosts/contracts/fixtures/claude/`.
- Checks: `CLAUDE-11-runtime-payload-receipts` and
  `CLAUDE-12-runtime-receipt-lifecycle-isolation` in `tools/check_claude.py`,
  run by `make smoke`.

## Observed fields

Each row is the complete top-level field set of one receipt, exactly as the
runtime emitted it.

| Event | Observed top-level fields |
| --- | --- |
| `SessionStart` | `cwd`, `hook_event_name`, `session_id`, `source`, `transcript_path` |
| `UserPromptSubmit` | `cwd`, `hook_event_name`, `permission_mode`, `prompt`, `prompt_id`, `session_id`, `transcript_path` |
| `PostToolUse` (`Read`) | `cwd`, `duration_ms`, `effort`, `hook_event_name`, `permission_mode`, `prompt_id`, `session_id`, `tool_input`, `tool_name`, `tool_response`, `tool_use_id`, `transcript_path` |
| `Stop` | `background_tasks`, `cwd`, `effort`, `hook_event_name`, `last_assistant_message`, `permission_mode`, `prompt_id`, `session_crons`, `session_id`, `stop_hook_active`, `transcript_path` |
| `SessionEnd` | `cwd`, `hook_event_name`, `prompt_id`, `reason`, `session_id`, `transcript_path` |

## Intentional differences from the Codex mapping

- **Turn identity is `prompt_id`, not `turn_id`.** No captured Claude receipt
  carries `turn_id`. The shared parser projects `prompt_id` into `turn_id` for
  Claude hosts only, and the fixtures fail if that projection is removed. Turn
  identity is what isolates one turn's instruction artifact and grounding
  receipt from the next, so this is the single most load-bearing difference.
- **`prompt_id` is present on far more than the prompt event.** It appears on
  `PostToolUse`, `Stop`, and `SessionEnd` as well, which is what lets the
  grounding receipt and the Stop gate be scoped to the current turn rather than
  to the session.
- **A resumed session keeps its `session_id`.** The second captured turn starts
  with a `SessionStart` carrying `source: "resume"` and the first run's
  `session_id`, but no `prompt_id`. The following `UserPromptSubmit` supplies a
  new `prompt_id`. Session-scoped cleanup must therefore not assume one session
  equals one turn.
- **No version marker.** No captured receipt carries `version`, `host_version`,
  or `model`, so `native_version` resolves to `unknown` on every real Claude
  event. Nothing may treat that value as evidence of a host capability.
- **No `permission_mode` on `SessionStart`.** It appears on every later event in
  the turn but not on the session-start receipt.
- **`last_assistant_message` is the final assistant text.** It is read
  transiently for the Stop decision and the grounding audit line, and is never
  retained or projected.
- **The `Read` response envelope is not a stable contract.** The captured shape
  is `tool_response.file.content` alongside `filePath`, `numLines`, `startLine`,
  and `totalLines`. The terminator search stays shape-agnostic on purpose, so a
  host that wraps the body differently does not cost a compliant turn a repair
  pass.

### Adapter change made from these receipts

`effort` (on `PostToolUse` and `Stop`) and `background_tasks` and
`session_crons` (on `Stop`) were absent from the parser's known-field sets, so
an ordinary Claude payload raised `native_unknown_field_ignored`. They are now
listed. The parser still never reads them; the change keeps that diagnostic
meaning "this host sent something we have never seen" instead of firing on every
turn. No parsing, projection, or gating behavior changed.

## Sanitization

No fixture contains prompt, transcript, path, credential, or user-identifying
content. Field names, value types, and container shapes are preserved exactly as
captured; only values were replaced, with fixed synthetic markers:

| Field | Committed value |
| --- | --- |
| `session_id` | a fixed synthetic UUID |
| `prompt_id` | a fixed synthetic UUID per turn |
| `transcript_path` | `/synthetic/transcript.jsonl` |
| `cwd` | `/synthetic/workspace` |
| `prompt` | `<synthetic-prompt>` |
| `last_assistant_message` | `<synthetic-final-message>` |
| `tool_use_id` | `toolu-synthetic-1` / `toolu-synthetic-2` |
| `file_path`, `filePath` | `/synthetic/workspace/instruction-artifact.md` |
| `content` | `<synthetic-read-body>` |

`CLAUDE-11-runtime-payload-receipts` walks every native payload and refuses any
string outside a closed vocabulary, so a future re-capture cannot commit real
payload content by accident. It also asserts that each fixture's field set
still matches the `capture.observed_field_names` recorded with it.

## Re-capturing

1. Create a scratch workspace with a `.claude/settings.json` that registers a
   command hook on `SessionStart`, `UserPromptSubmit`, `PostToolUse` (matcher
   `Read`), `Stop`, and `SessionEnd`. The hook appends its stdin verbatim to one
   capture file.
2. Run one prompt that triggers a `Read`, then a second prompt resumed into the
   same session, so two consecutive turns of one session are captured.
3. Sanitize with the table above, refresh `capture.observed_field_names` and
   `host_version`, and run `make smoke`.

The `PostToolUse` and `Stop` receipts in this set were produced by pointing the
runtime at a local stub of the model endpoint, because the capture host could
not reach a live model. The hook envelope is authored by the runtime either way;
the stub only decided that the turn would call `Read` and then finish. The
values that came from the stub rather than the runtime — `tool_use_id` and the
read body — are recorded as such in the fixture's `capture.note` and are
replaced by synthetic markers.
