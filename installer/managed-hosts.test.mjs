import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { createHash } from "node:crypto";
import { runManagedHost, ManagedHostError } from "./managed-hosts.mjs";

const VERSION = "1.5.0";
const IDS = Array.from({ length: 48 }, (_, i) => `method-${i + 1}`);
const HASH = `sha256:${"a".repeat(64)}`;
const digest = (value) => createHash("sha256").update(value).digest("hex");
const jsonBytes = (value) => `${JSON.stringify(value, null, 2)}\n`;
async function write(path, value, mode = 0o600) {
  await fs.mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await fs.writeFile(path, value, { mode });
}
async function exists(path) { try { await fs.lstat(path); return true; } catch (error) { if (error.code === "ENOENT") return false; throw error; } }
async function readJson(path) { return JSON.parse(await fs.readFile(path, "utf8")); }
async function snapshot(root) {
  const output = {};
  async function visit(path, prefix = "") {
    for (const child of await fs.readdir(path, { withFileTypes: true })) {
      const name = prefix ? `${prefix}/${child.name}` : child.name;
      if (child.isDirectory()) await visit(join(path, child.name), name);
      else output[name] = digest(await fs.readFile(join(path, child.name)));
    }
  }
  await visit(root); return output;
}

async function fixture(base, host, { version = VERSION, variant = "original" } = {}) {
  const root = join(base, `package-${host}-${variant}`);
  const skill = host === "claude-chat" ? "opensocrates" : host === "antigravity" ? ".agents/skills/opensocrates" : "skills/opensocrates";
  const payload = {};
  const add = (name, value) => { payload[name] = Buffer.from(value); };
  add(`${skill}/SKILL.md`, `---\nname: opensocrates\ndescription: Synthetic fixture\n---\n${variant}\n`);
  for (const locale of ["en", "ko"]) for (const id of IDS) add(`${skill}/references/decision/methods/${locale}/${id}.md`, `Method ID: ${id}\nContent revision: 3\nLocale: ${locale}\nComplete synthetic procedure ${variant}.\n`);
  if (host === "antigravity") add(".agents/rules/opensocrates.md", `---\ntrigger: always_on\ndescription: Synthetic fixture\n---\nRead the installed controller. ${variant}\n`);
  const manifest = {
    schema: host === "claude" ? "opensocrates.plugin-release-manifest/1.0.0" : "opensocrates.content-host-manifest/1.0.0",
    host, product_version: version, method_count: 48, method_ids: IDS,
    source_tree_hash: HASH, source_identity: { canonical: HASH, templates: HASH },
    skill_root: skill, public_skills: ["opensocrates"],
    runtime_targets: host === "claude" ? ["darwin-arm64"] : [],
    release_targets: host === "claude" ? ["darwin-arm64"] : [],
    launchers: host === "claude" ? ["bin/launch.sh"] : [],
  };
  if (host === "claude") {
    add(".claude-plugin/plugin.json", jsonBytes({ name: "opensocrates", version }));
    add("bin/launch.sh", "#!/bin/sh\nexit 0\n");
    add("runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime", "#!/bin/sh\nexit 0\n");
  } else {
    manifest.canonical_methods = [];
    for (const locale of ["en", "ko"]) for (const id of IDS) {
      const path = `${skill}/references/decision/methods/${locale}/${id}.md`;
      manifest.canonical_methods.push({ method_id: id, locale, path, sha256: `sha256:${digest(payload[path])}` });
    }
  }
  manifest.files = Object.entries(payload).map(([path, value]) => ({ path, sha256: `sha256:${digest(value)}` }));
  const manifestPath = host === "claude-chat" ? "opensocrates/release-manifest.json" : "release-manifest.json";
  payload[manifestPath] = Buffer.from(jsonBytes(manifest));
  for (const [name, bytes] of Object.entries(payload)) await write(join(root, name), bytes, name === "bin/launch.sh" || name.endsWith("/opensocrates-runtime") ? 0o700 : 0o600);
  const asset = join(base, `${host}-${variant}.zip`);
  await write(asset, `synthetic verified outer ZIP bytes ${host} ${variant}`);
  return { root, asset, manifestPath, manifest };
}

