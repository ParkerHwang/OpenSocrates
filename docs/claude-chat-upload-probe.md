# Claude Chat standalone skill evidence

Archive inspection, public-release provenance, and live Claude UI acceptance are
separate claims. A local Claude Code/Desktop Local/Cowork plugin observation
cannot establish the state of a manually uploaded Chat skill, and neither can
establish the source of an existing synced/custom skill.

## Current v1.2.1 state

Exact v1.2.1 Chat release artifact: **unavailable; live upload pending.**

The 2026-08-15 public-release audit found no GitHub `v1.2.1` tag or release.
The latest public release was `v1.2.0`; therefore the expected
`opensocrates-1.2.1-claude-chat-skills.zip`, its `.sha256` asset, and an exact
release commit were all unavailable. Prompt 4 is merged at
`2ced9500aea5c7672f644ecc345b58ed30a31701`, but a ZIP generated from repository
source after that merge is only a candidate. It is not a public v1.2.1 release
artifact and must not be substituted for one in Cloud evidence.

The three provenance states remain distinct:

- **Claude Code/Desktop Local/Cowork local plugin:** an earlier status
  observation recorded version 1.2.1 through the namespaced plugin route. This
  is local-plugin evidence only and was not re-probed here.
- **Manual Claude Chat standalone ZIP:** the exact v1.2.1 public release archive
  is unavailable, so Customize → Skills was not opened and no upload, status,
  content-revision, 48-system, or routing observation was made.
- **Pre-existing synced/custom skill:** an earlier Cloud observation recorded
  version 1.1.2. It was not reclassified as the local plugin and was not changed
  by the local installer or this pending probe.

The privacy-safe current receipt is
[`docs/evidence/claude-chat-upload-probe-v1.2.1.json`](evidence/claude-chat-upload-probe-v1.2.1.json).
Its `pending` status is a passing claim-calibration result, not a passing live
upload. It records only versions, release/archive availability, booleans, and
categorical source/routing states. It contains no prompt, conversation, account
identifier, local path, raw accessibility snapshot, uploaded content, token, or
credential.

The state may change to live-validated only after all of these controls pass:

1. GitHub publishes the exact `v1.2.1` tag and release commit containing Prompt
   4.
2. The named Chat ZIP and checksum asset exist, and the checksum matches both
   the downloaded archive and the same-source release candidate.
3. Claude Customize → Skills accepts that exact hash without crossing an
   authentication, 2FA, or user-confirmation boundary.
4. The standalone `/opensocrates status` reports 1.2.1, content revision 1, and
   48 internal systems, and a representative reference route is observed
   categorically.

## Historical v1.1.2 live receipt

The historical upload probe targeted the exact release archive
`opensocrates-1.1.2-claude-chat-skills.zip`. The accepted archive has 51 files
and SHA-256
`920fe772d1e926e0b9e315d15c197d9d878d45d7f596d768360694bb21af9178`.
It contains one top-level `opensocrates/` folder with `SKILL.md` directly
inside, one internal catalog, 48 internal method references, and LICENSE. It
contains no plugin manifest, hooks, launcher, native runtime, commands
directory, or credential-shaped file.

On 2026-08-11, the original 52-file plugin-shaped archive was rejected because
its `SKILL.md` was nested below `skills/opensocrates/`. The corrected 51-file
archive passed the uploader security check in Claude Desktop 1.26832.0.
Replacing the existing user-provided skill left exactly one visible
`opensocrates` entry. A live `/opensocrates` invocation exposed the catalog and
48 method files, routed to representative internal references, and produced a
grounding audit.

That result supports only the historical v1.1.2 claim “skills-only; upload path
validated.” It does not validate the current v1.2.1 source or release. The
categorical historical receipt remains unchanged at
[`docs/evidence/claude-chat-upload-probe-v1.1.2.json`](evidence/claude-chat-upload-probe-v1.1.2.json).
