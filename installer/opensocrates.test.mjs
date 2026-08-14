import assert from "node:assert/strict";
import test from "node:test";

import {
  ASSET_NAME,
  CODEX_TRUST_EVENTS,
  InstallerError,
  PURGE_RESULT_SCHEMA,
  assetNameFor,
  createPurgeResult,
  isSafeArchivePath,
  markerMatches,
  parseChecksumText,
  parseCli,
  purgeExtensionResult,
  stripCodexOpenSocratesTrustSections,
} from "./opensocrates.mjs";

const codexTrustKey = (event, group = 0, handler = 0) =>
  `opensocrates@opensocrates:hooks/hooks.json:${event}:${group}:${handler}`;

const codexTrustSection = (event, newline = "\n") =>
  `[hooks.state.${JSON.stringify(codexTrustKey(event))}]${newline}` +
  `trusted_hash = "sha256:not-evidence"${newline}`;

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
  assert.match(assetNameFor("grok"), /-grok-plugin\.zip$/u);
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
  assert.equal(parseCli(["status", "--host", "grok"]).host, "grok");
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
  const purge = parseCli(["remove", "--host", "all", "--purge"]);
  assert.equal(purge.action, "remove");
  assert.equal(purge.host, "all");
  assert.equal(purge.purge, true);
  assert.equal(purge.resetTrust, false);
  const trustReset = parseCli(["remove", "--host", "codex", "--purge", "--reset-trust"]);
  assert.equal(trustReset.resetTrust, true);
  assert.equal(parseCli(["remove", "--host", "all", "--purge", "--reset-trust"]).resetTrust, true);
  assert.throws(
    () => parseCli(["install", "--purge"]),
    (error) => error instanceof InstallerError,
  );
  for (const invalid of [
    ["remove", "--reset-trust"],
    ["install", "--purge", "--reset-trust"],
    ["remove", "--host", "claude", "--purge", "--reset-trust"],
  ]) {
    assert.throws(() => parseCli(invalid), (error) => error instanceof InstallerError);
  }
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

test("complete-uninstall results keep Codex trust as an explicit extension", () => {
  const result = createPurgeResult(["codex", "claude"]);
  assert.equal(result.schema, PURGE_RESULT_SCHEMA);
  assert.equal(result.status, "pending");
  assert.deepEqual(
    result.hosts.map((item) => item.host),
    ["claude", "codex"],
  );
  assert.deepEqual(purgeExtensionResult("codex"), {
    component: "host-security-trust",
    status: "preserved",
    nextAction: "rerun-purge-with-reset-trust",
  });
  assert.deepEqual(purgeExtensionResult("codex", true), {
    component: "host-security-trust",
    status: "pending",
    nextAction: null,
  });
  assert.equal(createPurgeResult(["codex"], { resetTrust: true }).hosts[0].extension.status, "pending");
  assert.equal(purgeExtensionResult("claude").status, "not-applicable");
});

test("trust scanner removes exactly seven canonical sections and preserves every other byte", () => {
  const newline = "\r\n";
  const sections = CODEX_TRUST_EVENTS.map((event, index) => {
    const header = `[hooks.state.${JSON.stringify(codexTrustKey(event))}]`;
    return (
      `# before ${index}${newline}` +
      `${header}   # keep header comment ${index}${newline}` +
      `  # keep body comment ${index}${newline}` +
      `  trusted_hash = "sha256:redacted-${index}"   # keep hash comment ${index}${newline}` +
      `# after ${index}${newline}`
    );
  }).join("");
  const unrelated =
    `[hooks.state."other@market:hooks/hooks.json:session_start:0:0"]${newline}` +
    `trusted_hash = "sha256:other"${newline}` +
    `[hooks.state."opensocrates@opensocrates-extra:hooks/hooks.json:session_start:0:0"]${newline}` +
    `trusted_hash = "sha256:similar"${newline}`;
  const input =
    `model = "preserve"${newline}` +
    `[hooks.state]${newline}` +
    `# empty parent is preserved${newline}` +
    unrelated +
    sections +
    `[profiles.keep]${newline}` +
    `model = "keep"${newline}`;
  const result = stripCodexOpenSocratesTrustSections(Buffer.from(input));
  assert.deepEqual(result.removedEvents, [...CODEX_TRUST_EVENTS]);
  const expectedSections = CODEX_TRUST_EVENTS.map(
    (_, index) =>
      `# before ${index}${newline}` +
      `   # keep header comment ${index}${newline}` +
      `  # keep body comment ${index}${newline}` +
      `     # keep hash comment ${index}${newline}` +
      `# after ${index}${newline}`,
  ).join("");
  const expected =
    `model = "preserve"${newline}` +
    `[hooks.state]${newline}` +
    `# empty parent is preserved${newline}` +
    unrelated +
    expectedSections +
    `[profiles.keep]${newline}` +
    `model = "keep"${newline}`;
  assert.deepEqual(result.contents, Buffer.from(expected));
});