const MOCK = `#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
const args = process.argv.slice(2);
const file = process.env.MOCK_CLAUDE_STATE;
let state = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file,'utf8')) : { marketplaces: [], plugins: [], calls: [] };
state.calls.push(args); fs.writeFileSync(file,JSON.stringify(state));
const failFile = process.env.MOCK_CLAUDE_FAIL;
if (failFile && fs.existsSync(failFile) && args.join(' ').startsWith(fs.readFileSync(failFile,'utf8').trim())) { fs.unlinkSync(failFile); process.stderr.write('synthetic failure'); process.exit(2); }
function save(){fs.writeFileSync(file,JSON.stringify(state));}
function out(value){process.stdout.write(JSON.stringify(value));}
if(args.slice(0,3).join(' ')==='plugin marketplace list'){out(state.marketplaces);}
else if(args.slice(0,3).join(' ')==='plugin marketplace add'){
  const root=args[3], manifest=JSON.parse(fs.readFileSync(path.join(root,'.claude-plugin/marketplace.json'),'utf8'));
  if(state.marketplaces.some(x=>x.name===manifest.name)){process.exit(2);}
  state.marketplaces.push({name:manifest.name,source:'directory',path:root,installLocation:root}); save(); out({});
}else if(args.slice(0,3).join(' ')==='plugin marketplace remove'){state.marketplaces=state.marketplaces.filter(x=>x.name!==args[3]);save();out({});}
else if(args.slice(0,2).join(' ')==='plugin list'){out(state.plugins);}
else if(args[0]==='plugin'&&args[1]==='install'){
  const id=args[2], market=state.marketplaces.find(x=>x.name===id.split('@')[1]);
  if(!market) process.exit(2);
  const manifest=JSON.parse(fs.readFileSync(path.join(market.path,'plugin/.claude-plugin/plugin.json'),'utf8'));
  state.plugins=state.plugins.filter(x=>x.id!==id);state.plugins.push({id,version:manifest.version,scope:'user',enabled:true,installPath:'synthetic-cache'});save();out({command:'install',outcome:'ok',plugin:id,pluginId:id,scope:'user'});
}else if(args[0]==='plugin'&&args[1]==='uninstall'){state.plugins=state.plugins.filter(x=>x.id!==args[2]);save();out({});}
else if(args[0]==='plugin'&&['enable','disable'].includes(args[1])){const item=state.plugins.find(x=>x.id===args[2]);if(!item)process.exit(2);item.enabled=args[1]==='enable';save();out({});}
else process.exit(2);
`;

async function box(t) {
  // Canonicalize the system temp alias before the driver's no-symlink ancestor gate.
  const base = await fs.mkdtemp(join(await fs.realpath(tmpdir()), "opensocrates-managed-test-"));
  const saved = {};
  for (const name of ["CLAUDE_CONFIG_DIR", "ANTIGRAVITY_CONFIG_DIR", "MOCK_CLAUDE_STATE", "MOCK_CLAUDE_FAIL"]) saved[name] = process.env[name];
  process.env.CLAUDE_CONFIG_DIR = join(base, "claude-home");
  process.env.ANTIGRAVITY_CONFIG_DIR = join(base, "antigravity-home");
  process.env.MOCK_CLAUDE_STATE = join(base, "cli-state.json");
  process.env.MOCK_CLAUDE_FAIL = join(base, "cli-fail.txt");
  const mock = join(base, "mock-claude.mjs");
  await write(mock, MOCK, 0o700);
  await write(process.env.MOCK_CLAUDE_STATE, jsonBytes({ marketplaces: [{ name: "unrelated", source: "directory", path: join(base, "unrelated"), installLocation: join(base, "unrelated") }], plugins: [{ id: "other@unrelated", version: "7.0.0", scope: "user", enabled: false }], calls: [] }));
  let cleanupCount = 0;
  const helpers = (pkg, version = VERSION) => ({ version, platform: "darwin", arch: "arm64", claudeBinary: mock, preparePackage: async () => ({ root: pkg.root, asset: pkg.asset, cleanup: async () => { cleanupCount++; } }) });
  const options = (host, action, extras = {}) => ({ host, action, asset: null, checksum: null, workspace: null, output: null, purge: false, resetTrust: false, ...extras });
  t.after(async () => {
    for (const [name, value] of Object.entries(saved)) if (value === undefined) delete process.env[name]; else process.env[name] = value;
    await fs.rm(base, { recursive: true, force: true });
  });
  return { base, helpers, options, cleanupCount: () => cleanupCount, state: () => readJson(process.env.MOCK_CLAUDE_STATE), nativeRoot: join(process.env.CLAUDE_CONFIG_DIR, "managed-marketplaces/opensocrates-macos"), globalRule: join(process.env.ANTIGRAVITY_CONFIG_DIR, "rules/opensocrates.md"), globalSkill: join(process.env.ANTIGRAVITY_CONFIG_DIR, "skills/opensocrates") };
}

