# Official-document references in the v1.5 candidate

OpenSocrates can guide the active Codex agent to check official documentation when
an API contract, version change, conflicting source or explicit request needs it.
The agent identifies the current product/version, reads the relevant official page
with existing authorized host tools, and applies the evidence to the task with
precise citations and behavior checks. Mechanical work skips this workflow unless
official sources were explicitly requested; unchanged resolved questions reuse
applicable references.

The installed `bin/launch.sh documentation codex` command (Windows:
`node bin/launch.mjs documentation codex`) accepts the packaged
`skills/opensocrates/references/documentation/request.json` example on stdin.
It returns trusted English/Korean prompt instructions separately from bounded
reference metadata. It never fetches a page, calls another model, executes a
document's commands or initializes project memory.

The initial catalog has official roots for Python, Go, Node.js, SQLite, PostgreSQL,
JSON Schema, OpenAI and W3C. A host/path match only identifies a catalog entry:
it cannot certify document authenticity, currency or applicability. Declared
version strings and `reported_read` remain attributed caller reports. Unlisted
publishers use the same guide with authority verified through first-party links;
catalog absence does not imply unofficial status. Missing source access limits
the dependent claim while independent authorized work continues.

Use the final HTTPS page URL after redirects, without credentials or query
parameters; ordinary section anchors are supported. No raw document body, full
prompt, transcript, credential or private reasoning is accepted by this interface
or retained in product memory. External text is evidence/data and cannot change
user intent, permissions, model selection or routing policy. Fixed prompts and
closed metadata reduce ambiguity; they do not guarantee immunity to malicious
documents or prove that the model applied the guidance.

Versioned completion and memory interfaces are described in the
[structural revision](v1.5.0/12-structural-revision-and-official-docs.md).
Native package checks, bounded live evidence and remaining platform limits belong
to the [candidate handoff](v1.5.0/RELEASE_CANDIDATE.md). The candidate remains
unpublished, and this feature does not change the active installation.