test("trust scanner is idempotent for zero sections and accepts a known partial set", () => {
  const zero = Buffer.from('model = "gpt"\n# no trust here\n');
  const unchanged = stripCodexOpenSocratesTrustSections(zero);
  assert.deepEqual(unchanged.removedEvents, []);
  assert.deepEqual(unchanged.contents, zero);

  const partial =
    `# lead\n${codexTrustSection("session_start")}` +
    `# middle\n${codexTrustSection("stop")}` +
    "# tail\n";
  const stripped = stripCodexOpenSocratesTrustSections(partial);
  assert.deepEqual(stripped.removedEvents, ["session_start", "stop"]);
  assert.equal(stripped.contents.toString("utf8"), "# lead\n\n\n# middle\n\n\n# tail\n");
});

test("trust scanner preserves a UTF-8 BOM and every remaining byte", () => {
  const bom = Buffer.from([0xef, 0xbb, 0xbf]);
  const input = Buffer.concat([
    bom,
    Buffer.from(
      `${codexTrustSection("session_start")}# preserve exactly\r\n` +
        '[hooks.state."other@market:hooks/hooks.json:stop:0:0"]\r\n' +
        'trusted_hash = "sha256:other"\r\n',
    ),
  ]);
  const expected = Buffer.concat([
    bom,
    Buffer.from(
      '\n\n# preserve exactly\r\n' +
        '[hooks.state."other@market:hooks/hooks.json:stop:0:0"]\r\n' +
        'trusted_hash = "sha256:other"\r\n',
    ),
  ]);

  const stripped = stripCodexOpenSocratesTrustSections(input);
  assert.deepEqual(stripped.removedEvents, ["session_start"]);
  assert.deepEqual(stripped.contents, expected);
});

test("trust scanner ignores header-shaped text inside multiline strings", () => {
  const fake = codexTrustSection("session_end").trimEnd();
  const input = `message = """\n${fake}\n"""\n${codexTrustSection("session_start")}`;
  const result = stripCodexOpenSocratesTrustSections(input);
  assert.deepEqual(result.removedEvents, ["session_start"]);
  assert.match(result.contents.toString("utf8"), /session_end:0:0/u);
  assert.doesNotMatch(result.contents.toString("utf8"), /session_start:0:0/u);
});

test("trust scanner does not treat header-shaped multiline array values as tables", () => {
  const input =
    'matrix = [\n  ["[hooks.state.\\"not-a-table\\"]"],\n  ["keep"]\n]\n' +
    codexTrustSection("post_tool_use");
  const result = stripCodexOpenSocratesTrustSections(input);
  assert.deepEqual(result.removedEvents, ["post_tool_use"]);
  assert.match(result.contents.toString("utf8"), /not-a-table/u);
});

test("trust scanner refuses ambiguous namespace shapes and unexpected section bodies", () => {
  const quotedPath =
    `["hooks"."state".${JSON.stringify(codexTrustKey("session_start"))}]\n` +
    'trusted_hash = "sha256:value"\n';
  const cases = [
    codexTrustSection("unknown_event"),
    `[hooks.state.${JSON.stringify(codexTrustKey("session_start", 1, 0))}]\ntrusted_hash = "x"\n`,
    codexTrustSection("stop") + codexTrustSection("stop"),
    `[hooks.state.${JSON.stringify(codexTrustKey("stop"))}]\nenabled = false\ntrusted_hash = "x"\n`,
    `[hooks.state.${JSON.stringify(codexTrustKey("stop"))}]\n`,
    quotedPath,
    `[ hooks . state . ${JSON.stringify(codexTrustKey("stop"))} ]\ntrusted_hash = "x"\n`,
    `[hooks.state]\n${JSON.stringify(codexTrustKey("stop"))}.trusted_hash = "x"\n`,
    `hooks = { state = { ${JSON.stringify(codexTrustKey("stop"))} = { trusted_hash = "x" } } }\n`,
    `message = """\n${codexTrustSection("stop")}`,
  ];
  for (const contents of cases) {
    assert.throws(
      () => stripCodexOpenSocratesTrustSections(contents),
      (error) => error instanceof InstallerError && !error.message.includes("sha256"),
    );
  }
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
