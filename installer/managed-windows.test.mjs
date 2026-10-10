import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { spawn, spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { runManagedHost } from "./managed-hosts.mjs";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const HELPER = join(ROOT, "installer/windows.ps1");
const VERSION = (await fs.readFile(join(ROOT, "VERSION"), "utf8")).trim();
const NATIVE = { skip: process.platform !== "win32" || process.arch !== "x64", timeout: 240_000 };
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const jsonBytes = (value) => `${JSON.stringify(value, null, 2)}\n`;

function powershell(source, environment = {}) {
  return spawnSync("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command",
    "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); " + source], {
    encoding: "utf8", windowsHide: true, timeout: 30_000, maxBuffer: 1024 * 1024,
    env: { ...process.env, ...environment },
  });
}
function windows(action, path, environment = {}) {
  return spawnSync("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", HELPER, "-Action", action], {
    encoding: "utf8", windowsHide: true, timeout: 30_000, maxBuffer: 1024 * 1024,
    env: { ...process.env, ...environment, OPENSOCRATES_WINDOWS_PATH: path },
  });
}
function requireHelper(action, path) {
  const result = windows(action, path);
  assert.equal(result.status, 0, `Windows ${action} helper failed`);
  assert.equal(result.error, undefined);
}
async function privateDirectory(path) { requireHelper("mkdir-private", path); return path; }
async function exists(path) {
  try { await fs.lstat(path); return true; }
  catch (error) { if (error.code === "ENOENT") return false; throw error; }
}
async function write(path, bytes) {
  await fs.mkdir(dirname(path), { recursive: true });
  await fs.writeFile(path, bytes);
}
async function snapshot(root) {
  const result = {};
  if (!(await exists(root))) return result;
  async function walk(directory) {
    for (const item of await fs.readdir(directory, { withFileTypes: true })) {
      const path = join(directory, item.name);
      if (item.isSymbolicLink()) result[relative(root, path)] = "linked";
      else if (item.isDirectory()) await walk(path);
      else result[relative(root, path)] = digest(await fs.readFile(path));
    }
  }
  await walk(root);
  return result;
}
function acl(path) {
  const result = powershell(
    "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; " +
    "$acl=(Get-Item -LiteralPath $env:TEST_PATH -Force).GetAccessControl(); " +
    "@{sid=$sid;owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;protected=$acl.AreAccessRulesProtected;" +
    "rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {" +
    "@{sid=$_.IdentityReference.Value;rights=[int]$_.FileSystemRights;inherited=$_.IsInherited;type=$_.AccessControlType.ToString()}})} | ConvertTo-Json -Depth 4 -Compress",
    { TEST_PATH: path },
  );
  assert.equal(result.status, 0, "Cannot inspect synthetic DACL");
  return JSON.parse(result.stdout);
}
async function hold(path, { directory = false } = {}) {
  const args = directory
    ? ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", HELPER, "-Action", "lease"]
    : ["-NoProfile", "-NonInteractive", "-Command",
      "$ErrorActionPreference='Stop'; $stream=[IO.File]::Open(('\\\\?\\'+$env:OPENSOCRATES_WINDOWS_PATH),[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite); " +
      "try {[Console]::WriteLine('ready');[Console]::Out.Flush();[void][Console]::In.ReadLine()} finally {$stream.Dispose()}"];
  const child = spawn("powershell.exe", args, {
    windowsHide: true, stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, OPENSOCRATES_WINDOWS_PATH: path },
  });
  child.stderr.resume();
  let exited = false;
  child.once("exit", () => { exited = true; });
  await new Promise((accept, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error("Synthetic Windows lock did not become ready")); }, 20_000);
    const fail = () => { clearTimeout(timer); reject(new Error("Synthetic Windows lock was unavailable")); };
    child.once("error", fail); child.once("exit", fail);
    let output = "";
    child.stdout.on("data", (data) => {
      output += data.toString("utf8");
      if (output === "ready\r\n" || output === "ready\n") { clearTimeout(timer); accept(); }
    });
  });
  return async () => {
    if (exited) return;
    const closed = new Promise((accept) => child.once("exit", accept));
    child.stdin.end("done\n");
    await closed;
  };
}

