#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash, randomInt, randomUUID } from "node:crypto";
import {
  constants as fsConstants,
  createReadStream,
  createWriteStream,
  existsSync,
  readFileSync,
  realpathSync,
} from "node:fs";
import {
  access,
  chmod,
  cp,
  lstat,
  mkdir,
  mkdtemp,
  open,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";

export const PRODUCT_VERSION = "1.1.5";
export const REPOSITORY = "ParkerHwang/OpenSocrates";
export const MARKETPLACE_NAME = "opensocrates";
export const PLUGIN_NAME = "opensocrates";
export const PLUGIN_ID = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
export const DEFAULT_HOST = "codex";
export const SUPPORTED_HOSTS = Object.freeze(["antigravity", "claude", "codex", "cursor"]);
export const ALL_HOST = "all";
export const HOST_CHOICES = Object.freeze([ALL_HOST, ...SUPPORTED_HOSTS]);
export function assetNameFor(host = DEFAULT_HOST) {
  if (!SUPPORTED_HOSTS.includes(host)) {
    fail(`unsupported host ${JSON.stringify(host)}`);
  }
  return `opensocrates-${PRODUCT_VERSION}-${host}-plugin.zip`;
}
export const ASSET_NAME = assetNameFor(DEFAULT_HOST);
export const CHECKSUM_NAME = `${ASSET_NAME}.sha256`;

const MARKER_NAME = ".opensocrates-managed.json";
const CODEX_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
});
const CLAUDE_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "claude",
});
const CURSOR_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "cursor",
  registrationKind: "file-drop",
});
const ANTIGRAVITY_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "antigravity",
  registrationKind: "file-drop",
});
const HOST_LAYOUTS = Object.freeze({
  antigravity: {
    marketplaceRelative: null,
    pluginRelative: ".",
    manifestRelative: "plugin.json",
    requiresRuntime: false,
  },
  claude: {
    marketplaceRelative: join(".claude-plugin", "marketplace.json"),
    pluginRelative: join("plugins", PLUGIN_NAME),
    manifestRelative: join(".claude-plugin", "plugin.json"),
    requiresRuntime: true,
  },
  codex: {
    marketplaceRelative: join(".agents", "plugins", "marketplace.json"),
    pluginRelative: join("build", "generated", "plugins", "codex"),
    manifestRelative: join(".codex-plugin", "plugin.json"),
    requiresRuntime: true,
  },
  cursor: {
    marketplaceRelative: null,
    pluginRelative: ".",
    manifestRelative: "plugin.json",
    requiresRuntime: false,
  },
});
const MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024;
const MAX_ARCHIVE_ENTRIES = 10_000;
const DESIRED_STATE_SCHEMA = "opensocrates.desired-state/1.0.0";
const RECEIPT_SCHEMA = "opensocrates.auto-update-receipt/1.0.0";
const AUTO_UPDATE_LABEL = "com.opensocrates.auto-update";
const AUTO_UPDATE_MIN_INTERVAL_HOURS = 1;
const AUTO_UPDATE_MAX_INTERVAL_HOURS = 24 * 7;
const AUTO_UPDATE_DEFAULT_INTERVAL_HOURS = 24;
const AUTO_UPDATE_POLL_SECONDS = 60 * 60;
const LOCK_STALE_MILLISECONDS = 2 * 60 * 60 * 1000;

export class InstallerError extends Error {}

function fail(message) {
  throw new InstallerError(message);
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

async function exists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

export function statePaths() {
  const stateDirectory = resolve(
    process.env.OPENSOCRATES_STATE_DIR || join(homedir(), ".opensocrates"),
  );
  const launchAgentsDirectory = resolve(
    process.env.OPENSOCRATES_LAUNCH_AGENTS_DIR || join(homedir(), "Library", "LaunchAgents"),
  );
  return {
    directory: stateDirectory,
    desiredState: join(stateDirectory, "desired-state.json"),
    receipt: join(stateDirectory, "auto-update-receipt.json"),
    lock: join(stateDirectory, "lifecycle.lock"),
    launchAgentsDirectory,
    launchAgent: join(launchAgentsDirectory, `${AUTO_UPDATE_LABEL}.plist`),
  };
}

function defaultDesiredState() {
  return {
    schema: DESIRED_STATE_SCHEMA,
    channel: "stable",
    installedHosts: [],
    activeVersion: null,
    updatePolicy: {
      intervalHours: AUTO_UPDATE_DEFAULT_INTERVAL_HOURS,
      allowMajor: false,
    },
    autoUpdate: {
      enabled: false,
      hosts: [],
      nextCheckAt: null,
    },
    availableVersion: null,
    lastCheckAt: null,
    lastSuccessfulUpdateAt: null,
  };
}

function normalizeDesiredState(value) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    value.schema !== DESIRED_STATE_SCHEMA
  ) {
    fail("the OpenSocrates desired-state manifest has an unsupported schema");
  }
  const installedHosts = value.installedHosts;
  if (
    !Array.isArray(installedHosts) ||
    installedHosts.some((host) => !SUPPORTED_HOSTS.includes(host)) ||
    new Set(installedHosts).size !== installedHosts.length
  ) {
    fail("the OpenSocrates desired-state manifest has an invalid host set");
  }
  const channel = value.channel;
  if (!new Set(["stable", "next"]).has(channel)) {
    fail("the OpenSocrates desired-state manifest has an invalid update channel");
  }
  const intervalHours = value.updatePolicy?.intervalHours;
  if (
    !Number.isInteger(intervalHours) ||
    intervalHours < AUTO_UPDATE_MIN_INTERVAL_HOURS ||
    intervalHours > AUTO_UPDATE_MAX_INTERVAL_HOURS ||
    typeof value.updatePolicy?.allowMajor !== "boolean" ||
    typeof value.autoUpdate?.enabled !== "boolean"
  ) {
    fail("the OpenSocrates desired-state manifest has an invalid update policy");
  }
  const autoUpdateHosts =
    value.autoUpdate.hosts === undefined
      ? value.autoUpdate.enabled
        ? installedHosts
        : []
      : value.autoUpdate.hosts;
  if (
    !Array.isArray(autoUpdateHosts) ||
    autoUpdateHosts.some(
      (host) => !SUPPORTED_HOSTS.includes(host) || !installedHosts.includes(host),
    ) ||
    new Set(autoUpdateHosts).size !== autoUpdateHosts.length ||
    (value.autoUpdate.enabled && autoUpdateHosts.length === 0) ||
    (!value.autoUpdate.enabled && autoUpdateHosts.length > 0)
  ) {
    fail("the OpenSocrates desired-state manifest has an invalid automatic-update host set");
  }
  return {
    ...defaultDesiredState(),
    ...value,
    installedHosts: [...installedHosts].sort(),
    updatePolicy: {
      intervalHours,
      allowMajor: value.updatePolicy.allowMajor,
    },
    autoUpdate: {
      enabled: value.autoUpdate.enabled,
      hosts: [...autoUpdateHosts].sort(),
      nextCheckAt: value.autoUpdate.nextCheckAt ?? null,
    },
  };
}

export async function readDesiredState() {
  const { desiredState } = statePaths();
  if (!(await exists(desiredState))) {
    return defaultDesiredState();
  }
  let value;
  try {
    value = JSON.parse(await readFile(desiredState, "utf8"));
  } catch (error) {
    fail(`cannot read the OpenSocrates desired-state manifest: ${error.message}`);
  }
  return normalizeDesiredState(value);
}

async function ensurePrivateDirectory(directory) {
  if (await exists(directory)) {
    const info = await lstat(directory);
    if (!info.isDirectory() || info.isSymbolicLink()) {
      fail(`refusing to use a non-directory or symbolic-link state path: ${directory}`);
    }
    await chmod(directory, 0o700);
    return;
  }
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const info = await lstat(directory);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail(`refusing to use an unsafe state path: ${directory}`);
  }
  await chmod(directory, 0o700);
}

