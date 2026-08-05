// Isolated installer lifecycle tests.
//
// Every test runs against a throwaway host home and a fake host binary. None
// of these tests reads or writes the developer's real ~/.claude or ~/.codex
// directory, and none of them contacts the network: packages are built locally
// and passed with --asset/--checksum.

import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { PRODUCT_VERSION, main } from "./opensocrates.mjs";

const MARKETPLACE = "opensocrates";
const PLUGIN_ID = `opensocrates@${MARKETPLACE}`;

// ---------------------------------------------------------------------------
// Platform spoofing: install/update are gated to darwin-arm64. The gate is
// intentional, so tests spoof the platform rather than weakening it.
// ---------------------------------------------------------------------------
function withDarwinArm64(fn) {
  const platform = Object.getOwnPropertyDescriptor(process, "platform");
  const arch = Object.getOwnPropertyDescriptor(process, "arch");
  Object.defineProperty(process, "platform", { value: "darwin", configurable: true });
  Object.defineProperty(process, "arch", { value: "arm64", configurable: true });
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
  const manifestDir = host === "claude" ? ".claude-plugin" : ".codex-plugin";
  mkdirSync(join(tree, manifestDir), { recursive: true });
  mkdirSync(join(tree, "runtime", "darwin-arm64", "opensocrates-runtime"), { recursive: true });

  const files = {};
  files[`${manifestDir}/plugin.json`] = JSON.stringify(
    { name: "opensocrates", version: manifestVersion ?? version },
    null,
    2,
  );
  files["release-manifest.json"] = JSON.stringify(
    { product_version: version, host, schema: "opensocrates.plugin-release-manifest/1.0.0" },
    null,
    2,
  );
  files["runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime"] = "#!/bin/sh\nexit 0\n";

  for (const [name, body] of Object.entries(files)) {
    writeFileSync(join(tree, ...name.split("/")), body);
  }
  chmodSync(join(tree, "runtime", "darwin-arm64", "opensocrates-runtime", "opensocrates-runtime"), 0o755);

  const lines = Object.entries(files).map(([name, body]) => {
    const digest = corrupt && name === "release-manifest.json" ? "0".repeat(64) : sha256(Buffer.from(body));
    return `${digest}  ${name}`;
  });
  writeFileSync(join(tree, "checksums.sha256"), `${lines.join("\n")}\n`);

  const asset = join(root, `opensocrates-${version}-${host}-plugin.zip`);
  const zip = spawnSync("zip", ["-q", "-r", "-X", asset, "."], { cwd: tree, encoding: "utf8" });
  assert.equal(zip.status, 0, `zip failed: ${zip.stderr}`);
  const checksum = `${asset}.sha256`;
  writeFileSync(checksum, `${sha256(readFileSync(asset))}  opensocrates-${version}-${host}-plugin.zip\n`);
  return { asset, checksum, tree };
}