async function box(t) {
  const parent = await fs.realpath(tmpdir());
  const base = await fs.mkdtemp(join(parent, "OpenSocrates managed 한글 space "));
  requireHelper("seal-new", base); // Exclusively created synthetic fixture, never a user tree.
  const saved = Object.fromEntries(["ANTIGRAVITY_CONFIG_DIR", "CLAUDE_CONFIG_DIR", "CLAUDE_BIN"].map((name) => [name, process.env[name]]));
  process.env.ANTIGRAVITY_CONFIG_DIR = join(base, "Antigravity 사용자 설정");
  process.env.CLAUDE_CONFIG_DIR = join(base, "Claude 계정 설정");
  process.env.CLAUDE_BIN = join(base, "no-auth-or-cli.exe");
  let prepared = 0, cleaned = 0;
  const helpers = (pkg, version = VERSION) => ({
    version, platform: "win32", arch: "x64",
    get claudeBinary() { throw new Error("Content delivery accessed the native Claude CLI"); },
    preparePackage: async () => {
      prepared++;
      return { root: pkg.root, asset: pkg.asset, cleanup: async () => { cleaned++; } };
    },
  });
  const options = (host, action, extra = {}) => ({ host, action, workspace: null, output: null, purge: false, resetTrust: false, ...extra });
  t.after(async () => {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name]; else process.env[name] = value;
    }
    const boundary = relative(parent, base);
    assert.ok(boundary && !boundary.startsWith(`..${sep}`) && !boundary.includes(sep), "Unexpected fixture cleanup boundary");
    await fs.rm(base, { recursive: true, force: true });
  });
  return {
    base, helpers, options, counts: () => ({ prepared, cleaned }),
    global: process.env.ANTIGRAVITY_CONFIG_DIR,
    rule: join(process.env.ANTIGRAVITY_CONFIG_DIR, "rules/opensocrates.md"),
    skill: join(process.env.ANTIGRAVITY_CONFIG_DIR, "skills/opensocrates"),
    store: join(process.env.ANTIGRAVITY_CONFIG_DIR, ".opensocrates-managed/antigravity"),
  };
}
async function contentPackage(b, host, { version = VERSION, changed = false } = {}) {
  const source = join(ROOT, "dist", `${host === "claude-chat" ? "claude-chat" : "antigravity"}-content`);
  assert.ok(await exists(source), "Build generated content packages before Windows managed tests");
  const root = await privateDirectory(join(b.base, `package ${host} 한글 ${randomUUID()}`));
  await fs.cp(source, root, { recursive: true, dereference: false });
  const manifestPath = join(root, host === "claude-chat" ? "opensocrates/release-manifest.json" : "release-manifest.json");
  if (changed) {
    const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
    manifest.product_version = version;
    const path = ".agents/rules/opensocrates.md";
    await fs.appendFile(join(root, path), "\nSynthetic updated fixture.\n");
    manifest.files.find((row) => row.path === path).sha256 = `sha256:${digest(await fs.readFile(join(root, path)))}`;
    await fs.writeFile(manifestPath, jsonBytes(manifest));
  }
  requireHelper("seal-new", root); // Only the newly copied generated fixture is sealed.
  let asset;
  if (host === "claude-chat") {
    asset = join(b.base, `account export 한글 ${randomUUID()}.zip`);
    const zip = powershell("Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::CreateFromDirectory($env:TEST_SOURCE,$env:TEST_ZIP)", { TEST_SOURCE: root, TEST_ZIP: asset });
    assert.equal(zip.status, 0, "Cannot create generated account ZIP fixture");
    requireHelper("seal-new", asset);
  }
  return { root, asset };
}
async function sentinels(b) {
  await privateDirectory(b.global);
  const rows = {
    "settings.json": '{"synthetic_user_setting":true}\n',
    "GEMINI.md": "Synthetic user instructions 한글\n",
    "rules/unrelated.md": "Synthetic user standing rule\n",
    "skills/unrelated/SKILL.md": "Synthetic user skill\n",
  };
  for (const [name, bytes] of Object.entries(rows)) await write(join(b.global, name), bytes);
  // This complete test-only settings tree was exclusively created by this fixture.
  requireHelper("seal-new", b.global);
  return async () => {
    for (const [name, bytes] of Object.entries(rows)) assert.equal(await fs.readFile(join(b.global, name), "utf8"), bytes);
  };
}

