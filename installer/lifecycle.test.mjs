// Isolated installer lifecycle tests.
//
// Every test runs against a throwaway host home and a fake host binary. None
// of these tests reads or writes the developer's real host configuration
// directory, and none of them contacts the network: packages are built locally
// and passed with --asset/--checksum.

import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
  existsSync,
  readdirSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import { PRODUCT_VERSION, main, transientPathsFor, withOperationLock } from "./opensocrates.mjs";
import { inspectManagedLayout } from "../tools/clean_machine_acceptance.mjs";

const MARKETPLACE = "opensocrates";
const PLUGIN_ID = `opensocrates@${MARKETPLACE}`;

// ---------------------------------------------------------------------------
// Platform spoofing: install/update are gated to darwin-arm64. The gate is
// intentional, so tests spoof the platform rather than weakening it.
// ---------------------------------------------------------------------------
function withDarwinArm64(fn) {
  const platform = Object.getOwnPropertyDescriptor(process, "platform");
  const arch = Object.getOwnPropertyDescriptor(process, "arch");
  Object.defineProperty(process, "platform", {
    value: "darwin",
    configurable: true,
  });
  Object.defineProperty(process, "arch", {
    value: "arm64",
    configurable: true,
  });
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      Object.defineProperty(process, "platform", platform);
      Object.defineProperty(process, "arch", arch);
    });
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

// ---------------------------------------------------------------------------
// Package fixture
// ---------------------------------------------------------------------------
function buildPackage(root, host, { version = PRODUCT_VERSION, corrupt = false, manifestVersion = null } = {}) {
  const tree = join(root, `pkg-${host}`);
  const manifestPath = ["antigravity", "cursor", "grok"].includes(host)
    ? "plugin.json"
    : host === "opencode"
      ? "opencode-plugin.json"
      : `${host === "claude" ? ".claude-plugin" : ".codex-plugin"}/plugin.json`;
  mkdirSync(dirname(join(tree, manifestPath)), { recursive: true });
  if (["claude", "codex"].includes(host)) {
    mkdirSync(join(tree, "runtime", "darwin-arm64", "opensocrates-runtime"), { recursive: true });
  }
  mkdirSync(join(tree, "skills", "opensocrates"), { recursive: true });

  const files = {};
  files[manifestPath] = JSON.stringify(
    {
      ...(host === "cursor"
        ? {
            $schema: "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
          }
        : host === "opencode"
          ? {
              schema: "opensocrates.opencode-package/1.0.0",
              minimum_opencode_version: "1.18.18",
              stable_plugin_hook: "chat.message",
              beta_v2_api: false,
            }
          : {}),
      ...(host === "grok" ? { skills: "./skills" } : {}),
      name: "opensocrates",
      version: manifestVersion ?? version,
    },
    null,
    2,
  );
  files["release-manifest.json"] = JSON.stringify(
    {
      product_version: version,
      host,
      schema: "opensocrates.plugin-release-manifest/1.0.0",
      launchers: [],
      runtime_targets: [],
    },
    null,
    2,
  );
  if (["claude", "codex"].includes(host)) {
    files["runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime"] = "#!/bin/sh\nexit 0\n";
  }
  files["skills/opensocrates/SKILL.md"] = "# OpenSocrates controller\n";
  if (host === "opencode") {
    files["skills/opensocrates/references/catalog.md"] = "# Catalog\n";
    files["plugins/opensocrates.js"] =
      "export const OpenSocratesPlugin = async () => ({ 'chat.message': async () => {} });\n";
  }

  for (const [name, body] of Object.entries(files)) {
    mkdirSync(dirname(join(tree, ...name.split("/"))), { recursive: true });
    writeFileSync(join(tree, ...name.split("/")), body);
  }
  if (["claude", "codex"].includes(host)) {
    chmodSync(join(tree, "runtime", "darwin-arm64", "opensocrates-runtime", "opensocrates-runtime"), 0o755);
  }

  const lines = Object.entries(files).map(([name, body]) => {
    const digest = corrupt && name === "release-manifest.json" ? "0".repeat(64) : sha256(Buffer.from(body));
    return `${digest}  ${name}`;
  });
  writeFileSync(join(tree, "checksums.sha256"), `${lines.join("\n")}\n`);

  const asset = join(root, `opensocrates-${version}-${host}-plugin.zip`);
  const zip = spawnSync("zip", ["-q", "-r", "-X", asset, "."], {
    cwd: tree,
    encoding: "utf8",
  });
  assert.equal(zip.status, 0, `zip failed: ${zip.stderr}`);
  const checksum = `${asset}.sha256`;
  writeFileSync(checksum, `${sha256(readFileSync(asset))}  opensocrates-${version}-${host}-plugin.zip\n`);
  return { asset, checksum, tree };
}

// ---------------------------------------------------------------------------
// Fake host binaries. State lives in a JSON file so registration survives
// across separate invocations, exactly like the real hosts.
// ---------------------------------------------------------------------------
function writeFakeHost(
  root,
  name,
  {
    kind = name,
    failInstall = false,
    failInstallOnce = false,
    failAuth = false,
    corruptMarkerOnInstall = false,
    corruptBackupOnInstall = false,
    blockRootRemovalOnInstall = false,
    claudeMarketplaceWrapper = false,
    claudePluginWrapper = false,
    malformedClaudeMarketplaceList = false,
    malformedClaudePluginList = false,
    duplicateClaudeMarketplace = false,
    duplicateClaudePlugin = false,
    conflictingClaudeMarketplaceRoots = false,
    invalidClaudePluginEnabled = false,
  } = {},
) {
  const host = kind;
  const statePath = join(root, `${name}-state.json`);
  writeFileSync(statePath, JSON.stringify({ marketplaces: [], plugins: [] }));
  const binary = join(root, name);
  const script = `#!/usr/bin/env node
import { chmodSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
const STATE = ${JSON.stringify(statePath)};
const HOST = ${JSON.stringify(host)};
const FAIL_INSTALL = ${JSON.stringify(failInstall)};
const FAIL_INSTALL_ONCE = ${JSON.stringify(failInstallOnce)};
const FAIL_AUTH = ${JSON.stringify(failAuth)};
const CORRUPT_MARKER = ${JSON.stringify(corruptMarkerOnInstall)};
const CORRUPT_BACKUP = ${JSON.stringify(corruptBackupOnInstall)};
const BLOCK_ROOT_REMOVAL = ${JSON.stringify(blockRootRemovalOnInstall)};
const CLAUDE_MARKETPLACE_WRAPPER = ${JSON.stringify(claudeMarketplaceWrapper)};
const CLAUDE_PLUGIN_WRAPPER = ${JSON.stringify(claudePluginWrapper)};
const MALFORMED_CLAUDE_MARKETPLACES = ${JSON.stringify(malformedClaudeMarketplaceList)};
const MALFORMED_CLAUDE_PLUGINS = ${JSON.stringify(malformedClaudePluginList)};
const DUPLICATE_CLAUDE_MARKETPLACE = ${JSON.stringify(duplicateClaudeMarketplace)};
const DUPLICATE_CLAUDE_PLUGIN = ${JSON.stringify(duplicateClaudePlugin)};
const CONFLICTING_CLAUDE_ROOTS = ${JSON.stringify(conflictingClaudeMarketplaceRoots)};
const INVALID_CLAUDE_ENABLED = ${JSON.stringify(invalidClaudePluginEnabled)};
const VERSION = ${JSON.stringify(PRODUCT_VERSION)};
const MARKETPLACE = ${JSON.stringify(MARKETPLACE)};
const PLUGIN_ID = ${JSON.stringify(PLUGIN_ID)};
const argv = process.argv.slice(2);
const state = JSON.parse(readFileSync(STATE, "utf8"));
const save = () => writeFileSync(STATE, JSON.stringify(state));
const out = (value) => process.stdout.write(JSON.stringify(value));
const has = (...parts) => parts.every((part) => argv.includes(part));

// OpenCode is gated to >=1.18.18 and <2.0.0, so the shared 2.1.205 fake would
// trip its fail-closed ceiling. Report a version each host actually accepts.
if (has("--version")) {
  process.stdout.write(HOST === "opencode" ? "1.18.18 (fake)\\n" : "2.1.205 (fake)\\n");
  process.exit(0);
}
if (HOST === "claude" && has("auth", "status")) {
  if (FAIL_AUTH) process.exit(1);
  out({ loggedIn: true }); process.exit(0);
}
if (HOST === "codex" && has("login", "status")) {
  if (FAIL_AUTH) process.exit(1);
  process.stdout.write("Logged in using ChatGPT\\n"); process.exit(0);
}
if (HOST === "grok" && has("inspect", "--json")) {
  const root = join(process.env.GROK_HOME, "plugins", MARKETPLACE);
  let discoveredRoot = root;
  try {
    const scannedBackup = readdirSync(join(process.env.GROK_HOME, "plugins")).find(
      (entry) => entry.startsWith(".opensocrates.backup-")
    );
    if (scannedBackup) discoveredRoot = join(process.env.GROK_HOME, "plugins", scannedBackup);
  } catch {
    // A missing plugins directory is reported as no discovered plugin below.
  }
  try {
    JSON.parse(readFileSync(join(discoveredRoot, "plugin.json"), "utf8"));
    out({
      plugins: [{
        name: MARKETPLACE,
        scope: "user",
        path: discoveredRoot,
        enabled: state.grokEnabled !== false,
        provides: { skills: 1, agents: 0, hooks: false, mcpServers: 0 },
      }],
    });
  } catch {
    out({ plugins: [] });
  }
  process.exit(0);
}

if (HOST === "claude") {
  if (has("plugin", "marketplace", "list")) {
    if (MALFORMED_CLAUDE_MARKETPLACES) { out({ entries: state.marketplaces }); process.exit(0); }
    let entries = state.marketplaces.map((entry) =>
      CONFLICTING_CLAUDE_ROOTS && entry.name === MARKETPLACE
        ? { ...entry, installLocation: entry.path + "-conflict" }
        : entry
    );
    if (DUPLICATE_CLAUDE_MARKETPLACE) entries = [...entries, ...entries.filter((entry) => entry.name === MARKETPLACE)];
    out(CLAUDE_MARKETPLACE_WRAPPER ? { marketplaces: entries } : entries); process.exit(0);
  }
  if (has("plugin", "marketplace", "add")) {
    const path = argv[argv.indexOf("add") + 1];
    state.marketplaces.push({ name: MARKETPLACE, source: "local", path });
    save(); process.exit(0);
  }
  if (has("plugin", "marketplace", "remove")) {
    state.marketplaces = state.marketplaces.filter((entry) => entry.name !== MARKETPLACE);
    save(); process.exit(0);
  }
  if (has("plugin", "list")) {
    if (MALFORMED_CLAUDE_PLUGINS) { out({ entries: state.plugins }); process.exit(0); }
    let entries = state.plugins.map((entry) =>
      INVALID_CLAUDE_ENABLED && entry.id === PLUGIN_ID ? { ...entry, enabled: "yes" } : entry
    );
    if (DUPLICATE_CLAUDE_PLUGIN) entries = [...entries, ...entries.filter((entry) => entry.id === PLUGIN_ID)];
    out(CLAUDE_PLUGIN_WRAPPER ? { plugins: entries } : entries); process.exit(0);
  }
  if (has("plugin", "install")) {
    const installAttempt = state.installAttempts ?? 0;
    state.installAttempts = installAttempt + 1;
    if (CORRUPT_MARKER) {
      // Simulate a host that leaves the new root unreadable as it fails, so a
      // rollback stage itself throws.
      const entry = state.marketplaces[state.marketplaces.length - 1];
      if (entry && entry.path) writeFileSync(entry.path + "/.opensocrates-managed.json", "{ not json");
    }
    if (CORRUPT_BACKUP) {
      const entry = state.marketplaces[state.marketplaces.length - 1];
      if (entry && entry.path) {
        const parent = dirname(entry.path);
        const backup = readdirSync(parent).find((item) => item.startsWith(".opensocrates.backup-"));
        if (backup) writeFileSync(join(parent, backup, ".opensocrates-managed.json"), "{ not json");
      }
    }
    if (BLOCK_ROOT_REMOVAL) {
      const entry = state.marketplaces[state.marketplaces.length - 1];
      if (entry && entry.path) chmodSync(dirname(entry.path), 0o500);
    }
    if (FAIL_INSTALL || (FAIL_INSTALL_ONCE && installAttempt === 0)) {
      save(); process.stderr.write("refused by strictKnownMarketplaces\\n"); process.exit(1);
    }
    state.plugins.push({ id: PLUGIN_ID, version: VERSION, enabled: true }); save(); process.exit(0);
  }
  if (has("plugin", "uninstall")) {
    state.plugins = state.plugins.filter((entry) => entry.id !== PLUGIN_ID); save(); process.exit(0);
  }
  if (has("plugin", "disable")) {
    state.plugins = state.plugins.map((entry) =>
      entry.id === PLUGIN_ID ? { ...entry, enabled: false } : entry
    ); save(); process.exit(0);
  }
  if (has("plugin", "enable")) {
    state.plugins = state.plugins.map((entry) =>
      entry.id === PLUGIN_ID ? { ...entry, enabled: true } : entry
    ); save(); process.exit(0);
  }
  process.exit(1);
}

if (has("plugin", "marketplace", "list")) { out({ marketplaces: state.marketplaces }); process.exit(0); }
if (has("plugin", "marketplace", "add")) {
  const path = argv[argv.indexOf("add") + 1];
  state.marketplaces.push({ name: MARKETPLACE, root: path }); save(); out({ ok: true }); process.exit(0);
}
if (has("plugin", "marketplace", "remove")) {
  state.marketplaces = state.marketplaces.filter((entry) => entry.name !== MARKETPLACE);
  save(); out({ ok: true }); process.exit(0);
}
if (has("plugin", "list")) {
  out({ installed: state.plugins, available: state.plugins.length ? [] : [] }); process.exit(0);
}
if (has("plugin", "add")) {
  const installAttempt = state.installAttempts ?? 0;
  state.installAttempts = installAttempt + 1;
  if (CORRUPT_MARKER) {
    const entry = state.marketplaces[state.marketplaces.length - 1];
    if (entry && entry.root) writeFileSync(entry.root + "/.opensocrates-managed.json", "{ not json");
  }
  if (FAIL_INSTALL || (FAIL_INSTALL_ONCE && installAttempt === 0)) {
    save(); process.stderr.write("refused\\n"); process.exit(1);
  }
  state.plugins.push({ pluginId: PLUGIN_ID, version: VERSION }); save();
  out({ pluginId: PLUGIN_ID, version: VERSION }); process.exit(0);
}
if (has("plugin", "remove")) {
  state.plugins = state.plugins.filter((entry) => entry.pluginId !== PLUGIN_ID);
  save(); out({ ok: true }); process.exit(0);
}
process.exit(1);
`;
  writeFileSync(binary, script);
  chmodSync(binary, 0o755);
  return { binary, statePath };
}