async function atomicWritePrivateFile(target, contents) {
  const parent = dirname(target);
  await ensurePrivateDirectory(parent);
  const temporary = join(parent, `.${basename(target)}.${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, contents, { encoding: "utf8", mode: 0o600, flag: "wx" });
    await chmod(temporary, 0o600);
    await rename(temporary, target);
  } finally {
    if (await exists(temporary)) {
      await rm(temporary, { force: true });
    }
  }
}

export async function writeDesiredState(value) {
  const normalized = normalizeDesiredState(value);
  await atomicWritePrivateFile(
    statePaths().desiredState,
    `${JSON.stringify(normalized, null, 2)}\n`,
  );
  return normalized;
}

async function writeAutoUpdateReceipt({ version, checkedAt, hosts, result, errorCategory }) {
  const receipt = {
    schema: RECEIPT_SCHEMA,
    version,
    checkedAt,
    hosts: [...hosts]
      .sort((left, right) => left.host.localeCompare(right.host))
      .map(({ host, result: hostResult }) => ({ host, result: hostResult })),
    result,
    errorCategory: errorCategory ?? null,
  };
  await atomicWritePrivateFile(
    statePaths().receipt,
    `${JSON.stringify(receipt, null, 2)}\n`,
  );
}

function nowIso() {
  return new Date().toISOString();
}

function nextCheckAt(intervalHours) {
  const intervalMilliseconds = intervalHours * 60 * 60 * 1000;
  const jitterBasisPoints = randomInt(-1500, 1501);
  return new Date(Date.now() + intervalMilliseconds * (1 + jitterBasisPoints / 10_000)).toISOString();
}

function majorVersion(value) {
  const match = String(value ?? "").match(/^(\d+)\./u);
  return match ? Number(match[1]) : null;
}

function errorCategory(error) {
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  if (/checksum|manifest|archive|symbolic link/u.test(message)) return "verification";
  if (/download|fetch|network|offline|timed? ?out/u.test(message)) return "network";
  if (/preflight|not logged|auth|version is required|could not run/u.test(message)) return "preflight";
  if (/rollback|restore/u.test(message)) return "rollback";
  if (/lock|already running/u.test(message)) return "locked";
  if (/register|plugin|marketplace/u.test(message)) return "activation";
  return "internal";
}

async function acquireOperationLock() {
  const paths = statePaths();
  await ensurePrivateDirectory(paths.directory);
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const handle = await open(paths.lock, "wx", 0o600);
      try {
        await handle.writeFile(
          `${JSON.stringify({ pid: process.pid, startedAt: nowIso() })}\n`,
          "utf8",
        );
      } catch (writeError) {
        await handle.close().catch(() => undefined);
        await rm(paths.lock, { force: true }).catch(() => undefined);
        throw writeError;
      }
      return async () => {
        try {
          await handle.close();
        } finally {
          await rm(paths.lock, { force: true });
        }
      };
    } catch (error) {
      if (error?.code !== "EEXIST") {
        throw error;
      }
      let stale = false;
      try {
        const lock = JSON.parse(await readFile(paths.lock, "utf8"));
        const started = Date.parse(lock.startedAt);
        let ownerAlive = null;
        if (Number.isInteger(lock.pid) && lock.pid > 0) {
          try {
            process.kill(lock.pid, 0);
            ownerAlive = true;
          } catch (processError) {
            ownerAlive = processError?.code === "ESRCH" ? false : true;
          }
        }
        stale =
          ownerAlive === false ||
          (ownerAlive === null &&
            Number.isFinite(started) &&
            Date.now() - started > LOCK_STALE_MILLISECONDS);
      } catch {
        const info = await lstat(paths.lock);
        stale = Date.now() - info.mtimeMs > LOCK_STALE_MILLISECONDS;
      }
      if (!stale || attempt > 0) {
        fail("another OpenSocrates lifecycle operation is already running");
      }
      await rm(paths.lock, { force: true });
    }
  }
  fail("could not acquire the OpenSocrates lifecycle lock");
}

export async function withOperationLock(action) {
  const release = await acquireOperationLock();
  try {
    return await action();
  } finally {
    await release();
  }
}

function jsonEqual(left, right) {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return (
    leftKeys.length === rightKeys.length &&
    leftKeys.every((key, index) => key === rightKeys[index] && left[key] === right[key])
  );
}

function markerFor(host) {
  if (host === "cursor") return CURSOR_MARKER;
  if (host === "antigravity") return ANTIGRAVITY_MARKER;
  return host === "claude" ? CLAUDE_MARKER : CODEX_MARKER;
}

export function markerMatches(value, host = DEFAULT_HOST) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    jsonEqual(value, markerFor(host))
  );
}

export function isSafeArchivePath(value) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.includes("\0") ||
    value.includes("\\") ||
    value.startsWith("/")
  ) {
    return false;
  }
  const candidate = value.endsWith("/") ? value.slice(0, -1) : value;
  if (candidate.length === 0) {
    return false;
  }
  return candidate.split("/").every((part) => part.length > 0 && part !== "." && part !== "..");
}

export function parseChecksumText(text, expectedName = ASSET_NAME) {
  const candidates = String(text)
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  for (const line of candidates) {
    const match = line.match(/^([a-fA-F0-9]{64})(?:\s+[*]?(.+))?$/u);
    if (!match) {
      continue;
    }
    const namedFile = match[2]?.trim();
    if (namedFile && basename(namedFile) !== expectedName) {
      continue;
    }
    return match[1].toLowerCase();
  }
  fail(`checksum file does not contain a SHA-256 entry for ${expectedName}`);
}

export function parseCli(argv) {
  const actions = new Set([
    "install",
    "status",
    "update",
    "remove",
    "verify",
    "auto-update",
    "help",
  ]);
  const args = [...argv];
  let action = "install";
  if (args[0] && !args[0].startsWith("-")) {
    action = args.shift();
  }
  if (!actions.has(action)) {
    fail(`unknown action ${JSON.stringify(action)}`);
  }
  let autoUpdateAction = null;
  if (action === "auto-update") {
    if (["--help", "-h"].includes(args[0])) {
      args.shift();
      action = "help";
    } else {
      autoUpdateAction = args.shift() ?? "status";
      if (!new Set(["enable", "status", "disable", "run"]).has(autoUpdateAction)) {
        fail(`unknown auto-update action ${JSON.stringify(autoUpdateAction)}`);
      }
    }
  }
  const options = {
    action,
    autoUpdateAction,
    host: action === "auto-update" ? ALL_HOST : DEFAULT_HOST,
    asset: null,
    checksum: null,
    hostAssets: Object.fromEntries(
      SUPPORTED_HOSTS.map((host) => [host, { asset: null, checksum: null }]),
    ),
    channel: "stable",
    intervalHours: AUTO_UPDATE_DEFAULT_INTERVAL_HOURS,
    allowMajor: false,
    force: false,
  };
  const seenOptions = new Set();
  while (args.length > 0) {
    const flag = args.shift();
    if (flag === "--help" || flag === "-h") {
      options.action = "help";
      continue;
    }
    if (flag === "--host") {
      seenOptions.add("host");
      const host = args.shift();
      if (!HOST_CHOICES.includes(host)) {
        fail(`--host must be one of: ${HOST_CHOICES.join(", ")}`);
      }
      options.host = host;
      continue;
    }
    if (flag === "--allow-major") {
      seenOptions.add("allow-major");
      options.allowMajor = true;
      continue;
    }
    if (flag === "--force") {
      seenOptions.add("force");
      options.force = true;
      continue;
    }
    if (flag === "--channel") {
      seenOptions.add("channel");
      const channel = args.shift();
      if (!new Set(["stable", "next"]).has(channel)) {
        fail("--channel must be one of: stable, next");
      }
      options.channel = channel;
      continue;
    }
    if (flag === "--interval-hours") {
      seenOptions.add("interval-hours");
      const raw = args.shift();
      const value = Number(raw);
      if (
        !Number.isInteger(value) ||
        value < AUTO_UPDATE_MIN_INTERVAL_HOURS ||
        value > AUTO_UPDATE_MAX_INTERVAL_HOURS
      ) {
        fail(
          `--interval-hours must be an integer from ${AUTO_UPDATE_MIN_INTERVAL_HOURS} ` +
            `through ${AUTO_UPDATE_MAX_INTERVAL_HOURS}`,
        );
      }
      options.intervalHours = value;
      continue;
    }
    const qualified = flag?.match(
      new RegExp(`^--(asset|checksum)-(${SUPPORTED_HOSTS.join("|")})$`, "u"),
    );
    if (qualified) {
      seenOptions.add(qualified[1]);
      const value = args.shift();
      if (!value || value.startsWith("-")) {
        fail(`${flag} requires a file path`);
      }
      options.hostAssets[qualified[2]][qualified[1]] = resolve(value);
      continue;
    }
    if (flag !== "--asset" && flag !== "--checksum") {
      fail(`unknown option ${JSON.stringify(flag)}`);
    }
    const value = args.shift();
    if (!value || value.startsWith("-")) {
      fail(`${flag} requires a file path`);
    }
    options[flag === "--asset" ? "asset" : "checksum"] = resolve(value);
    seenOptions.add(flag.slice(2));
  }
  if ((options.asset === null) !== (options.checksum === null)) {
    fail("--asset and --checksum must be supplied together");
  }
  for (const host of SUPPORTED_HOSTS) {
    const inputs = options.hostAssets[host];
    if ((inputs.asset === null) !== (inputs.checksum === null)) {
      fail(`--asset-${host} and --checksum-${host} must be supplied together`);
    }
  }
  if (options.host === ALL_HOST && options.asset !== null) {
    fail("--host all requires host-qualified --asset-<host> and --checksum-<host> options");
  }
  if (
    options.host !== ALL_HOST &&
    SUPPORTED_HOSTS.some((host) => options.hostAssets[host].asset !== null)
  ) {
    fail("host-qualified asset options are only valid with --host all");
  }
  if (["status", "remove", "help"].includes(options.action) && options.asset !== null) {
    fail(`${options.action} does not accept --asset or --checksum`);
  }
  if (
    ["status", "remove", "help"].includes(options.action) &&
    SUPPORTED_HOSTS.some((host) => options.hostAssets[host].asset !== null)
  ) {
    fail(`${options.action} does not accept host-qualified asset options`);
  }
  if (
    options.action === "auto-update" &&
    options.autoUpdateAction !== "run" &&
    (options.asset !== null ||
      SUPPORTED_HOSTS.some((host) => options.hostAssets[host].asset !== null))
  ) {
    fail(`auto-update ${options.autoUpdateAction} does not accept local asset options`);
  }
  const autoUpdateEnable =
    options.action === "auto-update" && options.autoUpdateAction === "enable";
  const autoUpdateRun = options.action === "auto-update" && options.autoUpdateAction === "run";
  for (const policyOption of ["allow-major", "channel", "interval-hours"]) {
    if (seenOptions.has(policyOption) && !autoUpdateEnable) {
      fail(`--${policyOption} is only valid with auto-update enable`);
    }
  }
  if (seenOptions.has("force") && !autoUpdateRun) {
    fail("--force is only valid with auto-update run");
  }
  if (
    seenOptions.has("host") &&
    options.action === "auto-update" &&
    new Set(["status", "disable"]).has(options.autoUpdateAction)
  ) {
    fail(`auto-update ${options.autoUpdateAction} does not accept --host`);
  }
  if (autoUpdateRun && seenOptions.has("host") && options.host !== ALL_HOST) {
    fail("auto-update run always reconciles desired state and only accepts --host all");
  }
  return options;
}

function showHelp() {
  console.log(`OpenSocrates ${PRODUCT_VERSION}

Usage:
  opensocrates install [--host all|antigravity|claude|codex|cursor] [--asset ZIP --checksum SHA256]
  opensocrates status [--host all|antigravity|claude|codex|cursor]
  opensocrates update [--host all|antigravity|claude|codex|cursor] [--asset ZIP --checksum SHA256]
  opensocrates remove [--host all|antigravity|claude|codex|cursor]
  opensocrates verify [--host all|antigravity|claude|codex|cursor] [--asset ZIP --checksum SHA256]
  opensocrates auto-update enable [--host all|antigravity|claude|codex|cursor]
      [--channel stable|next] [--interval-hours ${AUTO_UPDATE_DEFAULT_INTERVAL_HOURS}]
      [--allow-major]
  opensocrates auto-update status
  opensocrates auto-update disable

Without --asset, install, update, and verify download the v${PRODUCT_VERSION}
package and checksum from GitHub Releases. The default lifecycle host is codex.
For offline --host all verification, provide an asset/checksum pair for each
supported host. Automatic updates are opt-in.
`);
}

function managedPaths(host) {
  const configured =
    host === "antigravity"
      ? process.env.ANTIGRAVITY_CONFIG_DIR
      : host === "cursor"
        ? process.env.CURSOR_CONFIG_DIR
      : host === "claude"
        ? process.env.CLAUDE_CONFIG_DIR
        : process.env.CODEX_HOME;
  const defaultHome =
    host === "antigravity"
      ? join(homedir(), ".gemini", "config")
      : host === "cursor"
        ? join(homedir(), ".cursor")
      : join(homedir(), host === "claude" ? ".claude" : ".codex");
  const configuredHome = resolve(
    configured ? configured : defaultHome,
  );
  let hostHome = configuredHome;
  try {
    hostHome = realpathSync(configuredHome);
  } catch {
    // The installer creates a missing host home below after validating its
    // explicit, non-recursive target. Lexical resolution is the only
    // available normalization until then.
  }
  const root =
    host === "antigravity"
      ? join(hostHome, "plugins", PLUGIN_NAME)
      : host === "cursor"
        ? join(hostHome, "plugins", "local", PLUGIN_NAME)
      : join(hostHome, "managed-marketplaces", MARKETPLACE_NAME);
  const layout = HOST_LAYOUTS[host];
  return {
    hostHome,
    root,
    parent: dirname(root),
    marker: join(root, MARKER_NAME),
    marketplace:
      typeof layout.marketplaceRelative === "string"
        ? join(root, layout.marketplaceRelative)
        : null,
    plugin: join(root, layout.pluginRelative),
  };
}

function codexBinary() {
  return process.env.CODEX_BIN || "codex";
}

function claudeBinary() {
  return process.env.CLAUDE_BIN || "claude";
}

function cursorBinary() {
  return process.env.CURSOR_BIN || "cursor";
}

function cursorAppPaths() {
  return [
    "/Applications/Cursor.app",
    join(homedir(), "Applications", "Cursor.app"),
  ];
}

function antigravityBinary() {
  return process.env.AGY_BIN || "agy";
}

function run(command, args, { allowFailure = false } = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    env: process.env,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error) {
    if (allowFailure) {
      return result;
    }
    fail(`could not run ${command}: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = result.stderr?.trim() || result.stdout?.trim() || `exit ${result.status}`;
    fail(`${command} ${args.join(" ")} failed: ${detail}`);
  }
  return result;
}

