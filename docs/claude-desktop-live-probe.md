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

## 2026-08-11 result

After the Mac was unlocked, Computer Use opened Claude Desktop 1.26832.0 and a
real local Claude Code session on macOS 26.5.2 arm64. The Customize UI showed
the user-marketplace OpenSocrates 1.1.2 plugin enabled, one skill, and all five
declared hook surfaces, including UserPromptSubmit, PostToolUse(Read), and Stop.

After authenticating the supported Claude Code CLI, one fresh non-sensitive,
read-only local session completed. The UI recorded two Read calls: the authored
OpenSocrates instruction artifact and the repository README. A bounded,
content-free monitor observed the owner-only instruction artifact first, then
the authenticated grounding receipt. Both disappeared after the completed Stop
callback. Content-free session metadata separately recorded successful
SessionStart and Stop callbacks, while the created artifact, receipt, and final
cleanup establish delivery of the OpenSocrates UserPromptSubmit,
PostToolUse(Read), and Stop lifecycle.

The result passes every acceptance criterion and upgrades Claude Code desktop
to “locally validated” on this environment. No prompt, transcript, credential,
local path, artifact content, raw payload, selector reasoning, or user identity
was retained.

The categorical passing receipt is
[`docs/evidence/claude-desktop-live-probe-v1.1.2.json`](evidence/claude-desktop-live-probe-v1.1.2.json).