function makeSandbox(host, options = {}) {
  const root = mkdtempSync(join(tmpdir(), "opensocrates-lifecycle-"));
  const home = join(root, `${host}-home`);
  mkdirSync(home, { recursive: true });
  const { binary, statePath } = writeFakeHost(root, host, options);
  const saved = { ...process.env };
  if (host === "antigravity") {
    process.env.AGY_BIN = binary;
    process.env.ANTIGRAVITY_CONFIG_DIR = home;
  } else if (host === "cursor") {
    process.env.CURSOR_BIN = binary;
    process.env.CURSOR_CONFIG_DIR = home;
  } else if (host === "opencode") {
    process.env.OPENCODE_BIN = binary;
    process.env.OPENCODE_CONFIG_DIR = home;
  } else if (host === "claude") {
    process.env.CLAUDE_BIN = binary;
    process.env.CLAUDE_CONFIG_DIR = home;
  } else if (host === "grok") {
    process.env.GROK_BIN = binary;
    process.env.GROK_HOME = home;
  } else {
    process.env.CODEX_BIN = binary;
    process.env.CODEX_HOME = home;
  }
  process.env.OPENSOCRATES_STATE_DIR = join(root, "state");
  process.env.OPENSOCRATES_LAUNCH_AGENTS_DIR = join(root, "LaunchAgents");
  process.env.OPENSOCRATES_SKIP_LAUNCHCTL = "1";
  const managedParent =
    host === "antigravity"
      ? join(home, "plugins")
      : host === "cursor"
        ? join(home, "plugins", "local")
        : host === "grok"
          ? join(home, "plugins")
          : host === "opencode"
            ? join(home, "skills")
            : join(home, "managed-marketplaces");
  const managedRoot = join(managedParent, MARKETPLACE);
  return {
    root,
    home,
    managedRoot,
    statePath,
    state: () => JSON.parse(readFileSync(statePath, "utf8")),
    backups: () =>
      existsSync(managedParent) ? readdirSync(managedParent).filter((n) => n.startsWith(".opensocrates.backup-")) : [],
    cleanup: () => {
      for (const key of [
        "AGY_BIN",
        "ANTIGRAVITY_CONFIG_DIR",
        "CLAUDE_BIN",
        "CLAUDE_CONFIG_DIR",
        "CODEX_BIN",
        "CODEX_HOME",
        "CURSOR_BIN",
        "CURSOR_CONFIG_DIR",
        "GROK_BIN",
        "GROK_HOME",
        "OPENCODE_BIN",
        "OPENCODE_CONFIG_DIR",
        "OPENSOCRATES_STATE_DIR",
        "OPENSOCRATES_LAUNCH_AGENTS_DIR",
        "OPENSOCRATES_SKIP_LAUNCHCTL",
      ]) {
        if (saved[key] === undefined) delete process.env[key];
        else process.env[key] = saved[key];
      }
      rmSync(root, { recursive: true, force: true });
    },
  };
}

function replaceSandboxHost(box, host, name, options = {}) {
  const replacement = writeFakeHost(box.root, name, {
    kind: host,
    ...options,
  });
  writeFileSync(
    replacement.binary,
    readFileSync(replacement.binary, "utf8").replace(
      JSON.stringify(replacement.statePath),
      JSON.stringify(box.statePath),
    ),
  );
  chmodSync(replacement.binary, 0o755);
  const binaryKey =
    host === "antigravity"
      ? "AGY_BIN"
      : host === "claude"
        ? "CLAUDE_BIN"
        : host === "cursor"
          ? "CURSOR_BIN"
          : host === "grok"
            ? "GROK_BIN"
            : host === "opencode"
              ? "OPENCODE_BIN"
              : "CODEX_BIN";
  process.env[binaryKey] = replacement.binary;
  return replacement;
}

