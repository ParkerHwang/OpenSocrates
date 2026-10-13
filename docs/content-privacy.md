# OpenSocrates content-only privacy notice

[한국어](content-privacy.ko.md) · [Agent guide](agent-discovery.md)

Last updated: October 13, 2026.

Scope: the released v1.5.1 Claude account skill and the separately prepared, unpublished
OpenAI wrapper containing the same skill files. This notice does not describe native
executable integrations; see the [Security
Policy](https://github.com/ParkerHwang/OpenSocrates/blob/5a6a7fa2897dd42772c4503a1301770e48bd1f29/SECURITY.md)
for those profiles. The OpenAI wrapper has not been submitted or accepted by a
directory.

The content-only package contains reasoning instructions and reference files. It has no
hooks, executable runtime, credential access, telemetry or developer-operated service.
The package does not send prompts, uploaded files, conversation transcripts or account
credentials to the developer. There is no developer service that receives or retains
this task content through the package, and no developer-side recipients or retention
period for it.

Your assistant host processes the content you provide under its own privacy policy,
permissions and retention settings. OpenSocrates does not replace those policies. Use
the host's available skill/plugin controls to disable or remove the package, and its
conversation controls to manage stored chats. Removing the package does not delete host
conversation history.

If you voluntarily open a [public GitHub support
issue](https://github.com/ParkerHwang/OpenSocrates/issues), the text, attachments and
GitHub account identity you include are visible to the maintainer and the public. The
maintainer can use that information to address the support request. Storage, retention
and available editing/deletion controls follow GitHub's policies and controls; no
separate fixed deletion schedule is promised here. Do not post credentials, private
prompts, transcripts or confidential files in public issues. Report vulnerabilities
through [GitHub's private reporting
route](https://github.com/ParkerHwang/OpenSocrates/security/advisories/new), following
the [Security
Policy](https://github.com/ParkerHwang/OpenSocrates/blob/5a6a7fa2897dd42772c4503a1301770e48bd1f29/SECURITY.md).

Source: [v1.5.1 content
package](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip)
· [release record](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1).
