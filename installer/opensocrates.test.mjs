import assert from "node:assert/strict";
import test from "node:test";

import {
  ASSET_NAME,
  InstallerError,
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

test("accepts only the exact ownership marker", () => {
  assert.equal(
    markerMatches({
      schemaVersion: 1,
      marketplaceName: "opensocrates",
      pluginName: "opensocrates",
    }),
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
  assert.deepEqual(parseCli([]), { action: "install", asset: null, checksum: null });
  assert.deepEqual(parseCli(["status"]), { action: "status", asset: null, checksum: null });
  const parsed = parseCli(["verify", "--asset", "bundle.zip", "--checksum", "bundle.sha256"]);
  assert.equal(parsed.action, "verify");
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
});