test("offline content verify binds all canonical identities and always cleans up", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity");
  const result = await runManagedHost(b.options("antigravity", "verify"), { ...b.helpers(pkg), platform: "linux" });
  assert.equal(result.installation, "verified-package"); assert.equal(result.automatic_entry, "unverified");
  await fs.appendFile(join(pkg.root, ".agents/skills/opensocrates/references/decision/methods/ko/method-1.md"), "tampered");
  await assert.rejects(runManagedHost(b.options("antigravity", "verify"), b.helpers(pkg)), { code: "inventory_mismatch" });
  assert.equal(b.cleanupCount(), 2);
  assert.equal(await exists(process.env.ANTIGRAVITY_CONFIG_DIR), false);
});

test("content verification rejects incomplete canonical identities and executable surfaces", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude-chat");
  pkg.manifest.canonical_methods.pop();
  await write(join(pkg.root, pkg.manifestPath), jsonBytes(pkg.manifest));
  await assert.rejects(runManagedHost(b.options("claude-chat", "verify"), b.helpers(pkg)), { code: "invalid_canonical_content" });
  const pkg2 = await fixture(b.base, "claude-chat", { variant: "executable" });
  await fs.chmod(join(pkg2.root, "opensocrates/SKILL.md"), 0o700);
  await assert.rejects(runManagedHost(b.options("claude-chat", "verify"), b.helpers(pkg2)), { code: "unexpected_executable_surface" });
});

test("Antigravity global install, disable, update, enable and exact remove preserve sentinels", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity");
  await write(join(process.env.ANTIGRAVITY_CONFIG_DIR, "rules/unrelated.md"), "untouched rule");
  await write(join(process.env.ANTIGRAVITY_CONFIG_DIR, "GEMINI.md"), "untouched GEMINI");
  await write(join(process.env.ANTIGRAVITY_CONFIG_DIR, "skills/unrelated/SKILL.md"), "untouched skill");
  const first = await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  assert.equal(first.installation, "managed-files"); assert.equal(first.enabled, true);
  await runManagedHost(b.options("antigravity", "disable"), b.helpers(pkg));
  assert.equal(await exists(b.globalRule), false); assert.equal(await exists(b.globalSkill), false);
  const changed = await fixture(b.base, "antigravity", { version: "1.5.1", variant: "changed" });
  const update = await runManagedHost(b.options("antigravity", "update"), b.helpers(changed, "1.5.1"));
  assert.equal(update.enabled, false); assert.equal(update.version, "1.5.1"); assert.equal(await exists(b.globalRule), false);
  await runManagedHost(b.options("antigravity", "enable"), b.helpers(changed, "1.5.1"));
  assert.match(await fs.readFile(b.globalRule, "utf8"), /changed/u);
  assert.equal((await runManagedHost(b.options("antigravity", "diagnose"), b.helpers(changed, "1.5.1"))).integrity, "verified");
  await runManagedHost(b.options("antigravity", "remove"), b.helpers(changed, "1.5.1"));
  assert.equal(await exists(b.globalRule), false); assert.equal(await exists(b.globalSkill), false);
  assert.equal(await fs.readFile(join(process.env.ANTIGRAVITY_CONFIG_DIR, "rules/unrelated.md"), "utf8"), "untouched rule");
  assert.equal(await fs.readFile(join(process.env.ANTIGRAVITY_CONFIG_DIR, "GEMINI.md"), "utf8"), "untouched GEMINI");
  assert.equal(await fs.readFile(join(process.env.ANTIGRAVITY_CONFIG_DIR, "skills/unrelated/SKILL.md"), "utf8"), "untouched skill");
  assert.equal((await b.state()).calls.length, 0, "Content-only lifecycle invoked a host CLI");
});

