#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const environment = {
  ...process.env,
  npm_config_dry_run: "false",
  npm_config_json: "true",
};

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function writeFakeHost(sandbox, host) {
  const target = join(sandbox, `fake-${host}`);
  const script = `#!/usr/bin/env node
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
const argv = process.argv.slice(2);
const has = (...items) => items.every((item) => argv.includes(item));
if (has("--version")) {
  process.stdout.write("2.1.205 (packed smoke)\\n");
  process.exit(0);
}
if (${JSON.stringify(host)} === "codex" && has("--strict-config", "features", "list")) {
  const config = join(process.env.CODEX_HOME, "config.toml");
  if (existsSync(config)) readFileSync(config);
  process.stdout.write("hooks stable true\\n");
  process.exit(0);
}
if (${JSON.stringify(host)} === "claude") {
  if (has("plugin", "marketplace", "list") || has("plugin", "list")) {
    process.stdout.write("[]");
    process.exit(0);
  }
} else {
  if (has("plugin", "marketplace", "list")) {
    process.stdout.write(JSON.stringify({ marketplaces: [] }));
    process.exit(0);
  }
  if (has("plugin", "list")) {
    process.stdout.write(JSON.stringify({ installed: [], available: [] }));
    process.exit(0);
  }
}
process.exit(1);
`;
  writeFileSync(target, script);
  chmodSync(target, 0o755);
  return target;
}

function seedPackageTree(root, host) {
  const version = "1.2.1";
  const manifest = `${host === "claude" ? ".claude-plugin" : ".codex-plugin"}/plugin.json`;
  const files = {
    [manifest]: `${JSON.stringify({ name: "opensocrates", version }, null, 2)}\n`,
    "release-manifest.json": `${JSON.stringify(
      {
        schema: "opensocrates.plugin-release-manifest/1.0.0",
        product_version: version,
        host,
        content_revision: 1,
      },
      null,
      2,
    )}\n`,
    "payload.txt": "packed npm purge smoke payload\n",
  };
  for (const [name, contents] of Object.entries(files)) {
    const target = join(root, ...name.split("/"));
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, contents);
  }
  writeFileSync(
    join(root, "checksums.sha256"),
    `${Object.entries(files)
      .map(([name, contents]) => `${sha256(Buffer.from(contents))}  ${name}`)
      .join("\n")}\n`,
  );
  return root;
}

function seedCache(hostHome, host) {
  const version = "1.2.1";
  const root = join(hostHome, "plugins", "cache", "opensocrates", "opensocrates", version);
  seedPackageTree(root, host);
  writeFileSync(join(root, ".orphaned_at"), "packed-smoke\n");
  return join(hostHome, "plugins", "cache", "opensocrates");
}

function seedManagedRoot(hostHome, host) {
  const version = "1.2.1";
  const root = join(hostHome, "managed-marketplaces", "opensocrates");
  const plugin =
    host === "claude"
      ? join(root, "plugins", "opensocrates")
      : join(root, "build", "generated", "plugins", "codex");
  seedPackageTree(plugin, host);
  writeFileSync(
    join(root, ".opensocrates-managed.json"),
    `${JSON.stringify(
      host === "claude"
        ? { schemaVersion: 1, marketplaceName: "opensocrates", pluginName: "opensocrates", host }
        : { schemaVersion: 1, marketplaceName: "opensocrates", pluginName: "opensocrates" },
      null,
      2,
    )}\n`,
  );
  const marketplace =
    host === "claude"
      ? {
          name: "opensocrates",
          owner: { name: "Parker Hwang" },
          metadata: {
            description: "OpenSocrates reasoning support for Claude Code and Cowork",
            version,
          },
          plugins: [
            {
              name: "opensocrates",
              source: "./plugins/opensocrates",
              description:
                "Local reasoning-system selection for Claude Code and Cowork, plus one /opensocrates entry.",
              category: "workflow",
            },
          ],
        }
      : {
          name: "opensocrates",
          interface: { displayName: "OpenSocrates" },
          plugins: [
            {
              name: "opensocrates",
              source: { source: "local", path: "./build/generated/plugins/codex" },
              policy: { installation: "AVAILABLE", authentication: "ON_INSTALL" },
              category: "Productivity",
            },
          ],
        };
  const marketplacePath =
    host === "claude"
      ? join(root, ".claude-plugin", "marketplace.json")
      : join(root, ".agents", "plugins", "marketplace.json");
  mkdirSync(dirname(marketplacePath), { recursive: true });
  writeFileSync(marketplacePath, `${JSON.stringify(marketplace, null, 2)}\n`);
  return root;
}

