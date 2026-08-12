import assert from "node:assert/strict";
import test from "node:test";

import {
  ASSET_NAME,
  InstallerError,
  assetNameFor,
  isSafeArchivePath,
  markerMatches,
  parseChecksumText,
  parseCli,
} from "./opensocrates.mjs";

test("accepts safe package paths and rejects traversal", () => {
  assert.equal(isSafeArchivePath(".codex-plugin/plugin.json"), true);
  assert.equal(isSafeArchivePath("runtime/darwin-arm64/tool"), true);
  assert.equal(isSafeArchivePath("../outside"), false);
  assert.equal(isSafeArchivePath("runtime/../../outside"), false);
  assert.equal(isSafeArchivePath("/absolute"), false);
  assert.equal(isSafeArchivePath("windows\\path"), false);
});

test("parses the expected release checksum", () => {
  const digest = "a".repeat(64);
  assert.equal(parseChecksumText(`${digest}  ${ASSET_NAME}\n`), digest);
  assert.equal(parseChecksumText(`${digest}\n`), digest);
  assert.throws(
    () => parseChecksumText(`${digest}  another.zip\n`),
    (error) => error instanceof InstallerError,
  );
});

test("derives host-specific release assets", () => {
  assert.match(assetNameFor("antigravity"), /-antigravity-plugin\.zip$/u);
  assert.match(assetNameFor("codex"), /-codex-plugin\.zip$/u);
  assert.match(assetNameFor("claude"), /-claude-plugin\.zip$/u);
  assert.match(assetNameFor("cursor"), /-cursor-plugin\.zip$/u);
  assert.throws(() => assetNameFor("unknown"), (error) => error instanceof InstallerError);
});

test("accepts only the exact ownership marker", () => {
  assert.equal(
    markerMatches(
      {
        schemaVersion: 1,
        marketplaceName: "opensocrates",
        pluginName: "opensocrates",
        host: "cursor",
        registrationKind: "file-drop",
      },
      "cursor",
    ),
    true,
  );
  assert.equal(
    markerMatches(
      {
        schemaVersion: 1,
        marketplaceName: "opensocrates",
        pluginName: "opensocrates",
        host: "antigravity",
        registrationKind: "file-drop",
      },
      "antigravity",
    ),
    true,
  );
  assert.equal(
    markerMatches({
      schemaVersion: 1,
      marketplaceName: "opensocrates",
      pluginName: "opensocrates",
    }),
    true,
  );
  assert.equal(
    markerMatches(
      {
        schemaVersion: 1,
        marketplaceName: "opensocrates",
        pluginName: "opensocrates",
        host: "claude",
      },
      "claude",
    ),
    true,
  );
  assert.equal(
    markerMatches({
      schemaVersion: 1,
      marketplaceName: "opensocrates",
      pluginName: "opensocrates",
      extra: true,
    }),
    false,
  );
});

test("parses lifecycle actions and paired local asset options", () => {
  const defaults = parseCli([]);
  assert.equal(defaults.action, "install");
  assert.equal(defaults.host, "codex");
  assert.equal(defaults.asset, null);
  assert.equal(defaults.checksum, null);
  const status = parseCli(["status", "--host", "claude"]);
  assert.equal(status.action, "status");
  assert.equal(status.host, "claude");
  assert.equal(parseCli(["status", "--host", "cursor"]).host, "cursor");
  const antigravity = parseCli(["status", "--host", "antigravity"]);
  assert.equal(antigravity.host, "antigravity");
  const parsed = parseCli(["verify", "--asset", "bundle.zip", "--checksum", "bundle.sha256"]);
  assert.equal(parsed.action, "verify");
  assert.equal(parsed.host, "codex");
  assert.equal(parsed.asset.endsWith("bundle.zip"), true);
  assert.equal(parsed.checksum.endsWith("bundle.sha256"), true);
  assert.throws(
    () => parseCli(["install", "--asset", "bundle.zip"]),
    (error) => error instanceof InstallerError,
  );
  assert.throws(
    () => parseCli(["remove", "--asset", "bundle.zip", "--checksum", "bundle.sha256"]),
    (error) => error instanceof InstallerError,
  );
  assert.throws(
    () => parseCli(["install", "--host", "web"]),
    (error) => error instanceof InstallerError,
  );
  const all = parseCli([
    "install",
    "--host",
    "all",
    "--asset-claude",
    "claude.zip",
    "--checksum-claude",
    "claude.sha256",
    "--asset-codex",
    "codex.zip",
    "--checksum-codex",
    "codex.sha256",
  ]);
  assert.equal(all.host, "all");
  assert.equal(all.hostAssets.claude.asset.endsWith("claude.zip"), true);
  assert.equal(all.hostAssets.codex.checksum.endsWith("codex.sha256"), true);
  assert.throws(
    () => parseCli(["install", "--host", "all", "--asset", "bundle.zip", "--checksum", "sum"]),
    (error) => error instanceof InstallerError,
  );
});

test("parses opt-in automatic update policy", () => {
  const options = parseCli([
    "auto-update",
    "enable",
    "--host",
    "all",
    "--channel",
    "next",
    "--interval-hours",
    "12",
    "--allow-major",
  ]);
  assert.equal(options.action, "auto-update");
  assert.equal(options.autoUpdateAction, "enable");
  assert.equal(options.host, "all");
  assert.equal(options.channel, "next");
  assert.equal(options.intervalHours, 12);
  assert.equal(options.allowMajor, true);
  assert.throws(
    () => parseCli(["auto-update", "enable", "--interval-hours", "0"]),
    (error) => error instanceof InstallerError,
  );
  assert.throws(
    () => parseCli(["status", "--allow-major"]),
    (error) => error instanceof InstallerError,
  );
  assert.throws(
    () => parseCli(["install", "--force"]),
    (error) => error instanceof InstallerError,
  );
  assert.throws(
    () => parseCli(["auto-update", "disable", "--host", "all"]),
    (error) => error instanceof InstallerError,
  );
  assert.throws(
    () => parseCli(["auto-update", "run", "--host", "claude"]),
    (error) => error instanceof InstallerError,
  );
});