function runJson(command, args, label) {
  const result = run(command, args);
  try {
    const payload = JSON.parse(result.stdout);
    if (payload === null || typeof payload !== "object") {
      fail(`${label} returned a non-container JSON value`);
    }
    return payload;
  } catch (error) {
    if (error instanceof InstallerError) {
      throw error;
    }
    fail(`${label} returned invalid JSON for ${args.join(" ")}: ${error.message}`);
  }
}

function runCodexJson(args) {
  const payload = runJson(codexBinary(), args, "Codex");
  if (Array.isArray(payload)) {
    fail("Codex returned an unexpected JSON array");
  }
  return payload;
}

function runClaudeJson(args) {
  return runJson(claudeBinary(), args, "Claude Code");
}

function claudeListEntries(payload, wrapper, label) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (
    payload !== null &&
    typeof payload === "object" &&
    !Array.isArray(payload) &&
    Object.keys(payload).length === 1 &&
    Array.isArray(payload[wrapper])
  ) {
    return payload[wrapper];
  }
  fail(`Claude Code ${label} returned an unexpected schema`);
}

function requireUniqueClaudeEntries(entries, identity, label) {
  const seen = new Set();
  for (const entry of entries) {
    if (
      entry === null ||
      typeof entry !== "object" ||
      Array.isArray(entry) ||
      typeof entry[identity] !== "string" ||
      entry[identity].trim().length === 0
    ) {
      fail(`Claude Code ${label} returned a malformed entry`);
    }
    if (seen.has(entry[identity])) {
      fail(`Claude Code ${label} returned duplicate entries for ${entry[identity]}`);
    }
    seen.add(entry[identity]);
  }
  return entries;
}

function claudeMarketplaceEntries(payload) {
  return requireUniqueClaudeEntries(
    claudeListEntries(payload, "marketplaces", "marketplace list"),
    "name",
    "marketplace list",
  );
}

function claudePluginEntries(payload) {
  return requireUniqueClaudeEntries(
    claudeListEntries(payload, "plugins", "plugin list"),
    "id",
    "plugin list",
  );
}

function versionAtLeast(value, minimum) {
  const match = String(value).match(/(\d+)\.(\d+)\.(\d+)/u);
  if (!match) {
    return false;
  }
  const current = match.slice(1).map(Number);
  for (let index = 0; index < minimum.length; index += 1) {
    if (current[index] > minimum[index]) return true;
    if (current[index] < minimum[index]) return false;
  }
  return true;
}

function requireHostCli(host, { authenticated = false } = {}) {
  if (host === "cursor") {
    if (process.env.CURSOR_CONFIG_DIR) return;
    if (process.env.CURSOR_BIN) {
      const result = run(cursorBinary(), ["--version"]);
      if (!versionAtLeast(result.stdout, [2, 5, 0])) {
        fail(`Cursor 2.5.0 or later is required; got ${result.stdout.trim()}`);
      }
      return;
    }
    const app = cursorAppPaths().find((candidate) => existsSync(candidate));
    if (app) {
      const result = run(
        "/usr/bin/plutil",
        ["-extract", "CFBundleShortVersionString", "raw", join(app, "Contents", "Info.plist")],
        { allowFailure: true },
      );
      if (result.status !== 0 || !versionAtLeast(result.stdout, [2, 5, 0])) {
        fail("Cursor 2.5.0 or later is required for Agent Plugin support");
      }
      return;
    }
    const result = run(cursorBinary(), ["--version"]);
    if (!versionAtLeast(result.stdout, [2, 5, 0])) {
      fail(`Cursor 2.5.0 or later is required; got ${result.stdout.trim()}`);
    }
    return;
  }
  if (host === "antigravity") {
    if (process.env.ANTIGRAVITY_CONFIG_DIR) return;
    run(antigravityBinary(), ["--version"]);
    return;
  }
  if (host === "claude") {
    const result = run(claudeBinary(), ["--version"]);
    if (!versionAtLeast(result.stdout, [2, 1, 205])) {
      fail(
        `Claude Code 2.1.205 or later is required for structured selector output; got ${result.stdout.trim()}`,
      );
    }
    if (authenticated) {
      run(claudeBinary(), ["auth", "status"]);
    }
    return;
  }
  run(codexBinary(), ["--version"]);
  if (authenticated) {
    run(codexBinary(), ["login", "status"]);
  }
}

function marketplaceEntries(host) {
  if (["antigravity", "cursor"].includes(host)) {
    const paths = managedPaths(host);
    return existsSync(paths.root) ? [{ name: MARKETPLACE_NAME, root: paths.root }] : [];
  }
  const payload =
    host === "claude"
      ? runClaudeJson(["plugin", "marketplace", "list", "--json"])
      : runCodexJson(["plugin", "marketplace", "list", "--json"]).marketplaces;
  const entries = host === "claude" ? claudeMarketplaceEntries(payload) : payload;
  if (!Array.isArray(entries)) {
    fail(`${host} marketplace list returned an unexpected schema`);
  }
  return entries;
}

function marketplaceEntry(host) {
  const entries = marketplaceEntries(host);
  const matches = entries.filter((entry) => entry?.name === MARKETPLACE_NAME);
  if (matches.length > 1) {
    fail(`${host} reported duplicate marketplaces named ${MARKETPLACE_NAME}`);
  }
  return matches[0] ?? null;
}

function pluginState(host) {
  if (["antigravity", "cursor"].includes(host)) {
    const paths = managedPaths(host);
    if (!existsSync(paths.root)) return { kind: "missing", version: null };
    let manifest;
    try {
      manifest = JSON.parse(readFileSync(join(paths.root, "plugin.json"), "utf8"));
    } catch (error) {
      fail(`${host} plugin manifest is unreadable: ${error.message}`);
    }
    if (
      manifest === null ||
      typeof manifest !== "object" ||
      Array.isArray(manifest) ||
      (host === "cursor" &&
        manifest.$schema !== "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json") ||
      manifest.name !== PLUGIN_NAME ||
      typeof manifest.version !== "string" ||
      manifest.version.trim().length === 0
    ) {
      fail(`${host} reported an invalid OpenSocrates plugin manifest`);
    }
    return { kind: "installed", version: manifest.version };
  }
  if (host === "claude") {
    const installed = claudePluginEntries(runClaudeJson(["plugin", "list", "--json"]));
    const matches = installed.filter((entry) => entry?.id === PLUGIN_ID);
    if (matches.length === 0) return { kind: "missing", version: null };
    const entry = matches[0];
    if (
      (entry.version !== undefined &&
        entry.version !== null &&
        (typeof entry.version !== "string" || entry.version.trim().length === 0)) ||
      typeof entry.enabled !== "boolean"
    ) {
      fail(`Claude Code reported an invalid state for ${PLUGIN_ID}`);
    }
    return {
      kind: entry.enabled ? "installed" : "disabled",
      version: entry.version ?? null,
    };
  }
  const payload = runCodexJson([
    "plugin", "list", "--marketplace", MARKETPLACE_NAME, "--available", "--json",
  ]);
  const installed = Array.isArray(payload.installed) ? payload.installed : null;
  const available = Array.isArray(payload.available) ? payload.available : null;
  if (installed === null || available === null) {
    fail("Codex plugin list returned an unexpected schema");
  }
  const installedMatches = installed.filter((entry) => entry?.pluginId === PLUGIN_ID);
  const availableMatches = available.filter((entry) => entry?.pluginId === PLUGIN_ID);
  if (installedMatches.length > 1 || availableMatches.length > 1) {
    fail(`Codex reported duplicate entries for ${PLUGIN_ID}`);
  }
  if (installedMatches.length === 1) {
    return { kind: "installed", version: installedMatches[0].version ?? null };
  }
  if (availableMatches.length === 1) {
    return { kind: "available", version: availableMatches[0].version ?? null };
  }
  return { kind: "missing", version: null };
}

function detectLegacyClaudeInstallation() {
  const marketplaces = marketplaceEntries("claude").filter(
    (entry) =>
      typeof entry?.name === "string" &&
      entry.name !== MARKETPLACE_NAME &&
      entry.name.toLowerCase() === MARKETPLACE_NAME,
  );
  const plugins = claudePluginEntries(runClaudeJson(["plugin", "list", "--json"]));
  const legacyPlugins = plugins.filter(
    (entry) =>
      entry.id !== PLUGIN_ID &&
      entry.id.toLowerCase() === PLUGIN_ID,
  );
  const names = marketplaces.map((entry) => entry.name).join(", ") || "OpenSocrates";
  return { found: marketplaces.length > 0 || legacyPlugins.length > 0, names };
}