test("Windows private creation has the current user SID at creation and rejects collisions", NATIVE, async (t) => {
  const b = await box(t), hostile = await privateDirectory(join(b.base, "hostile parent 한글"));
  const grant = powershell("$item=Get-Item -LiteralPath $env:TEST_PATH; $acl=$item.GetAccessControl(); $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Write','ContainerInherit,ObjectInherit','None','Allow')); $item.SetAccessControl($acl)", { TEST_PATH: hostile });
  assert.equal(grant.status, 0);
  const child = await privateDirectory(join(hostile, "private child"));
  const inspected = acl(child);
  assert.equal(inspected.owner, inspected.sid);
  assert.equal(inspected.protected, true);
  assert.deepEqual(inspected.rules.map((row) => row.sid).sort(), [inspected.sid, "S-1-5-18", "S-1-5-32-544"].sort());
  assert.ok(inspected.rules.every((row) => !row.inherited && row.type === "Allow"));
  requireHelper("check", child);
  await fs.writeFile(join(child, "sentinel"), "preserve private collision");
  assert.notEqual(windows("mkdir-private", child).status, 0);
  assert.equal(await fs.readFile(join(child, "sentinel"), "utf8"), "preserve private collision");
});

test("Windows Antigravity full global lifecycle preserves settings and disabled updates", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), preserved = await sentinels(b);
  assert.equal((await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg))).enabled, true);
  requireHelper("check-tree", b.store); requireHelper("check-tree", b.skill); requireHelper("check", b.rule);
  assert.equal((await runManagedHost(b.options("antigravity", "status"), b.helpers(pkg))).integrity, "verified");
  assert.equal((await runManagedHost(b.options("antigravity", "disable"), b.helpers(pkg))).enabled, false);
  assert.equal(await exists(b.rule), false); assert.equal(await exists(b.skill), false);
  const updated = await contentPackage(b, "antigravity", { version: "1.5.1", changed: true });
  const update = await runManagedHost(b.options("antigravity", "update"), b.helpers(updated, "1.5.1"));
  assert.equal(update.version, "1.5.1"); assert.equal(update.enabled, false);
  assert.equal(await exists(b.rule), false); assert.equal(await exists(b.skill), false);
  await runManagedHost(b.options("antigravity", "enable"), b.helpers(updated, "1.5.1"));
  assert.match(await fs.readFile(b.rule, "utf8"), /Synthetic updated fixture/u);
  assert.equal((await runManagedHost(b.options("antigravity", "diagnose"), b.helpers(updated, "1.5.1"))).integrity, "verified");
  await runManagedHost(b.options("antigravity", "remove"), b.helpers(updated, "1.5.1"));
  assert.equal(await exists(b.rule), false); assert.equal(await exists(b.skill), false); assert.equal(await exists(b.store), false);
  await preserved();
  assert.deepEqual(b.counts(), { prepared: 2, cleaned: 2 });
});

test("Windows workspace lifecycle uses explicit Unicode paths and preserves AGENTS", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity");
  const workspace = await privateDirectory(join(b.base, "작업 공간 ' $ `"));
  await fs.writeFile(join(workspace, "AGENTS.md"), "Synthetic user workspace instructions");
  const options = (action) => b.options("antigravity", action, { workspace });
  assert.equal((await runManagedHost(options("install"), b.helpers(pkg))).scope, "workspace");
  assert.equal(await exists(join(workspace, ".agents/rules/opensocrates.md")), true);
  assert.equal(await exists(b.global), false);
  await runManagedHost(options("remove"), b.helpers(pkg));
  assert.equal(await fs.readFile(join(workspace, "AGENTS.md"), "utf8"), "Synthetic user workspace instructions");
  await assert.rejects(runManagedHost(b.options("antigravity", "install", { workspace: "relative" }), b.helpers(pkg)), { code: "invalid_scope" });
});

async function longWorkspace(b) {
  const parent = await privateDirectory(join(b.base, "합성 경로 space ".repeat(9).trim()));
  const workspace = await privateDirectory(join(parent, "긴 작업 폴더 space ".repeat(8).trim()));
  assert.ok(workspace.length > 260, "Fixture must exercise MAX_PATH rather than only Unicode");
  return workspace;
}