function makeAllSandbox(options = {}) {
  const root = mkdtempSync(join(tmpdir(), "opensocrates-all-hosts-"));
  const includeOpenCode = options.includeOpenCode === true;
  const homes = {
    claude: join(root, "claude-home"),
    codex: join(root, "codex-home"),
    ...(includeOpenCode ? { opencode: join(root, "opencode-home") } : {}),
  };
  for (const home of Object.values(homes)) mkdirSync(home, { recursive: true });
  const hosts = {
    claude: writeFakeHost(root, "claude", {
      kind: "claude",
      ...options.claude,
    }),
    codex: writeFakeHost(root, "codex", {
      kind: "codex",
      ...options.codex,
    }),
    ...(includeOpenCode
      ? {
          opencode: writeFakeHost(root, "opencode", {
            kind: "opencode",
            ...options.opencode,
          }),
        }
      : {}),
  };
  const saved = { ...process.env };
  process.env.CLAUDE_BIN = hosts.claude.binary;
  process.env.CLAUDE_CONFIG_DIR = homes.claude;
  process.env.CODEX_BIN = hosts.codex.binary;
  process.env.CODEX_HOME = homes.codex;
  // Keep all-host tests hermetic: real developer installations must not add
  // content-only hosts to this two-host fixture.
  process.env.CURSOR_BIN = join(root, "unavailable-cursor");
  process.env.AGY_BIN = join(root, "unavailable-agy");
  process.env.GROK_BIN = join(root, "unavailable-grok");
  // Grok resolves its managed root from GROK_HOME without consulting the CLI,
  // so an isolated home is what keeps a developer's real ~/.grok out of the
  // all-host fixture. Setting CURSOR_CONFIG_DIR or ANTIGRAVITY_CONFIG_DIR would
  // instead satisfy their preflight and pull them into this two-host fixture.
  process.env.GROK_HOME = join(root, "grok-home");
  if (includeOpenCode) {
    process.env.OPENCODE_BIN = hosts.opencode.binary;
    process.env.OPENCODE_CONFIG_DIR = homes.opencode;
  } else {
    process.env.OPENCODE_BIN = join(root, "unavailable-opencode");
    // Same hermetic reasoning as GROK_HOME above: keep a developer's real
    // ~/.config/opencode out of the fixture.
    process.env.OPENCODE_CONFIG_DIR = join(root, "opencode-home-unused");
  }
  process.env.OPENSOCRATES_STATE_DIR = join(root, "state");
  process.env.OPENSOCRATES_LAUNCH_AGENTS_DIR = join(root, "LaunchAgents");
  process.env.OPENSOCRATES_SKIP_LAUNCHCTL = "1";
  const managedRoots = {
    claude: join(homes.claude, "managed-marketplaces", MARKETPLACE),
    codex: join(homes.codex, "managed-marketplaces", MARKETPLACE),
    ...(includeOpenCode ? { opencode: join(homes.opencode, "skills", MARKETPLACE) } : {}),
  };
  const state = (host) => JSON.parse(readFileSync(hosts[host].statePath, "utf8"));
  return {
    root,
    homes,
    hosts,
    managedRoots,
    state,
    desired: () => JSON.parse(readFileSync(join(root, "state", "desired-state.json"), "utf8")),
    receipt: () => JSON.parse(readFileSync(join(root, "state", "auto-update-receipt.json"), "utf8")),
    launchAgent: join(root, "LaunchAgents", "com.opensocrates.auto-update.plist"),
    setBinary(host, binary) {
      process.env[host === "claude" ? "CLAUDE_BIN" : host === "opencode" ? "OPENCODE_BIN" : "CODEX_BIN"] = binary;
    },
    cleanup: () => {
      for (const key of [
        "AGY_BIN",
        "ANTIGRAVITY_CONFIG_DIR",
        "CLAUDE_BIN",
        "CLAUDE_CONFIG_DIR",
        "CODEX_BIN",
        "CODEX_HOME",
        "CURSOR_BIN",
        "CURSOR_CONFIG_DIR",
        "GROK_BIN",
        "GROK_HOME",
        "OPENCODE_BIN",
        "OPENCODE_CONFIG_DIR",
        "OPENSOCRATES_STATE_DIR",
        "OPENSOCRATES_LAUNCH_AGENTS_DIR",
        "OPENSOCRATES_SKIP_LAUNCHCTL",
        "OPENSOCRATES_NPX_BIN",
        "OPENSOCRATES_NODE_BIN",
        "OPENSOCRATES_LAUNCHCTL_BIN",
      ]) {
        if (saved[key] === undefined) delete process.env[key];
        else process.env[key] = saved[key];
      }
      rmSync(root, { recursive: true, force: true });
    },
  };
}

function allAssetArgs(packages) {
  const args = [
    "--host",
    "all",
    "--asset-claude",
    packages.claude.asset,
    "--checksum-claude",
    packages.claude.checksum,
    "--asset-codex",
    packages.codex.asset,
    "--checksum-codex",
    packages.codex.checksum,
  ];
  if (packages.opencode) {
    args.push("--asset-opencode", packages.opencode.asset, "--checksum-opencode", packages.opencode.checksum);
  }
  return args;
}

function replaceAllHostBinary(box, host, name, options) {
  const replacement = writeFakeHost(box.root, name, {
    kind: host,
    ...options,
  });
  writeFileSync(
    replacement.binary,
    readFileSync(replacement.binary, "utf8").replace(
      JSON.stringify(replacement.statePath),
      JSON.stringify(box.hosts[host].statePath),
    ),
  );
  chmodSync(replacement.binary, 0o755);
  box.setBinary(host, replacement.binary);
  return replacement;
}

function configureFakeNpx(box) {
  const binary = join(box.root, "npx");
  writeFileSync(binary, "#!/bin/sh\nexit 0\n");
  chmodSync(binary, 0o755);
  process.env.OPENSOCRATES_NPX_BIN = binary;
  return binary;
}

function configureFakeLaunchctl(box, { failBootout = false } = {}) {
  const statePath = join(box.root, "launchctl-state.json");
  writeFileSync(statePath, JSON.stringify({ loaded: false, bootstraps: 0, bootouts: 0 }));
  const binary = join(box.root, "launchctl");
  writeFileSync(
    binary,
    `#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
const statePath = ${JSON.stringify(statePath)};
const failBootout = ${JSON.stringify(failBootout)};
const state = JSON.parse(readFileSync(statePath, "utf8"));
const command = process.argv[2];
if (command === "print") process.exit(state.loaded ? 0 : 3);
if (command === "bootout") {
  if (failBootout) process.exit(9);
  state.loaded = false;
  state.bootouts += 1;
  writeFileSync(statePath, JSON.stringify(state));
  process.exit(0);
}
if (command === "bootstrap") {
  if (state.loaded) process.exit(5);
  state.loaded = true;
  state.bootstraps += 1;
  writeFileSync(statePath, JSON.stringify(state));
  process.exit(0);
}
process.exit(2);
`,
  );
  chmodSync(binary, 0o755);
  process.env.OPENSOCRATES_LAUNCHCTL_BIN = binary;
  process.env.OPENSOCRATES_NODE_BIN = process.execPath;
  delete process.env.OPENSOCRATES_SKIP_LAUNCHCTL;
  return {
    state: () => JSON.parse(readFileSync(statePath, "utf8")),
  };
}

