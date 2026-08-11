# Claude Code desktop live probe

The v1.1.2 desktop probe must observe one real, non-sensitive
`UserPromptSubmit` → `PostToolUse(Read)` → `Stop` lifecycle. A passing receipt
requires all of these categorical observations:

1. the managed OpenSocrates registration is visible in Claude Code desktop;
2. UserPromptSubmit creates an authored instruction artifact;
3. a complete Read callback creates its authenticated grounding receipt;
4. Stop reaches OpenSocrates and removes the artifact turn tree.

Record only desktop/plugin versions, macOS/architecture, registration path
kind, booleans, and a fixed blocker if needed. Do not record prompts,
transcripts, credentials, local paths, artifact content, raw hook payloads, or
selector reasoning.

## 2026-08-11 attempt

Computer Use attempted to inspect the real Claude app on macOS 26.5.2 arm64.
The automation service reported that the Mac was locked and automatic unlock
failed. The app UI and desktop version were not accessible. No lifecycle event
or cleanup was observed, so the support level remains “implemented; no live
probe receipt.”

The categorical blocked receipt is
[`docs/evidence/claude-desktop-live-probe-v1.1.2.json`](evidence/claude-desktop-live-probe-v1.1.2.json).