test("Windows long Unicode workspace lifecycle and locked update preserve the complete preimage", { ...NATIVE, timeout: 420_000 }, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), workspace = await longWorkspace(b);
  const sentinel = join(workspace, "AGENTS.md");
  await fs.writeFile(sentinel, "Synthetic unrelated instructions in a long path\n");
  const options = (action) => b.options("antigravity", action, { workspace });
  await runManagedHost(options("install"), b.helpers(pkg));
  const activeSkill = join(workspace, ".agents/skills/opensocrates");
  const before = await snapshot(workspace);
  const release = await hold(join(activeSkill, "SKILL.md"));
  try { await assert.rejects(runManagedHost(options("update"), b.helpers(pkg))); }
  finally { await release(); }
  assert.deepEqual(await snapshot(workspace), before);
  await runManagedHost(options("update"), b.helpers(pkg)); // Inspect deep renamed backup before deleting it.
  assert.equal((await runManagedHost(options("disable"), b.helpers(pkg))).enabled, false);
  assert.equal((await runManagedHost(options("update"), b.helpers(pkg))).enabled, false);
  assert.equal(await exists(activeSkill), false);
  await runManagedHost(options("enable"), b.helpers(pkg));
  assert.equal((await runManagedHost(options("diagnose"), b.helpers(pkg))).integrity, "verified");
  await runManagedHost(options("remove"), b.helpers(pkg));
  assert.equal(await fs.readFile(sentinel, "utf8"), "Synthetic unrelated instructions in a long path\n");
  assert.equal(await exists(activeSkill), false);
});

test("Windows long paths retain ZIP bytes, extraction containment, DACL checks and ancestor leases", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "claude-chat"), workspace = await longWorkspace(b);
  // The generic .NET fixture ZIP uses Windows separators. Exercise the actual
  // portable product archive here; the helper continues to reject backslashes.
  pkg.asset = join(ROOT, "dist/opensocrates-1.5.0-claude-chat-skills.zip");
  const output = join(workspace, "계정 export.zip");
  const result = await runManagedHost(b.options("claude-chat", "export", { output }), b.helpers(pkg));
  assert.equal(result.sha256, digest(await fs.readFile(pkg.asset)));
  assert.deepEqual(await fs.readFile(output), await fs.readFile(pkg.asset));
  requireHelper("check", output);
  const extraction = await privateDirectory(join(workspace, "압축 해제"));
  const unpacked = windows("extract", output, { OPENSOCRATES_WINDOWS_DESTINATION: extraction });
  assert.equal(unpacked.status, 0, `Cannot extract the portable ZIP under a long path: ${unpacked.stderr.replaceAll(workspace, "<synthetic-workspace>").replaceAll(b.base, "<synthetic-base>").replaceAll(ROOT, "<source>")}`);
  assert.deepEqual(await snapshot(extraction), await snapshot(pkg.root));
  requireHelper("seal-new", extraction);
  requireHelper("check-tree", extraction);
  const release = await hold(workspace, { directory: true });
  try { await assert.rejects(fs.rename(workspace, `${workspace}-replacement`), (error) => ["EPERM", "EACCES", "EBUSY"].includes(error.code)); }
  finally { await release(); }
  const changed = powershell("$item=Get-Item -LiteralPath ('\\\\?\\'+$env:TEST_PATH); $acl=$item.GetAccessControl(); $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Write','None','None','Allow')); $item.SetAccessControl($acl)", { TEST_PATH: workspace });
  assert.equal(changed.status, 0);
  const before = await snapshot(workspace);
  await assert.rejects(runManagedHost(b.options("claude-chat", "export", { output: join(workspace, "refused.zip") }), b.helpers(pkg)), { code: "unsafe_windows_path" });
  assert.deepEqual(await snapshot(workspace), before);
});

test("Windows owned lifecycle refuses unknown or modified files without removing them", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity");
  await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  const addition = join(b.skill, "user-added.txt");
  await fs.writeFile(addition, "Synthetic user addition"); requireHelper("seal-new", addition);
  await assert.rejects(runManagedHost(b.options("antigravity", "remove"), b.helpers(pkg)), { code: "owned_files_modified" });
  assert.equal(await fs.readFile(addition, "utf8"), "Synthetic user addition");
  assert.equal((await runManagedHost(b.options("antigravity", "diagnose"), b.helpers(pkg))).reason, "owned_files_modified");
  await fs.unlink(addition);
  await fs.appendFile(b.rule, "Synthetic user edit\n");
  const before = await snapshot(b.global);
  await assert.rejects(runManagedHost(b.options("antigravity", "update"), b.helpers(pkg)), { code: "owned_files_modified" });
  assert.deepEqual(await snapshot(b.global), before);
});