function quiet(fn) {
  const log = console.log;
  const warn = console.warn;
  const error = console.error;
  const captured = [];
  console.log = (...a) => captured.push(a.join(" "));
  console.warn = (...a) => captured.push(a.join(" "));
  console.error = (...a) => captured.push(a.join(" "));
  return Promise.resolve()
    .then(fn)
    .then(
      (value) => ({ value, output: captured.join("\n") }),
      (error_) => ({ error: error_, output: captured.join("\n") }),
    )
    .finally(() => {
      console.log = log;
      console.warn = warn;
      console.error = error;
    });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
for (const host of ["claude", "codex"]) {
  test(`${host}: install -> status -> update -> verify -> remove`, async () => {
    const box = makeSandbox(host);
    try {
      const pkg = buildPackage(box.root, host);
      const args = ["--host", host, "--asset", pkg.asset, "--checksum", pkg.checksum];

      await withDarwinArm64(async () => {
        const install = await quiet(() => main(["install", ...args]));
        assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
        if (host === "codex") {
          assert.match(install.output, /open one interactive Codex session/);
          assert.match(install.output, /codex exec silently skips hooks/);
        } else {
          assert.doesNotMatch(install.output, /Codex approval required/);
        }
      });
      assert.equal(box.state().plugins.length, 1, "plugin was not registered");
      assert.ok(existsSync(join(box.managedRoot, ".opensocrates-managed.json")), "ownership marker missing");

      const status = await quiet(() => main(["status", "--host", host]));
      assert.equal(status.error, undefined);
      assert.match(status.output, new RegExp(`OpenSocrates ${PRODUCT_VERSION} is installed`));

      await withDarwinArm64(async () => {
        const update = await quiet(() => main(["update", ...args]));
        assert.equal(update.error, undefined, `update failed: ${update.error?.message}`);
      });
      assert.deepEqual(box.backups(), [], "update left a backup directory behind");

      const verify = await quiet(() => main(["verify", ...args]));
      assert.equal(verify.error, undefined);

      const remove = await quiet(() => main(["remove", "--host", host]));
      assert.equal(remove.error, undefined);
      assert.equal(box.state().plugins.length, 0, "plugin registration survived remove");
      assert.equal(box.state().marketplaces.length, 0, "marketplace survived remove");
      assert.equal(existsSync(box.managedRoot), false, "managed root survived remove");
    } finally {
      box.cleanup();
    }
  });

  test(`${host}: failed registration rolls back and restores the previous install`, async () => {
    const good = makeSandbox(host);
    let box = good;
    try {
      const pkg = buildPackage(good.root, host);
      const args = ["--host", host, "--asset", pkg.asset, "--checksum", pkg.checksum];
      await withDarwinArm64(async () => {
        const install = await quiet(() => main(["install", ...args]));
        assert.equal(install.error, undefined);
      });

      // Swap in a host binary that refuses plugin installation, keeping state.
      const failing = writeFakeHost(good.root, `${host}-failing`, {
        kind: host,
        failInstall: true,
      });
      writeFileSync(
        failing.binary,
        readFileSync(failing.binary, "utf8").replace(
          JSON.stringify(join(good.root, `${host}-failing-state.json`)),
          JSON.stringify(good.statePath),
        ),
      );
      chmodSync(failing.binary, 0o755);
      process.env[host === "claude" ? "CLAUDE_BIN" : "CODEX_BIN"] = failing.binary;

      const result = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
      assert.notEqual(result.error, undefined, "failed registration did not surface an error");
      // The previous installation must be back in place, not stranded.
      assert.ok(existsSync(box.managedRoot), "previous managed root was not restored");
      assert.deepEqual(box.backups(), [], "a backup directory was left behind after successful restore");
    } finally {
      box.cleanup();
    }
  });
}

for (const host of ["antigravity", "cursor", "grok"]) {
  test(`${host}: content-only plugin install -> status -> update -> verify -> remove`, async () => {
    const box = makeSandbox(host);
    try {
      const pkg = buildPackage(box.root, host);
      const args = ["--host", host, "--asset", pkg.asset, "--checksum", pkg.checksum];

      const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
      assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
      assert.match(install.output, new RegExp(`installed successfully for ${host}`));
      if (host === "cursor") assert.match(install.output, /Developer: Reload Window/);
      assert.doesNotMatch(install.output, /approval required/i);
      assert.ok(existsSync(join(box.managedRoot, "plugin.json")), "plugin manifest missing");
      assert.ok(existsSync(join(box.managedRoot, ".opensocrates-managed.json")), "ownership marker missing");
      assert.equal(existsSync(join(box.managedRoot, "runtime")), false, "runtime was installed");
      assert.equal(existsSync(join(box.managedRoot, "hooks")), false, "hooks were installed");

      const status = await quiet(() => main(["status", "--host", host]));
      assert.equal(status.error, undefined, `status failed: ${status.error?.message}`);
      assert.match(status.output, new RegExp(`OpenSocrates ${PRODUCT_VERSION} is installed`));
      if (host === "grok") {
        assert.match(status.output, /automatic native-skill selection/);
        assert.match(install.output, /invoke \/opensocrates explicitly/);
      } else {
        assert.match(status.output, /experimental and explicit-skill/);
      }

      const update = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
      assert.equal(update.error, undefined, `update failed: ${update.error?.message}`);
      assert.deepEqual(box.backups(), [], "update left a backup directory behind");

      const verify = await quiet(() => main(["verify", ...args]));
      assert.equal(verify.error, undefined, `verify failed: ${verify.error?.message}`);

      const remove = await quiet(() => main(["remove", "--host", host]));
      assert.equal(remove.error, undefined, `remove failed: ${remove.error?.message}`);
      assert.equal(existsSync(box.managedRoot), false, "managed root survived remove");
    } finally {
      box.cleanup();
    }
  });
}

test("opencode: install -> status -> verify -> update -> remove preserves unrelated files", async () => {
  const box = makeSandbox("opencode");
  try {
    const pkg = buildPackage(box.root, "opencode");
    const args = ["--host", "opencode", "--asset", pkg.asset, "--checksum", pkg.checksum];
    mkdirSync(join(box.home, "plugins"), { recursive: true });
    mkdirSync(join(box.home, "skills", "unrelated"), { recursive: true });
    writeFileSync(join(box.home, "plugins", "unrelated.js"), "export default {};\n");
    writeFileSync(join(box.home, "skills", "unrelated", "SKILL.md"), "# Unrelated\n");
    writeFileSync(join(box.home, "opencode.json"), '{"theme":"system"}\n');

    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
    assert.match(install.output, /stable chat\.message bridge/);
    assert.ok(existsSync(join(box.home, "plugins", "opensocrates.js")));
    assert.ok(existsSync(join(box.home, "plugins", ".opensocrates-managed.json")));
    assert.ok(existsSync(join(box.managedRoot, "SKILL.md")));
    assert.ok(existsSync(join(box.managedRoot, ".opensocrates-installation.json")));
    const desired = JSON.parse(readFileSync(join(box.root, "state", "desired-state.json"), "utf8"));
    assert.deepEqual(desired.installedHosts, ["opencode"]);
    assert.equal(desired.activeVersion, PRODUCT_VERSION);

    const status = await quiet(() => main(["status", "--host", "opencode"]));
    assert.equal(status.error, undefined, `status failed: ${status.error?.message}`);
    assert.match(status.output, /stable same-turn bridge/);

    const verify = await quiet(() => main(["verify", ...args]));
    assert.equal(verify.error, undefined, `verify failed: ${verify.error?.message}`);
    assert.match(verify.output, /verified installed bridge, skill inventory, and ownership/);

    const update = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.equal(update.error, undefined, `update failed: ${update.error?.message}`);
    assert.deepEqual(box.backups(), []);

    const remove = await quiet(() => main(["remove", "--host", "opencode"]));
    assert.equal(remove.error, undefined, `remove failed: ${remove.error?.message}`);
    assert.equal(existsSync(box.managedRoot), false);
    assert.equal(existsSync(join(box.home, "plugins", "opensocrates.js")), false);
    assert.equal(existsSync(join(box.home, "plugins", ".opensocrates-managed.json")), false);
    assert.equal(readFileSync(join(box.home, "plugins", "unrelated.js"), "utf8"), "export default {};\n");
    assert.equal(readFileSync(join(box.home, "skills", "unrelated", "SKILL.md"), "utf8"), "# Unrelated\n");
    assert.equal(readFileSync(join(box.home, "opencode.json"), "utf8"), '{"theme":"system"}\n');
  } finally {
    box.cleanup();
  }
});

test("opencode: refuses unowned and symbolic-link trust-boundary paths", async () => {
  const box = makeSandbox("opencode");
  try {
    const pkg = buildPackage(box.root, "opencode");
    const args = ["--host", "opencode", "--asset", pkg.asset, "--checksum", pkg.checksum];
    mkdirSync(join(box.home, "plugins"), { recursive: true });
    writeFileSync(join(box.home, "plugins", "opensocrates.js"), "// user-owned\n");
    const unowned = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.notEqual(unowned.error, undefined);
    assert.match(unowned.error.message, /partial or unowned/);
    assert.equal(readFileSync(join(box.home, "plugins", "opensocrates.js"), "utf8"), "// user-owned\n");

    rmSync(join(box.home, "plugins", "opensocrates.js"));
    mkdirSync(join(box.home, "real-plugins"));
    rmSync(join(box.home, "plugins"), { recursive: true });
    symlinkSync(join(box.home, "real-plugins"), join(box.home, "plugins"), "dir");
    const linked = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.notEqual(linked.error, undefined);
    assert.match(linked.error.message, /unsafe OpenCode plugins directory/);
  } finally {
    box.cleanup();
  }
});

test("opencode: a post-removal scheduler failure restores skill, bridge, and sidecar", async () => {
  const box = makeSandbox("opencode");
  try {
    const pkg = buildPackage(box.root, "opencode");
    const args = ["--host", "opencode", "--asset", pkg.asset, "--checksum", pkg.checksum];
    await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    configureFakeNpx(box);
    configureFakeLaunchctl(box, { failBootout: true });
    const enabled = await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "opencode"])));
    assert.equal(enabled.error, undefined, `auto-update enable failed: ${enabled.error?.message}`);

    const removed = await withDarwinArm64(() => quiet(() => main(["remove", "--host", "opencode"])));
    assert.notEqual(removed.error, undefined, "scheduler failure did not abort removal");
    assert.match(removed.error.message, /could not stop/);
    assert.ok(existsSync(join(box.managedRoot, "SKILL.md")));
    assert.ok(existsSync(join(box.home, "plugins", "opensocrates.js")));
    assert.ok(existsSync(join(box.home, "plugins", ".opensocrates-managed.json")));
    assert.deepEqual(JSON.parse(readFileSync(join(box.root, "state", "desired-state.json"), "utf8")).installedHosts, [
      "opencode",
    ]);
    const verify = await quiet(() => main(["verify", ...args]));
    assert.equal(
      verify.error,
      undefined,
      `restored OpenCode installation failed verification: ${verify.error?.message}`,
    );
  } finally {
    box.cleanup();
  }
});

// Regression: OPENCODE_CONFIG_DIR used to short-circuit requireHostCli, so an
// install could place the executing bridge without ever confirming the host
// was a supported OpenCode. The config directory selects where files go; it
// must not decide whether the host is supported.
test("opencode: OPENCODE_CONFIG_DIR does not waive the CLI/version gate", async () => {
  const box = makeSandbox("opencode");
  try {
    const pkg = buildPackage(box.root, "opencode");
    const args = ["--host", "opencode", "--asset", pkg.asset, "--checksum", pkg.checksum];
    // The sandbox always sets OPENCODE_CONFIG_DIR. Point the binary at a path
    // that does not exist: the gate must still refuse the install.
    process.env.OPENCODE_BIN = join(box.root, "absent-opencode");

    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.notEqual(install.error, undefined, "install proceeded without a usable OpenCode CLI");
    assert.equal(existsSync(box.managedRoot), false, "a gated install still wrote the skill");
    assert.equal(
      existsSync(join(box.home, "plugins", "opensocrates.js")),
      false,
      "a gated install still wrote the executing bridge",
    );
  } finally {
    box.cleanup();
  }
});

// Regression: the package declares minimum_opencode_version 1.18.18 with a
// fail-closed <2.0.0 ceiling. Both bounds must be enforced at install time.
for (const [label, reported] of [
  ["below the floor", "1.18.17"],
  ["at or above the ceiling", "2.0.0"],
]) {
  test(`opencode: install refuses a host version ${label}`, async () => {
    const box = makeSandbox("opencode");
    try {
      const pkg = buildPackage(box.root, "opencode");
      const args = ["--host", "opencode", "--asset", pkg.asset, "--checksum", pkg.checksum];
      const fake = join(box.root, `opencode-${reported}`);
      writeFileSync(fake, `#!/bin/sh\necho "${reported} (fake)"\nexit 0\n`);
      chmodSync(fake, 0o755);
      process.env.OPENCODE_BIN = fake;

      const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
      assert.notEqual(install.error, undefined, `install accepted OpenCode ${reported}`);
      assert.match(install.error.message, /OpenCode >=1\.18\.18 and <2\.0\.0 is required/);
      assert.equal(existsSync(box.managedRoot), false, "a rejected version still wrote the skill");
    } finally {
      box.cleanup();
    }
  });
}

