# Security Policy

## Supported versions

Security fixes are provided for the latest `1.x` release. Pre-1.0 builds are
not supported.

| Version | Supported |
| --- | --- |
| 1.x | Yes |
| < 1.0 | No |

## Report a vulnerability

Do not publish credentials, private prompts, transcripts, workspace data, or
exploit details in a public issue.

Use GitHub's
[private vulnerability reporting](https://github.com/ParkerHwang/OpenSocrates/security/advisories/new)
to send a confidential report. Include:

- the affected version and platform;
- the smallest reproducible example;
- expected and observed impact;
- whether credentials or private user data may be exposed;
- any suggested mitigation.

If private reporting is unavailable, open a public issue requesting a private
contact channel without including vulnerability details.

Reports are reviewed as maintainer capacity allows. Acknowledgement,
assessment, remediation, and disclosure timing depend on reproducibility,
severity, and the availability of a safe fix.

## Security boundary

OpenSocrates 1.0:

- runs locally through Codex and uses the user's existing OAuth session;
- does not require or store an OpenAI API key;
- does not host an OpenSocrates backend or add telemetry;
- verifies downloadable packages with SHA-256 release and package manifests;
- fails open when the selector cannot safely complete.

Signing, notarization, clean-machine installation, platforms other than
`darwin-arm64`, and actual host hook delivery are not claimed as validated.
See the release limitations file for the complete measured boundary.