test("Windows operation locks preserve a preexisting lock and native leases block ancestor rename", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), preserved = await sentinels(b);
  const lock = join(b.global, ".opensocrates-antigravity-operation.lock");
  await fs.writeFile(lock, "Synthetic active operation"); requireHelper("seal-new", lock);
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), { code: "operation_locked" });
  assert.equal(await fs.readFile(lock, "utf8"), "Synthetic active operation");
  await preserved();
  const release = await hold(b.global, { directory: true });
  try { await assert.rejects(fs.rename(b.global, join(b.base, "renamed settings")), (error) => ["EPERM", "EACCES", "EBUSY"].includes(error.code)); }
  finally { await release(); }
  requireHelper("check", b.global);
});

test("Windows transaction leases block replacement of the actual rule, skill, and metadata parents", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), preserved = await sentinels(b);
  const original = fs.rename;
  let attempted = false;
  fs.rename = async (source, target) => {
    if (!attempted && target === b.rule && source.endsWith(`${sep}rule.md`)) {
      attempted = true;
      for (const parent of [dirname(b.rule), dirname(b.skill), dirname(b.store)]) {
        await assert.rejects(original(parent, `${parent}-replacement`), (error) => ["EPERM", "EACCES", "EBUSY"].includes(error.code));
        assert.equal(await exists(`${parent}-replacement`), false);
      }
    }
    return original(source, target);
  };
  try { await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)); }
  finally { fs.rename = original; }
  assert.equal(attempted, true, "No real mutation boundary was reached");
  assert.equal((await runManagedHost(b.options("antigravity", "diagnose"), b.helpers(pkg))).integrity, "verified");
  await preserved();
});

test("Windows refuses an existing foreign-writer rule parent without changing settings or its DACL", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), preserved = await sentinels(b);
  const rules = dirname(b.rule);
  const altered = powershell("$item=Get-Item -LiteralPath $env:TEST_PATH; $acl=$item.GetAccessControl(); $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Write','None','None','Allow')); $item.SetAccessControl($acl)", { TEST_PATH: rules });
  assert.equal(altered.status, 0);
  const beforeDacl = acl(rules), beforeFiles = await snapshot(b.global);
  assert.ok(beforeDacl.rules.some((row) => row.sid === "S-1-1-0" && !row.inherited && row.type === "Allow"));
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), { code: "unsafe_windows_path" });
  assert.deepEqual(acl(rules), beforeDacl);
  assert.ok(isDeepStrictEqual(await snapshot(b.global), beforeFiles), "Refused operation changed the existing settings tree");
  await preserved();
});

test("Windows unprivileged junctions are rejected without modifying their targets", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), target = await privateDirectory(join(b.base, "junction target"));
  await fs.writeFile(join(target, "sentinel"), "Synthetic protected target");
  await fs.symlink(target, b.global, "junction");
  assert.notEqual(windows("check", b.global).status, 0);
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), (error) => ["unsafe_path", "unsafe_windows_path"].includes(error.code));
  assert.equal(await fs.readFile(join(target, "sentinel"), "utf8"), "Synthetic protected target");
  const packageLink = join(pkg.root, "linked package directory");
  await fs.symlink(target, packageLink, "junction");
  await assert.rejects(runManagedHost(b.options("antigravity", "verify"), b.helpers(pkg)), { code: "unsafe_windows_path" });
  assert.equal(await fs.readFile(join(target, "sentinel"), "utf8"), "Synthetic protected target");
});

test("Windows rejects inherited foreign writers without rewriting the existing DACL", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), parent = await privateDirectory(join(b.base, "foreign writer parent"));
  const altered = powershell("$item=Get-Item -LiteralPath $env:TEST_PATH; $acl=$item.GetAccessControl(); $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Write','ContainerInherit,ObjectInherit','None','Allow')); $item.SetAccessControl($acl)", { TEST_PATH: parent });
  // Create the child beneath that parent so the writable ACE is actually inherited.
  assert.equal(altered.status, 0);
  const child = join(parent, "inherited settings");
  const inherited = powershell("[IO.Directory]::CreateDirectory($env:TEST_PATH) | Out-Null; $item=Get-Item -LiteralPath $env:TEST_PATH; $acl=$item.GetAccessControl(); $acl.SetOwner([Security.Principal.WindowsIdentity]::GetCurrent().User); $item.SetAccessControl($acl)", { TEST_PATH: child });
  assert.equal(inherited.status, 0);
  process.env.ANTIGRAVITY_CONFIG_DIR = child;
  const before = acl(child);
  assert.ok(before.rules.some((row) => row.sid === "S-1-1-0" && row.inherited && row.type === "Allow"));
  assert.notEqual(windows("check", child).status, 0);
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), { code: "unsafe_windows_path" });
  assert.deepEqual(acl(child), before);
  assert.deepEqual(await snapshot(child), {});
});