test("grok: staging and rollback directories stay outside the scanned plugins directory", async () => {
  const box = makeSandbox("grok");
  try {
    // The installer canonicalizes the host home, so compare against the
    // resolved sandbox home rather than the literal one: macOS reports
    // /private/var for a /var temporary directory.
    const home = realpathSync(box.home);
    const placement = transientPathsFor("grok");
    assert.equal(placement.parent, join(home, "plugins"));
    assert.equal(placement.transient, home);
    assert.equal(
      placement.transient.startsWith(`${placement.parent}/`),
      false,
      "a transient directory would be discoverable as a second Grok plugin",
    );

    // An install must leave the scanned directory holding the managed root
    // only: a staging or backup directory left there by an interrupted run is
    // discovered by Grok as a duplicate OpenSocrates plugin.
    const pkg = buildPackage(box.root, "grok");
    const args = ["--host", "grok", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
    assert.deepEqual(readdirSync(placement.parent), [MARKETPLACE]);

    const update = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.equal(update.error, undefined, `update failed: ${update.error?.message}`);
    assert.deepEqual(readdirSync(placement.parent), [MARKETPLACE]);
    assert.deepEqual(
      readdirSync(home).filter((entry) => entry.startsWith(".opensocrates.")),
      [],
      "a committed transaction left a transient directory in the Grok home",
    );
  } finally {
    box.cleanup();
  }
});

for (const host of ["antigravity", "cursor", "claude", "codex"]) {
  test(`${host}: transient directories keep their established location`, () => {
    const box = makeSandbox(host);
    try {
      const placement = transientPathsFor(host);
      assert.equal(placement.transient, placement.parent);
      assert.equal(placement.parent, dirname(placement.root));
    } finally {
      box.cleanup();
    }
  });
}

test("grok: files stay inspectable and removable without a runnable Grok CLI", async () => {
  const box = makeSandbox("grok");
  try {
    const pkg = buildPackage(box.root, "grok");
    const args = ["--host", "grok", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);

    // Grok Build itself can be uninstalled while its managed OpenSocrates
    // files remain. Reading and removing what this installer owns is plain
    // file ownership work and must not depend on the host command.
    process.env.GROK_BIN = join(box.root, "uninstalled-grok");

    const status = await quiet(() => main(["status", "--host", "grok"]));
    assert.equal(status.error, undefined, `status failed: ${status.error?.message}`);
    assert.match(status.output, new RegExp(`OpenSocrates ${PRODUCT_VERSION} is installed`));
    assert.match(status.output, /could not read Grok Build plugin state/);

    const remove = await quiet(() => main(["remove", "--host", "grok"]));
    assert.equal(remove.error, undefined, `remove failed: ${remove.error?.message}`);
    assert.equal(existsSync(box.managedRoot), false, "managed root survived remove");
    assert.deepEqual(
      readdirSync(box.home).filter((entry) => entry.startsWith(".opensocrates.")),
      [],
      "remove left a rollback directory behind",
    );
  } finally {
    box.cleanup();
  }
});

test("grok: a stale managed directory cannot block an all-host lifecycle", async () => {
  const box = makeSandbox("grok");
  try {
    for (const [binaryKey, configKey] of [
      ["AGY_BIN", "ANTIGRAVITY_CONFIG_DIR"],
      ["CLAUDE_BIN", "CLAUDE_CONFIG_DIR"],
      ["CODEX_BIN", "CODEX_HOME"],
      ["CURSOR_BIN", "CURSOR_CONFIG_DIR"],
    ]) {
      process.env[binaryKey] = join(box.root, `unavailable-${binaryKey.toLowerCase()}`);
      process.env[configKey] = join(box.root, `isolated-${configKey.toLowerCase()}`);
    }
    const pkg = buildPackage(box.root, "grok");
    const args = ["--host", "grok", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);

    process.env.GROK_BIN = join(box.root, "uninstalled-grok");
    const remove = await quiet(() => main(["remove", "--host", "all"]));
    assert.equal(remove.error, undefined, `all-host remove failed: ${remove.error?.message}`);
    assert.equal(existsSync(box.managedRoot), false, "managed root survived all-host remove");
  } finally {
    box.cleanup();
  }
});

test("grok: disabled plugin state is visible without mutating unrelated configuration", async () => {
  const box = makeSandbox("grok");
  try {
    const pkg = buildPackage(box.root, "grok");
    const args = ["--host", "grok", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
    const state = box.state();
    state.grokEnabled = false;
    writeFileSync(box.statePath, JSON.stringify(state));
    const status = await quiet(() => main(["status", "--host", "grok"]));
    assert.equal(status.error, undefined, `status failed: ${status.error?.message}`);
    assert.match(status.output, /installed but disabled/);
    assert.ok(existsSync(box.managedRoot), "status mutated the managed plugin root");
  } finally {
    box.cleanup();
  }
});

test("grok: --host all preserves desired-state migration and unrelated Grok files", async () => {
  const box = makeSandbox("grok");
  try {
    for (const [binaryKey, configKey] of [
      ["AGY_BIN", "ANTIGRAVITY_CONFIG_DIR"],
      ["CLAUDE_BIN", "CLAUDE_CONFIG_DIR"],
      ["CODEX_BIN", "CODEX_HOME"],
      ["CURSOR_BIN", "CURSOR_CONFIG_DIR"],
    ]) {
      process.env[binaryKey] = join(box.root, `unavailable-${binaryKey.toLowerCase()}`);
      process.env[configKey] = join(box.root, `isolated-${configKey.toLowerCase()}`);
    }
    const unrelatedPlugin = join(box.home, "plugins", "unrelated", "plugin.json");
    const unrelatedConfig = join(box.home, "config.toml");
    mkdirSync(dirname(unrelatedPlugin), { recursive: true });
    writeFileSync(unrelatedPlugin, '{"name":"unrelated"}\n');
    writeFileSync(unrelatedConfig, "theme = 'dark'\n");

    const pkg = buildPackage(box.root, "grok");
    const directArgs = ["--host", "grok", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...directArgs])));
    assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
    assert.deepEqual(
      JSON.parse(readFileSync(join(box.root, "state", "desired-state.json"), "utf8"))
        .installedHosts,
      ["grok"],
    );

    const allArgs = [
      "--host", "all", "--asset-grok", pkg.asset, "--checksum-grok", pkg.checksum,
    ];
    const update = await withDarwinArm64(() => quiet(() => main(["update", ...allArgs])));
    assert.equal(update.error, undefined, `all-host update failed: ${update.error?.message}`);
    assert.equal(readFileSync(unrelatedConfig, "utf8"), "theme = 'dark'\n");
    assert.equal(readFileSync(unrelatedPlugin, "utf8"), '{"name":"unrelated"}\n');

    const remove = await quiet(() => main(["remove", "--host", "all"]));
    assert.equal(remove.error, undefined, `all-host remove failed: ${remove.error?.message}`);
    assert.equal(existsSync(box.managedRoot), false);
    assert.equal(existsSync(unrelatedConfig), true);
    assert.equal(existsSync(unrelatedPlugin), true);
  } finally {
    box.cleanup();
  }
});

test("claude: supported list wrappers preserve the complete lifecycle", async () => {
  const box = makeSandbox("claude", {
    claudeMarketplaceWrapper: true,
    claudePluginWrapper: true,
  });
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `wrapped install failed: ${install.error?.message}`);
    const status = await quiet(() => main(["status", "--host", "claude"]));
    assert.equal(status.error, undefined, `wrapped status failed: ${status.error?.message}`);
    assert.match(status.output, /is installed/);
    const remove = await quiet(() => main(["remove", "--host", "claude"]));
    assert.equal(remove.error, undefined, `wrapped remove failed: ${remove.error?.message}`);
  } finally {
    box.cleanup();
  }
});

test("claude: malformed list wrappers fail closed before mutation", async () => {
  const box = makeSandbox("claude", { malformedClaudeMarketplaceList: true });
  try {
    const pkg = buildPackage(box.root, "claude");
    const result = await withDarwinArm64(() =>
      quiet(() => main(["install", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum])),
    );
    assert.notEqual(result.error, undefined, "malformed wrapper was accepted");
    assert.match(result.error.message, /marketplace list returned an unexpected schema/);
    assert.equal(existsSync(box.managedRoot), false, "malformed preflight mutated the managed root");
  } finally {
    box.cleanup();
  }
});

test("claude: duplicate, conflicting, and invalid managed entries fail closed", async () => {
  const cases = [
    [{ duplicateClaudeMarketplace: true }, /duplicate entries for opensocrates/],
    [{ duplicateClaudePlugin: true }, /duplicate entries for opensocrates@opensocrates/],
    [{ conflictingClaudeMarketplaceRoots: true }, /reported conflicting roots/],
    [{ invalidClaudePluginEnabled: true }, /reported an invalid state/],
    [{ malformedClaudePluginList: true }, /plugin list returned an unexpected schema/],
  ];
  for (const [options, expected] of cases) {
    const box = makeSandbox("claude");
    try {
      const pkg = buildPackage(box.root, "claude");
      const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
      const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
      assert.equal(install.error, undefined, `setup install failed: ${install.error?.message}`);
      replaceSandboxHost(box, "claude", `claude-schema-${Object.keys(options)[0]}`, options);
      const status = await quiet(() => main(["status", "--host", "claude"]));
      assert.notEqual(status.error, undefined, `${Object.keys(options)[0]} was accepted`);
      assert.match(status.error.message, expected);
      assert.ok(existsSync(box.managedRoot), "schema rejection changed the managed root");
    } finally {
      box.cleanup();
    }
  }
});

test("claude: disabled status is visible and update re-enables the plugin", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `setup install failed: ${install.error?.message}`);
    const state = box.state();
    state.plugins[0].enabled = false;
    writeFileSync(box.statePath, JSON.stringify(state));

    const status = await quiet(() => main(["status", "--host", "claude"]));
    assert.equal(status.error, undefined);
    assert.match(status.output, /installed but disabled/);

    const update = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.equal(update.error, undefined, `update failed: ${update.error?.message}`);
    assert.equal(box.state().plugins[0].enabled, true, "update did not re-enable Claude");
  } finally {
    box.cleanup();
  }
});

test("claude: failed update restores the previous disabled registration", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `setup install failed: ${install.error?.message}`);
    const state = box.state();
    state.plugins[0].enabled = false;
    state.installAttempts = 0;
    writeFileSync(box.statePath, JSON.stringify(state));
    replaceSandboxHost(box, "claude", "claude-disabled-rollback", {
      failInstallOnce: true,
    });

    const update = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.notEqual(update.error, undefined, "sabotaged update reported success");
    assert.equal(box.state().plugins.length, 1, "previous disabled plugin was not restored");
    assert.equal(box.state().plugins[0].enabled, false, "rollback re-enabled the disabled plugin");
  } finally {
    box.cleanup();
  }
});

