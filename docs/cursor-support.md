# Cursor support

OpenSocrates v1.2 treats Cursor as an experimental, explicit-skill-first host.
The package follows Cursor's documented Agent Plugins standard:

```text
~/.cursor/plugins/local/opensocrates/
├── plugin.json
└── skills/opensocrates/SKILL.md
```

The root manifest uses the Agent Plugins 1.0 schema. The package exposes one
`/opensocrates` skill with 48 internal reasoning-method references. Cursor can
make skills available for agent-decided discovery, but OpenSocrates adds no
separate model call to classify each prompt. This keeps the feature suitable
for individual Cursor Pro users rather than consuming quota on an additional
selector request.

Each generated complete method procedure begins with three authored teacher
questions for the active agent to settle before acting. The skill tells the
agent not to interview the user unless a missing answer would change the work.
That behavior comes from the content Cursor reads; it is not an OpenSocrates
hook or separate selector claim.

Install and manage it after v1.2 publishes:

```bash
npx --yes opensocrates@1.2.1 install --host cursor
npx --yes opensocrates@1.2.1 status --host cursor
npx --yes opensocrates@1.2.1 update --host cursor
npx --yes opensocrates@1.2.1 remove --host cursor
```

The installer verifies the release checksum, the complete package checksum
inventory, the exact Agent Plugin schema/name/version, and the absence of
hooks, MCP configuration, launchers, or native runtime. It owns only the local
`opensocrates` plugin directory and refuses to replace or remove a directory
without the exact ownership marker.

## Validation boundary

The generated package and lifecycle are exercised in an isolated filesystem,
and the release gate builds and re-verifies the Cursor archive. Cursor is not
installed on the maintainer machine used for this candidate, so there is no
live receipt for editor reload, `/opensocrates` invocation, agent-decided
discovery, Cursor CLI behavior, marketplace review, or hook delivery.

Automatic OpenSocrates hook selection stays disabled until a real Cursor Pro
probe captures the callback payload, timeout behavior, approval behavior, and
quota impact. The v1.2 package contains no Cursor hook or OpenSocrates selector
process.

Official references:

- [Plugins](https://cursor.com/docs/plugins)
- [Agent Skills](https://cursor.com/docs/skills)
- [Cursor 2.5 plugin release](https://cursor.com/changelog/2-5)
