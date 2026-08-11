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

OpenSocrates 1.x:

- runs its integration locally through Claude or Codex and uses the user's
  existing host login;
- does not require or store an Anthropic or OpenAI API key;
- does not host an OpenSocrates backend or add telemetry;
- verifies downloadable packages with SHA-256 release and package manifests;
- keeps cross-host activation transactional and restores prior managed
  registrations when a coordinated activation fails;
- leaves scheduled updates disabled until explicitly enabled and stores only
  owner-readable desired state, a single-instance lock, and content-free update
  receipts;
- fails open when the selector cannot safely complete.

The Claude selector runs a bounded, non-persistent `claude --safe-mode -p`
process. Safe mode disables user, project, and plugin customizations, and
OpenSocrates additionally passes `--tools ""`, `--disallowedTools "mcp__*"`, and
`--strict-mcp-config` so no built-in or MCP tool remains. It receives the current
prompt and authored selection catalog only. The process uses the user's Claude
login, so model requests remain subject to Anthropic's service and data-handling
terms. The Codex selector uses the pinned Codex SDK and existing OAuth session in
its own isolated worker.

The selector environment is default-deny. `CLAUDE_CONFIG_DIR` is one of the
small set of allowed path variables because the child needs it to locate the
user's existing Claude login when a non-default config directory is in use.
OpenSocrates does not copy, inspect, or log credentials from that directory.

Managed policy settings are part of the host trust boundary and are not disabled.
Anthropic's [CLI reference](https://code.claude.com/docs/en/cli-reference) states
that under `--safe-mode` "managed settings policy still applies, including
policy-configured hooks". Consequences on an organization-managed machine:

- a managed `UserPromptSubmit` hook executes inside the selector process,
  receives the current prompt on standard input, and can return
  `additionalContext` that enters selection;
- managed plugins, managed skills, managed `CLAUDE.md`, and policy-configured
  MCP servers do not load.

OpenSocrates does not detect or override managed policy. Selection remains
bounded regardless: the model's returned instruction text is discarded, and only
authored catalog content assembled by OpenSocrates is ever injected. Operators
who cannot accept managed-hook visibility of the selector prompt should not
enable OpenSocrates selection on those machines.

On Claude surfaces that deliver the packaged hooks, the grounding gate observes
only successful `Read` callbacks for the current turn's exact instruction file.
It transiently checks that the response reached an authored terminal marker and
does not retain the response. The owner-only authenticated receipt stores only
the artifact digest, content revision, selected method IDs, and keyed
authentication/tool-use tags; prompts, transcripts, raw tool output,
credentials, workspace paths, and artifact paths are excluded. `Stop` removes
the receipt with the turn artifact. If `Stop` is absent, the next
`UserPromptSubmit` in that session removes prior prompt trees without touching
the new active tree. `SessionEnd` remains the session backstop, and the
24-hour `SessionStart` sweep covers crash leftovers when neither event arrives.

The gate's scope is deliberate and worth stating plainly. It establishes that a
successful `Read` callback naming the exact current-turn artifact returned
content reaching the authored terminal marker. It does not cryptographically
prove that every artifact byte was returned: a synthetic payload carrying only
the marker would satisfy the marker test. That is not reachable by the model,
which does not author `tool_response`, and the marker is the artifact's last
line, so a truncated read loses it. Anything able to forge that callback already
controls the hook's standard input and is outside the boundary this gate
defends. The gate raises the cost of an ungrounded answer; it is not a proof of
delivery, and it fails open by design.

The optional macOS LaunchAgent invokes the selected published npm channel and
then uses the same verified installer path as a manual update. It does not read
or terminate active Claude or Codex sessions. Its receipt contains only the
checked version, timestamp, per-host result, and an error category; prompts,
transcripts, workspace paths, credentials, and raw error output are excluded.
Automatic major-version upgrades are disabled unless the user explicitly
changes that policy.

Installer rollback mutates only its owner-marked managed marketplace root. If
the failed root cannot be removed and the previous backup therefore cannot be
renamed into place, the installer preserves that backup and prints quoted,
executable recovery commands naming only those two managed paths.

Signing, notarization, clean-machine installation, platforms other than
`darwin-arm64`, Claude Chat automatic hooks, and live delivery on every host
surface are not claimed as validated. Native plugin archives ship only
`bin/launch.sh`; it rejects macOS Intel, Linux, Windows, and every other target,
and no PowerShell launcher is included. See the release limitations file for
the complete measured boundary.
