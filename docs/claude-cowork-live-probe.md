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

## 2026-08-11 result

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

Because no Cowork-native OpenSocrates plugin could be installed, the declared
UserPromptSubmit, PostToolUse(Read), and Stop hooks were not active in the
Cowork task. No instruction artifact or grounding receipt was created, so hook
delivery and cleanup cannot be credited. The exact blocker is now
`cowork_plugin_archive_exceeds_upload_limits`; the validated support level is
the standalone skill path only. No prompt, transcript, credential, local path,
artifact content, raw payload, selector reasoning, or user identity was
retained.

The categorical blocked receipt is
[`docs/evidence/claude-cowork-live-probe-v1.1.2.json`](evidence/claude-cowork-live-probe-v1.1.2.json).