test("claude: supported-version JSON fixture contains no local evidence values", () => {
  const fixturePath = join("installer", "fixtures", "claude-cli", "2.1.226.sanitized.json");
  const text = readFileSync(fixturePath, "utf8");
  const fixture = JSON.parse(text);
  assert.equal(fixture.claudeCodeVersion, "2.1.226");
  assert.equal(fixture.marketplaceList.container, "array");
  assert.equal(fixture.pluginList.entries[0].enabled, true);
  assert.equal(fixture.privacy.credentialsPresent, false);
  assert.doesNotMatch(text, /\/Users\//u);
  assert.doesNotMatch(text, /20\d\d-\d\d-\d\dT\d\d:/u);
});

test("all hosts: fresh install uses one desired version and one manifest", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    const result = await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    assert.equal(result.error, undefined, `all-host install failed: ${result.error?.message}`);
    for (const host of ["claude", "codex"]) {
      assert.equal(box.state(host).plugins.length, 1, `${host} was not installed`);
      assert.ok(
        existsSync(join(box.managedRoots[host], ".opensocrates-managed.json")),
        `${host} ownership marker is missing`,
      );
    }
    const desired = box.desired();
    assert.deepEqual(desired.installedHosts, ["claude", "codex"]);
    assert.equal(desired.activeVersion, PRODUCT_VERSION);
    assert.deepEqual(inspectManagedLayout(box.managedRoots), {
      claudePublicSkills: ["opensocrates"],
      claudeCommandsPresent: false,
      codexControllerPresent: true,
    });

    const status = await quiet(() => main(["status", "--host", "all"]));
    assert.equal(status.error, undefined);
    assert.match(status.output, /claude: installed .* \(in sync\)/);
    assert.match(status.output, /codex: installed .* \(in sync\)/);
    assert.match(status.output, /Overall: no detected drift/);
  } finally {
    box.cleanup();
  }
});

test("all hosts: OpenCode joins desired state and preserves unrelated config", async () => {
  const box = makeAllSandbox({ includeOpenCode: true });
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
      opencode: buildPackage(box.root, "opencode"),
    };
    mkdirSync(join(box.homes.opencode, "plugins"), { recursive: true });
    writeFileSync(join(box.homes.opencode, "plugins", "unrelated.js"), "export default {};\n");
    writeFileSync(join(box.homes.opencode, "opencode.json"), '{"theme":"system"}\n');

    const result = await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    assert.equal(result.error, undefined, `all-host install with OpenCode failed: ${result.error?.message}`);
    assert.deepEqual(box.desired().installedHosts, ["claude", "codex", "opencode"]);
    assert.ok(existsSync(join(box.managedRoots.opencode, "SKILL.md")));
    assert.ok(existsSync(join(box.homes.opencode, "plugins", "opensocrates.js")));
    assert.equal(readFileSync(join(box.homes.opencode, "plugins", "unrelated.js"), "utf8"), "export default {};\n");
    assert.equal(readFileSync(join(box.homes.opencode, "opencode.json"), "utf8"), '{"theme":"system"}\n');
  } finally {
    box.cleanup();
  }
});

test("status all reports a desired host that is no longer active as drift", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    const codexState = box.state("codex");
    codexState.plugins = [];
    writeFileSync(box.hosts.codex.statePath, JSON.stringify(codexState));

    const status = await quiet(() => main(["status", "--host", "all"]));
    assert.equal(status.error, undefined);
    assert.match(status.output, /codex: not installed \(drift: desired host is missing\)/);
    assert.match(status.output, /Overall: drift detected/);
  } finally {
    box.cleanup();
  }
});

test("status all reports a disabled Claude plugin as drift", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    const claudeState = box.state("claude");
    claudeState.plugins[0].enabled = false;
    writeFileSync(box.hosts.claude.statePath, JSON.stringify(claudeState));

    const status = await quiet(() => main(["status", "--host", "all"]));
    assert.equal(status.error, undefined);
    assert.match(status.output, /claude: installed but disabled .*desired host is not active/);
    assert.match(status.output, /Overall: drift detected/);
  } finally {
    box.cleanup();
  }
});

test("all hosts: a required-host preflight failure changes neither host", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    const sentinels = {};
    for (const host of ["claude", "codex"]) {
      sentinels[host] = join(box.managedRoots[host], `preflight-${host}.txt`);
      writeFileSync(sentinels[host], "previous installation\n");
    }
    replaceAllHostBinary(box, "claude", "claude-no-auth", {
      failAuth: true,
    });

    const result = await withDarwinArm64(() => quiet(() => main(["update", ...allAssetArgs(packages)])));
    assert.notEqual(result.error, undefined, "update ignored a required host preflight failure");
    assert.match(result.error.message, /preflight failed for claude/);
    for (const host of ["claude", "codex"]) {
      assert.ok(existsSync(sentinels[host]), `${host} changed before all preflights passed`);
      assert.equal(box.state(host).plugins.length, 1, `${host} registration changed`);
    }
  } finally {
    box.cleanup();
  }
});

test("all hosts: a second-host activation failure rolls both hosts back", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    const sentinels = {};
    for (const host of ["claude", "codex"]) {
      sentinels[host] = join(box.managedRoots[host], `rollback-${host}.txt`);
      writeFileSync(sentinels[host], "previous installation\n");
    }
    const codexState = box.state("codex");
    codexState.installAttempts = 0;
    writeFileSync(box.hosts.codex.statePath, JSON.stringify(codexState));
    replaceAllHostBinary(box, "codex", "codex-fail-once", {
      failInstallOnce: true,
    });

    const result = await withDarwinArm64(() => quiet(() => main(["update", ...allAssetArgs(packages)])));
    assert.notEqual(result.error, undefined, "cross-host activation unexpectedly succeeded");
    for (const host of ["claude", "codex"]) {
      assert.ok(existsSync(sentinels[host]), `${host} previous files were not restored`);
      assert.equal(box.state(host).plugins.length, 1, `${host} previous registration was not restored`);
    }
    assert.deepEqual(box.desired().installedHosts, ["claude", "codex"]);
  } finally {
    box.cleanup();
  }
});

test("all hosts: a fresh partial activation leaves neither host installed", async () => {
  const box = makeAllSandbox({ codex: { failInstallOnce: true } });
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    const result = await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    assert.notEqual(result.error, undefined, "partial activation reported success");
    for (const host of ["claude", "codex"]) {
      assert.equal(box.state(host).plugins.length, 0, `${host} registration survived rollback`);
      assert.equal(existsSync(box.managedRoots[host]), false, `${host} root survived rollback`);
    }
  } finally {
    box.cleanup();
  }
});

test("claude: update replaces the v1.1.0 multi-skill projection", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    const stale = join(box.managedRoot, "plugins", MARKETPLACE, "skills", "critical-thinking", "SKILL.md");
    mkdirSync(join(stale, ".."), { recursive: true });
    writeFileSync(stale, "legacy method skill\n");
    assert.ok(existsSync(stale), "stale skill fixture was not created");

    const result = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.equal(result.error, undefined, `update failed: ${result.error?.message}`);
    assert.equal(existsSync(stale), false, "stale top-level method skill survived update");
  } finally {
    box.cleanup();
  }
});

test("auto-update: enable is opt-in and remove all cannot orphan the LaunchAgent", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    const npx = configureFakeNpx(box);
    const enabled = await withDarwinArm64(() =>
      quiet(() => main(["auto-update", "enable", "--host", "all", "--interval-hours", "12"])),
    );
    assert.equal(enabled.error, undefined, `enable failed: ${enabled.error?.message}`);
    assert.ok(existsSync(box.launchAgent), "LaunchAgent was not installed");
    const plist = readFileSync(box.launchAgent, "utf8");
    assert.match(plist, new RegExp(npx.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.doesNotMatch(plist, /prompt|transcript|workspace/iu);
    assert.equal(box.desired().autoUpdate.enabled, true);
    assert.deepEqual(box.desired().autoUpdate.hosts, ["claude", "codex"]);
    assert.equal(box.desired().updatePolicy.intervalHours, 12);
    assert.equal(statSync(box.launchAgent).mode & 0o777, 0o600);
    assert.equal(statSync(join(box.root, "state")).mode & 0o777, 0o700);

    const removed = await quiet(() => main(["remove", "--host", "all"]));
    assert.equal(removed.error, undefined, `remove all failed: ${removed.error?.message}`);
    assert.equal(existsSync(box.launchAgent), false, "remove all left an orphaned LaunchAgent");
    assert.deepEqual(box.desired().installedHosts, []);
    assert.equal(box.desired().autoUpdate.enabled, false);
    assert.deepEqual(box.desired().autoUpdate.hosts, []);
    assert.equal(existsSync(box.managedRoots.claude), false);
    assert.equal(existsSync(box.managedRoots.codex), false);
  } finally {
    box.cleanup();
  }
});

test("auto-update: a single-host scope preserves the complete installed-host set", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    configureFakeNpx(box);
    const enabled = await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "claude"])));
    assert.equal(enabled.error, undefined, `single-host enable failed: ${enabled.error?.message}`);
    assert.deepEqual(box.desired().installedHosts, ["claude", "codex"]);
    assert.deepEqual(box.desired().autoUpdate.hosts, ["claude"]);

    const initialStatus = await quiet(() => main(["status", "--host", "all"]));
    assert.equal(initialStatus.error, undefined);
    assert.match(initialStatus.output, /claude: installed .* \(in sync\)/);
    assert.match(initialStatus.output, /codex: installed .* \(in sync\)/);
    assert.match(initialStatus.output, /Overall: no detected drift/);

    for (const host of ["claude", "codex"]) {
      const state = box.state(host);
      state.plugins[0].version = "1.1.0";
      writeFileSync(box.hosts[host].statePath, JSON.stringify(state));
    }
    const previous = box.desired();
    previous.activeVersion = "1.1.0";
    writeFileSync(join(box.root, "state", "desired-state.json"), `${JSON.stringify(previous, null, 2)}\n`);

    const scheduled = await withDarwinArm64(() =>
      quiet(() => main(["auto-update", "run", "--force", ...allAssetArgs(packages)])),
    );
    assert.equal(scheduled.error, undefined, `single-host update failed: ${scheduled.error?.message}`);
    assert.equal(box.state("claude").plugins[0].version, PRODUCT_VERSION);
    assert.equal(box.state("codex").plugins[0].version, "1.1.0");
    assert.deepEqual(box.desired().installedHosts, ["claude", "codex"]);
    assert.deepEqual(box.desired().autoUpdate.hosts, ["claude"]);
    assert.deepEqual(box.receipt().hosts, [{ host: "claude", result: "updated" }]);

    const reconciled = await withDarwinArm64(() => quiet(() => main(["update", ...allAssetArgs(packages)])));
    assert.equal(reconciled.error, undefined, `all-host reconciliation failed: ${reconciled.error?.message}`);
    assert.equal(box.state("codex").plugins[0].version, PRODUCT_VERSION);
    const finalStatus = await quiet(() => main(["status", "--host", "all"]));
    assert.match(finalStatus.output, /Overall: no detected drift/);
  } finally {
    box.cleanup();
  }
});