test("Antigravity workspace targets only the explicit workspace and preserves AGENTS", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity"), workspace = join(b.base, "space — 한국어");
  await write(join(workspace, "AGENTS.md"), "user instructions");
  await runManagedHost(b.options("antigravity", "install", { workspace }), b.helpers(pkg));
  assert.equal(await exists(join(workspace, ".agents/rules/opensocrates.md")), true);
  assert.equal(await exists(process.env.ANTIGRAVITY_CONFIG_DIR), false);
  await runManagedHost(b.options("antigravity", "remove", { workspace }), b.helpers(pkg));
  assert.equal(await fs.readFile(join(workspace, "AGENTS.md"), "utf8"), "user instructions");
  await assert.rejects(runManagedHost(b.options("antigravity", "install", { workspace: "relative" }), b.helpers(pkg)), { code: "invalid_scope" });
});

test("Antigravity refuses unmanaged, legacy, modified and unknown content", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity");
  await write(b.globalRule, "user owned rule");
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), { code: "unowned_collision" });
  assert.equal(await fs.readFile(b.globalRule, "utf8"), "user owned rule");
  await fs.unlink(b.globalRule);
  await write(join(process.env.ANTIGRAVITY_CONFIG_DIR, "plugins/opensocrates/plugin.json"), "legacy");
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), { code: "unowned_collision" });
  await fs.rm(join(process.env.ANTIGRAVITY_CONFIG_DIR, "plugins/opensocrates"), { recursive: true });
  await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  await write(join(b.globalSkill, "unknown.txt"), "user addition");
  await assert.rejects(runManagedHost(b.options("antigravity", "remove"), b.helpers(pkg)), { code: "owned_files_modified" });
  assert.equal(await fs.readFile(join(b.globalSkill, "unknown.txt"), "utf8"), "user addition");
  assert.equal((await runManagedHost(b.options("antigravity", "diagnose"), b.helpers(pkg))).reason, "owned_files_modified");
  await fs.unlink(join(b.globalSkill, "unknown.txt"));
  await fs.appendFile(b.globalRule, "edited");
  await assert.rejects(runManagedHost(b.options("antigravity", "update"), b.helpers(pkg)), { code: "owned_files_modified" });
});

test("Antigravity multi-file activation failure restores the full previous state", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity");
  await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  const before = await snapshot(process.env.ANTIGRAVITY_CONFIG_DIR);
  const changed = await fixture(b.base, "antigravity", { version: "1.5.1", variant: "update" });
  const original = fs.rename;
  let injected = false;
  fs.rename = async (source, destination) => {
    if (!injected && destination === b.globalSkill && source.endsWith("/skill")) { injected = true; throw new Error("synthetic rename failure"); }
    return original(source, destination);
  };
  try { await assert.rejects(runManagedHost(b.options("antigravity", "update"), b.helpers(changed, "1.5.1")), /synthetic rename failure/u); }
  finally { fs.rename = original; }
  assert.equal(injected, true); assert.deepEqual(await snapshot(process.env.ANTIGRAVITY_CONFIG_DIR), before);
});

test("symlink roots and package entries are rejected without touching their targets", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity"), other = join(b.base, "other");
  await write(join(other, "sentinel"), "safe");
  await fs.symlink(other, process.env.ANTIGRAVITY_CONFIG_DIR);
  await assert.rejects(runManagedHost(b.options("antigravity", "install"), b.helpers(pkg)), { code: "unsafe_path" });
  assert.equal(await fs.readFile(join(other, "sentinel"), "utf8"), "safe");
  await fs.symlink(join(other, "sentinel"), join(pkg.root, "linked"));
  await assert.rejects(runManagedHost(b.options("antigravity", "verify"), b.helpers(pkg)), { code: "unsafe_path" });
});

test("native Claude lifecycle uses only the owned namespace and preserves unrelated registration/settings", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude");
  await write(join(process.env.CLAUDE_CONFIG_DIR, "settings.json"), '{"unrelated":true}\n');
  const initial = await fs.readFile(join(process.env.CLAUDE_CONFIG_DIR, "settings.json"));
  const installed = await runManagedHost(b.options("claude", "install"), b.helpers(pkg));
  assert.equal(installed.registration, "confirmed"); assert.equal(installed.enabled, true);
  await runManagedHost(b.options("claude", "disable"), b.helpers(pkg));
  const next = await fixture(b.base, "claude", { version: "1.5.1", variant: "next" });
  const updated = await runManagedHost(b.options("claude", "update"), b.helpers(next, "1.5.1"));
  assert.equal(updated.enabled, false); assert.equal(updated.version, "1.5.1");
  const observed = await runManagedHost(b.options("claude", "status"), b.helpers(next, "1.5.1"));
  assert.equal(observed.automatic_entry, "unverified"); assert.equal(observed.enabled, false);
  await runManagedHost(b.options("claude", "enable"), b.helpers(next, "1.5.1"));
  await runManagedHost(b.options("claude", "remove"), b.helpers(next, "1.5.1"));
  assert.equal(await exists(b.nativeRoot), false);
  const state = await b.state();
  assert.equal(state.marketplaces.length, 1); assert.equal(state.marketplaces[0].name, "unrelated");
  assert.equal(state.plugins.length, 1); assert.equal(state.plugins[0].enabled, false);
  assert.deepEqual(await fs.readFile(join(process.env.CLAUDE_CONFIG_DIR, "settings.json")), initial);
  assert.ok(state.calls.some((args) => args.join(" ") === "plugin install opensocrates@opensocrates-macos --scope user --json"));
});