function seedPackedPurgeSandbox() {
  const sandbox = mkdtempSync(join(tmpdir(), "opensocrates-packed-purge-"));
  const homes = Object.fromEntries(
    ["antigravity", "claude", "codex", "cursor", "grok", "opencode"].map((host) => [
      host,
      join(sandbox, `${host}-home`),
    ]),
  );
  for (const home of Object.values(homes)) mkdirSync(home, { recursive: true });
  const state = join(sandbox, "state");
  const launchAgents = join(sandbox, "LaunchAgents");
  mkdirSync(state);
  mkdirSync(launchAgents);
  writeFileSync(
    join(state, "desired-state.json"),
    `${JSON.stringify(
      {
        schema: "opensocrates.desired-state/1.0.0",
        channel: "stable",
        installedHosts: ["claude", "codex"],
        activeVersion: "1.2.1",
        updatePolicy: { intervalHours: 24, allowMajor: false },
        autoUpdate: { enabled: true, hosts: ["claude", "codex"], nextCheckAt: null },
        availableVersion: "1.2.1",
        lastCheckAt: null,
        lastSuccessfulUpdateAt: null,
      },
      null,
      2,
    )}\n`,
  );
  writeFileSync(join(state, "auto-update-receipt.json"), "{}\n");
  const launchAgent = join(launchAgents, "com.opensocrates.auto-update.plist");
  writeFileSync(
    launchAgent,
    `<?xml version="1.0"?><plist><dict><key>Label</key><string>com.opensocrates.auto-update</string><key>ProgramArguments</key><array><string>/usr/bin/npx</string><string>--yes</string><string>opensocrates@latest</string><string>auto-update</string><string>run</string></array></dict></plist>\n`,
  );
  const cacheRoots = [seedCache(homes.claude, "claude"), seedCache(homes.codex, "codex")];
  const managedRoots = [
    seedManagedRoot(homes.claude, "claude"),
    seedManagedRoot(homes.codex, "codex"),
  ];
  const pluginData = [
    join(homes.claude, "plugins", "data", "opensocrates-inline"),
    join(homes.claude, "plugins", "data", "opensocrates-opensocrates"),
  ];
  for (const target of pluginData) mkdirSync(target, { recursive: true });
  const history = join(homes.claude, "projects", "opensocrates-user-history.jsonl");
  mkdirSync(dirname(history), { recursive: true });
  writeFileSync(history, "preserve packed smoke history\n");
  const unrelated = [
    [join(homes.claude, "plugins", "cache", "unrelated", "payload.txt"), "preserve unrelated cache\n"],
    [join(homes.claude, "plugins", "data", "unrelated-plugin", "state.json"), '{"keep":true}\n'],
  ];
  for (const [target, contents] of unrelated) {
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, contents);
  }
  const trustPrefix = "opensocrates@opensocrates:hooks/hooks.json:";
  const events = [
    "pre_tool_use",
    "post_tool_use",
    "pre_compact",
    "session_start",
    "session_end",
    "user_prompt_submit",
    "stop",
  ];
  const trustConfig = join(homes.codex, "config.toml");
  const trustSections = events
    .map(
      (event) =>
        `# packed ${event}\n` +
        `[hooks.state."${trustPrefix}${event}:0:0"]\n` +
        `trusted_hash = "sha256:packed-${event}"\n`,
    )
    .join("");
  const expectedTrustConfig =
    'model = "packed-smoke"\n' +
    '[hooks.state."other@market:hooks/hooks.json:session_start:0:0"]\n' +
    'trusted_hash = "sha256:other"\n' +
    events.map((event) => `# packed ${event}\n\n\n`).join("");
  writeFileSync(
    trustConfig,
    'model = "packed-smoke"\n' +
      '[hooks.state."other@market:hooks/hooks.json:session_start:0:0"]\n' +
      'trusted_hash = "sha256:other"\n' +
      trustSections,
  );
  return {
    sandbox,
    state,
    launchAgent,
    cacheRoots,
    managedRoots,
    pluginData,
    history,
    unrelated,
    trustConfig,
    expectedTrustConfig,
    environment: {
      ...process.env,
      AGY_BIN: join(sandbox, "missing-agy"),
      ANTIGRAVITY_CONFIG_DIR: homes.antigravity,
      CLAUDE_BIN: writeFakeHost(sandbox, "claude"),
      CLAUDE_CONFIG_DIR: homes.claude,
      CODEX_BIN: writeFakeHost(sandbox, "codex"),
      CODEX_HOME: homes.codex,
      CURSOR_BIN: join(sandbox, "missing-cursor"),
      CURSOR_CONFIG_DIR: homes.cursor,
      GROK_BIN: join(sandbox, "missing-grok"),
      GROK_HOME: homes.grok,
      OPENCODE_BIN: join(sandbox, "missing-opencode"),
      OPENCODE_CONFIG_DIR: homes.opencode,
      OPENSOCRATES_STATE_DIR: state,
      OPENSOCRATES_LAUNCH_AGENTS_DIR: launchAgents,
      OPENSOCRATES_SKIP_LAUNCHCTL: "1",
      npm_config_dry_run: "false",
      npm_config_json: "false",
    },
  };
}

