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

After the Mac was unlocked, Computer Use opened Claude Desktop 1.26832.0 and a
real local Claude Code session on macOS 26.5.2 arm64. The Customize UI showed
the user-marketplace OpenSocrates 1.1.2 plugin enabled, one skill, and all five
declared hook surfaces, including UserPromptSubmit, PostToolUse(Read), and Stop.

One non-sensitive, read-only task completed and the UI recorded a Read tool
call. Content-free session metadata also recorded an error-free packaged
OpenSocrates launcher invocation in the Stop hook summary, so Stop delivery is
observed. However, UserPromptSubmit did not produce an instruction artifact,
the Read callback did not produce a grounding receipt, and no artifact existed
after Stop. The supported Claude Code CLI remains unauthenticated, so the
selector cannot complete its fresh subprocess call. UserPromptSubmit and
PostToolUse(Read) delivery therefore remain unconfirmed, and cleanup cannot be
credited without first observing artifact creation.

The blocker is now `claude_not_authenticated`, rather than `mac_locked`. The
support level remains “implemented; no complete live probe receipt.” No prompt,
transcript, credential, local path, artifact content, raw payload, or selector
reasoning was retained.

The categorical blocked receipt is
[`docs/evidence/claude-desktop-live-probe-v1.1.2.json`](evidence/claude-desktop-live-probe-v1.1.2.json).