test("failed native update restores prior files, registration and disabled state", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude");
  await runManagedHost(b.options("claude", "install"), b.helpers(pkg));
  await runManagedHost(b.options("claude", "disable"), b.helpers(pkg));
  const before = await snapshot(b.nativeRoot);
  const next = await fixture(b.base, "claude", { version: "1.5.1", variant: "bad-update" });
  await write(process.env.MOCK_CLAUDE_FAIL, "plugin install");
  await assert.rejects(runManagedHost(b.options("claude", "update"), b.helpers(next, "1.5.1")), { code: "claude_cli_unavailable" });
  assert.deepEqual(await snapshot(b.nativeRoot), before);
  const state = await b.state();
  const plugin = state.plugins.find((row) => row.id === "opensocrates@opensocrates-macos");
  assert.equal(plugin.version, VERSION); assert.equal(plugin.enabled, false);
});

test("native companion refuses unmanaged registration collisions, tampering and unknown files", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude"), state = await b.state();
  state.marketplaces.push({ name: "opensocrates-macos", source: "directory", path: join(b.base, "user-market"), installLocation: join(b.base, "user-market") });
  await write(process.env.MOCK_CLAUDE_STATE, jsonBytes(state));
  await assert.rejects(runManagedHost(b.options("claude", "install"), b.helpers(pkg)), { code: "unowned_collision" });
  state.marketplaces.pop(); await write(process.env.MOCK_CLAUDE_STATE, jsonBytes(state));
  await runManagedHost(b.options("claude", "install"), b.helpers(pkg));
  await write(join(b.nativeRoot, "user-extra.txt"), "preserve");
  await assert.rejects(runManagedHost(b.options("claude", "remove"), b.helpers(pkg)), { code: "owned_files_modified" });
  assert.equal(await fs.readFile(join(b.nativeRoot, "user-extra.txt"), "utf8"), "preserve");
  assert.equal((await runManagedHost(b.options("claude", "diagnose"), b.helpers(pkg))).reason, "owned_files_modified");
});

test("native package verification rejects cross-platform runtimes and incomplete canonical pairs", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude");
  pkg.manifest.runtime_targets = ["windows-x64"];
  await write(join(pkg.root, pkg.manifestPath), jsonBytes(pkg.manifest));
  await assert.rejects(runManagedHost(b.options("claude", "verify"), b.helpers(pkg)), { code: "unsupported_package_target" });
  const good = await fixture(b.base, "claude", { variant: "missing" });
  const remove = "skills/opensocrates/references/decision/methods/en/method-48.md";
  await fs.unlink(join(good.root, remove));
  good.manifest.files = good.manifest.files.filter((row) => row.path !== remove);
  await write(join(good.root, good.manifestPath), jsonBytes(good.manifest));
  await assert.rejects(runManagedHost(b.options("claude", "verify"), b.helpers(good)), { code: "invalid_canonical_content" });
});

test("Chat export preserves verified ZIP bytes, refuses replacement and makes no account claim", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude-chat"), output = join(b.base, "account-export.zip");
  const exported = await runManagedHost(b.options("claude-chat", "export", { output }), { ...b.helpers(pkg), platform: "linux" });
  assert.equal(exported.installation, "export-only"); assert.equal(exported.account_activation, "unverified");
  assert.deepEqual(await fs.readFile(output), await fs.readFile(pkg.asset));
  await runManagedHost(b.options("claude-chat", "export", { output }), b.helpers(pkg));
  await fs.appendFile(output, "different");
  await assert.rejects(runManagedHost(b.options("claude-chat", "export", { output }), b.helpers(pkg)), { code: "export_conflict" });
  await assert.rejects(runManagedHost(b.options("claude-chat", "install"), b.helpers(pkg)), { code: "account_action_unavailable" });
  assert.equal((await b.state()).calls.length, 0);
});