// ---------------------------------------------------------------------------
// Fake host binaries. State lives in a JSON file so registration survives
// across separate invocations, exactly like the real hosts.
// ---------------------------------------------------------------------------
function writeFakeHost(root, name, { kind = name, failInstall = false, corruptMarkerOnInstall = false } = {}) {
  const host = kind;
  const statePath = join(root, `${name}-state.json`);
  writeFileSync(statePath, JSON.stringify({ marketplaces: [], plugins: [] }));
  const binary = join(root, name);
  const script = `#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
const STATE = ${JSON.stringify(statePath)};
const HOST = ${JSON.stringify(host)};
const FAIL_INSTALL = ${JSON.stringify(failInstall)};
const CORRUPT_MARKER = ${JSON.stringify(corruptMarkerOnInstall)};
const VERSION = ${JSON.stringify(PRODUCT_VERSION)};
const MARKETPLACE = ${JSON.stringify(MARKETPLACE)};
const PLUGIN_ID = ${JSON.stringify(PLUGIN_ID)};
const argv = process.argv.slice(2);
const state = JSON.parse(readFileSync(STATE, "utf8"));
const save = () => writeFileSync(STATE, JSON.stringify(state));
const out = (value) => process.stdout.write(JSON.stringify(value));
const has = (...parts) => parts.every((part) => argv.includes(part));

if (has("--version")) { process.stdout.write("2.1.205 (fake)\\n"); process.exit(0); }

if (HOST === "claude") {
  if (has("plugin", "marketplace", "list")) { out(state.marketplaces); process.exit(0); }
  if (has("plugin", "marketplace", "add")) {
    const path = argv[argv.indexOf("add") + 1];
    state.marketplaces.push({ name: MARKETPLACE, source: "local", path });
    save(); process.exit(0);
  }
  if (has("plugin", "marketplace", "remove")) {
    state.marketplaces = state.marketplaces.filter((entry) => entry.name !== MARKETPLACE);
    save(); process.exit(0);
  }
  if (has("plugin", "list")) { out(state.plugins); process.exit(0); }
  if (has("plugin", "install")) {
    if (CORRUPT_MARKER) {
      // Simulate a host that leaves the new root unreadable as it fails, so a
      // rollback stage itself throws.
      const entry = state.marketplaces[state.marketplaces.length - 1];
      if (entry && entry.path) writeFileSync(entry.path + "/.opensocrates-managed.json", "{ not json");
    }
    if (FAIL_INSTALL) { process.stderr.write("refused by strictKnownMarketplaces\\n"); process.exit(1); }
    state.plugins.push({ id: PLUGIN_ID, version: VERSION }); save(); process.exit(0);
  }
  if (has("plugin", "uninstall")) {
    state.plugins = state.plugins.filter((entry) => entry.id !== PLUGIN_ID); save(); process.exit(0);
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
  if (CORRUPT_MARKER) {
    const entry = state.marketplaces[state.marketplaces.length - 1];
    if (entry && entry.root) writeFileSync(entry.root + "/.opensocrates-managed.json", "{ not json");
  }
  if (FAIL_INSTALL) { process.stderr.write("refused\\n"); process.exit(1); }
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
  const home = join(root, host === "claude" ? "claude-home" : "codex-home");
  mkdirSync(home, { recursive: true });
  const { binary, statePath } = writeFakeHost(root, host, options);
  const saved = { ...process.env };
  if (host === "claude") {
    process.env.CLAUDE_BIN = binary;
    process.env.CLAUDE_CONFIG_DIR = home;
  } else {
    process.env.CODEX_BIN = binary;
    process.env.CODEX_HOME = home;
  }
  const managedRoot = join(home, "managed-marketplaces", MARKETPLACE);
  return {
    root,
    home,
    managedRoot,
    statePath,
    state: () => JSON.parse(readFileSync(statePath, "utf8")),
    backups: () =>
      existsSync(join(home, "managed-marketplaces"))
        ? readdirSync(join(home, "managed-marketplaces")).filter((n) => n.startsWith(".opensocrates.backup-"))
        : [],
    cleanup: () => {
      for (const key of ["CLAUDE_BIN", "CLAUDE_CONFIG_DIR", "CODEX_BIN", "CODEX_HOME"]) {
        if (saved[key] === undefined) delete process.env[key];
        else process.env[key] = saved[key];
      }
      rmSync(root, { recursive: true, force: true });
    },
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
      const failing = writeFakeHost(good.root, `${host}-failing`, { kind: host, failInstall: true });
      writeFileSync(failing.binary, readFileSync(failing.binary, "utf8").replace(
        JSON.stringify(join(good.root, `${host}-failing-state.json`)),
        JSON.stringify(good.statePath),
      ));
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
    state.marketplaces.push({ name: "OpenSocrates", source: "local", path: "/legacy" });
    state.plugins.push({ id: "opensocrates@OpenSocrates", version: "0.9.0" });
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
    state.marketplaces.push({ name: "OpenSocrates", source: "local", path: "/legacy" });
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
    const pkg = buildPackage(box.root, "claude", { manifestVersion: "9.9.9" });
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
    const link = spawnSync("sh", ["-c", `cd ${JSON.stringify(pkg.tree)} && ln -s /etc/passwd leak && zip -q -y ${JSON.stringify(pkg.asset)} leak`], { encoding: "utf8" });
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
    state.marketplaces.push({ name: MARKETPLACE, source: "local", path: "/somewhere/else" });
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
      assert.deepEqual(
        box.backups(),
        [],
        "previous installation was stranded in a backup directory",
      );
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
    // Corrupt the marker of the *backup* by corrupting the live root before the
    // update renames it, so restore cannot verify ownership.
    writeFileSync(join(box.managedRoot, ".opensocrates-managed.json"), "{ not json");
    const failing = writeFakeHost(box.root, "claude-failing2", { kind: "claude", failInstall: true });
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
    // requireOwnedRoot rejects the corrupted marker before anything is renamed,
    // so nothing is stranded; if a backup ever is, the path must be printed.
    if (box.backups().length > 0) {
      assert.match(result.output, /your previous files are preserved at:/);
    }
  } finally {
    box.cleanup();
  }
});