test("auto-update: partial removal rewrites the remaining scheduler scope", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    configureFakeNpx(box);
    await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "all"])));

    const removed = await withDarwinArm64(() => quiet(() => main(["remove", "--host", "claude"])));
    assert.equal(removed.error, undefined, `partial remove failed: ${removed.error?.message}`);
    assert.deepEqual(box.desired().installedHosts, ["codex"]);
    assert.equal(box.desired().autoUpdate.enabled, true);
    assert.deepEqual(box.desired().autoUpdate.hosts, ["codex"]);
    assert.equal(existsSync(box.managedRoots.claude), false);
    assert.equal(existsSync(box.managedRoots.codex), true);
    const plist = readFileSync(box.launchAgent, "utf8");
    assert.doesNotMatch(plist, /<key>CLAUDE_BIN<\/key>/);
    assert.match(plist, /<key>CODEX_BIN<\/key>/);

    const status = await quiet(() => main(["status", "--host", "all"]));
    assert.equal(status.error, undefined);
    assert.match(status.output, /Overall: no detected drift/);
  } finally {
    box.cleanup();
  }
});

test("auto-update: reconfiguration replaces a loaded LaunchAgent cleanly", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    configureFakeNpx(box);
    const launchctl = configureFakeLaunchctl(box);

    const first = await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "all"])));
    assert.equal(first.error, undefined, `first enable failed: ${first.error?.message}`);
    const second = await withDarwinArm64(() =>
      quiet(() => main(["auto-update", "enable", "--host", "all", "--channel", "next", "--interval-hours", "6"])),
    );
    assert.equal(second.error, undefined, `reconfiguration failed: ${second.error?.message}`);
    assert.deepEqual(launchctl.state(), {
      loaded: true,
      bootstraps: 2,
      bootouts: 1,
    });
    const plist = readFileSync(box.launchAgent, "utf8");
    assert.match(plist, /opensocrates@next/);
    assert.match(plist, /<key>CLAUDE_BIN<\/key>/);
    assert.match(plist, /<key>CODEX_BIN<\/key>/);
    assert.match(plist, /<key>PATH<\/key>/);

    const disabled = await quiet(() => main(["auto-update", "disable"]));
    assert.equal(disabled.error, undefined, `disable failed: ${disabled.error?.message}`);
    assert.deepEqual(launchctl.state(), {
      loaded: false,
      bootstraps: 2,
      bootouts: 2,
    });
    assert.equal(existsSync(box.launchAgent), false);
  } finally {
    box.cleanup();
  }
});

test("auto-update: a successful check reconciles every desired host", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    for (const host of ["claude", "codex"]) {
      const state = box.state(host);
      state.plugins[0].version = "1.1.0";
      writeFileSync(box.hosts[host].statePath, JSON.stringify(state));
    }
    const desired = box.desired();
    desired.activeVersion = null;
    writeFileSync(join(box.root, "state", "desired-state.json"), `${JSON.stringify(desired, null, 2)}\n`);
    configureFakeNpx(box);
    await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "all"])));
    assert.equal(box.desired().activeVersion, "1.1.0");

    const result = await withDarwinArm64(() =>
      quiet(() => main(["auto-update", "run", "--force", ...allAssetArgs(packages)])),
    );
    assert.equal(result.error, undefined, `scheduled update failed: ${result.error?.message}`);
    for (const host of ["claude", "codex"]) {
      assert.equal(box.state(host).plugins[0].version, PRODUCT_VERSION);
    }
    assert.equal(box.desired().activeVersion, PRODUCT_VERSION);
    assert.ok(box.desired().lastSuccessfulUpdateAt);
    assert.equal(box.receipt().result, "updated");
  } finally {
    box.cleanup();
  }
});

test("auto-update: major releases remain blocked unless explicitly allowed", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    for (const host of ["claude", "codex"]) {
      const state = box.state(host);
      state.plugins[0].version = "0.9.0";
      writeFileSync(box.hosts[host].statePath, JSON.stringify(state));
    }
    const desired = box.desired();
    desired.activeVersion = "0.9.0";
    writeFileSync(join(box.root, "state", "desired-state.json"), `${JSON.stringify(desired, null, 2)}\n`);
    configureFakeNpx(box);
    await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "all"])));

    const result = await withDarwinArm64(() =>
      quiet(() => main(["auto-update", "run", "--force", ...allAssetArgs(packages)])),
    );
    assert.equal(result.error, undefined, `major-version policy check failed: ${result.error?.message}`);
    assert.equal(box.receipt().result, "blocked");
    assert.equal(box.receipt().errorCategory, "major-policy");
    assert.equal(box.desired().activeVersion, "0.9.0");
    for (const host of ["claude", "codex"]) {
      assert.equal(box.state(host).plugins[0].version, "0.9.0");
    }
  } finally {
    box.cleanup();
  }
});

test("auto-update: checksum failure preserves both hosts and records only a category", async () => {
  const box = makeAllSandbox();
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    configureFakeNpx(box);
    await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "all"])));
    const desired = box.desired();
    desired.activeVersion = "1.1.0";
    writeFileSync(join(box.root, "state", "desired-state.json"), `${JSON.stringify(desired, null, 2)}\n`);
    const sentinels = {};
    for (const host of ["claude", "codex"]) {
      sentinels[host] = join(box.managedRoots[host], `checksum-${host}.txt`);
      writeFileSync(sentinels[host], "previous installation\n");
    }
    writeFileSync(packages.codex.checksum, `${"0".repeat(64)}  ${packages.codex.asset.split("/").pop()}\n`);

    const result = await withDarwinArm64(() =>
      quiet(() => main(["auto-update", "run", "--force", ...allAssetArgs(packages)])),
    );
    assert.notEqual(result.error, undefined, "checksum failure reported success");
    for (const host of ["claude", "codex"]) {
      assert.ok(existsSync(sentinels[host]), `${host} changed before package verification completed`);
      assert.equal(box.state(host).plugins.length, 1, `${host} registration changed`);
    }
    const receipt = box.receipt();
    assert.equal(receipt.result, "failed");
    assert.equal(receipt.errorCategory, "verification");
    assert.deepEqual(
      Object.keys(receipt).sort(),
      ["checkedAt", "errorCategory", "hosts", "result", "schema", "version"].sort(),
    );
    assert.equal(statSync(join(box.root, "state", "auto-update-receipt.json")).mode & 0o777, 0o600);
  } finally {
    box.cleanup();
  }
});

test("auto-update: offline check preserves the active version and records network failure", async () => {
  const box = makeAllSandbox();
  const originalFetch = globalThis.fetch;
  try {
    const packages = {
      claude: buildPackage(box.root, "claude"),
      codex: buildPackage(box.root, "codex"),
    };
    await withDarwinArm64(() => quiet(() => main(["install", ...allAssetArgs(packages)])));
    configureFakeNpx(box);
    await withDarwinArm64(() => quiet(() => main(["auto-update", "enable", "--host", "all"])));
    const desired = box.desired();
    desired.activeVersion = "1.1.0";
    writeFileSync(join(box.root, "state", "desired-state.json"), `${JSON.stringify(desired, null, 2)}\n`);
    globalThis.fetch = async () => {
      throw new Error("offline network");
    };

    const result = await withDarwinArm64(() => quiet(() => main(["auto-update", "run", "--force"])));
    assert.notEqual(result.error, undefined, "offline update reported success");
    assert.equal(box.receipt().errorCategory, "network");
    assert.equal(box.desired().activeVersion, "1.1.0");
    for (const host of ["claude", "codex"]) {
      assert.equal(box.state(host).plugins.length, 1, `${host} was changed while offline`);
    }
  } finally {
    globalThis.fetch = originalFetch;
    box.cleanup();
  }
});

test("lifecycle lock rejects a concurrent operation and is released afterward", async () => {
  const box = makeAllSandbox();
  let releaseFirst;
  let markEntered;
  const gate = new Promise((resolve) => {
    releaseFirst = resolve;
  });
  const entered = new Promise((resolve) => {
    markEntered = resolve;
  });
  try {
    const first = withOperationLock(async () => {
      markEntered();
      await gate;
    });
    await entered;
    const second = await quiet(() => withOperationLock(async () => undefined));
    assert.notEqual(second.error, undefined, "a concurrent lifecycle operation acquired the lock");
    assert.match(second.error.message, /already running/);
    const lock = join(box.root, "state", "lifecycle.lock");
    assert.equal(existsSync(lock), true, "the active operation's lock disappeared");
    releaseFirst();
    await first;
    assert.equal(existsSync(lock), false, "the completed operation left its lock behind");
  } finally {
    releaseFirst?.();
    box.cleanup();
  }
});

test("claude: legacy registration warns on status and does not block remove", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    await withDarwinArm64(async () => {
      const install = await quiet(() =>
        main(["install", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum]),
      );
      assert.equal(install.error, undefined);
    });

    // Inject a pre-1.0 case-variant registration alongside the managed one.
    const state = box.state();
    state.marketplaces.push({
      name: "OpenSocrates",
      source: "local",
      path: "/legacy",
    });
    state.plugins.push({
      id: "opensocrates@OpenSocrates",
      version: "0.9.0",
    });
    writeFileSync(box.statePath, JSON.stringify(state));

    const status = await quiet(() => main(["status", "--host", "claude"]));
    assert.equal(status.error, undefined, "legacy registration blocked status");
    assert.match(status.output, /warning: a legacy Claude marketplace/);

    const remove = await quiet(() => main(["remove", "--host", "claude"]));
    assert.equal(remove.error, undefined, "legacy registration blocked remove");

    const after = box.state();
    assert.ok(
      after.marketplaces.some((entry) => entry.name === "OpenSocrates"),
      "remove deleted the legacy marketplace",
    );
    assert.ok(
      after.plugins.some((entry) => entry.id === "opensocrates@OpenSocrates"),
      "remove deleted the legacy plugin",
    );
  } finally {
    box.cleanup();
  }
});

