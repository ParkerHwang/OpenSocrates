# Claude structured-output reliability matrix

OpenSocrates asks Claude Code for JSON-schema-constrained output with one model
turn. This opt-in matrix measures that exact production boundary without
storing model content:

```bash
OPENSOCRATES_CLAUDE_RELIABILITY=1 make claude-reliability-check
```

The default row uses the host-configured default model because the production
selector does not override it. Named rows are included only when the operator
supplies exact model identifiers:

```bash
OPENSOCRATES_CLAUDE_RELIABILITY=1 \
OPENSOCRATES_CLAUDE_RELIABILITY_MODELS=MODEL_ID_FROM_CLAUDE_DOCUMENTATION \
make claude-reliability-check
```

Each observed row requires 20–50 attempts; 20 is the default. At least 95% must
return a valid complete structured-output envelope, so the default 20-attempt
row requires 19 successes. The aggregate report counts only the selector's
fixed outcomes. It never stores fixture text, individual candidates, stdout,
stderr, credentials, transcripts, environment values, or reasoning.

A row meeting the threshold is marked `supported: true` for that exact CLI
version and model selector only. A row below threshold is not supported. The
runtime fallback remains unchanged: timeout, nonzero exit, malformed output,
or turn-limit/schema failure produces a fixed content-free diagnostic and
fails open with no intervention.

## Current matrix

On 2026-08-11 an authenticated Claude Code 2.1.226 run observed the production
`host-default` row. All 20 attempts returned valid structured output, exceeding
the required 19 successes. Every fixed failure outcome was zero, so this exact
CLI/default-model selector is marked `supported: true` at 100% observed validity.
No named model row was run or claimed.

The committed aggregate receipt is
[`docs/evidence/claude-structured-output-matrix-v1.1.2.json`](evidence/claude-structured-output-matrix-v1.1.2.json).
It contains no prompt, raw output, credential, candidate, transcript, or
reasoning. The production fail-open behavior remains unchanged.

The runner requires Claude Code 2.1.205 or later, matching the installer. That
minimum remains unchanged until an authenticated matrix provides contrary
evidence. See the [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)
for the model and structured-output flags.
