# Claude Chat skills ZIP upload probe

The upload probe targets the exact release archive
`opensocrates-1.1.2-claude-chat-skills.zip`. Archive inspection and live UI
acceptance are separate claims.

The accepted archive has 51 files and SHA-256
`920fe772d1e926e0b9e315d15c197d9d878d45d7f596d768360694bb21af9178`.
It contains one top-level `opensocrates/` folder with `SKILL.md` directly
inside, one internal catalog, 48 internal method references, and LICENSE. It
contains no plugin manifest, hooks, launcher, native runtime, commands
directory, or credential-shaped file.

A passing live receipt uploads that exact hash through Claude's supported
Customize → Skills UI, observes one `/opensocrates` entry, and verifies catalog
routing plus representative internal method loading. The receipt may store
product/UI versions, the archive hash, counts, and booleans only. It must not
retain prompts, conversations, credentials, local paths, uploaded file
content, or raw UI data.

## 2026-08-11 attempt

The original 52-file, plugin-shaped archive was rejected by the live uploader:
its `SKILL.md` was nested below `skills/opensocrates/` instead of directly in a
single top-level skill folder. The package builder was corrected and the
51-file archive above passed the uploader's security check in Claude Desktop
1.26832.0. Replacing the existing user-provided skill left exactly one visible
`opensocrates` entry.

The installed skill exposed its catalog and all 48 method files. A live
`/opensocrates` invocation was recognized as a skill, routed through the
catalog, loaded the representative `cost-benefit-analysis@1` and
`premortem-analysis@1` references, and ended with a grounding audit containing
both method revision identifiers. The support claim is therefore
“skills-only; upload path validated.” No prompt, conversation, credential,
local path, uploaded content, or raw UI data was retained in the evidence.

The categorical passing receipt is
[`docs/evidence/claude-chat-upload-probe-v1.1.2.json`](evidence/claude-chat-upload-probe-v1.1.2.json).