test("claude: legacy registration still blocks install", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const state = box.state();
    state.marketplaces.push({
      name: "OpenSocrates",
      source: "local",
      path: "/legacy",
    });
    writeFileSync(box.statePath, JSON.stringify(state));
    const result = await withDarwinArm64(() =>
      quiet(() => main(["install", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum])),
    );
    assert.notEqual(result.error, undefined, "install proceeded despite a legacy registration");
    assert.match(result.error.message, /legacy Claude marketplace/);
  } finally {
    box.cleanup();
  }
});

test("claude: canonicalizes a host-reported marketplace path through a symlink", async () => {
  const box = makeSandbox("claude");
  try {
    const homeAlias = join(box.root, "claude-home-alias");
    symlinkSync(box.home, homeAlias, "dir");
    process.env.CLAUDE_CONFIG_DIR = homeAlias;

    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    await withDarwinArm64(async () => {
      const install = await quiet(() => main(["install", ...args]));
      assert.equal(install.error, undefined, `install failed: ${install.error?.message}`);
    });

    const state = box.state();
    state.marketplaces[0].path = join(homeAlias, "managed-marketplaces", MARKETPLACE);
    writeFileSync(box.statePath, JSON.stringify(state));

    const status = await quiet(() => main(["status", "--host", "claude"]));
    assert.equal(status.error, undefined, `status rejected an equivalent path: ${status.error?.message}`);
    assert.match(status.output, new RegExp(`OpenSocrates ${PRODUCT_VERSION} is installed`));

    const remove = await quiet(() => main(["remove", "--host", "claude"]));
    assert.equal(remove.error, undefined, `remove rejected an equivalent path: ${remove.error?.message}`);
    assert.equal(existsSync(box.managedRoot), false, "managed root survived remove");
  } finally {
    box.cleanup();
  }
});

test("verify rejects a package whose checksum manifest does not match", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude", { corrupt: true });
    const result = await quiet(() =>
      main(["verify", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum]),
    );
    assert.notEqual(result.error, undefined, "corrupted package passed verification");
    assert.match(result.error.message, /package checksum mismatch/);
  } finally {
    box.cleanup();
  }
});

test("verify rejects a host/version mismatched package", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude", {
      manifestVersion: "9.9.9",
    });
    const result = await quiet(() =>
      main(["verify", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum]),
    );
    assert.notEqual(result.error, undefined, "mismatched manifest passed verification");
    assert.match(result.error.message, /plugin manifest mismatch/);
  } finally {
    box.cleanup();
  }
});

test("verify rejects an outer checksum mismatch", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    writeFileSync(pkg.checksum, `${"0".repeat(64)}  ${pkg.asset.split("/").pop()}\n`);
    const result = await quiet(() =>
      main(["verify", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum]),
    );
    assert.notEqual(result.error, undefined, "outer checksum mismatch passed verification");
    assert.match(result.error.message, /release checksum mismatch/);
  } finally {
    box.cleanup();
  }
});

test("verify rejects an archive containing a symbolic link", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const link = spawnSync(
      "sh",
      ["-c", `cd ${JSON.stringify(pkg.tree)} && ln -s /etc/passwd leak && zip -q -y ${JSON.stringify(pkg.asset)} leak`],
      { encoding: "utf8" },
    );
    assert.equal(link.status, 0, `fixture setup failed: ${link.stderr}`);
    writeFileSync(pkg.checksum, `${sha256(readFileSync(pkg.asset))}  ${pkg.asset.split("/").pop()}\n`);
    const result = await quiet(() =>
      main(["verify", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum]),
    );
    assert.notEqual(result.error, undefined, "archive with a symlink passed verification");
    assert.match(result.error.message, /symbolic link|checksum manifest/);
  } finally {
    box.cleanup();
  }
});

test("install refuses a marketplace registered at an unmanaged location", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const state = box.state();
    state.marketplaces.push({
      name: MARKETPLACE,
      source: "local",
      path: "/somewhere/else",
    });
    writeFileSync(box.statePath, JSON.stringify(state));
    const result = await withDarwinArm64(() =>
      quiet(() => main(["install", "--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum])),
    );
    assert.notEqual(result.error, undefined, "install overwrote an unmanaged registration");
    assert.match(result.error.message, /refusing to overwrite an unmanaged location/);
  } finally {
    box.cleanup();
  }
});

test("install refuses a managed root with a corrupted ownership marker", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    await withDarwinArm64(async () => {
      const install = await quiet(() => main(["install", ...args]));
      assert.equal(install.error, undefined);
    });
    writeFileSync(join(box.managedRoot, ".opensocrates-managed.json"), '{"schemaVersion":1}');
    const result = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.notEqual(result.error, undefined, "update proceeded against a corrupted marker");
    assert.match(result.error.message, /ownership marker/);
    assert.ok(existsSync(box.managedRoot), "an unowned root was deleted");
  } finally {
    box.cleanup();
  }
});

// ---------------------------------------------------------------------------
// Regression: a rollback stage that throws must not prevent later stages.
//
// Against the pre-fix installer this test fails: requireOwnedRoot() throws
// inside the catch block, escapes the handler, and the restore stage never
// runs, leaving the previous installation stranded in a .opensocrates.backup-*
// directory that no message names.
// ---------------------------------------------------------------------------
for (const host of ["claude", "codex"]) {
  test(`${host}: a failing rollback stage still restores the previous install`, async () => {
    const box = makeSandbox(host);
    try {
      const pkg = buildPackage(box.root, host);
      const args = ["--host", host, "--asset", pkg.asset, "--checksum", pkg.checksum];
      await withDarwinArm64(async () => {
        const install = await quiet(() => main(["install", ...args]));
        assert.equal(install.error, undefined, `setup install failed: ${install.error?.message}`);
      });

      // Swap in a host that corrupts the new root's ownership marker and then
      // refuses installation, so the "remove the failed root" rollback stage
      // throws before the "restore the previous install" stage can run.
      const sabotage = writeFakeHost(box.root, `${host}-sabotage`, {
        kind: host,
        failInstall: true,
        corruptMarkerOnInstall: true,
      });
      writeFileSync(
        sabotage.binary,
        readFileSync(sabotage.binary, "utf8").replace(
          JSON.stringify(join(box.root, `${host}-sabotage-state.json`)),
          JSON.stringify(box.statePath),
        ),
      );
      chmodSync(sabotage.binary, 0o755);
      process.env[host === "claude" ? "CLAUDE_BIN" : "CODEX_BIN"] = sabotage.binary;

      const result = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
      assert.notEqual(result.error, undefined, "sabotaged update reported success");

      // The previous installation must be back at the managed root.
      assert.ok(
        existsSync(join(box.managedRoot, ".opensocrates-managed.json")),
        "previous installation was not restored after a failing rollback stage",
      );
      assert.deepEqual(box.backups(), [], "previous installation was stranded in a backup directory");
    } finally {
      box.cleanup();
    }
  });
}

test("an unrecoverable rollback prints the preserved backup path", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    await withDarwinArm64(async () => {
      await quiet(() => main(["install", ...args]));
    });
    // Corrupt the backup only after update has moved the valid previous root
    // there, then fail plugin registration. Restore must refuse the corrupted
    // backup, preserve it, and print instructions that account for a failed
    // root-removal stage leaving the destination occupied.
    const failing = writeFakeHost(box.root, "claude-failing2", {
      kind: "claude",
      failInstall: true,
      corruptBackupOnInstall: true,
    });
    writeFileSync(
      failing.binary,
      readFileSync(failing.binary, "utf8").replace(
        JSON.stringify(join(box.root, "claude-failing2-state.json")),
        JSON.stringify(box.statePath),
      ),
    );
    chmodSync(failing.binary, 0o755);
    process.env.CLAUDE_BIN = failing.binary;

    const result = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    assert.notEqual(result.error, undefined, "update reported success");
    assert.equal(box.backups().length, 1, "the unrecoverable backup was not preserved");
    assert.match(result.output, /your previous files are preserved at:/);
    assert.match(result.output, /recovery command: \/bin\/rm -rf -- /);
    assert.match(result.output, /recovery command: \/bin\/mv -- /);
  } finally {
    box.cleanup();
  }
});

test("a root-removal rollback failure preserves the backup and prints executable recovery", async () => {
  const box = makeSandbox("claude");
  try {
    const pkg = buildPackage(box.root, "claude");
    const args = ["--host", "claude", "--asset", pkg.asset, "--checksum", pkg.checksum];
    const install = await withDarwinArm64(() => quiet(() => main(["install", ...args])));
    assert.equal(install.error, undefined, `setup install failed: ${install.error?.message}`);

    replaceSandboxHost(box, "claude", "claude-root-removal-blocked", {
      failInstall: true,
      blockRootRemovalOnInstall: true,
    });
    const result = await withDarwinArm64(() => quiet(() => main(["update", ...args])));
    chmodSync(dirname(box.managedRoot), 0o700);

    assert.notEqual(result.error, undefined, "sabotaged update reported success");
    assert.equal(box.backups().length, 1, "the previous installation backup was not preserved");
    const [backupName] = box.backups();
    assert.match(result.output, /your previous files are preserved at:/);
    assert.match(result.output, new RegExp(backupName));
    assert.match(result.output, /recovery command: \/bin\/rm -rf -- /);
    assert.match(result.output, /recovery command: \/bin\/mv -- /);
    assert.match(result.output, /recovery command: opensocrates install --host claude/);
    assert.match(result.output, /managed-marketplaces\/opensocrates/);
  } finally {
    chmodSync(dirname(box.managedRoot), 0o700);
    box.cleanup();
  }
});