// Install and update write into the managed root, so a case-variant pre-1.0
// registration must be resolved by the user first. Status and remove are
// diagnostic and scoped to the root this installer owns, so they only warn:
// blocking them would strand a user who needs to inspect or back out.
function requireNoLegacyClaudeInstallation() {
  const legacy = detectLegacyClaudeInstallation();
  if (legacy.found) {
    fail(
      `a legacy Claude marketplace (${legacy.names}) is installed; OpenSocrates will not remove it automatically. ` +
        "Uninstall its plugin and marketplace explicitly, then rerun this command. See the README migration section.",
    );
  }
}

function warnLegacyClaudeInstallation() {
  let legacy;
  try {
    legacy = detectLegacyClaudeInstallation();
  } catch {
    return;
  }
  if (legacy.found) {
    console.warn(
      `warning: a legacy Claude marketplace (${legacy.names}) is also registered. ` +
        "OpenSocrates never removes it automatically; this command only affects the root it owns. " +
        "See the README migration section.",
    );
  }
}

async function readJsonObject(target) {
  let payload;
  try {
    payload = JSON.parse(await readFile(target, "utf8"));
  } catch (error) {
    fail(`cannot read valid JSON from ${target}: ${error.message}`);
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    fail(`expected a JSON object in ${target}`);
  }
  return payload;
}

async function requireOwnedRoot(root, host) {
  const info = await lstat(root);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail(`managed marketplace path is not an owned directory: ${root}`);
  }
  const marker = await readJsonObject(join(root, MARKER_NAME));
  if (!markerMatches(marker, host)) {
    fail(`managed marketplace path has no valid ownership marker: ${root}`);
  }
}

async function sha256File(target) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(target)) {
    hash.update(chunk);
  }
  return hash.digest("hex");
}

async function downloadFile(url, destination) {
  const response = await fetch(url, {
    headers: {
      accept: "application/octet-stream",
      "user-agent": `OpenSocrates-installer/${PRODUCT_VERSION}`,
    },
    redirect: "follow",
    signal: AbortSignal.timeout(15 * 60 * 1000),
  });
  if (!response.ok || response.body === null) {
    fail(`download failed (${response.status}) for ${url}`);
  }
  const contentLength = Number(response.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_DOWNLOAD_BYTES) {
    fail(`download exceeds the ${MAX_DOWNLOAD_BYTES}-byte safety limit`);
  }
  await pipeline(Readable.fromWeb(response.body), createWriteStream(destination, { mode: 0o600 }));
  const downloaded = (await stat(destination)).size;
  if (downloaded === 0 || downloaded > MAX_DOWNLOAD_BYTES) {
    fail(`downloaded file has an invalid size: ${downloaded} bytes`);
  }
}

function localAssetInputs(options, host) {
  if (options.host === ALL_HOST) {
    return options.hostAssets[host];
  }
  return { asset: options.asset, checksum: options.checksum };
}

async function resolveAssetInputs(options, scratch, host) {
  const local = localAssetInputs(options, host);
  if (local.asset !== null) {
    if (!(await exists(local.asset)) || !(await exists(local.checksum))) {
      fail("the supplied asset or checksum file does not exist");
    }
    return local;
  }
  const base = `https://github.com/${REPOSITORY}/releases/download/v${PRODUCT_VERSION}`;
  const assetName = assetNameFor(host);
  const checksumName = `${assetName}.sha256`;
  const asset = join(scratch, assetName);
  const checksum = join(scratch, checksumName);
  console.log(`Downloading OpenSocrates ${PRODUCT_VERSION} from GitHub Releases...`);
  await downloadFile(`${base}/${assetName}`, asset);
  await downloadFile(`${base}/${checksumName}`, checksum);
  return { asset, checksum };
}

async function verifyOuterChecksum(asset, checksum, host) {
  const expected = parseChecksumText(await readFile(checksum, "utf8"), assetNameFor(host));
  const actual = await sha256File(asset);
  if (actual !== expected) {
    fail(`release checksum mismatch: expected ${expected}, got ${actual}`);
  }
}

function archiveEntries(asset) {
  const unzip = process.platform === "darwin" ? "/usr/bin/unzip" : "unzip";
  const result = run(unzip, ["-Z1", asset]);
  const entries = result.stdout.split(/\r?\n/u).filter(Boolean);
  if (entries.length === 0 || entries.length > MAX_ARCHIVE_ENTRIES) {
    fail(`archive contains an invalid number of entries: ${entries.length}`);
  }
  const unique = new Set();
  for (const entry of entries) {
    if (!isSafeArchivePath(entry)) {
      fail(`archive contains an unsafe path: ${JSON.stringify(entry)}`);
    }
    if (unique.has(entry)) {
      fail(`archive contains a duplicate path: ${entry}`);
    }
    unique.add(entry);
  }
  return entries;
}

async function extractArchive(asset, destination) {
  archiveEntries(asset);
  await mkdir(destination, { recursive: true, mode: 0o700 });
  const unzip = process.platform === "darwin" ? "/usr/bin/unzip" : "unzip";
  run(unzip, ["-q", asset, "-d", destination]);
}

async function walkFiles(root, current = root, output = []) {
  const entries = await readdir(current, { withFileTypes: true });
  for (const entry of entries) {
    const absolute = join(current, entry.name);
    const info = await lstat(absolute);
    if (info.isSymbolicLink()) {
      fail(`package contains a symbolic link: ${relative(root, absolute)}`);
    }
    if (info.isDirectory()) {
      await walkFiles(root, absolute, output);
    } else if (info.isFile()) {
      output.push(relative(root, absolute).split(sep).join("/"));
    } else {
      fail(`package contains an unsupported filesystem entry: ${relative(root, absolute)}`);
    }
  }
  return output;
}

async function verifyPackageChecksums(pluginRoot) {
  const checksumPath = join(pluginRoot, "checksums.sha256");
  const lines = (await readFile(checksumPath, "utf8"))
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  const declared = new Set();
  for (const line of lines) {
    const match = line.match(/^([a-fA-F0-9]{64})\s+[*]?(.+)$/u);
    if (!match) {
      fail(`invalid package checksum line: ${line}`);
    }
    const expected = match[1].toLowerCase();
    const item = match[2].trim();
    if (!isSafeArchivePath(item) || item === "checksums.sha256" || declared.has(item)) {
      fail(`invalid or duplicate package checksum path: ${item}`);
    }
    declared.add(item);
    const target = join(pluginRoot, ...item.split("/"));
    if (!(await exists(target))) {
      fail(`package checksum references a missing file: ${item}`);
    }
    const actual = await sha256File(target);
    if (actual !== expected) {
      fail(`package checksum mismatch for ${item}`);
    }
  }
  const actualFiles = new Set((await walkFiles(pluginRoot)).filter((item) => item !== "checksums.sha256"));
  if (
    actualFiles.size !== declared.size ||
    [...actualFiles].some((item) => !declared.has(item))
  ) {
    fail("package checksum manifest does not cover the complete archive");
  }
  return declared.size;
}

async function verifyExtractedPackage(pluginRoot, host) {
  const manifest = await readJsonObject(join(pluginRoot, HOST_LAYOUTS[host].manifestRelative));
  if (manifest.name !== PLUGIN_NAME || manifest.version !== PRODUCT_VERSION) {
    fail(
      `plugin manifest mismatch: expected ${PLUGIN_NAME} ${PRODUCT_VERSION}, ` +
        `got ${String(manifest.name)} ${String(manifest.version)}`,
    );
  }
  const release = await readJsonObject(join(pluginRoot, "release-manifest.json"));
  if (
    release.product_version !== PRODUCT_VERSION ||
    release.host !== host ||
    release.schema !== "opensocrates.plugin-release-manifest/1.0.0"
  ) {
    fail("package release manifest does not match this installer");
  }
  if (HOST_LAYOUTS[host].requiresRuntime) {
    const runtime = join(
      pluginRoot,
      "runtime",
      "darwin-arm64",
      "opensocrates-runtime",
      "opensocrates-runtime",
    );
    const runtimeInfo = await stat(runtime);
    if (!runtimeInfo.isFile() || (runtimeInfo.mode & 0o111) === 0) {
      fail("package is missing the executable darwin-arm64 runtime");
    }
  } else if (
    release.launchers?.length !== 0 ||
    release.runtime_targets?.length !== 0 ||
    (await exists(join(pluginRoot, "runtime"))) ||
    (await exists(join(pluginRoot, "hooks"))) ||
    (await exists(join(pluginRoot, "bin"))) ||
    (host === "cursor" && (await exists(join(pluginRoot, "mcp.json"))))
  ) {
    fail(`${host} explicit-skill package must not contain executable integration surfaces`);
  }
  return verifyPackageChecksums(pluginRoot);
}

async function prepareVerifiedPackage(options, host = options.host) {
  if (!SUPPORTED_HOSTS.includes(host)) {
    fail(`cannot prepare a package for unsupported host ${JSON.stringify(host)}`);
  }
  const scratch = await mkdtemp(join(tmpdir(), "opensocrates-install-"));
  try {
    const { asset, checksum } = await resolveAssetInputs(options, scratch, host);
    await verifyOuterChecksum(asset, checksum, host);
    const pluginRoot = join(scratch, "plugin");
    await extractArchive(asset, pluginRoot);
    const checkedFiles = await verifyExtractedPackage(pluginRoot, host);
    return { scratch, pluginRoot, checkedFiles, host };
  } catch (error) {
    await rm(scratch, { recursive: true, force: true });
    throw error;
  }
}

async function prepareVerifiedPackages(options, hosts) {
  const settled = await Promise.allSettled(
    hosts.map((host) => prepareVerifiedPackage(options, host)),
  );
  const prepared = settled
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value);
  const failure = settled.find((result) => result.status === "rejected");
  if (failure) {
    await Promise.all(
      prepared.map((item) => rm(item.scratch, { recursive: true, force: true })),
    );
    throw failure.reason;
  }
  return prepared;
}