test("Mac lifecycle guard and destructive-option rejection happen before package or host effects", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity");
  for (const platform of ["win32", "linux"]) await assert.rejects(runManagedHost(b.options("antigravity", "install"), { ...b.helpers(pkg), platform }), { code: "unsupported_platform" });
  await assert.rejects(runManagedHost(b.options("claude", "install"), { ...b.helpers(pkg), arch: "x64" }), { code: "unsupported_platform" });
  for (const flag of ["purge", "resetTrust"]) await assert.rejects(runManagedHost(b.options("antigravity", "remove", { [flag]: true }), b.helpers(pkg)), { code: "unsupported_destructive_action" });
  assert.equal(b.cleanupCount(), 0); assert.equal(await exists(process.env.ANTIGRAVITY_CONFIG_DIR), false);
  assert.ok(ManagedHostError.prototype instanceof Error);
});

test("missing installation status/remove does not create a host home or invoke Claude", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude");
  for (const host of ["claude", "antigravity"]) for (const action of ["status", "diagnose", "remove"]) {
    const value = await runManagedHost(b.options(host, action), b.helpers(pkg));
    assert.equal(value.installation, "missing");
  }
  assert.equal(await exists(process.env.CLAUDE_CONFIG_DIR), false);
  assert.equal(await exists(process.env.ANTIGRAVITY_CONFIG_DIR), false);
  assert.equal((await b.state()).calls.length, 0);
});

test("native checksum inventory is complete and includes the release manifest", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude"), all = await snapshot(pkg.root);
  const checksum = Object.entries(all).sort(([a], [c]) => a.localeCompare(c)).map(([name, value]) => `${value}  ${name}`).join("\n") + "\n";
  await write(join(pkg.root, "checksums.sha256"), checksum);
  assert.equal((await runManagedHost(b.options("claude", "verify"), b.helpers(pkg))).installation, "verified-package");
  await write(join(pkg.root, "checksums.sha256"), checksum.replace(/^./u, "0"));
  await assert.rejects(runManagedHost(b.options("claude", "verify"), b.helpers(pkg)), { code: "inventory_mismatch" });
});

test("undeclared additional runtime and unknown content layout cannot be hidden in valid hashes", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "claude");
  const path = "runtime/windows-x64/extra.exe", bytes = "foreign target";
  await write(join(pkg.root, path), bytes);
  pkg.manifest.files.push({ path, sha256: `sha256:${digest(bytes)}` });
  await write(join(pkg.root, pkg.manifestPath), jsonBytes(pkg.manifest));
  await assert.rejects(runManagedHost(b.options("claude", "verify"), b.helpers(pkg)), { code: "unsupported_package_target" });
  const content = await fixture(b.base, "claude-chat");
  await write(join(content.root, "outside.txt"), "unexpected");
  content.manifest.files.push({ path: "outside.txt", sha256: `sha256:${digest("unexpected")}` });
  await write(join(content.root, content.manifestPath), jsonBytes(content.manifest));
  await assert.rejects(runManagedHost(b.options("claude-chat", "verify"), b.helpers(content)), { code: "invalid_layout" });
});

test("a changed owned backup is restored rather than silently deleted at transaction commit", async (t) => {
  const b = await box(t), pkg = await fixture(b.base, "antigravity");
  await runManagedHost(b.options("antigravity", "install"), b.helpers(pkg));
  const next = await fixture(b.base, "antigravity", { version: "1.5.1", variant: "race" });
  const original = fs.rename;
  let inserted = false;
  fs.rename = async (source, destination) => {
    const value = await original(source, destination);
    if (!inserted && source === b.globalSkill && destination.endsWith("/backup-1")) {
      inserted = true; await write(join(destination, "concurrent-user-file.txt"), "preserve concurrent addition");
    }
    return value;
  };
  try { await assert.rejects(runManagedHost(b.options("antigravity", "update"), b.helpers(next, "1.5.1")), { code: "owned_files_modified" }); }
  finally { fs.rename = original; }
  assert.equal(await fs.readFile(join(b.globalSkill, "concurrent-user-file.txt"), "utf8"), "preserve concurrent addition");
  assert.match(await fs.readFile(b.globalRule, "utf8"), /original/u);
});