const packed = spawnSync(npm, ["pack", "--silent", "--json"], {
  cwd: root,
  encoding: "utf8",
  env: environment,
});
if (packed.status !== 0) {
  process.stderr.write(packed.stderr);
  process.exit(packed.status ?? 1);
}

let archive;
let purgeSandbox;
try {
  const metadata = JSON.parse(packed.stdout);
  archive = resolve(root, metadata[0].filename);
  const help = spawnSync(npx, ["--yes", `--package=${archive}`, "opensocrates", "help"], {
    cwd: root,
    encoding: "utf8",
    env: { ...process.env, npm_config_dry_run: "false", npm_config_json: "false" },
  });
  assert.equal(help.status, 0, help.stderr);
  assert.match(help.stdout, /remove \[--host .*\] \[--purge \[--reset-trust\]\]/u);
  assert.match(help.stdout, /host security trust, and user history are reported separately/u);
  assert.equal(help.stdout.match(/--asset ZIP --checksum FILE/gu)?.length, 3);
  assert.doesNotMatch(help.stdout, /--checksum SHA256/u);

  purgeSandbox = seedPackedPurgeSandbox();
  const purged = spawnSync(
    npx,
    [
      "--yes",
      `--package=${archive}`,
      "opensocrates",
      "remove",
      "--host",
      "all",
      "--purge",
      "--reset-trust",
    ],
    {
      cwd: root,
      encoding: "utf8",
      env: purgeSandbox.environment,
    },
  );
  assert.equal(purged.status, 0, `${purged.stdout}\n${purged.stderr}`);
  assert.match(purged.stdout, /OpenSocrates purge completed/u);
  assert.match(purged.stdout, /host security trust reset completed for 7 exact/u);
  for (const target of [
    purgeSandbox.state,
    purgeSandbox.launchAgent,
    ...purgeSandbox.cacheRoots,
    ...purgeSandbox.managedRoots,
    ...purgeSandbox.pluginData,
  ]) {
    assert.equal(existsSync(target), false, `packed purge left ${target}`);
  }
  assert.equal(readFileSync(purgeSandbox.history, "utf8"), "preserve packed smoke history\n");
  for (const [target, contents] of purgeSandbox.unrelated) {
    assert.equal(readFileSync(target, "utf8"), contents, `packed purge changed ${target}`);
  }
  assert.equal(readFileSync(purgeSandbox.trustConfig, "utf8"), purgeSandbox.expectedTrustConfig);
} finally {
  if (purgeSandbox) rmSync(purgeSandbox.sandbox, { recursive: true, force: true });
  if (archive) {
    unlinkSync(archive);
  }
}
