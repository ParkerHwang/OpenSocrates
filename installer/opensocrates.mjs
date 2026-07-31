#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { createReadStream, createWriteStream, realpathSync } from "node:fs";
import {
  access,
  cp,
  lstat,
  mkdir,
  mkdtemp,
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

export const PRODUCT_VERSION = "1.0.0";
export const REPOSITORY = "ParkerHwang/OpenSocrates";
export const MARKETPLACE_NAME = "opensocrates";
export const PLUGIN_NAME = "opensocrates";
export const PLUGIN_ID = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
export const ASSET_NAME = `opensocrates-${PRODUCT_VERSION}-codex-plugin.zip`;
export const CHECKSUM_NAME = `${ASSET_NAME}.sha256`;

const MARKER_NAME = ".opensocrates-managed.json";
const MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
});
const MARKETPLACE_RELATIVE = join(".agents", "plugins", "marketplace.json");
const PLUGIN_RELATIVE = join("build", "generated", "plugins", "codex");
const MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024;
const MAX_ARCHIVE_ENTRIES = 10_000;

export class InstallerError extends Error {}

function fail(message) {
  throw new InstallerError(message);
}

async function exists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
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

export function markerMatches(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    jsonEqual(value, MARKER)
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
  const actions = new Set(["install", "status", "update", "remove", "verify", "help"]);
  const args = [...argv];
  let action = "install";
  if (args[0] && !args[0].startsWith("-")) {
    action = args.shift();
  }
  if (!actions.has(action)) {
    fail(`unknown action ${JSON.stringify(action)}`);
  }
  const options = { action, asset: null, checksum: null };
  while (args.length > 0) {
    const flag = args.shift();
    if (flag === "--help" || flag === "-h") {
      options.action = "help";
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
  }
  if ((options.asset === null) !== (options.checksum === null)) {
    fail("--asset and --checksum must be supplied together");
  }
  if (["status", "remove", "help"].includes(options.action) && options.asset !== null) {
    fail(`${options.action} does not accept --asset or --checksum`);
  }
  return options;
}

function showHelp() {
  console.log(`OpenSocrates ${PRODUCT_VERSION}

Usage:
  opensocrates install [--asset ZIP --checksum SHA256]
  opensocrates status
  opensocrates update [--asset ZIP --checksum SHA256]
  opensocrates remove
  opensocrates verify [--asset ZIP --checksum SHA256]

Without --asset, install, update, and verify download the v${PRODUCT_VERSION}
package and checksum from GitHub Releases.
`);
}

function managedPaths() {
  const configured = process.env.CODEX_HOME;
  const codexHome = resolve(configured ? configured : join(homedir(), ".codex"));
  const root = join(codexHome, "managed-marketplaces", MARKETPLACE_NAME);
  return {
    codexHome,
    root,
    parent: dirname(root),
    marker: join(root, MARKER_NAME),
    marketplace: join(root, MARKETPLACE_RELATIVE),
    plugin: join(root, PLUGIN_RELATIVE),
  };
}

function codexBinary() {
  return process.env.CODEX_BIN || "codex";
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

function runCodexJson(args) {
  const result = run(codexBinary(), args);
  try {
    const payload = JSON.parse(result.stdout);
    if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
      fail("Codex returned a non-object JSON value");
    }
    return payload;
  } catch (error) {
    if (error instanceof InstallerError) {
      throw error;
    }
    fail(`Codex returned invalid JSON for ${args.join(" ")}: ${error.message}`);
  }
}

function requireCodex() {
  run(codexBinary(), ["--version"]);
}

function marketplaceEntry() {
  const payload = runCodexJson(["plugin", "marketplace", "list", "--json"]);
  const entries = payload.marketplaces;
  if (!Array.isArray(entries)) {
    fail("Codex marketplace list returned an unexpected schema");
  }
  const matches = entries.filter((entry) => entry?.name === MARKETPLACE_NAME);
  if (matches.length > 1) {
    fail(`Codex reported duplicate marketplaces named ${MARKETPLACE_NAME}`);
  }
  return matches[0] ?? null;
}

function pluginState() {
  const payload = runCodexJson([
    "plugin",
    "list",
    "--marketplace",
    MARKETPLACE_NAME,
    "--available",
    "--json",
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

async function requireOwnedRoot(root) {
  const info = await lstat(root);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail(`managed marketplace path is not an owned directory: ${root}`);
  }
  const marker = await readJsonObject(join(root, MARKER_NAME));
  if (!markerMatches(marker)) {
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

async function resolveAssetInputs(options, scratch) {
  if (options.asset !== null) {
    if (!(await exists(options.asset)) || !(await exists(options.checksum))) {
      fail("the supplied asset or checksum file does not exist");
    }
    return { asset: options.asset, checksum: options.checksum };
  }
  const base = `https://github.com/${REPOSITORY}/releases/download/v${PRODUCT_VERSION}`;
  const asset = join(scratch, ASSET_NAME);
  const checksum = join(scratch, CHECKSUM_NAME);
  console.log(`Downloading OpenSocrates ${PRODUCT_VERSION} from GitHub Releases...`);
  await downloadFile(`${base}/${ASSET_NAME}`, asset);
  await downloadFile(`${base}/${CHECKSUM_NAME}`, checksum);
  return { asset, checksum };
}

async function verifyOuterChecksum(asset, checksum) {
  const expected = parseChecksumText(await readFile(checksum, "utf8"));
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

async function verifyExtractedPackage(pluginRoot) {
  const manifest = await readJsonObject(join(pluginRoot, ".codex-plugin", "plugin.json"));
  if (manifest.name !== PLUGIN_NAME || manifest.version !== PRODUCT_VERSION) {
    fail(
      `plugin manifest mismatch: expected ${PLUGIN_NAME} ${PRODUCT_VERSION}, ` +
        `got ${String(manifest.name)} ${String(manifest.version)}`,
    );
  }
  const release = await readJsonObject(join(pluginRoot, "release-manifest.json"));
  if (
    release.product_version !== PRODUCT_VERSION ||
    release.host !== "codex" ||
    release.schema !== "opensocrates.plugin-release-manifest/1.0.0"
  ) {
    fail("package release manifest does not match this installer");
  }
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
  return verifyPackageChecksums(pluginRoot);
}

async function prepareVerifiedPackage(options) {
  const scratch = await mkdtemp(join(tmpdir(), "opensocrates-install-"));
  try {
    const { asset, checksum } = await resolveAssetInputs(options, scratch);
    await verifyOuterChecksum(asset, checksum);
    const pluginRoot = join(scratch, "plugin");
    await extractArchive(asset, pluginRoot);
    const checkedFiles = await verifyExtractedPackage(pluginRoot);
    return { scratch, pluginRoot, checkedFiles };
  } catch (error) {
    await rm(scratch, { recursive: true, force: true });
    throw error;
  }
}

function expectedMarketplace() {
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

async function buildStagingTree(parent, pluginSource) {
  const staging = await mkdtemp(join(parent, ".opensocrates.staging-"));
  try {
    const marketplace = join(staging, MARKETPLACE_RELATIVE);
    const plugin = join(staging, PLUGIN_RELATIVE);
    await mkdir(dirname(marketplace), { recursive: true, mode: 0o700 });
    await mkdir(dirname(plugin), { recursive: true, mode: 0o700 });
    await cp(pluginSource, plugin, { recursive: true, preserveTimestamps: true });
    await writeFile(marketplace, `${JSON.stringify(expectedMarketplace(), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await writeFile(join(staging, MARKER_NAME), `${JSON.stringify(MARKER, null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await verifyExtractedPackage(plugin);
    return staging;
  } catch (error) {
    await rm(staging, { recursive: true, force: true });
    throw error;
  }
}

function entryRoot(entry) {
  if (entry === null) {
    return null;
  }
  if (typeof entry.root !== "string" || entry.root.trim().length === 0) {
    fail(`Codex marketplace ${MARKETPLACE_NAME} has no usable root`);
  }
  return resolve(entry.root);
}

function removeRegistration(entry, state) {
  if (state.kind === "installed") {
    runCodexJson(["plugin", "remove", PLUGIN_ID, "--json"]);
  }
  if (entry !== null) {
    runCodexJson(["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"]);
  }
}

function addRegistration(root, installPlugin) {
  runCodexJson(["plugin", "marketplace", "add", root, "--json"]);
  if (installPlugin) {
    return runCodexJson(["plugin", "add", PLUGIN_ID, "--json"]);
  }
  return null;
}

function removeRegistrationBestEffort() {
  const entry = (() => {
    try {
      return marketplaceEntry();
    } catch {
      return null;
    }
  })();
  if (entry === null) {
    return;
  }
  try {
    const state = pluginState();
    if (state.kind === "installed") {
      run(codexBinary(), ["plugin", "remove", PLUGIN_ID, "--json"], { allowFailure: true });
    }
  } catch {
    // Rollback continues with marketplace cleanup.
  }
  run(codexBinary(), ["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"], {
    allowFailure: true,
  });
}

async function installVerifiedPackage(pluginSource, action) {
  requireCodex();
  const paths = managedPaths();
  await mkdir(paths.parent, { recursive: true, mode: 0o700 });

  const previousEntry = marketplaceEntry();
  if (previousEntry !== null && entryRoot(previousEntry) !== paths.root) {
    fail(
      `marketplace ${MARKETPLACE_NAME} is already registered at ${entryRoot(previousEntry)}; ` +
        "refusing to overwrite an unmanaged location",
    );
  }
  const previousState = previousEntry === null ? { kind: "missing", version: null } : pluginState();
  if (await exists(paths.root)) {
    await requireOwnedRoot(paths.root);
  }

  const staging = await buildStagingTree(paths.parent, pluginSource);
  const backup = join(paths.parent, `.opensocrates.backup-${randomUUID()}`);
  let registrationRemoved = false;
  let backupCreated = false;
  let newRootActive = false;
  try {
    if (previousEntry !== null) {
      registrationRemoved = true;
      removeRegistration(previousEntry, previousState);
    }
    if (await exists(paths.root)) {
      await rename(paths.root, backup);
      backupCreated = true;
    }
    await rename(staging, paths.root);
    newRootActive = true;
    const result = addRegistration(paths.root, true);
    const state = pluginState();
    if (
      result?.pluginId !== PLUGIN_ID ||
      result?.version !== PRODUCT_VERSION ||
      state.kind !== "installed" ||
      state.version !== PRODUCT_VERSION
    ) {
      fail("Codex did not confirm the expected installed plugin and version");
    }
    if (backupCreated) {
      await requireOwnedRoot(backup);
      await rm(backup, { recursive: true });
    }
    const verb = action === "update" ? "updated" : "installed";
    console.log(`OpenSocrates ${PRODUCT_VERSION} ${verb} successfully.`);
    console.log(`Managed marketplace: ${paths.root}`);
    console.log("Start a new Codex task to load the updated skills and hooks.");
  } catch (error) {
    removeRegistrationBestEffort();
    if (newRootActive && (await exists(paths.root))) {
      await requireOwnedRoot(paths.root);
      await rm(paths.root, { recursive: true });
    }
    if (backupCreated && (await exists(backup))) {
      await requireOwnedRoot(backup);
      await rename(backup, paths.root);
    }
    if (registrationRemoved && previousEntry !== null) {
      try {
        addRegistration(paths.root, previousState.kind === "installed");
      } catch (rollbackError) {
        fail(`${error.message}; rollback also failed: ${rollbackError.message}`);
      }
    }
    throw error;
  } finally {
    if (await exists(staging)) {
      await rm(staging, { recursive: true, force: true });
    }
  }
}

async function showStatus() {
  requireCodex();
  const paths = managedPaths();
  const entry = marketplaceEntry();
  if (entry === null) {
    if (await exists(paths.root)) {
      await requireOwnedRoot(paths.root);
      console.log(`OpenSocrates files are present but not registered: ${paths.root}`);
    } else {
      console.log("OpenSocrates is not installed.");
    }
    return;
  }
  if (entryRoot(entry) !== paths.root) {
    fail(`OpenSocrates is registered at an unmanaged location: ${entryRoot(entry)}`);
  }
  await requireOwnedRoot(paths.root);
  const state = pluginState();
  if (state.kind === "installed") {
    console.log(`OpenSocrates ${state.version ?? "unknown"} is installed.`);
  } else if (state.kind === "available") {
    console.log(`OpenSocrates ${state.version ?? "unknown"} is available but not installed.`);
  } else {
    console.log("The OpenSocrates marketplace is registered, but the plugin is missing.");
  }
}

async function removeInstalled() {
  requireCodex();
  const paths = managedPaths();
  const entry = marketplaceEntry();
  if (entry !== null && entryRoot(entry) !== paths.root) {
    fail(`OpenSocrates is registered at an unmanaged location: ${entryRoot(entry)}`);
  }
  const state = entry === null ? { kind: "missing", version: null } : pluginState();
  removeRegistration(entry, state);
  if (await exists(paths.root)) {
    await requireOwnedRoot(paths.root);
    await rm(paths.root, { recursive: true });
  }
  console.log("OpenSocrates was removed from Codex.");
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseCli(argv);
  if (options.action === "help") {
    showHelp();
    return 0;
  }
  if (options.action === "status") {
    await showStatus();
    return 0;
  }
  if (options.action === "remove") {
    await removeInstalled();
    return 0;
  }
  if (
    ["install", "update"].includes(options.action) &&
    (process.platform !== "darwin" || process.arch !== "arm64")
  ) {
    fail(
      `OpenSocrates ${PRODUCT_VERSION} prebuilt installation supports darwin-arm64 only; ` +
        `detected ${process.platform}-${process.arch}`,
    );
  }

  const prepared = await prepareVerifiedPackage(options);
  try {
    console.log(
      `Verified OpenSocrates ${PRODUCT_VERSION} release and ${prepared.checkedFiles} package files.`,
    );
    if (options.action === "verify") {
      return 0;
    }
    await installVerifiedPackage(prepared.pluginRoot, options.action);
    return 0;
  } finally {
    await rm(prepared.scratch, { recursive: true, force: true });
  }
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
