# Claude Cowork marketplace and hook probe

The Cowork probe separates two questions that repository tests cannot answer:

1. Does a marketplace registered by `claude plugin marketplace add --scope
   user` appear in Cowork without a second installation?
2. If available, does one non-sensitive `UserPromptSubmit` →
   `PostToolUse(Read)` → `Stop` lifecycle reach OpenSocrates and clean its
   artifact?

If the CLI registration is absent in Cowork, the supported Customize UI path
must be tested separately. A passing receipt records only product versions,
macOS/architecture, installation path kind, and categorical observations. It
must not retain prompts, transcripts, credentials, local paths, artifact
content, raw payloads, or selector reasoning.

## 2026-08-11 attempt

Claude Code CLI 2.1.226 confirmed that the `opensocrates` marketplace is
registered in CLI user scope. No path was retained. After the Mac was unlocked,
Computer Use opened Cowork in Claude Desktop 1.26832.0. The shared Customize UI
showed OpenSocrates 1.1.2 from the `opensocrates` marketplace, enabled without a
second install, with one skill and all five declared hook surfaces. This
establishes that the CLI user-scope marketplace registration is visible to the
current Cowork surface.

The installed skill did not become invocable in Cowork: submitting
`/opensocrates` produced the categorical “unknown skill” result. A separate
non-sensitive Cowork task connected the repository folder, completed a Read,
and stopped normally, but no OpenSocrates instruction artifact or grounding
receipt appeared during a bounded live monitor. Hook delivery and cleanup
therefore remain unconfirmed. The supported Claude Code CLI is also still
unauthenticated, so the fresh selector subprocess cannot complete.

The blocker is now `claude_not_authenticated`, rather than `mac_locked`;
Cowork slash-skill availability is an additional unresolved observation. The
support claim remains experimental with no complete live probe receipt. No
prompt, transcript, credential, local path, artifact content, raw payload, or
selector reasoning was retained.

The categorical blocked receipt is
[`docs/evidence/claude-cowork-live-probe-v1.1.2.json`](evidence/claude-cowork-live-probe-v1.1.2.json).
