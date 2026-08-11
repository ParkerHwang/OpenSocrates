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
registered in CLI user scope. No path was retained. Computer Use could not
inspect the Claude app because the Mac was locked and automatic unlock failed.
Cowork visibility and every hook observation therefore remain false. This does
not establish that CLI registration is shared with Cowork.

The categorical blocked receipt is
[`docs/evidence/claude-cowork-live-probe-v1.1.2.json`](evidence/claude-cowork-live-probe-v1.1.2.json).