test("Windows locked leaf file causes update rollback to restore the complete previous state", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), preserved = await sentinels(b);
  await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  const before = await snapshot(b.global), updated = await contentPackage(b, "antigravity", { version: "1.5.1", changed: true });
  const release = await hold(join(b.skill, "SKILL.md"));
  try { await assert.rejects(runManagedHost(b.options("antigravity", "update"), b.helpers(updated, "1.5.1"))); }
  finally { await release(); }
  assert.deepEqual(await snapshot(b.global), before);
  assert.equal((await runManagedHost(b.options("antigravity", "diagnose"), b.helpers(pkg))).integrity, "verified");
  await preserved();
});

test("Windows rollback preserves a user replacement inserted during the transaction and its backup", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "antigravity"), preserved = await sentinels(b);
  await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  const oldRule = await fs.readFile(b.rule), updated = await contentPackage(b, "antigravity", { version: "1.5.1", changed: true });
  const original = fs.rename;
  let injected = false;
  fs.rename = async (source, target) => {
    if (!injected && target === b.skill && source.endsWith(`${sep}skill`)) {
      injected = true;
      await fs.writeFile(b.rule, "Synthetic user replacement during transaction\n");
      throw new Error("Synthetic skill activation interruption");
    }
    return original(source, target);
  };
  try { await assert.rejects(runManagedHost(b.options("antigravity", "update"), b.helpers(updated, "1.5.1")), { code: "rollback_incomplete" }); }
  finally { fs.rename = original; }
  assert.equal(injected, true);
  assert.equal(await fs.readFile(b.rule, "utf8"), "Synthetic user replacement during transaction\n");
  const recovery = (await fs.readdir(b.global)).filter((name) => name.startsWith(".opensocrates-transaction-"));
  assert.equal(recovery.length, 1);
  assert.deepEqual(await fs.readFile(join(b.global, recovery[0], "backup-0")), oldRule);
  await preserved();
});

test("Windows native Code and account activation are unavailable before any package or settings effect", NATIVE, async (t) => {
  const b = await box(t), helpers = b.helpers({});
  for (const action of ["install", "update", "status", "diagnose", "enable", "disable", "remove"]) {
    await assert.rejects(runManagedHost(b.options("claude", action), helpers), { code: "unsupported_platform" });
  }
  await assert.rejects(runManagedHost(b.options("claude-chat", "install"), helpers), { code: "account_action_unavailable" });
  assert.deepEqual(b.counts(), { prepared: 0, cleaned: 0 });
  assert.equal(await exists(process.env.CLAUDE_CONFIG_DIR), false);
  assert.equal(await exists(b.global), false);
});

test("Windows Claude account verify and export preserve exact ZIP bytes, conflicts, and account settings", NATIVE, async (t) => {
  const b = await box(t), pkg = await contentPackage(b, "claude-chat");
  const account = await privateDirectory(process.env.CLAUDE_CONFIG_DIR);
  await fs.writeFile(join(account, "settings.json"), '{"synthetic_account_setting":true}\n');
  const before = await snapshot(account), output = join(b.base, "Claude account 한글 upload.zip");
  const verified = await runManagedHost(b.options("claude-chat", "verify"), b.helpers(pkg));
  assert.equal(verified.installation, "verified-package");
  assert.equal(verified.automatic_entry, "unverified");
  const exported = await runManagedHost(b.options("claude-chat", "export", { output }), b.helpers(pkg));
  assert.equal(exported.installation, "export-only");
  assert.deepEqual(await fs.readFile(output), await fs.readFile(pkg.asset));
  requireHelper("check", output);
  await runManagedHost(b.options("claude-chat", "export", { output }), b.helpers(pkg));
  await fs.writeFile(output, "Synthetic user conflicting ZIP bytes");
  await assert.rejects(runManagedHost(b.options("claude-chat", "export", { output }), b.helpers(pkg)), { code: "export_conflict" });
  assert.equal(await fs.readFile(output, "utf8"), "Synthetic user conflicting ZIP bytes");
  assert.deepEqual(await snapshot(account), before);
  assert.deepEqual(b.counts(), { prepared: 4, cleaned: 4 });
});
