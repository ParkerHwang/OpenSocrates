# Google Antigravity support

OpenSocrates v1.2 treats Google Antigravity as an experimental, explicit-skill
host. The integration follows Antigravity's documented global plugin layout:

```text
~/.gemini/config/plugins/opensocrates/
├── plugin.json
└── skills/opensocrates/SKILL.md
```

The generated package contains one public `opensocrates` skill and 48 internal
reasoning-method references. It contains no hooks, launcher, native runtime,
MCP server, background process, telemetry, or automatic selector. Consequently
it makes no extra model request merely to choose a reasoning method.

On explicit skill use, each selected generated method begins with three authored
teacher questions. The active agent settles them before using the rest of the
complete procedure as a check and does not interview the user unless a missing
answer would change the work. This is visible skill content, not hidden hook
delivery.

Install and manage it with the same lifecycle as the other hosts:

```bash
npx --yes opensocrates@1.2.1 install --host antigravity
npx --yes opensocrates@1.2.1 status --host antigravity
npx --yes opensocrates@1.2.1 update --host antigravity
npx --yes opensocrates@1.2.1 remove --host antigravity
```

The installer verifies the release checksum, the complete package checksum
inventory, the exact `plugin.json` name/version, and the absence of executable
or hook surfaces. It owns only the `opensocrates` plugin directory and refuses
to replace or remove a directory without the exact ownership marker.

## Validation boundary

The generated candidate passed `agy plugin validate` with Antigravity CLI
1.0.6 on macOS: one skill was processed and agents, commands, MCP servers, and
hooks were absent. The privacy-safe receipt is in
[`docs/evidence/antigravity-plugin-validate-2026-08-12.json`](evidence/antigravity-plugin-validate-2026-08-12.json).

That receipt proves package-shape recognition, not authenticated skill
invocation, Desktop/IDE behavior, marketplace publication, native hook
delivery, or automatic selection. Those capabilities remain unclaimed until
separate live receipts exist.

Official references:

- [Agent Skills](https://antigravity.google/docs/skills)
- [Plugins](https://antigravity.google/docs/ide/plugins)
- [Hooks](https://www.antigravity.google/docs/hooks)
