# Claude Chat skills ZIP upload probe

The upload probe targets the exact release archive
`opensocrates-1.1.2-claude-chat-skills.zip`. Archive inspection and live UI
acceptance are separate claims.

The inspected archive has 52 files and SHA-256
`8e5ca35b33df7721b42727128fd3ab5ae35d887d0419d2c7163c060adecdb07c`.
It contains one visible `skills/opensocrates/SKILL.md`, one internal catalog,
48 internal method references, the plugin manifest, and LICENSE. It contains
no hooks, launcher, native runtime, commands directory, or credential-shaped
file.

A passing live receipt must upload that exact hash through the supported
Claude customization/plugin UI, observe one `/opensocrates` entry, and verify
catalog routing plus representative internal method loading. The receipt may
store product/UI versions, the archive hash, counts, and booleans only. It must
not retain prompts, conversations, credentials, local paths, uploaded file
content, or raw UI data.

## 2026-08-11 attempt

The archive inspection passed. Computer Use could not access the Claude upload
UI because the Mac was locked and automatic unlock failed. Upload acceptance
and skill loading remain unobserved, so the support claim stays “skills-only;
upload path unvalidated.”

The categorical blocked receipt is
[`docs/evidence/claude-chat-upload-probe-v1.1.2.json`](evidence/claude-chat-upload-probe-v1.1.2.json).
