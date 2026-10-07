// Additive managed-host lifecycle. No Codex engine, user settings rewrite or model calls.
import fs from "node:fs/promises";
import { constants } from "node:fs";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, parse, relative, resolve, sep } from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HOSTS = new Set(["claude", "antigravity", "claude-chat"]);
const ACTIONS = new Set(["install", "update", "status", "diagnose", "remove", "disable", "enable", "verify", "export"]);
const MARKER = ".opensocrates-managed.json";
const MARKER_SCHEMA = "opensocrates.managed-host/1.0.0";
const NAMESPACE = "opensocrates-macos";
const PLUGIN_ID = `opensocrates@${NAMESPACE}`;
const SHA = /^(?:sha256:)?[a-f0-9]{64}$/u;
const METHOD = /^[a-z0-9]+(?:-[a-z0-9]+)*$/u;
const MAX_FILES = 10_000;
const MAX_JSON_BYTES = 8 * 1024 * 1024;

export class ManagedHostError extends Error {
  constructor(code, message = code) {
    super(message);
    this.name = "ManagedHostError";
    this.code = code;
  }
}

function fail(code, message) { throw new ManagedHostError(code, message); }
function windowsArgs(action) {
  return ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", fileURLToPath(new URL("./windows.ps1", import.meta.url)), "-Action", action];
}
function windows(action, path) {
  if (process.platform !== "win32") return;
  const value = spawnSync("powershell.exe", windowsArgs(action), { encoding: "utf8", windowsHide: true, timeout: 30_000, maxBuffer: 1024 * 1024, env: { ...process.env, OPENSOCRATES_WINDOWS_PATH: path } });
  if (value.error || value.status !== 0) fail("unsafe_windows_path", "Windows ownership, DACL or reparse validation failed; no unowned path is modified.");
}
async function privateDirectory(path) {
  if (process.platform === "win32") windows("mkdir-private", path);
  else await fs.mkdir(path, { mode: 0o700 });
}
async function privateScratch(parent, prefix) {
  const path = join(parent, `${prefix}${randomUUID()}`);
  await privateDirectory(path);
  return path;
}
async function withWindowsLease(path, action) {
  if (process.platform !== "win32") return action();
  const lease = spawn("powershell.exe", windowsArgs("lease"), { windowsHide: true, stdio: ["pipe", "pipe", "pipe"], env: { ...process.env, OPENSOCRATES_WINDOWS_PATH: path } });
  let ready = false, exited = false;
  lease.on("exit", () => { exited = true; });
  lease.stderr.resume(); // Host/user paths and raw helper errors are never retained.
  try {
    await new Promise((accept, reject) => {
      let output = "";
      const timer = setTimeout(() => reject(new ManagedHostError("unsafe_windows_path", "Cannot acquire the Windows directory lease.")), 30_000);
      const failed = () => { clearTimeout(timer); reject(new ManagedHostError("unsafe_windows_path", "Windows directory lease was unavailable.")); };
      lease.once("error", failed); lease.once("exit", failed);
      lease.stdout.on("data", (data) => {
        output += data.toString("utf8");
        if (output.length > 64) failed();
        if (output === "ready\r\n" || output === "ready\n") { ready = true; clearTimeout(timer); accept(); }
      });
    });
    const value = await action();
    if (exited) fail("lease_interrupted", "Windows ancestor protection was interrupted; inspect the owned recovery state before retrying.");
    return value;
  } finally {
    if (ready && !exited) {
      const closed = new Promise((accept) => lease.once("exit", accept));
      lease.stdin.end("done\n");
      await closed;
    } else if (!exited) lease.kill();
  }
}
function object(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function hash(bytes) { return createHash("sha256").update(bytes).digest("hex"); }
function digest(value) {
  if (typeof value !== "string" || !SHA.test(value)) fail("invalid_inventory", "Invalid SHA-256 inventory.");
  return value.replace(/^sha256:/u, "");
}
function safeRelative(value) {
  if (typeof value !== "string" || !value || value.includes("\\") || value.includes("\0") || isAbsolute(value) || value.split("/").some((p) => !p || p === "." || p === "..")) {
    fail("unsafe_path", "Package inventory contains an unsafe relative path.");
  }
  if (value.split("/").some((part) => /[\x00-\x1f<>:"|?*]/u.test(part) || /[. ]$/u.test(part) || /^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/iu.test(part))) fail("unsafe_path", "Package paths must not use Windows aliases or alternate streams.");
  return value;
}
async function entry(path) {
  try { return await fs.lstat(path); } catch (error) { if (error.code === "ENOENT") return null; throw error; }
}
async function regular(path) {
  const info = await entry(path);
  if (!info || !info.isFile() || info.isSymbolicLink()) fail("unsafe_path", "Expected an owned regular file.");
  return info;
}
async function safeParents(path, { create = false } = {}) {
  const absolute = resolve(path);
  if (process.platform === "win32" && !/^[a-z]:[\\/]/iu.test(absolute)) fail("unsafe_path", "Managed Windows paths require a local absolute drive path.");
  const root = parse(absolute).root;
  const parts = absolute.slice(root.length).split(sep).filter(Boolean);
  let current = root;
  for (const part of parts) {
    current = join(current, part);
    let info = await entry(current);
    if (!info && create) { await privateDirectory(current); info = await fs.lstat(current); }
    if (!info || !info.isDirectory() || info.isSymbolicLink()) fail("unsafe_path", "Managed directory or ancestor is missing, linked or not a directory.");
  }
  return absolute;
}
async function json(path) {
  const info = await regular(path);
  if (info.size > MAX_JSON_BYTES) fail("invalid_manifest", "Manifest exceeds the bounded input size.");
  let result;
  try { result = JSON.parse(await fs.readFile(path, "utf8")); } catch { fail("invalid_manifest", "Cannot read a valid managed manifest."); }
  if (!object(result)) fail("invalid_manifest", "Managed manifest must be an object.");
  return result;
}
async function files(root) {
  windows("check-tree", root);
  const rootInfo = await entry(root);
  if (!rootInfo || !rootInfo.isDirectory() || rootInfo.isSymbolicLink()) fail("unsafe_path", "Package or managed root is not a regular directory.");
  const result = {};
  async function walk(directory) {
    const children = await fs.readdir(directory, { withFileTypes: true });
    for (const child of children) {
      const path = join(directory, child.name);
      const info = await fs.lstat(path);
      if (info.isSymbolicLink()) fail("unsafe_path", "Symlinks are not supported in managed packages.");
      if (info.isDirectory()) await walk(path);
      else if (info.isFile()) {
        if (Object.keys(result).length >= MAX_FILES) fail("invalid_inventory", "Managed inventory exceeds its file bound.");
        result[relative(root, path).split(sep).join("/")] = hash(await fs.readFile(path));
      } else fail("unsafe_path", "Special filesystem entries are not supported.");
    }
  }
  await walk(root);
  return result;
}
function inventory(rows) {
  if (!Array.isArray(rows) || !rows.length || rows.length > MAX_FILES) fail("invalid_inventory", "Missing complete file inventory.");
  const result = {};
  for (const item of rows) {
    if (!object(item) || Object.keys(item).sort().join(",") !== "path,sha256") fail("invalid_inventory", "Inventory rows must contain path and sha256 only.");
    const name = safeRelative(item.path);
    if (Object.hasOwn(result, name)) fail("invalid_inventory", "Duplicate inventory path.");
    result[name] = digest(item.sha256);
  }
  return result;
}
function equalInventory(actual, expected) {
  const names = Object.keys(actual).sort();
  return JSON.stringify(names) === JSON.stringify(Object.keys(expected).sort()) && names.every((name) => actual[name] === expected[name]);
}
function canonical(manifest, expected, skillRoot) {
  const ids = manifest.method_ids;
  if (manifest.method_count !== 48 || !Array.isArray(ids) || ids.length !== 48 || new Set(ids).size !== 48 || ids.some((id) => typeof id !== "string" || !METHOD.test(id))) fail("invalid_canonical_content", "Expected 48 unique canonical methods.");
  if (!Array.isArray(manifest.canonical_methods) || manifest.canonical_methods.length !== 96) fail("invalid_canonical_content", "Expected all 96 EN/KO canonical procedures.");
  const seen = new Set();
  for (const row of manifest.canonical_methods) {
    if (!object(row) || Object.keys(row).sort().join(",") !== "locale,method_id,path,sha256" || !ids.includes(row.method_id) || !["en", "ko"].includes(row.locale)) fail("invalid_canonical_content", "Canonical procedure identity is invalid.");
    const name = `${skillRoot}/references/decision/methods/${row.locale}/${row.method_id}.md`;
    const key = `${row.locale}:${row.method_id}`;
    if (row.path !== name || seen.has(key) || expected[name] !== digest(row.sha256)) fail("invalid_canonical_content", "Canonical procedure path or hash is inconsistent.");
    seen.add(key);
  }
}
async function verifyPackage(root, host, version) {
  const actual = await files(root);
  const manifestPath = host === "claude-chat" ? "opensocrates/release-manifest.json" : "release-manifest.json";
  const manifest = await json(join(root, manifestPath));
  if (manifest.product_version !== version || manifest.host !== host) fail("package_identity_mismatch", "Package host/version does not match the requested installer.");
  const expected = inventory(manifest.files);
  if (Object.hasOwn(expected, manifestPath)) fail("invalid_inventory", "A manifest cannot inventory itself.");
  const rest = { ...actual };
  delete rest[manifestPath];
  if (host === "claude") {
    if (manifest.schema !== "opensocrates.plugin-release-manifest/1.0.0") fail("invalid_manifest", "Invalid native plugin release manifest.");
    // Release assembly adds an exact package checksum file outside the generator inventory.
    if (Object.hasOwn(rest, "checksums.sha256") && !Object.hasOwn(expected, "checksums.sha256")) {
      const text = await fs.readFile(join(root, "checksums.sha256"), "utf8");
      const checksums = {};
      for (const line of text.trim().split(/\r?\n/u)) {
        const match = /^([a-f0-9]{64})  (.+)$/u.exec(line);
        if (!match || Object.hasOwn(checksums, match[2])) fail("invalid_inventory", "Invalid native checksum inventory.");
        checksums[safeRelative(match[2])] = match[1];
      }
      const full = { ...actual }; delete full["checksums.sha256"];
      if (!equalInventory(full, checksums)) fail("inventory_mismatch", "Native checksum inventory does not match the package.");
      delete rest["checksums.sha256"];
    }
    if (!equalInventory(rest, expected)) fail("inventory_mismatch", "Native package has modified, missing or unknown files.");
    const plugin = await json(join(root, ".claude-plugin/plugin.json"));
    if (plugin.name !== "opensocrates" || plugin.version !== version || manifest.method_count !== 48 || !Array.isArray(manifest.method_ids) || manifest.method_ids.length !== 48 || new Set(manifest.method_ids).size !== 48 || manifest.method_ids.some((id) => typeof id !== "string" || !METHOD.test(id))) fail("package_identity_mismatch", "Native plugin or core method identity is inconsistent.");
    for (const key of ["runtime_targets", "release_targets"]) if (JSON.stringify(manifest[key]) !== '["darwin-arm64"]') fail("unsupported_package_target", "The Claude companion must contain only the Apple-silicon Mac runtime.");
    if (Object.keys(expected).some((name) => name.startsWith("runtime/") && !name.startsWith("runtime/darwin-arm64/"))) fail("unsupported_package_target", "The Claude companion contains an undeclared runtime target.");
    const runtime = join(root, "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime");
    if (process.platform !== "win32" && !((await regular(runtime)).mode & 0o111)) fail("invalid_runtime", "The Mac runtime is not executable.");
    await regular(runtime);
    const launcher = join(root, "bin/launch.sh");
    if ((process.platform !== "win32" && !((await regular(launcher)).mode & 0o111)) || JSON.stringify(manifest.launchers) !== '["bin/launch.sh"]') fail("invalid_runtime", "The Mac launcher identity is invalid.");
    await regular(launcher);
    const localeIds = { en: new Set(), ko: new Set() };
    for (const name of Object.keys(expected)) {
      const match = /^skills\/opensocrates\/references\/decision\/methods\/(en|ko)\/([a-z0-9-]+)\.md$/u.exec(name);
      if (match) localeIds[match[1]].add(match[2]);
    }
    for (const locale of ["en", "ko"]) if (localeIds[locale].size !== 48 || manifest.method_ids.some((id) => !localeIds[locale].has(id))) fail("invalid_canonical_content", "The native companion is missing full EN/KO canonical procedures.");
  } else {
    if (manifest.schema !== "opensocrates.content-host-manifest/1.0.0" || !equalInventory(rest, expected)) fail("inventory_mismatch", "Content package has modified, missing or unknown files.");
    const skillRoot = host === "claude-chat" ? "opensocrates" : ".agents/skills/opensocrates";
    if (manifest.skill_root !== skillRoot || !object(manifest.source_identity) || !/^sha256:[a-f0-9]{64}$/u.test(manifest.source_identity.canonical ?? "") || !/^sha256:[a-f0-9]{64}$/u.test(manifest.source_identity.templates ?? "") || manifest.source_identity.canonical !== manifest.source_tree_hash) fail("invalid_manifest", "Content package source identity is missing or inconsistent.");
    for (const key of ["launchers", "runtime_targets"]) if (JSON.stringify(manifest[key]) !== "[]") fail("unexpected_executable_surface", "Content packages cannot carry launchers or native runtimes.");
    if (JSON.stringify(manifest.public_skills) !== '["opensocrates"]') fail("invalid_manifest", "Expected one public discovery controller.");
    for (const name of Object.keys(actual)) {
      if (host === "claude-chat" ? !name.startsWith("opensocrates/") : name !== manifestPath && name !== ".agents/rules/opensocrates.md" && !name.startsWith(`${skillRoot}/`)) fail("invalid_layout", "Unexpected content package layout.");
      if (name.split("/").some((part) => ["bin", "runtime", "hooks", ".claude-plugin"].includes(part))) fail("unexpected_executable_surface", "Content package contains a native integration surface.");
      if (process.platform !== "win32" && (await regular(join(root, name))).mode & 0o111) fail("unexpected_executable_surface", "Content package contains an executable file.");
      if (/\.(?:exe|dll|com|cmd|bat|ps1|sh|mjs|py|pyc)$/iu.test(name)) fail("unexpected_executable_surface", "Content packages contain authored references only.");
    }
    if (!Object.hasOwn(expected, `${skillRoot}/SKILL.md`)) fail("invalid_layout", "Discovery skill is missing.");
    canonical(manifest, expected, skillRoot);
    if (host === "antigravity") {
      const rule = await fs.readFile(join(root, ".agents/rules/opensocrates.md"));
      if (rule.length > 4096 || !rule.toString("utf8").startsWith("---\ntrigger: always_on\n")) fail("invalid_layout", "Antigravity entry must be a bounded always_on rule.");
    }
  }
  return { root, host, version, manifest, manifestPath, hashes: actual };
}

function marker(host, scope, version, hashes, enabled) {
  return { schema: MARKER_SCHEMA, host, scope, version, hashes, enabled };
}
function validateMarker(value, host, scope) {
  if (!object(value) || Object.keys(value).sort().join(",") !== "enabled,hashes,host,schema,scope,version" || value.schema !== MARKER_SCHEMA || value.host !== host || value.scope !== scope || typeof value.enabled !== "boolean" || !/^\d+\.\d+\.\d+$/u.test(value.version) || !object(value.hashes) || !Object.keys(value.hashes).length) fail("unowned_collision", "Existing managed root has no exact ownership marker.");
  for (const [name, valueHash] of Object.entries(value.hashes)) { safeRelative(name); digest(valueHash); }
  return value;
}
async function writeJson(path, value) {
  await fs.writeFile(path, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600, flag: "wx" });
  windows("seal-new", path);
}
async function atomicMarker(path, value) {
  const temporary = join(dirname(path), `.opensocrates-marker-${randomUUID()}`);
  try { await writeJson(temporary, value); await fs.rename(temporary, path); }
  finally { await fs.rm(temporary, { force: true }); }
}
async function withLock(root, host, action) {
  await safeParents(root, { create: true });
  windows("check", root);
  const lock = join(root, `.opensocrates-${host}-operation.lock`);
  let descriptor;
  try { descriptor = await fs.open(lock, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600); }
  catch (error) { if (error.code === "EEXIST" || error.code === "ELOOP") fail("operation_locked", "Another managed-host operation is active; no stale lock is removed automatically."); throw error; }
  const identity = await descriptor.stat();
  try { windows("seal-new", lock); return await withWindowsLease(root, action); }
  finally {
    const current = await entry(lock);
    await descriptor.close();
    if (!current || current.dev !== identity.dev || current.ino !== identity.ino || current.isSymbolicLink()) fail("operation_lock_changed", "Operation lock changed; no replacement lock is deleted.");
    await fs.unlink(lock);
  }
}

function basePaths(options) {
  if (options.host === "claude") {
    if (options.workspace) fail("invalid_scope", "The native Claude companion uses explicit user scope.");
    const base = resolve(process.env.CLAUDE_CONFIG_DIR || join(homedir(), ".claude"));
    return { base, scope: "global", root: join(base, "managed-marketplaces", NAMESPACE) };
  }
  if (options.workspace !== null && options.workspace !== undefined) {
    if (typeof options.workspace !== "string" || !isAbsolute(options.workspace)) fail("invalid_scope", "Workspace must be an explicit absolute existing directory.");
    const workspace = resolve(options.workspace);
    return { workspace, base: join(workspace, ".agents"), scope: "workspace", root: join(workspace, ".agents/.opensocrates-managed/antigravity"), rule: join(workspace, ".agents/rules/opensocrates.md"), skill: join(workspace, ".agents/skills/opensocrates") };
  }
  const base = resolve(process.env.ANTIGRAVITY_CONFIG_DIR || join(homedir(), ".gemini/config"));
  return { base, scope: "global", root: join(base, ".opensocrates-managed/antigravity"), rule: join(base, "rules/opensocrates.md"), skill: join(base, "skills/opensocrates") };
}
function result(options, details = {}) {
  return { host: options.host, action: options.action, automatic_entry: "unverified", method_application: "unverified", ...details };
}
function cli(helpers, args, { jsonOutput = false } = {}) {
  const command = spawnSync(helpers.claudeBinary || process.env.CLAUDE_BIN || "claude", args, { encoding: "utf8", windowsHide: true, timeout: 30_000, maxBuffer: 8 * 1024 * 1024, env: process.env });
  if (command.error || command.status !== 0) fail("claude_cli_unavailable", "Claude plugin operation failed; host output is not retained.");
  if (!jsonOutput) return null;
  try { return JSON.parse(command.stdout); } catch { fail("claude_cli_schema", "Claude plugin command did not return valid JSON."); }
}
function arrayResult(value, key) {
  if (Array.isArray(value)) return value;
  if (object(value) && Array.isArray(value[key])) return value[key];
  fail("claude_cli_schema", "Claude plugin inventory has an unrecognized JSON shape.");
}
function nativeState(helpers, paths) {
  const marketplaces = arrayResult(cli(helpers, ["plugin", "marketplace", "list", "--json"], { jsonOutput: true }), "marketplaces");
  const matches = marketplaces.filter((value) => value?.name === NAMESPACE);
  if (matches.length > 1) fail("unowned_collision", "Claude reports duplicate managed marketplace names.");
  const registration = matches[0] ?? null;
  if (registration) {
    const source = registration.source;
    const location = registration.path ?? registration.installLocation ?? registration.root ?? (object(source) ? source.path : null);
    // Prefer the original local source when the CLI also exposes a cache installLocation.
    const sourcePath = object(source) && typeof source.path === "string" ? source.path : location;
    if ((typeof source === "string" && source !== "directory") || typeof sourcePath !== "string" || !isAbsolute(sourcePath) || resolve(sourcePath) !== paths.root || (registration.scope && registration.scope !== "user")) fail("unowned_collision", "Claude marketplace name is registered to an unmanaged origin or scope.");
  }
  const plugins = arrayResult(cli(helpers, ["plugin", "list", "--json"], { jsonOutput: true }), "plugins");
  const installed = plugins.filter((value) => (value?.id ?? value?.pluginId ?? value?.name) === PLUGIN_ID);
  if (installed.length > 1) fail("unowned_collision", "Claude reports duplicate managed plugin origins.");
  const plugin = installed[0] ?? null;
  if (plugin && (!registration || plugin.scope !== "user")) fail("unowned_collision", "Claude plugin has an unmanaged registration or scope.");
  if (plugin && (typeof plugin.enabled !== "boolean" || typeof plugin.version !== "string")) fail("claude_cli_schema", "Claude plugin enabled state or version is unavailable.");
  return { registration, plugin, enabled: plugin ? plugin.enabled !== false : null, version: plugin?.version ?? null };
}
function registerNative(helpers, paths, enabled) {
  cli(helpers, ["plugin", "marketplace", "add", paths.root, "--scope", "user"]);
  cli(helpers, ["plugin", "install", PLUGIN_ID, "--scope", "user", "--json"], { jsonOutput: true });
  if (!enabled) cli(helpers, ["plugin", "disable", PLUGIN_ID, "--scope", "user"]);
}
function unregisterNative(helpers, state) {
  if (state.plugin) cli(helpers, ["plugin", "uninstall", PLUGIN_ID, "--scope", "user"]);
  if (state.registration) cli(helpers, ["plugin", "marketplace", "remove", NAMESPACE, "--scope", "user"]);
}
async function nativeOwned(paths) {
  if (!(await entry(paths.base))) return null;
  await safeParents(paths.base);
  windows("check", paths.base);
  const info = await entry(paths.root);
  if (!info) return null;
  if (!info.isDirectory() || info.isSymbolicLink()) fail("unsafe_path", "Claude managed root is linked or not a directory.");
  await safeParents(paths.root);
  const owned = validateMarker(await json(join(paths.root, MARKER)), "claude", paths.scope);
  const actual = await files(paths.root); delete actual[MARKER];
  if (!equalInventory(actual, owned.hashes)) fail("owned_files_modified", "Claude managed files have changed, are missing or contain unknown additions.");
  return owned;
}
async function nativeInstall(options, helpers, paths, prepared) {
  const owned = await nativeOwned(paths);
  const before = nativeState(helpers, paths);
  if (before.registration && !owned) fail("unowned_collision", "Existing Claude registration has no owned managed root.");
  const enabled = before.plugin ? before.enabled : owned?.enabled ?? true;
  await safeParents(dirname(paths.root), { create: true });
  const scratch = await fs.mkdtemp(join(dirname(paths.root), ".opensocrates-transaction-"));
  const staging = join(scratch, "staging");
  const backup = join(scratch, "backup");
  let oldMoved = false, activated = false, registrationTouched = false;
  try {
    await fs.mkdir(staging, { mode: 0o700 });
    await fs.cp(prepared.root, join(staging, "plugin"), { recursive: true, preserveTimestamps: true, dereference: false });
    await fs.mkdir(join(staging, ".claude-plugin"), { mode: 0o700 });
    await writeJson(join(staging, ".claude-plugin/marketplace.json"), { name: NAMESPACE, owner: { name: "OpenSocrates" }, plugins: [{ name: "opensocrates", source: "./plugin", version: helpers.version }] });
    const hashes = await files(staging);
    await writeJson(join(staging, MARKER), marker("claude", paths.scope, helpers.version, hashes, enabled));
    // Repeat the ownership check immediately before unregistering/moving anything.
    if (owned) await nativeOwned(paths);
    else if (await entry(paths.root)) fail("unowned_collision", "A managed target appeared during staging.");
    registrationTouched = true;
    unregisterNative(helpers, before);
    if (owned) { await fs.rename(paths.root, backup); oldMoved = true; }
    await fs.rename(staging, paths.root); activated = true;
    registerNative(helpers, paths, enabled);
    const after = nativeState(helpers, paths);
    if (!after.plugin || after.version !== helpers.version || after.enabled !== enabled) fail("claude_registration_unconfirmed", "Claude did not confirm the exact companion version and enabled state.");
    await nativeOwned(paths);
    if (oldMoved) { await nativeOwned({ ...paths, root: backup }); await fs.rm(backup, { recursive: true }); oldMoved = false; }
    return result(options, { installation: "installed", version: helpers.version, enabled, scope: paths.scope, registration: "confirmed" });
  } catch (error) {
    let rollbackFailed = false;
    if (registrationTouched) try { unregisterNative(helpers, nativeState(helpers, paths)); } catch { rollbackFailed = true; }
    try {
      if (activated) { await nativeOwned(paths); await fs.rm(paths.root, { recursive: true }); }
      if (oldMoved) { await fs.rename(backup, paths.root); oldMoved = false; }
      if (registrationTouched && before.registration) {
        cli(helpers, ["plugin", "marketplace", "add", paths.root, "--scope", "user"]);
        if (before.plugin) {
          cli(helpers, ["plugin", "install", PLUGIN_ID, "--scope", "user", "--json"], { jsonOutput: true });
          if (!before.enabled) cli(helpers, ["plugin", "disable", PLUGIN_ID, "--scope", "user"]);
        }
      }
    } catch { rollbackFailed = true; }
    if (rollbackFailed) fail("rollback_incomplete", "Claude rollback was incomplete; owned backups are preserved for recovery.");
    throw error;
  } finally {
    // Never discard the last preserved old tree when rollback was incomplete.
    if (!oldMoved) await fs.rm(scratch, { recursive: true, force: true });
  }
}
async function nativeAction(options, helpers, paths) {
  if (!(await entry(paths.base))) return result(options, { installation: "missing", version: null, enabled: false, scope: paths.scope, integrity: "not-installed", registration: "absent" });
  const owned = await nativeOwned(paths);
  const before = nativeState(helpers, paths);
  if (before.registration && !owned) fail("unowned_collision", "Registered companion has no exact owned root.");
  if (options.action === "status" || options.action === "diagnose") return result(options, { installation: owned ? before.plugin ? "installed" : "files-only" : "missing", version: owned?.version ?? null, enabled: before.enabled, scope: paths.scope, integrity: owned ? "verified" : "not-installed", registration: before.registration ? "confirmed" : "absent" });
  if (!owned) return result(options, { installation: "missing", version: null, enabled: false, scope: paths.scope });
  if (options.action === "enable" || options.action === "disable") {
    if (!before.plugin) fail("claude_registration_unconfirmed", "Enable or disable requires the exact installed companion registration.");
    const enabled = options.action === "enable";
    try {
      cli(helpers, ["plugin", options.action, PLUGIN_ID, "--scope", "user"]);
      const after = nativeState(helpers, paths);
      if (!after.plugin || after.enabled !== enabled) fail("claude_registration_unconfirmed", "Claude did not confirm the enabled state.");
      await nativeOwned(paths);
      await atomicMarker(join(paths.root, MARKER), { ...owned, enabled });
    } catch (error) {
      try { cli(helpers, ["plugin", before.enabled ? "enable" : "disable", PLUGIN_ID, "--scope", "user"]); } catch { fail("rollback_incomplete", "Claude enabled-state rollback was incomplete."); }
      throw error;
    }
    return result(options, { installation: "installed", version: owned.version, enabled, scope: paths.scope, registration: "confirmed" });
  }
  const backup = join(dirname(paths.root), `.opensocrates-removal-${randomUUID()}`);
  let moved = false;
  try {
    unregisterNative(helpers, before);
    await nativeOwned(paths);
    await fs.rename(paths.root, backup); moved = true;
    const backupFiles = await files(backup); delete backupFiles[MARKER];
    if (!equalInventory(backupFiles, owned.hashes)) fail("owned_files_modified", "Managed files changed during removal.");
    await fs.rm(backup, { recursive: true }); moved = false;
  } catch (error) {
    try {
      if (moved) { await fs.rename(backup, paths.root); moved = false; }
      if (before.registration) {
        cli(helpers, ["plugin", "marketplace", "add", paths.root, "--scope", "user"]);
        if (before.plugin) {
          cli(helpers, ["plugin", "install", PLUGIN_ID, "--scope", "user", "--json"], { jsonOutput: true });
          if (!before.enabled) cli(helpers, ["plugin", "disable", PLUGIN_ID, "--scope", "user"]);
        }
      }
    } catch { fail("rollback_incomplete", "Claude removal rollback was incomplete; owned backup remains."); }
    throw error;
  }
  return result(options, { installation: "missing", version: null, enabled: false, scope: paths.scope, registration: "absent" });
}

function antiPhysical(paths, logical, enabled) {
  if (logical === "release-manifest.json") return join(paths.root, "release-manifest.json");
  if (logical === ".agents/rules/opensocrates.md") return enabled ? paths.rule : join(paths.root, "disabled/rule.md");
  const prefix = ".agents/skills/opensocrates/";
  if (!logical.startsWith(prefix)) fail("invalid_inventory", "Unexpected modular content path.");
  return join(enabled ? paths.skill : join(paths.root, "disabled/skill"), logical.slice(prefix.length));
}
async function antiOwned(paths) {
  if (paths.workspace) await safeParents(paths.workspace);
  const baseInfo = await entry(paths.base);
  if (!baseInfo) return null;
  await safeParents(paths.base);
  windows("check", paths.base);
  // A legacy plugin is a separate owned scope; never overwrite or duplicate it silently.
  const legacy = join(paths.base, "plugins/opensocrates");
  if (await entry(legacy)) fail("unowned_collision", "A legacy Antigravity OpenSocrates plugin must be reconciled separately.");
  if (!(await entry(paths.root))) {
    if (await entry(paths.rule) || await entry(paths.skill)) fail("unowned_collision", "Antigravity entry/skill already exists without this exact ownership marker.");
    return null;
  }
  await safeParents(paths.root);
  windows("check-tree", paths.root);
  const owned = validateMarker(await json(join(paths.root, MARKER)), "antigravity", paths.scope);
  if (owned.enabled) windows("check", paths.rule);
  const actual = {};
  for (const name of Object.keys(owned.hashes)) {
    const path = antiPhysical(paths, name, owned.enabled);
    await safeParents(dirname(path));
    await regular(path);
    actual[name] = hash(await fs.readFile(path));
  }
  if (!equalInventory(actual, owned.hashes)) fail("owned_files_modified", "Antigravity managed content was modified or is incomplete.");
  const skill = owned.enabled ? paths.skill : join(paths.root, "disabled/skill");
  const expectedSkill = {};
  for (const [name, value] of Object.entries(owned.hashes)) if (name.startsWith(".agents/skills/opensocrates/")) expectedSkill[name.slice(".agents/skills/opensocrates/".length)] = value;
  if (!equalInventory(await files(skill), expectedSkill)) fail("owned_files_modified", "Antigravity skill contains unknown or modified files.");
  const store = await files(paths.root); delete store[MARKER];
  const expectedStore = { "release-manifest.json": owned.hashes["release-manifest.json"] };
  if (!owned.enabled) {
    expectedStore["disabled/rule.md"] = owned.hashes[".agents/rules/opensocrates.md"];
    for (const [name, value] of Object.entries(expectedSkill)) expectedStore[`disabled/skill/${name}`] = value;
    if (await entry(paths.rule) || await entry(paths.skill)) fail("unowned_collision", "Disabled Antigravity targets were replaced by unrelated files.");
  }
  if (!equalInventory(store, expectedStore)) fail("owned_files_modified", "Antigravity metadata contains unknown or modified files.");
  return owned;
}
async function antiParents(paths) {
  const parents = [...new Set([dirname(paths.rule), dirname(paths.skill), dirname(paths.root)])];
  for (const parent of parents) { await safeParents(parent, { create: true }); windows("check", parent); }
  return parents;
}
async function antiStage(paths, source, enabled, version, hashes) {
  await safeParents(paths.base, { create: true });
  await antiParents(paths);
  const scratch = await privateScratch(paths.base, ".opensocrates-transaction-");
  try {
    const store = join(scratch, "store");
    await fs.mkdir(store, { mode: 0o700 });
    await fs.copyFile(join(source, "release-manifest.json"), join(store, "release-manifest.json"));
    const rule = join(scratch, "rule.md"), skill = join(scratch, "skill");
    await fs.copyFile(join(source, ".agents/rules/opensocrates.md"), rule);
    await fs.cp(join(source, ".agents/skills/opensocrates"), skill, { recursive: true, dereference: false });
    if (!enabled) {
      await fs.mkdir(join(store, "disabled"), { mode: 0o700 });
      await fs.rename(rule, join(store, "disabled/rule.md"));
      await fs.rename(skill, join(store, "disabled/skill"));
    }
    await writeJson(join(store, MARKER), marker("antigravity", paths.scope, version, hashes, enabled));
    windows("seal-new", scratch);
    return { scratch, store, rule: enabled ? rule : null, skill: enabled ? skill : null };
  } catch (error) { await fs.rm(scratch, { recursive: true, force: true }); throw error; }
}
async function antiSwap(paths, stage, previous) {
  // Pin the actual mutation parents as well as the operation root. A root
  // handle alone does not prevent a rules/skills directory being replaced.
  let entered = false;
  try {
    const parents = await antiParents(paths);
    const held = (index) => index === parents.length
      ? (entered = true, antiSwapHeld(paths, stage, previous))
      : withWindowsLease(parents[index], () => held(index + 1));
    return await held(0);
  } catch (error) {
    if (!entered) throw new ManagedHostError(error.code ?? "transaction_unavailable", `Transaction parent protection failed; preserve the prepared recovery directory: ${stage.scratch}`);
    throw error;
  }
}
async function antiSwapHeld(paths, stage, previous) {
  const targets = [
    { target: paths.rule, staged: stage.rule },
    { target: paths.skill, staged: stage.skill },
    { target: paths.root, staged: stage.store },
  ];
  const changes = [];
  let rollbackComplete = true;
  try {
    const current = await antiOwned(paths);
    if (JSON.stringify(current) !== JSON.stringify(previous)) fail("owned_files_modified", "Managed state changed during staging.");
    for (let index = 0; index < targets.length; index++) {
      const item = targets[index];
      await safeParents(dirname(item.target), { create: true });
      const priorInfo = await entry(item.target);
      if (priorInfo && (priorInfo.isSymbolicLink() || (!priorInfo.isFile() && !priorInfo.isDirectory()))) fail("unsafe_path", "A transaction target changed to an unsafe filesystem entry.");
      const beforeHashes = priorInfo ? priorInfo.isDirectory() && !priorInfo.isSymbolicLink() ? await files(item.target) : { ".": hash(await fs.readFile(item.target)) } : null;
      const placedHashes = item.staged ? (await fs.lstat(item.staged)).isDirectory() ? await files(item.staged) : { ".": hash(await fs.readFile(item.staged)) } : null;
      const change = { ...item, beforeHashes, placedHashes, backup: join(stage.scratch, `backup-${index}`), backedUp: false, placed: false };
      changes.push(change);
      if (await entry(item.target)) { await fs.rename(item.target, change.backup); change.backedUp = true; }
      if (item.staged) { await fs.rename(item.staged, item.target); change.placed = true; }
    }
    if (stage.store) await antiOwned(paths);
    else if (await entry(paths.root) || await entry(paths.rule) || await entry(paths.skill)) fail("removal_unconfirmed", "Modular removal did not clear the exact owned targets.");
    for (const change of changes) if (change.backedUp) {
      const info = await fs.lstat(change.backup);
      const afterHashes = info.isDirectory() && !info.isSymbolicLink() ? await files(change.backup) : { ".": hash(await fs.readFile(change.backup)) };
      if (!equalInventory(afterHashes, change.beforeHashes)) fail("owned_files_modified", "Owned content changed during its transaction; preserving the preimage.");
    }
  } catch (error) {
    for (const change of [...changes].reverse()) {
      try {
        if (change.placed) {
          await safeParents(dirname(change.target));
          const info = await fs.lstat(change.target);
          if (info.isSymbolicLink()) fail("unsafe_path", "Rollback target became linked.");
          const actual = info.isDirectory() ? await files(change.target) : { ".": hash(await fs.readFile(change.target)) };
          if (!equalInventory(actual, change.placedHashes)) fail("owned_files_modified", "Rollback target changed; preserve it and the backup.");
          windows("check", change.target);
          await fs.rm(change.target, { recursive: true });
        }
        if (change.backedUp) await fs.rename(change.backup, change.target);
      } catch { rollbackComplete = false; }
    }
    if (!rollbackComplete) fail("rollback_incomplete", `Antigravity rollback was incomplete; preserve the recovery directory: ${stage.scratch}`);
    throw error;
  } finally {
    if (rollbackComplete) await fs.rm(stage.scratch, { recursive: true, force: true });
  }
}
async function antiAction(options, helpers, paths, prepared = null) {
  const owned = await antiOwned(paths);
  if (options.action === "status" || options.action === "diagnose") return result(options, { installation: owned ? "managed-files" : "missing", version: owned?.version ?? null, enabled: owned?.enabled ?? false, scope: paths.scope, integrity: owned ? "verified" : "not-installed", registration: "modular-files" });
  if (options.action === "remove") {
    if (!owned) return result(options, { installation: "missing", version: null, enabled: false, scope: paths.scope });
    const scratch = await privateScratch(paths.base, ".opensocrates-removal-");
    await antiSwap(paths, { scratch, store: null, rule: null, skill: null }, owned);
    return result(options, { installation: "missing", version: null, enabled: false, scope: paths.scope });
  }
  if (options.action === "install" || options.action === "update") {
    const enabled = owned?.enabled ?? true;
    const stage = await antiStage(paths, prepared.root, enabled, helpers.version, prepared.hashes);
    await antiSwap(paths, stage, owned);
    return result(options, { installation: "managed-files", version: helpers.version, enabled, scope: paths.scope, registration: "modular-files" });
  }
  if (!owned) fail("not_installed", "Enable or disable requires an owned Antigravity installation.");
  const enabled = options.action === "enable";
  if (owned.enabled === enabled) return result(options, { installation: "managed-files", version: owned.version, enabled, scope: paths.scope });
  const scratch = await privateScratch(paths.base, ".opensocrates-source-");
  try {
    for (const name of Object.keys(owned.hashes)) {
      const target = join(scratch, name);
      await fs.mkdir(dirname(target), { recursive: true, mode: 0o700 });
      await fs.copyFile(antiPhysical(paths, name, owned.enabled), target);
    }
    const stage = await antiStage(paths, scratch, enabled, owned.version, owned.hashes);
    await antiSwap(paths, stage, owned);
  } finally { await fs.rm(scratch, { recursive: true, force: true }); }
  return result(options, { installation: "managed-files", version: owned.version, enabled, scope: paths.scope, registration: "modular-files" });
}
async function exportChat(options, prepared) {
  if (typeof options.output !== "string" || !isAbsolute(options.output) || !options.output.endsWith(".zip")) fail("invalid_output", "Export requires an explicit absolute ZIP output path.");
  const target = resolve(options.output);
  await safeParents(dirname(target));
  windows("check", dirname(target));
  return withWindowsLease(dirname(target), () => exportChatHeld(options, prepared, target));
}
async function exportChatHeld(options, prepared, target) {
  const sourceInfo = await regular(prepared.asset);
  const sourceHash = hash(await fs.readFile(prepared.asset));
  const existing = await entry(target);
  if (existing) {
    if (!existing.isFile() || existing.isSymbolicLink() || hash(await fs.readFile(target)) !== sourceHash) fail("export_conflict", "Export output already exists with different bytes or an unsafe type.");
  } else {
    await fs.copyFile(prepared.asset, target, constants.COPYFILE_EXCL);
    windows("seal-new", target);
    await fs.chmod(target, sourceInfo.mode & 0o777 & ~0o111);
    if (hash(await fs.readFile(target)) !== sourceHash) fail("export_mismatch", "Export changed during verification; preserve the output for inspection.");
  }
  return result(options, { installation: "export-only", version: prepared.version, output: target, sha256: sourceHash, account_activation: "unverified" });
}

/** Return a JSON-safe record. Caller owns terminal presentation and its Codex engine. */
export async function runManagedHost(options, helpers) {
  if (!object(options) || !HOSTS.has(options.host) || !ACTIONS.has(options.action) || !object(helpers) || !/^\d+\.\d+\.\d+$/u.test(helpers.version ?? "")) fail("invalid_options", "Invalid managed-host action or version.");
  if (options.purge || options.resetTrust) fail("unsupported_destructive_action", "Managed addons do not support purge or trust resets; use exact owned remove.");
  if (options.action === "export" && options.host !== "claude-chat") fail("invalid_action", "Standalone export is only available for claude-chat.");
  if (options.host === "claude-chat" && !["verify", "export"].includes(options.action)) fail("account_action_unavailable", "Claude account installation and activation require the account UI; export/verify are local only.");
  const offline = options.action === "verify" || options.action === "export";
  const platform = helpers.platform ?? process.platform, arch = helpers.arch ?? process.arch;
  if (!offline && !((platform === "darwin" && arch === "arm64") || (platform === "win32" && arch === "x64" && options.host === "antigravity"))) fail("unsupported_platform", "Addon lifecycle supports Apple-silicon Mac and Windows x64 Antigravity. Windows Claude account delivery uses verify/export; native Code is outside this scope.");
  const needsPackage = ["install", "update", "verify", "export"].includes(options.action);
  let prepared;
  try {
    if (needsPackage) {
      if (typeof helpers.preparePackage !== "function") fail("package_unavailable", "A verified package helper is required.");
      prepared = await helpers.preparePackage(options.host, options);
      if (!object(prepared) || typeof prepared.root !== "string" || typeof prepared.cleanup !== "function") fail("package_unavailable", "Package helper did not return a scoped prepared package.");
      Object.assign(prepared, await verifyPackage(prepared.root, options.host, helpers.version));
    }
    if (options.action === "verify") return result(options, { installation: "verified-package", version: helpers.version, files: Object.keys(prepared.hashes).length });
    if (options.action === "export") return await exportChat(options, prepared);
    const paths = basePaths(options);
    if (paths.workspace) await safeParents(paths.workspace);
    const inspect = options.action === "status" || options.action === "diagnose";
    const action = async () => options.host === "claude"
      ? needsPackage ? nativeInstall(options, helpers, paths, prepared) : nativeAction(options, helpers, paths)
      : antiAction(options, helpers, paths, prepared);
    if (inspect) {
      try { return await action(); }
      catch (error) {
        if (!(error instanceof ManagedHostError)) throw error;
        return result(options, { installation: "unavailable", integrity: "unverified", reason: error.code, scope: paths.scope, version: null });
      }
    }
    if (!needsPackage && !(await entry(paths.base))) return result(options, { installation: "missing", version: null, enabled: false, scope: paths.scope, integrity: "not-installed" });
    return await withLock(paths.base, options.host, action);
  } finally { if (typeof prepared?.cleanup === "function") await prepared.cleanup(); }
}