function expectedMarketplace(host) {
  if (host === "claude") {
    return {
      name: MARKETPLACE_NAME,
      owner: { name: "Parker Hwang" },
      metadata: {
        description: "OpenSocrates reasoning support for Claude Code and Cowork",
        version: PRODUCT_VERSION,
      },
      plugins: [
        {
          name: PLUGIN_NAME,
          source: `./plugins/${PLUGIN_NAME}`,
          description:
            "Local reasoning-system selection for Claude Code and Cowork, plus one /opensocrates entry.",
          category: "workflow",
        },
      ],
    };
  }
  return {
    name: MARKETPLACE_NAME,
    interface: { displayName: "OpenSocrates" },
    plugins: [
      {
        name: PLUGIN_NAME,
        source: {
          source: "local",
          path: "./build/generated/plugins/codex",
        },
        policy: {
          installation: "AVAILABLE",
          authentication: "ON_INSTALL",
        },
        category: "Productivity",
      },
    ],
  };
}

async function buildStagingTree(parent, pluginSource, host) {
  const layout = HOST_LAYOUTS[host];
  const staging = await mkdtemp(join(parent, ".opensocrates.staging-"));
  try {
    if (["antigravity", "cursor"].includes(host)) {
      await cp(pluginSource, staging, { recursive: true, preserveTimestamps: true });
      await verifyExtractedPackage(staging, host);
      await writeFile(
        join(staging, MARKER_NAME),
        `${JSON.stringify(markerFor(host), null, 2)}\n`,
        { encoding: "utf8", mode: 0o600 },
      );
      return staging;
    }
    const marketplace = join(staging, layout.marketplaceRelative);
    const plugin = join(staging, layout.pluginRelative);
    await mkdir(dirname(marketplace), { recursive: true, mode: 0o700 });
    await mkdir(dirname(plugin), { recursive: true, mode: 0o700 });
    await cp(pluginSource, plugin, { recursive: true, preserveTimestamps: true });
    await writeFile(marketplace, `${JSON.stringify(expectedMarketplace(host), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await writeFile(join(staging, MARKER_NAME), `${JSON.stringify(markerFor(host), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await verifyExtractedPackage(plugin, host);
    return staging;
  } catch (error) {
    await rm(staging, { recursive: true, force: true });
    throw error;
  }
}

function entryRoot(entry, host) {
  if (entry === null) {
    return null;
  }
  let value;
  if (host === "claude") {
    const fields = ["path", "installLocation"].filter(
      (field) => entry[field] !== undefined && entry[field] !== null,
    );
    if (
      fields.length === 0 ||
      fields.some(
        (field) => typeof entry[field] !== "string" || entry[field].trim().length === 0,
      )
    ) {
      fail(`${host} marketplace ${MARKETPLACE_NAME} has no usable root`);
    }
    const roots = fields.map((field) => {
      const candidate = resolve(entry[field]);
      try {
        return realpathSync(candidate);
      } catch {
        return candidate;
      }
    });
    if (new Set(roots).size !== 1) {
      fail(`${host} marketplace ${MARKETPLACE_NAME} reported conflicting roots`);
    }
    [value] = roots;
  } else {
    value = entry.root;
  }
  if (typeof value !== "string" || value.trim().length === 0) {
    fail(`${host} marketplace ${MARKETPLACE_NAME} has no usable root`);
  }
  const resolved = resolve(value);
  try {
    // Host CLIs may report an equivalent canonical path even when the user
    // configured a symlinked home (for example /var versus /private/var on
    // macOS). Compare canonical existing paths without weakening ownership
    // checks for missing or unmanaged roots.
    return realpathSync(resolved);
  } catch {
    return resolved;
  }
}

function removeRegistration(host, entry, state) {
  if (["antigravity", "cursor"].includes(host)) return;
  if (host === "claude") {
    if (["installed", "disabled"].includes(state.kind)) {
      run(claudeBinary(), ["plugin", "uninstall", PLUGIN_ID, "--scope", "user"]);
    }
    if (entry !== null) {
      run(claudeBinary(), [
        "plugin", "marketplace", "remove", MARKETPLACE_NAME, "--scope", "user",
      ]);
    }
    return;
  }
  if (state.kind === "installed") {
    runCodexJson(["plugin", "remove", PLUGIN_ID, "--json"]);
  }
  if (entry !== null) {
    runCodexJson(["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"]);
  }
}

function addRegistration(host, root, installPlugin, { enabled = true } = {}) {
  if (["antigravity", "cursor"].includes(host)) return null;
  if (host === "claude") {
    run(claudeBinary(), ["plugin", "marketplace", "add", root, "--scope", "user"]);
    if (installPlugin) {
      run(claudeBinary(), ["plugin", "install", PLUGIN_ID, "--scope", "user"]);
      if (!enabled) {
        run(claudeBinary(), ["plugin", "disable", PLUGIN_ID, "--scope", "user"]);
      }
    }
    return null;
  }
  runCodexJson(["plugin", "marketplace", "add", root, "--json"]);
  if (installPlugin) {
    return runCodexJson(["plugin", "add", PLUGIN_ID, "--json"]);
  }
  return null;
}

function removeRegistrationBestEffort(host) {
  if (["antigravity", "cursor"].includes(host)) return;
  const entry = (() => {
    try {
      return marketplaceEntry(host);
    } catch {
      return null;
    }
  })();
  if (entry === null) {
    return;
  }
  try {
    const state = pluginState(host);
    if (["installed", "disabled"].includes(state.kind)) {
      const binary = host === "claude" ? claudeBinary() : codexBinary();
      const args =
        host === "claude"
          ? ["plugin", "uninstall", PLUGIN_ID, "--scope", "user"]
          : ["plugin", "remove", PLUGIN_ID, "--json"];
      run(binary, args, { allowFailure: true });
    }
  } catch {
    // Rollback continues with marketplace cleanup.
  }
  const binary = host === "claude" ? claudeBinary() : codexBinary();
  const args =
    host === "claude"
      ? ["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--scope", "user"]
      : ["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"];
  run(binary, args, { allowFailure: true });
}

async function recoveryStep(label, action) {
  try {
    await action();
    return true;
  } catch (recoveryError) {
    const detail =
      recoveryError instanceof Error ? recoveryError.message : String(recoveryError);
    console.error(`warning: rollback step failed (${label}): ${detail}`);
    return false;
  }
}

async function preflightHost(host, action) {
  if (!["antigravity", "cursor"].includes(host) || ["install", "update"].includes(action)) {
    requireHostCli(host, { authenticated: ["install", "update"].includes(action) });
  }
  if (host === "claude") {
    if (["install", "update"].includes(action)) {
      requireNoLegacyClaudeInstallation();
    } else {
      warnLegacyClaudeInstallation();
    }
  }
  const paths = managedPaths(host);
  const previousEntry = marketplaceEntry(host);
  if (previousEntry !== null && entryRoot(previousEntry, host) !== paths.root) {
    fail(
      `marketplace ${MARKETPLACE_NAME} is already registered at ${entryRoot(previousEntry, host)}; ` +
        "refusing to overwrite an unmanaged location",
    );
  }
  const rootExists = await exists(paths.root);
  if (rootExists) {
    await requireOwnedRoot(paths.root, host);
  }
  if (previousEntry !== null && !rootExists) {
    fail(`${host} has a managed registration whose root is missing: ${paths.root}`);
  }
  const previousState =
    previousEntry === null ? { kind: "missing", version: null } : pluginState(host);
  return { host, paths, previousEntry, previousState, rootExists };
}

async function preflightSelectedHosts(options, action, desiredState) {
  if (options.host !== ALL_HOST) {
    return [await preflightHost(options.host, action)];
  }
  const desiredHosts = new Set(desiredState.installedHosts);
  const rootPresence = Object.fromEntries(
    await Promise.all(
      SUPPORTED_HOSTS.map(async (host) => [host, await exists(managedPaths(host).root)]),
    ),
  );
  const settled = await Promise.allSettled(
    SUPPORTED_HOSTS.map((host) => preflightHost(host, action)),
  );
  const successes = new Map();
  const failures = new Map();
  settled.forEach((result, index) => {
    const host = SUPPORTED_HOSTS[index];
    if (result.status === "fulfilled") successes.set(host, result.value);
    else failures.set(host, result.reason);
  });

  const required = new Set();
  if (action === "install") {
    for (const host of SUPPORTED_HOSTS) {
      if (desiredHosts.has(host) || rootPresence[host]) required.add(host);
    }
  } else if (desiredHosts.size > 0) {
    for (const host of desiredHosts) required.add(host);
  } else if (action === "remove") {
    for (const host of SUPPORTED_HOSTS) {
      if (rootPresence[host]) required.add(host);
    }
  }
  for (const host of required) {
    if (failures.has(host)) {
      const reason = failures.get(host);
      fail(`preflight failed for ${host}: ${reason instanceof Error ? reason.message : reason}`);
    }
  }

  let selected;
  if (action === "update" && desiredHosts.size > 0) {
    selected = [...desiredHosts].map((host) => successes.get(host)).filter(Boolean);
  } else if (action === "remove") {
    selected = [...successes.values()].filter(
      (item) => desiredHosts.has(item.host) || item.rootExists || item.previousEntry !== null,
    );
  } else {
    selected = [...successes.values()];
  }
  for (const [host, reason] of failures) {
    if (!required.has(host)) {
      console.log(
        `${host}: skipped (host is unavailable or not authenticated: ` +
          `${reason instanceof Error ? reason.message : reason})`,
      );
    }
  }
  if (selected.length === 0 && action !== "remove") {
    fail(`preflight found no ready hosts for ${action} --host all`);
  }
  return selected.sort((left, right) => left.host.localeCompare(right.host));
}

async function stageInstallation(preflight, pluginSource) {
  const { host, paths } = preflight;
  await mkdir(paths.parent, { recursive: true, mode: 0o700 });
  const staging = await buildStagingTree(paths.parent, pluginSource, host);
  return {
    ...preflight,
    staging,
    backup: join(paths.parent, `.opensocrates.backup-${randomUUID()}`),
    registrationRemoved: false,
    backupCreated: false,
    newRootActive: false,
    activationStarted: false,
  };
}

async function activateInstallation(transaction) {
  const { host, paths, previousEntry, previousState } = transaction;
  transaction.activationStarted = true;
  if (previousEntry !== null) {
    transaction.registrationRemoved = true;
    removeRegistration(host, previousEntry, previousState);
  }
  if (await exists(paths.root)) {
    await rename(paths.root, transaction.backup);
    transaction.backupCreated = true;
  }
  await rename(transaction.staging, paths.root);
  transaction.newRootActive = true;
  const result = addRegistration(host, paths.root, true);
  const state = pluginState(host);
  if (
    (host === "codex" &&
      (result?.pluginId !== PLUGIN_ID || result?.version !== PRODUCT_VERSION)) ||
    state.kind !== "installed" ||
    state.version !== PRODUCT_VERSION
  ) {
    fail(`${host} did not confirm the expected installed plugin and version`);
  }
}

async function rollbackInstallation(transaction) {
  if (!transaction.activationStarted) return;
  const { host, paths, previousEntry, previousState } = transaction;
  let restored = false;
  await recoveryStep(`unregister the failed ${host} installation`, async () => {
    removeRegistrationBestEffort(host);
  });
  if (transaction.newRootActive && (await exists(paths.root))) {
    await recoveryStep(`remove the failed ${host} installation root`, async () => {
      // This root was created by this transaction, so deleting it cannot
      // cross the ownership boundary even if a failed host command damaged
      // its marker.
      await rm(paths.root, { recursive: true, force: true });
    });
  }
  if (transaction.backupCreated && (await exists(transaction.backup))) {
    restored = await recoveryStep(`restore the previous ${host} installation`, async () => {
      await requireOwnedRoot(transaction.backup, host);
      await rename(transaction.backup, paths.root);
    });
  }
  if (
    transaction.registrationRemoved &&
    previousEntry !== null &&
    (restored || !transaction.backupCreated)
  ) {
    await recoveryStep(`re-register the previous ${host} installation`, async () => {
      addRegistration(
        host,
        paths.root,
        ["installed", "disabled"].includes(previousState.kind),
        { enabled: previousState.kind !== "disabled" },
      );
    });
  }
  if (transaction.backupCreated && !restored) {
    console.error(
      `error: the previous ${host} OpenSocrates installation could not be restored automatically.`,
    );
    console.error(`error: your previous files are preserved at: ${transaction.backup}`);
    console.error(`error: recovery command: /bin/rm -rf -- ${shellQuote(paths.root)}`);
    console.error(
      `error: recovery command: /bin/mv -- ${shellQuote(transaction.backup)} ${shellQuote(paths.root)}`,
    );
    console.error(`error: recovery command: opensocrates install --host ${host}`);
  }
}

async function cleanupInstallationTransaction(transaction) {
  if (await exists(transaction.staging)) {
    await rm(transaction.staging, { recursive: true, force: true });
  }
}

async function commitInstallation(transaction) {
  if (transaction.backupCreated && (await exists(transaction.backup))) {
    await requireOwnedRoot(transaction.backup, transaction.host);
    await rm(transaction.backup, { recursive: true });
    transaction.backupCreated = false;
  }
}

function installedDesiredState(previous, hosts) {
  return {
    ...previous,
    installedHosts: [...new Set([...previous.installedHosts, ...hosts])].sort(),
    activeVersion: PRODUCT_VERSION,
    availableVersion: PRODUCT_VERSION,
  };
}

async function runInstallOrUpdate(options, action) {
  const desired = await readDesiredState();
  const preflights = await preflightSelectedHosts(options, action, desired);
  const hosts = preflights.map((item) => item.host);
  const prepared = await prepareVerifiedPackages(options, hosts);
  const packages = new Map(prepared.map((item) => [item.host, item]));
  const transactions = [];
  try {
    for (const preflight of preflights) {
      const item = packages.get(preflight.host);
      console.log(
        `${preflight.host}: verified OpenSocrates ${PRODUCT_VERSION} and ` +
          `${item.checkedFiles} package files`,
      );
      transactions.push(await stageInstallation(preflight, item.pluginRoot));
    }
    for (const transaction of transactions) {
      await activateInstallation(transaction);
      console.log(`${transaction.host}: activated OpenSocrates ${PRODUCT_VERSION}`);
    }
    await writeDesiredState(installedDesiredState(desired, hosts));
  } catch (error) {
    for (const transaction of [...transactions].reverse()) {
      await rollbackInstallation(transaction);
    }
    throw error;
  } finally {
    await Promise.all(transactions.map(cleanupInstallationTransaction));
    await Promise.all(
      prepared.map((item) => rm(item.scratch, { recursive: true, force: true })),
    );
  }
  for (const transaction of transactions) {
    const cleaned = await recoveryStep(`remove the committed ${transaction.host} backup`, async () => {
      await commitInstallation(transaction);
    });
    if (!cleaned) {
      console.warn(`warning: ${transaction.host} is active, but its previous backup needs cleanup`);
    }
  }
  const verb = action === "update" ? "updated" : "installed";
  console.log(
    `OpenSocrates ${PRODUCT_VERSION} ${verb} successfully for ${hosts.join(", ")}.`,
  );
  if (hosts.includes("codex")) {
    console.log(
      "Codex approval required: open one interactive Codex session and approve the " +
        "OpenSocrates hooks before relying on automatic selection. Non-interactive " +
        "codex exec silently skips hooks that have not been trusted.",
    );
  }
  if (hosts.includes("cursor")) {
    console.log(
      "Cursor: run Developer: Reload Window, then invoke /opensocrates from Agent chat. " +
        "This experimental package adds no automatic OpenSocrates hook selector.",
    );
  }
  console.log("Start new host tasks to load the updated skills and hooks.");
  return hosts;
}

async function inspectHostStatus(host) {
  if (!["antigravity", "cursor"].includes(host)) requireHostCli(host);
  if (host === "claude") warnLegacyClaudeInstallation();
  const paths = managedPaths(host);
  const entry = marketplaceEntry(host);
  if (entry === null) {
    if (await exists(paths.root)) {
      await requireOwnedRoot(paths.root, host);
      return { host, kind: "files-only", version: null, paths };
    }
    return { host, kind: "missing", version: null, paths };
  }
  if (entryRoot(entry, host) !== paths.root) {
    fail(`OpenSocrates is registered at an unmanaged location: ${entryRoot(entry, host)}`);
  }
  await requireOwnedRoot(paths.root, host);
  const state = pluginState(host);
  return { host, kind: state.kind, version: state.version, paths };
}

async function showStatus(host) {
  if (host === ALL_HOST) {
    const desired = await readDesiredState();
    console.log(`Desired version: ${desired.activeVersion ?? "none"}`);
    console.log(`Available version: ${desired.availableVersion ?? "unknown"}`);
    console.log(`Last check: ${desired.lastCheckAt ?? "never"}`);
    console.log(`Last successful update: ${desired.lastSuccessfulUpdateAt ?? "never"}`);
    console.log(`Auto-update: ${desired.autoUpdate.enabled ? "enabled" : "disabled"}`);
    let drift = false;
    for (const candidate of SUPPORTED_HOSTS) {
      try {
        const status = await inspectHostStatus(candidate);
        const expected = desired.installedHosts.includes(candidate);
        const hostDrift = expected
          ? status.kind !== "installed" ||
            desired.activeVersion === null ||
            status.version !== desired.activeVersion
          : status.kind !== "missing";
        drift ||= hostDrift;
        if (status.kind === "installed") {
          console.log(
            `${candidate}: installed ${status.version ?? "unknown"}` +
              (["antigravity", "cursor"].includes(candidate)
                ? " (experimental explicit-skill tier)"
                : "") +
              (expected
                ? hostDrift
                  ? ` (drift from ${desired.activeVersion ?? "desired state"})`
                  : " (in sync)"
                : " (not in desired state)"),
          );
        } else if (status.kind === "disabled") {
          console.log(
            `${candidate}: installed but disabled (${status.version ?? "unknown"})` +
              (expected ? " (drift: desired host is not active)" : " (not in desired state)"),
          );
        } else if (status.kind === "available") {
          console.log(
            `${candidate}: available but not installed (${status.version ?? "unknown"})` +
              (expected ? " (drift: desired host is not active)" : ""),
          );
        } else if (status.kind === "files-only") {
          console.log(`${candidate}: managed files present but not registered`);
        } else {
          console.log(
            `${candidate}: not installed` + (expected ? " (drift: desired host is missing)" : ""),
          );
        }
      } catch (error) {
        if (desired.installedHosts.includes(candidate)) drift = true;
        console.log(
          `${candidate}: unavailable (${errorCategory(error)})` +
            (desired.installedHosts.includes(candidate) ? " (drift unknown)" : ""),
        );
      }
    }
    console.log(`Overall: ${drift ? "drift detected" : "no detected drift"}`);
    return;
  }
  const status = await inspectHostStatus(host);
  if (status.kind === "installed") {
    console.log(
      `OpenSocrates ${status.version ?? "unknown"} is installed.` +
        (host === "antigravity"
          ? " Antigravity support is experimental and explicit-skill only."
          : host === "cursor"
            ? " Cursor support is experimental and explicit-skill first."
            : ""),
    );
  } else if (status.kind === "disabled") {
    console.log(
      `OpenSocrates ${status.version ?? "unknown"} is installed but disabled. ` +
        "Run install or update to re-enable it.",
    );
  } else if (status.kind === "available") {
    console.log(`OpenSocrates ${status.version ?? "unknown"} is available but not installed.`);
  } else if (status.kind === "files-only") {
    console.log(`OpenSocrates files are present but not registered: ${status.paths.root}`);
  } else {
    console.log("OpenSocrates is not installed.");
  }
}

function removalTransaction(preflight) {
  return {
    ...preflight,
    backup: join(preflight.paths.parent, `.opensocrates.removed-${randomUUID()}`),
    registrationRemoved: false,
    backupCreated: false,
  };
}

async function activateRemoval(transaction) {
  const { host, previousEntry, previousState, paths } = transaction;
  if (previousEntry !== null) {
    transaction.registrationRemoved = true;
    removeRegistration(host, previousEntry, previousState);
  }
  if (await exists(paths.root)) {
    await rename(paths.root, transaction.backup);
    transaction.backupCreated = true;
  }
}

async function rollbackRemoval(transaction) {
  let restored = !transaction.backupCreated;
  if (transaction.backupCreated && (await exists(transaction.backup))) {
    restored = await recoveryStep(`restore the removed ${transaction.host} files`, async () => {
      await requireOwnedRoot(transaction.backup, transaction.host);
      await rename(transaction.backup, transaction.paths.root);
    });
  }
  if (transaction.registrationRemoved && transaction.previousEntry !== null && restored) {
    await recoveryStep(`restore the removed ${transaction.host} registration`, async () => {
      addRegistration(
        transaction.host,
        transaction.paths.root,
        ["installed", "disabled"].includes(transaction.previousState.kind),
        { enabled: transaction.previousState.kind !== "disabled" },
      );
    });
  }
}

async function commitRemoval(transaction) {
  if (transaction.backupCreated && (await exists(transaction.backup))) {
    await requireOwnedRoot(transaction.backup, transaction.host);
    await rm(transaction.backup, { recursive: true });
  }
}

function xmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

async function executablePath(name, environmentOverride) {
  const override = process.env[environmentOverride];
  if (override) {
    const candidate = resolve(override);
    await access(candidate, fsConstants.X_OK);
    return candidate;
  }
  const which = run("/usr/bin/which", [name], { allowFailure: true });
  const candidate = which.status === 0 ? which.stdout.trim() : "";
  if (!candidate || !candidate.startsWith("/")) {
    fail(`could not find an executable ${name} for the automatic updater`);
  }
  await access(candidate, fsConstants.X_OK);
  return candidate;
}

function launchctlBinary() {
  return process.env.OPENSOCRATES_LAUNCHCTL_BIN || "/bin/launchctl";
}

function launchctlDomain() {
  if (typeof process.getuid !== "function") {
    fail("automatic updates require a user launchd domain");
  }
  return `gui/${process.getuid()}`;
}

function launchAgentDocument(npx, channel, environment) {
  const packageTag = channel === "next" ? "next" : "latest";
  const arguments_ = [
    npx,
    "--yes",
    `opensocrates@${packageTag}`,
    "auto-update",
    "run",
  ];
  const argumentsXml = arguments_
    .map((argument) => `      <string>${xmlEscape(argument)}</string>`)
    .join("\n");
  const environmentEntries = Object.entries(environment).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  const environmentXml =
    environmentEntries.length === 0
      ? ""
      : `\n    <key>EnvironmentVariables</key>\n    <dict>\n` +
        environmentEntries
          .map(
            ([key, value]) =>
              `      <key>${xmlEscape(key)}</key>\n` +
              `      <string>${xmlEscape(value)}</string>`,
          )
          .join("\n") +
        "\n    </dict>";
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${AUTO_UPDATE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
${argumentsXml}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>${AUTO_UPDATE_POLL_SECONDS}</integer>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>${environmentXml}
  </dict>
</plist>
`;
}

function launchAgentTarget() {
  return `${launchctlDomain()}/${AUTO_UPDATE_LABEL}`;
}

function launchAgentLoaded() {
  return run(launchctlBinary(), ["print", launchAgentTarget()], { allowFailure: true }).status === 0;
}

function stopLoadedLaunchAgent() {
  if (!launchAgentLoaded()) return;
  const stopped = run(launchctlBinary(), ["bootout", launchAgentTarget()], {
    allowFailure: true,
  });
  if (stopped.status !== 0 && launchAgentLoaded()) {
    const detail = stopped.stderr?.trim() || stopped.stdout?.trim() || `exit ${stopped.status}`;
    fail(`could not stop the OpenSocrates LaunchAgent: ${detail}`);
  }
}

async function updaterEnvironment(hosts, npx) {
  const node = await executablePath("node", "OPENSOCRATES_NODE_BIN");
  const environment = {
    PATH: [...new Set([dirname(npx), dirname(node), "/usr/bin", "/bin", "/usr/sbin", "/sbin"])].join(
      ":",
    ),
  };
  for (const host of hosts) {
    if (host === "cursor") {
      if (process.env.CURSOR_CONFIG_DIR) {
        environment.CURSOR_CONFIG_DIR = resolve(process.env.CURSOR_CONFIG_DIR);
        continue;
      }
      const app = cursorAppPaths().find((candidate) => existsSync(candidate));
      if (app) continue;
      const executable = await executablePath("cursor", "CURSOR_BIN");
      environment.CURSOR_BIN = executable;
      environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(
        ":",
      );
      continue;
    }
    if (host === "antigravity") {
      if (process.env.ANTIGRAVITY_CONFIG_DIR) {
        environment.ANTIGRAVITY_CONFIG_DIR = resolve(process.env.ANTIGRAVITY_CONFIG_DIR);
        continue;
      }
      const executable = await executablePath("agy", "AGY_BIN");
      environment.AGY_BIN = executable;
      environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(
        ":",
      );
      continue;
    }
    const key = host === "claude" ? "CLAUDE_BIN" : "CODEX_BIN";
    const executable = await executablePath(host, key);
    environment[key] = executable;
    environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(":");
  }
  for (const key of [
    "ANTIGRAVITY_CONFIG_DIR",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "CURSOR_CONFIG_DIR",
    "OPENSOCRATES_STATE_DIR",
  ]) {
    if (process.env[key]) environment[key] = resolve(process.env[key]);
  }
  return environment;
}

async function installLaunchAgent(channel, hosts) {
  if (process.platform !== "darwin" || process.arch !== "arm64") {
    fail(
      `automatic updates currently support darwin-arm64 only; detected ` +
        `${process.platform}-${process.arch}`,
    );
  }
  const paths = statePaths();
  const npx = await executablePath("npx", "OPENSOCRATES_NPX_BIN");
  const environment = await updaterEnvironment(hosts, npx);
  let previousDocument = null;
  if (await exists(paths.launchAgent)) {
    const info = await lstat(paths.launchAgent);
    if (!info.isFile() || info.isSymbolicLink()) {
      fail(`refusing to replace an unsafe LaunchAgent path: ${paths.launchAgent}`);
    }
    previousDocument = await readFile(paths.launchAgent, "utf8");
  }
  const document = launchAgentDocument(npx, channel, environment);
  if (process.env.OPENSOCRATES_SKIP_LAUNCHCTL === "1") {
    await atomicWritePrivateFile(paths.launchAgent, document);
    return;
  }
  const wasLoaded = launchAgentLoaded();
  if (wasLoaded) stopLoadedLaunchAgent();
  await atomicWritePrivateFile(paths.launchAgent, document);
  const launched = run(
    launchctlBinary(),
    ["bootstrap", launchctlDomain(), paths.launchAgent],
    { allowFailure: true },
  );
  if (launched.status !== 0) {
    if (previousDocument === null) {
      await rm(paths.launchAgent, { force: true });
    } else {
      await atomicWritePrivateFile(paths.launchAgent, previousDocument);
      if (wasLoaded) {
        const restored = run(
          launchctlBinary(),
          ["bootstrap", launchctlDomain(), paths.launchAgent],
          { allowFailure: true },
        );
        if (restored.status !== 0) {
          console.error("warning: the previous OpenSocrates LaunchAgent could not be reloaded");
        }
      }
    }
    const detail = launched.stderr?.trim() || launched.stdout?.trim() || `exit ${launched.status}`;
    fail(`could not enable the OpenSocrates LaunchAgent: ${detail}`);
  }
}

async function disableLaunchAgent() {
  const paths = statePaths();
  const agentPresent = await exists(paths.launchAgent);
  if (agentPresent) {
    const info = await lstat(paths.launchAgent);
    if (!info.isFile() || info.isSymbolicLink()) {
      fail(`refusing to remove an unsafe LaunchAgent path: ${paths.launchAgent}`);
    }
  }
  if (process.env.OPENSOCRATES_SKIP_LAUNCHCTL !== "1") {
    stopLoadedLaunchAgent();
  }
  if (agentPresent) await rm(paths.launchAgent);
}

async function disableAutoUpdateState(desired) {
  await disableLaunchAgent();
  return {
    ...desired,
    autoUpdate: { enabled: false, hosts: [], nextCheckAt: null },
  };
}

async function runRemove(options) {
  const desired = await readDesiredState();
  const preflights = await preflightSelectedHosts(options, "remove", desired);
  const removedHosts = preflights.map((item) => item.host);
  const remainingHosts = desired.installedHosts.filter((host) => !removedHosts.includes(host));
  const remainingAutoUpdateHosts = desired.autoUpdate.hosts.filter(
    (host) => !removedHosts.includes(host),
  );
  const keepAutoUpdate = desired.autoUpdate.enabled && remainingAutoUpdateHosts.length > 0;
  const nextDesired = {
    ...desired,
    installedHosts: remainingHosts,
    activeVersion: remainingHosts.length === 0 ? null : desired.activeVersion,
    autoUpdate: keepAutoUpdate
      ? { ...desired.autoUpdate, hosts: remainingAutoUpdateHosts }
      : { enabled: false, hosts: [], nextCheckAt: null },
  };
  const launchAgentPresent = await exists(statePaths().launchAgent);
  const schedulerNeedsChange =
    options.host === ALL_HOST ||
    remainingHosts.length === 0 ||
    launchAgentPresent !== keepAutoUpdate ||
    desired.autoUpdate.hosts.some((host) => removedHosts.includes(host));
  const transactions = preflights.map(removalTransaction);
  let schedulerTouched = false;
  try {
    for (const transaction of transactions) await activateRemoval(transaction);
    if (schedulerNeedsChange) {
      schedulerTouched = true;
      if (keepAutoUpdate) {
        await installLaunchAgent(desired.channel, remainingAutoUpdateHosts);
      } else {
        await disableLaunchAgent();
      }
    }
    await writeDesiredState(nextDesired);
  } catch (error) {
    for (const transaction of [...transactions].reverse()) await rollbackRemoval(transaction);
    if (schedulerTouched) {
      const schedulerRestored = await recoveryStep(
        "restore the automatic updater after removal failure",
        async () => {
          if (desired.autoUpdate.enabled) {
            await installLaunchAgent(desired.channel, desired.autoUpdate.hosts);
          } else {
            await disableLaunchAgent();
          }
        },
      );
      if (!schedulerRestored && desired.autoUpdate.enabled) {
        await recoveryStep("record the disabled updater after removal failure", async () => {
          await writeDesiredState({
            ...desired,
            autoUpdate: { enabled: false, hosts: [], nextCheckAt: null },
          });
        });
      }
    } else if (!nextDesired.autoUpdate.enabled && desired.autoUpdate.enabled) {
      await recoveryStep("record the disabled updater after removal failure", async () => {
        await writeDesiredState({
          ...desired,
          autoUpdate: { enabled: false, hosts: [], nextCheckAt: null },
        });
      });
    }
    throw error;
  }
  for (const transaction of transactions) await commitRemoval(transaction);
  for (const host of removedHosts) {
    const label =
      host === "antigravity"
        ? "Antigravity"
        : host === "claude"
          ? "Claude"
          : host === "cursor"
            ? "Cursor"
            : "Codex";
    console.log(`OpenSocrates was removed from ${label}.`);
  }
  if (removedHosts.length === 0) console.log("OpenSocrates is not installed on any managed host.");
}

async function enableAutoUpdate(options) {
  const previous = await readDesiredState();
  const preflights = new Map();
  let installedHosts = [...previous.installedHosts];
  if (installedHosts.length === 0) {
    const discoveryOptions = { ...options, host: ALL_HOST };
    const discovered = await preflightSelectedHosts(discoveryOptions, "update", previous);
    for (const item of discovered) {
      if (item.previousState.kind === "installed") {
        preflights.set(item.host, item);
        installedHosts.push(item.host);
      }
    }
  }
  let updateHosts = options.host === ALL_HOST ? [...installedHosts] : [options.host];
  if (updateHosts.length === 0) {
    fail("install OpenSocrates on at least one host before enabling automatic updates");
  }
  for (const host of updateHosts) {
    const preflight = preflights.get(host) ?? (await preflightHost(host, "update"));
    if (preflight.previousState.kind !== "installed") {
      fail(`OpenSocrates is not installed on ${host}`);
    }
    if (typeof preflight.previousState.version !== "string") {
      fail(`cannot determine the installed OpenSocrates version on ${host}`);
    }
    preflights.set(host, preflight);
    installedHosts.push(host);
  }
  installedHosts = [...new Set(installedHosts)].sort();
  updateHosts = [...new Set(updateHosts)].sort();
  let activeVersion = previous.activeVersion;
  if (activeVersion === null) {
    const observedVersions = new Set();
    for (const host of installedHosts) {
      const preflight = preflights.get(host) ?? (await preflightHost(host, "update"));
      if (
        preflight.previousState.kind !== "installed" ||
        typeof preflight.previousState.version !== "string"
      ) {
        fail(`cannot determine the installed OpenSocrates version on ${host}`);
      }
      preflights.set(host, preflight);
      observedVersions.add(preflight.previousState.version);
    }
    if (observedVersions.size !== 1) {
      fail(
        "installed hosts do not share one known version; run update --host all before enabling automatic updates",
      );
    }
    [activeVersion] = observedVersions;
  }
  const desired = {
    ...previous,
    channel: options.channel,
    installedHosts,
    activeVersion,
    updatePolicy: {
      intervalHours: options.intervalHours,
      allowMajor: options.allowMajor,
    },
    autoUpdate: {
      enabled: true,
      hosts: updateHosts,
      nextCheckAt: nowIso(),
    },
  };
  await writeDesiredState(desired);
  try {
    await installLaunchAgent(options.channel, desired.autoUpdate.hosts);
  } catch (error) {
    await writeDesiredState(previous);
    throw error;
  }
  console.log(
    `Automatic updates enabled for ${desired.autoUpdate.hosts.join(", ")} on the ` +
      `${desired.channel} channel every ${desired.updatePolicy.intervalHours} hours with jitter.`,
  );
  console.log(
    desired.updatePolicy.allowMajor
      ? "Automatic major-version upgrades are enabled."
      : "Automatic major-version upgrades remain disabled.",
  );
}

async function showAutoUpdateStatus() {
  const desired = await readDesiredState();
  const agentPresent = await exists(statePaths().launchAgent);
  console.log(`Automatic updates: ${desired.autoUpdate.enabled ? "enabled" : "disabled"}`);
  console.log(`LaunchAgent: ${agentPresent ? "installed" : "not installed"}`);
  console.log(`Channel: ${desired.channel}`);
  console.log(`Installed hosts: ${desired.installedHosts.join(", ") || "none"}`);
  console.log(`Automatic-update hosts: ${desired.autoUpdate.hosts.join(", ") || "none"}`);
  console.log(`Interval: ${desired.updatePolicy.intervalHours} hours with jitter`);
  console.log(`Major upgrades: ${desired.updatePolicy.allowMajor ? "allowed" : "blocked"}`);
  console.log(`Next check: ${desired.autoUpdate.nextCheckAt ?? "not scheduled"}`);
  console.log(`Last check: ${desired.lastCheckAt ?? "never"}`);
  console.log(`Last successful update: ${desired.lastSuccessfulUpdateAt ?? "never"}`);
}

async function disableAutoUpdate() {
  const desired = await readDesiredState();
  await writeDesiredState(await disableAutoUpdateState(desired));
  console.log("Automatic updates are disabled and the LaunchAgent was removed.");
}

async function runScheduledUpdate(options) {
  let desired = await readDesiredState();
  if (!desired.autoUpdate.enabled) {
    console.log("Automatic updates are disabled.");
    return;
  }
  const scheduledAt = Date.parse(desired.autoUpdate.nextCheckAt ?? "");
  if (!options.force && Number.isFinite(scheduledAt) && scheduledAt > Date.now()) {
    console.log(`The next automatic update check is scheduled for ${desired.autoUpdate.nextCheckAt}.`);
    return;
  }
  const checkedAt = nowIso();
  const hosts = desired.autoUpdate.hosts;
  if (hosts.length === 0) {
    fail("the automatic updater has no selected hosts in desired state");
  }
  const next = nextCheckAt(desired.updatePolicy.intervalHours);
  const currentMajor = majorVersion(desired.activeVersion);
  const availableMajor = majorVersion(PRODUCT_VERSION);
  if (
    !desired.updatePolicy.allowMajor &&
    currentMajor !== null &&
    availableMajor !== null &&
    availableMajor > currentMajor
  ) {
    desired = await writeDesiredState({
      ...desired,
      availableVersion: PRODUCT_VERSION,
      lastCheckAt: checkedAt,
      autoUpdate: { ...desired.autoUpdate, nextCheckAt: next },
    });
    await writeAutoUpdateReceipt({
      version: PRODUCT_VERSION,
      checkedAt,
      hosts: hosts.map((host) => ({ host, result: "blocked-major" })),
      result: "blocked",
      errorCategory: "major-policy",
    });
    console.log(`OpenSocrates ${PRODUCT_VERSION} is available but blocked by the major-version policy.`);
    return;
  }
  try {
    const ready = [];
    for (const host of hosts) ready.push(await preflightHost(host, "update"));
    const alreadyCurrent =
      desired.activeVersion === PRODUCT_VERSION &&
      ready.every(
        (item) =>
          item.previousState.kind === "installed" && item.previousState.version === PRODUCT_VERSION,
      );
    if (!alreadyCurrent) {
      if (hosts.length > 1) {
        await runInstallOrUpdate({ ...options, host: ALL_HOST }, "update");
      } else {
        const [host] = hosts;
        const local = localAssetInputs(options, host);
        await runInstallOrUpdate(
          { ...options, host, asset: local.asset, checksum: local.checksum },
          "update",
        );
      }
    }
    const refreshed = await readDesiredState();
    desired = await writeDesiredState({
      ...refreshed,
      availableVersion: PRODUCT_VERSION,
      lastCheckAt: checkedAt,
      lastSuccessfulUpdateAt: alreadyCurrent
        ? refreshed.lastSuccessfulUpdateAt
        : checkedAt,
      autoUpdate: { ...refreshed.autoUpdate, nextCheckAt: next },
    });
    await writeAutoUpdateReceipt({
      version: PRODUCT_VERSION,
      checkedAt,
      hosts: hosts.map((host) => ({ host, result: alreadyCurrent ? "current" : "updated" })),
      result: alreadyCurrent ? "no-update" : "updated",
      errorCategory: null,
    });
    console.log(
      alreadyCurrent
        ? `OpenSocrates ${PRODUCT_VERSION} is already current on every managed host.`
        : `OpenSocrates ${PRODUCT_VERSION} was reconciled across ${hosts.join(", ")}.`,
    );
  } catch (error) {
    await recoveryStep("record the failed automatic update", async () => {
      desired = await writeDesiredState({
        ...(await readDesiredState()),
        availableVersion: PRODUCT_VERSION,
        lastCheckAt: checkedAt,
        autoUpdate: { ...desired.autoUpdate, nextCheckAt: next },
      });
      await writeAutoUpdateReceipt({
        version: PRODUCT_VERSION,
        checkedAt,
        hosts: hosts.map((host) => ({ host, result: "failed" })),
        result: "failed",
        errorCategory: errorCategory(error),
      });
    });
    throw error;
  }
}

function requireSupportedPlatform() {
  if (process.platform !== "darwin" || process.arch !== "arm64") {
    fail(
      `OpenSocrates ${PRODUCT_VERSION} prebuilt installation supports darwin-arm64 only; ` +
        `detected ${process.platform}-${process.arch}`,
    );
  }
}

async function verifyPackages(options) {
  const hosts = options.host === ALL_HOST ? SUPPORTED_HOSTS : [options.host];
  const prepared = await prepareVerifiedPackages(options, hosts);
  try {
    for (const item of prepared) {
      console.log(
        `${item.host}: verified OpenSocrates ${PRODUCT_VERSION} release and ` +
          `${item.checkedFiles} package files.`,
      );
    }
  } finally {
    await Promise.all(
      prepared.map((item) => rm(item.scratch, { recursive: true, force: true })),
    );
  }
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseCli(argv);
  if (options.action === "help") {
    showHelp();
    return 0;
  }
  if (options.action === "status") {
    await showStatus(options.host);
    return 0;
  }
  if (options.action === "verify") {
    await verifyPackages(options);
    return 0;
  }
  if (options.action === "auto-update" && options.autoUpdateAction === "status") {
    await showAutoUpdateStatus();
    return 0;
  }
  return withOperationLock(async () => {
    if (options.action === "remove") {
      await runRemove(options);
      return 0;
    }
    if (options.action === "auto-update") {
      if (options.autoUpdateAction === "enable") {
        await enableAutoUpdate(options);
      } else if (options.autoUpdateAction === "disable") {
        await disableAutoUpdate();
      } else {
        requireSupportedPlatform();
        await runScheduledUpdate(options);
      }
      return 0;
    }
    requireSupportedPlatform();
    await runInstallOrUpdate(options, options.action);
    return 0;
  });
}

let invokedDirectly = false;
if (process.argv[1] !== undefined) {
  try {
    invokedDirectly = realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    invokedDirectly = false;
  }
}
if (invokedDirectly) {
  main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`error: ${message}`);
    process.exitCode = 1;
  });
}
