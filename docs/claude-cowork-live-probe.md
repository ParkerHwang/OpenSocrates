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

## 2026-08-11 results

Claude Code CLI 2.1.226 confirmed that the `opensocrates` marketplace is
registered in CLI user scope. No path was retained. After authenticating that
CLI, Computer Use opened a fresh Cowork task in Claude Desktop 1.26832.0. The
true Cowork Customize plugin inventory did not contain OpenSocrates: CLI
user-marketplace registration is not a Cowork-native plugin installation.

A separately uploaded OpenSocrates user skill was present. In a fresh session,
`/opensocrates` was recognized, loaded the skill, applied the requested method,
completed a repository Read, and emitted the public grounding audit line. The
earlier unknown-skill result was therefore a stale-session observation, not a
persistent product limitation.

The supported Cowork plugin upload path was tested with the exact published
v1.1.2 Claude plugin archive. The 134,354,629-byte ZIP expands to 341,004,558
bytes and was rejected with the categorical error `Zip file uncompressed size
exceeds 200MB`. [Anthropic's documented upload limit](https://support.claude.com/en/articles/13837433-manage-plugins-for-your-organization)
is also 50 MB compressed.
Repository sync was tested separately and rejected because this repository does
not contain `.claude-plugin/marketplace.json`.

That result remains the historical v1.1.2 receipt. Pull request #61 then built a
clean Claude-specific v1.1.3 candidate without the Codex SDK or CLI. The first
13.5 MB candidate exposed a second Cowork constraint: its PyInstaller runtime
contained `base_library.zip`, and Cowork rejected nested ZIP files. Rebuilding
the Claude runtime in no-archive mode removed that nested file and added a
release gate that rejects any future nested ZIP.

The corrected candidate was 13,827,377 bytes compressed and 34,093,317 bytes
uncompressed, with zero Codex runtime entries and zero nested ZIP entries.
Cowork accepted it through Customize's local plugin upload and replaced the
existing OpenSocrates installation. After reopening Customize, Cowork showed
OpenSocrates 1.1.3 enabled and displayed the UserPromptSubmit,
PostToolUse(Read), Stop, SessionStart, and SessionEnd declarations.

Two local task turns selected a method, read the injected grounding artifact
and repository README, and completed with the expected public grounding line.
During the second task, a bounded wait after Read exposed exactly one
instruction artifact and one matching HMAC-authenticated grounding receipt.
After Stop, the artifact, receipt, and all remaining files in that private
temporary tree were zero. The selector aggregate increased by two `selected`
outcomes and no failure outcome.

This validates Cowork native hook delivery for the pull-request candidate.
Version 1.1.4 is the first release to carry the reviewed runtime shape. This
does not claim Cowork marketplace availability or repository sync; installation
still uses the local plugin upload path. No prompt, transcript, credential,
local path, artifact content, raw payload, selector reasoning, or user identity
was retained.

The categorical receipts are the historical
[`v1.1.2 blocked probe`](evidence/claude-cowork-live-probe-v1.1.2.json) and the
[`v1.1.3 candidate pass`](evidence/claude-cowork-live-probe-v1.1.3.json).
