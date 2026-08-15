import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  existsSync,
  lstatSync,
  linkSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  realpathSync,
  renameSync,
  rmSync,
  symlinkSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir, tmpdir, userInfo } from "node:os";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { deflateRawSync, gzipSync } from "node:zlib";

import { SUPPORTED_HOSTS } from "../installer/opensocrates.mjs";
import * as acceptance from "./reinstall_cycle_acceptance.mjs";
import { publishExclusiveJson } from "./reinstall_cycle_operation_capsule.mjs";

import {
  AcceptanceError,
  applyMutationOutcome,
  assertSafeArchiveEntry,
  downloadImmutableArtifact,
  executeMutationPlan,
  hostRegistrationSnapshot,
  inspectKnownTransactionResidue,
  inspectStateResidue,
  installCommandArguments,
  makeReport as makeRuntimeReport,
  manualTemplate,
  packExisting,
  packedNpxInvocation,
  performStep,
  purgeCommandArguments,
  recoveryPlanForPhase,
  residueIsEmpty,
  validateArtifactMetadata,
  validateNpmPackMetadata,
  writeReports,
  zipReports,
} from "./reinstall_cycle_acceptance.mjs";

function makeReport() {
  const report = makeRuntimeReport();
  report.environment.platform = "darwin";
  report.environment.hardwareArchitecture = "arm64";
  report.environment.processArchitecture = "arm64";
  report.environment.identity = {
    uidMatchesEffectiveUid: true,
    homeOwnedByEffectiveUid: true,
    sudo: false,
  };
  return report;
}

function publicBaselineInventoryFixture(codexHooks) {
  const targetHosts = ["claude", "codex"];
  const hostMap = (factory) =>
    Object.fromEntries(targetHosts.map((host) => [host, factory(host)]));
  return {
    registrations: hostMap(() => ({
      marketplaceCount: 1,
      pluginCount: 1,
      version: "1.2.1",
      unsupportedLegacyConflictCount: 0,
      rootMatchesExpected: true,
    })),
    managedRootsPresent: hostMap(() => true),
    caches: hostMap(() => ({
      present: true,
      ownership: "verified",
      versionCount: 1,
      liveInUse: false,
    })),
    managedPayloadIntegrity: hostMap(() => "verified"),
    cachePayloadIntegrity: hostMap(() => "verified"),
    pluginData: [],
    statePresent: true,
    launchAgentPresent: false,
    launchAgentTemporaryCount: 0,
    launchAgentJobLoaded: false,
    codexTrust: {
      present: true,
      exactSectionCount: 7,
      events: [
        "postToolUse",
        "preCompact",
        "preToolUse",
        "sessionEnd",
        "sessionStart",
        "stop",
        "userPromptSubmit",
      ],
    },
    trustTransactionResidueCount: 0,
    codexHooks,
    nonTargetHosts: Object.fromEntries(
      SUPPORTED_HOSTS.filter((host) => !targetHosts.includes(host)).map((host) => [
        host,
        {
          managedRootPresent: false,
          bridgePresent: false,
          bridgeMarkerPresent: false,
        },
      ]),
    ),
    transactionResidue: Object.fromEntries(
      SUPPORTED_HOSTS.map((host) => [host, 0]),
    ),
    openCodeBridgeResidueCount: 0,
    ownership: "verified",
  };
}

async function withFixture(action) {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "opensocrates-reinstall-test-")));
  const siblingArchive = `${root}.zip`;
  try {
    return await action(root);
  } finally {
    rmSync(siblingArchive, { force: true });
    rmSync(root, { recursive: true, force: true });
    assert.equal(existsSync(siblingArchive), false);
    assert.equal(existsSync(root), false);
  }
}

async function prepareInstalledSealedFixture(outputDirectory, privateDirectory, report = makeReport()) {
  report.source.commit = report.source.commit ?? "a".repeat(40);
  report.automatedResult = "passed";
  report.manualResult = "pending";
  report.overallResult = "pending";
  report.mutation.finalState = "installed";
  writeReports(outputDirectory, report);
  acceptance.initializePrivateEvidenceManifest(privateDirectory, outputDirectory, report);
  const finalState = {
    status: "installed",
    version: "1.2.1",
    installedHosts: ["claude", "codex"],
  };
  const checkpoint = {
    schema: "opensocrates.reinstall-cycle-checkpoint/1.0.0",
    testId: report.testId,
    phase: "post-install-checks",
    reportDirectory: outputDirectory,
    sourceCommit: report.source.commit,
    lastObservedState: null,
  };
  const finalizationId = acceptance.beginFinalizationClaim(
    privateDirectory,
    checkpoint,
    { testId: report.testId, sourceCommit: report.source.commit },
  );
  await acceptance.runFinalVerificationOnce(
    privateDirectory,
    checkpoint,
    async () => finalState,
    { testId: report.testId, sourceCommit: report.source.commit, finalizationId },
  );
  const finalVerification = acceptance.makeFinalVerificationSnapshot(report, finalState);
  const sealed = acceptance.createSealedPublicResult(
    privateDirectory,
    report,
    finalVerification,
    { finalizationId },
  );
  checkpoint.phase = "final-verified";
  checkpoint.lastObservedState = {
    classification: "candidate_installed_verified",
    finalizationId,
    testId: report.testId,
    sourceCommit: report.source.commit,
    installedHosts: ["claude", "codex"],
    finalVerification,
    sealedPublicResult: {
      receiptSha256: sealed.receiptSha256,
      sealSha256: sealed.receipt.sealSha256,
      resultJsonSha256: sealed.receipt.files["result.json"].sha256,
    },
    actualStateRecorded: true,
    previousStateRestorationClaimed: false,
  };
  acceptance.persistRunAndFinalizeCheckpoint(
    report,
    outputDirectory,
    privateDirectory,
    checkpoint,
  );
  return { report, checkpoint, sealed, finalVerification, finalizationId };
}

async function waitUntil(predicate, message, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 20));
  }
  throw new Error(message);
}

function executionFixture(root) {
  const execution = {
    root: join(root, "isolated-npx"),
    runsRoot: join(root, "isolated-npx", "runs"),
    cwd: join(root, "isolated-npx", "cwd"),
    cache: join(root, "isolated-npx", "cache"),
    prefix: join(root, "isolated-npx", "prefix"),
    userConfig: join(root, "isolated-npx", "user.npmrc"),
    npxBinary: "/private/pinned/bin/npx",
    npmBinary: "/private/pinned/bin/npm",
    nodeBinary: process.execPath,
    pythonBinary: realpathSync(process.execPath),
    claudeBinary: realpathSync(process.execPath),
    codexBinary: realpathSync(process.execPath),
    accountHome: realpathSync(homedir()),
    accountUser: userInfo().username,
  };
  for (const target of [execution.root, execution.runsRoot, execution.cwd, execution.cache, execution.prefix]) {
    mkdirSync(target, { recursive: true, mode: 0o700 });
  }
  writeFileSync(execution.userConfig, "audit=false\n", { mode: 0o600 });
  return execution;
}

function candidateFixture(root) {
  return {
    packageArchive: join(root, "opensocrates-1.2.1.tgz"),
    execution: executionFixture(root),
    assets: {
      claude: {
        archivePath: join(root, "claude.zip"),
        checksumPath: join(root, "claude.sha256"),
      },
      codex: {
        archivePath: join(root, "codex.zip"),
        checksumPath: join(root, "codex.sha256"),
      },
    },
  };
}

function registrationRecorder({ claudeRoot, codexRoot }) {
  return {
    run: (label) => {
      if (label === "List Claude plugin marketplaces") {
        return {
          stdout: JSON.stringify([
            {
              name: "opensocrates",
              source: "directory",
              path: claudeRoot,
              installLocation: claudeRoot,
            },
          ]),
        };
      }
      if (label === "List Claude installed plugins") {
        return {
          stdout: JSON.stringify([
            { id: "opensocrates@opensocrates", version: "1.2.1" },
          ]),
        };
      }
      if (label === "List Codex plugin marketplaces") {
        return {
          stdout: JSON.stringify({
            marketplaces: [{ name: "opensocrates", root: codexRoot }],
          }),
        };
      }
      if (label === "List Codex OpenSocrates plugin state") {
        return {
          stdout: JSON.stringify({
            installed: [{ pluginId: "opensocrates@opensocrates", version: "1.2.1" }],
          }),
        };
      }
      throw new Error(`unexpected fixture command: ${label}`);
    },
  };
}

function emptyResidueTargets(root) {
  const allHosts = Object.fromEntries(
    SUPPORTED_HOSTS.map((host) => {
      const parent = join(root, host);
      return [
        host,
        {
          root: join(parent, "managed"),
          cacheRoot: join(parent, "cache-marketplace", "opensocrates"),
          cacheMarketplaceRoot: join(parent, "cache-marketplace"),
          pluginData: [join(parent, "data")],
          transactionParent: join(parent, "transactions"),
          bridge: host === "opencode" ? join(parent, "opensocrates.js") : null,
          bridgeMarker:
            host === "opencode" ? join(parent, ".opensocrates-managed.json") : null,
          bridgeParent: host === "opencode" ? parent : null,
        },
      ];
    }),
  );
  return {
    allHosts,
    claude: allHosts.claude,
    codex: { ...allHosts.codex, hostHome: join(root, "codex-home") },
    state: {
      directory: join(root, "state"),
      desiredState: join(root, "state", "desired-state.json"),
      receipt: join(root, "state", "auto-update-receipt.json"),
      launchAgentsDirectory: join(root, "LaunchAgents"),
      launchAgent: join(root, "LaunchAgents", "com.opensocrates.auto-update.plist"),
    },
  };
}

function deactivatedDesiredStateFixture() {
  return {
    schema: "opensocrates.desired-state/1.0.0",
    channel: "stable",
    installedHosts: [],
    activeVersion: null,
    updatePolicy: { intervalHours: 24, allowMajor: false },
    autoUpdate: { enabled: false, hosts: [], nextCheckAt: null },
    availableVersion: null,
    lastCheckAt: null,
    lastSuccessfulUpdateAt: null,
  };
}

function writeClaudeManagedRootFixture(root) {
  const managedRoot = join(root, "managed-claude");
  const pluginRoot = join(managedRoot, "plugins", "opensocrates");
  mkdirSync(join(managedRoot, ".claude-plugin"), { recursive: true, mode: 0o700 });
  mkdirSync(join(pluginRoot, ".claude-plugin"), { recursive: true, mode: 0o700 });
  writeFileSync(
    join(managedRoot, ".opensocrates-managed.json"),
    `${JSON.stringify({
      schemaVersion: 1,
      marketplaceName: "opensocrates",
      pluginName: "opensocrates",
      host: "claude",
    })}\n`,
    { mode: 0o600 },
  );
  const marketplace = {
    name: "opensocrates",
    owner: { name: "Parker Hwang" },
    metadata: {
      description: "OpenSocrates reasoning support for Claude Code and Cowork",
      version: "1.2.1",
    },
    plugins: [
      {
        name: "opensocrates",
        source: "./plugins/opensocrates",
        description:
          "Local reasoning-system selection for Claude Code and Cowork, plus one /opensocrates entry.",
        category: "workflow",
      },
    ],
  };
  writeFileSync(
    join(managedRoot, ".claude-plugin", "marketplace.json"),
    `${JSON.stringify(marketplace)}\n`,
    { mode: 0o600 },
  );
  const payloads = {
    ".claude-plugin/plugin.json": `${JSON.stringify({ name: "opensocrates", version: "1.2.1" })}\n`,
    "release-manifest.json": `${JSON.stringify({
      schema: "opensocrates.plugin-release-manifest/1.0.0",
      host: "claude",
      product_version: "1.2.1",
      content_revision: 1,
    })}\n`,
  };
  for (const [relativePath, contents] of Object.entries(payloads)) {
    writeFileSync(join(pluginRoot, ...relativePath.split("/")), contents, { mode: 0o600 });
  }
  const checksums = Object.entries(payloads)
    .map(([relativePath, contents]) =>
      `${createHash("sha256").update(contents).digest("hex")}  ${relativePath}`)
    .join("\n");
  writeFileSync(join(pluginRoot, "checksums.sha256"), `${checksums}\n`, { mode: 0o600 });
  return { managedRoot, pluginRoot, marketplace };
}

function writeSensitiveCliFixtures(root) {
  const binDirectory = join(root, "fixture-bin");
  mkdirSync(binDirectory, { mode: 0o700 });
  const source = String.raw`#!/usr/bin/env node
const readline = require("node:readline");
const tool = process.argv[1].split("/").pop();
const args = process.argv.slice(2);
const command = args.join(" ");
const canary = process.env.PRIVATE_CANARY;
const claudeRoot = process.env.FIXTURE_CLAUDE_ROOT;
const codexRoot = process.env.FIXTURE_CODEX_ROOT;

function emit(value) {
  process.stderr.write(canary + "\n");
  process.stdout.write(JSON.stringify(value) + "\n");
}

if (tool === "gh" && command === "auth status") {
  emit({ account: canary, status: "authenticated" });
} else if (tool === "claude" && command === "--version") {
  process.stderr.write(canary + "\n");
  process.stdout.write("2.1.205\n");
} else if (tool === "claude" && command === "auth status --json") {
  emit({ loggedIn: true, account: canary, status: "authenticated" });
} else if (tool === "claude" && command === "plugin marketplace list --json") {
  emit([
    {
      name: "opensocrates",
      source: "directory",
      path: claudeRoot,
      installLocation: claudeRoot,
      unrelatedAccount: canary,
    },
    { name: "unrelated", path: canary, account: canary },
  ]);
} else if (tool === "claude" && command === "plugin list --json") {
  emit([
    { id: "opensocrates@opensocrates", version: "1.2.1", account: canary },
    { id: "unrelated@private", version: canary, account: canary },
  ]);
} else if (tool === "codex" && command === "--version") {
  process.stderr.write(canary + "\n");
  process.stdout.write("codex-cli 1.0.0\n");
} else if (tool === "codex" && command === "login status") {
  emit({ account: canary, status: "authenticated" });
} else if (tool === "codex" && command === "plugin marketplace list --json") {
  emit({
    marketplaces: [
      { name: "opensocrates", root: codexRoot, account: canary },
      { name: "unrelated", root: canary, account: canary },
    ],
  });
} else if (
  tool === "codex" &&
  command === "plugin list --marketplace opensocrates --available --json"
) {
  emit({
    installed: [
      { pluginId: "opensocrates@opensocrates", version: "1.2.1", account: canary },
      { pluginId: "unrelated@private", version: canary, account: canary },
    ],
  });
} else if (tool === "codex" && command === "app-server --stdio") {
  process.stderr.write(canary + "\n");
  const lines = readline.createInterface({ input: process.stdin });
  lines.on("line", (line) => {
    const request = JSON.parse(line);
    if (request.id === 1) {
      process.stdout.write(JSON.stringify({ id: 1, result: {} }) + "\n");
    } else if (request.id === 2) {
      const events = [
        "postToolUse",
        "preCompact",
        "preToolUse",
        "sessionEnd",
        "sessionStart",
        "stop",
        "userPromptSubmit",
      ];
      const hooks = events.map((eventName) => ({
        pluginId: "opensocrates@opensocrates",
        eventName,
        timeoutSec: eventName === "sessionStart" ? 2 : 10,
        trustStatus: "untrusted",
      }));
      hooks.push({
        pluginId: "unrelated@private",
        eventName: "sessionStart",
        timeoutSec: 99,
        trustStatus: canary,
        account: canary,
      });
      process.stdout.write(
        JSON.stringify({
          id: 2,
          result: { data: [{ hooks, errors: [], warnings: [], account: canary }] },
        }) + "\n",
        () => process.exit(0),
      );
    }
  });
} else {
  process.exit(2);
}
`;
  for (const name of ["claude", "codex", "gh"]) {
    const target = join(binDirectory, name);
    writeFileSync(target, source, { mode: 0o700 });
    chmodSync(target, 0o700);
  }
  return binDirectory;
}

function checkpoint(phase, recovery = {}) {
  return {
    phase,
    recovery: {
      hostCloseRetriesUsed: 0,
      reinstallRetriesUsed: 0,
      ...recovery,
    },
  };
}

const TEST_ZIP_CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = (value & 1) !== 0 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
})();

function testZipCrc32(bytes) {
  let value = 0xffffffff;
  for (const byte of bytes) value = TEST_ZIP_CRC32_TABLE[(value ^ byte) & 0xff] ^ (value >>> 8);
  return (value ^ 0xffffffff) >>> 0;
}

function zipFixtureBytes(entries) {
  const localParts = [];
  const centralParts = [];
  let localOffset = 0;
  for (const entry of entries) {
    const name = entry.nameBytes ?? Buffer.from(entry.name, "utf8");
    const localName = entry.localNameBytes ?? name;
    const body = Buffer.isBuffer(entry.body)
      ? entry.body
      : Buffer.from(entry.body ?? "", "utf8");
    const method = entry.method ?? 0;
    const compressed =
      entry.compressedBody ??
      (method === 8 ? deflateRawSync(body) : body);
    const compressedSize = entry.compressedSize ?? compressed.length;
    const uncompressedSize = entry.uncompressedSize ?? body.length;
    const crc32 = entry.crc32 ?? testZipCrc32(body);
    const flags = entry.flags ?? 0x0800;
    const localFlags = entry.localFlags ?? flags;
    const localMethod = entry.localMethod ?? method;
    const localExtra = entry.localExtra ?? Buffer.alloc(0);
    const centralExtra = entry.centralExtra ?? Buffer.alloc(0);
    const comment = entry.comment ?? Buffer.alloc(0);
    const descriptor = entry.dataDescriptor
      ? (() => {
          const value = Buffer.alloc(16);
          value.writeUInt32LE(entry.descriptorSignature ?? 0x08074b50, 0);
          value.writeUInt32LE(entry.descriptorCrc32 ?? crc32, 4);
          value.writeUInt32LE(entry.descriptorCompressedSize ?? compressedSize, 8);
          value.writeUInt32LE(entry.descriptorUncompressedSize ?? uncompressedSize, 12);
          return value;
        })()
      : Buffer.alloc(0);
    const local = Buffer.alloc(
      30 + localName.length + localExtra.length + compressed.length + descriptor.length,
    );
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(entry.localRequiredVersion ?? entry.requiredVersion ?? 20, 4);
    local.writeUInt16LE(localFlags, 6);
    local.writeUInt16LE(localMethod, 8);
    local.writeUInt32LE(entry.localCrc32 ?? crc32, 14);
    local.writeUInt32LE(entry.localCompressedSize ?? compressedSize, 18);
    local.writeUInt32LE(entry.localUncompressedSize ?? uncompressedSize, 22);
    local.writeUInt16LE(localName.length, 26);
    local.writeUInt16LE(localExtra.length, 28);
    localName.copy(local, 30);
    localExtra.copy(local, 30 + localName.length);
    compressed.copy(local, 30 + localName.length + localExtra.length);
    descriptor.copy(local, 30 + localName.length + localExtra.length + compressed.length);
    localParts.push(local);

    const central = Buffer.alloc(46 + name.length + centralExtra.length + comment.length);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(entry.madeBy ?? 0x0314, 4);
    central.writeUInt16LE(entry.requiredVersion ?? 20, 6);
    central.writeUInt16LE(flags, 8);
    central.writeUInt16LE(method, 10);
    central.writeUInt32LE(crc32, 16);
    central.writeUInt32LE(compressedSize, 20);
    central.writeUInt32LE(uncompressedSize, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt16LE(centralExtra.length, 30);
    central.writeUInt16LE(comment.length, 32);
    central.writeUInt16LE(entry.entryDisk ?? 0, 34);
    central.writeUInt16LE(entry.internalAttributes ?? 0, 36);
    central.writeUInt32LE(
      entry.externalAttributes ??
        (((entry.mode ?? (entry.name.endsWith("/") ? 0o040700 : 0o100600)) << 16) >>> 0),
      38,
    );
    central.writeUInt32LE(entry.localOffset ?? localOffset, 42);
    name.copy(central, 46);
    centralExtra.copy(central, 46 + name.length);
    comment.copy(central, 46 + name.length + centralExtra.length);
    centralParts.push(central);
    localOffset += local.length;
  }
  const centralDirectory = Buffer.concat(centralParts);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralDirectory.length, 12);
  end.writeUInt32LE(localOffset, 16);
  return Buffer.concat([...localParts, centralDirectory, end]);
}

function writeZipFixture(target, entries) {
  writeFileSync(target, zipFixtureBytes(entries), { mode: 0o600 });
}

function writeStoredZipFixture(target, entries) {
  writeZipFixture(
    target,
    entries.map((entry) => ({ ...entry, method: entry.method ?? 0 })),
  );
}

function writeTarGzipFixture(target, entries) {
  const parts = [];
  const writeOctal = (buffer, offset, length, value) => {
    const encoded = value.toString(8).padStart(length - 1, "0");
    buffer.write(encoded, offset, length - 1, "ascii");
    buffer[offset + length - 1] = 0;
  };
  for (const entry of entries) {
    const body = Buffer.from(entry.body ?? "", "utf8");
    const header = Buffer.alloc(512);
    header.write(entry.name, 0, 100, "utf8");
    writeOctal(header, 100, 8, entry.mode ?? 0o600);
    writeOctal(header, 108, 8, 0);
    writeOctal(header, 116, 8, 0);
    writeOctal(header, 124, 12, body.length);
    writeOctal(header, 136, 12, 0);
    header.fill(0x20, 148, 156);
    header.write(entry.type ?? "0", 156, 1, "ascii");
    if (entry.linkName) header.write(entry.linkName, 157, 100, "utf8");
    header.write("ustar\0", 257, 6, "binary");
    header.write("00", 263, 2, "ascii");
    const checksum = header.reduce((sum, byte) => sum + byte, 0);
    header.write(checksum.toString(8).padStart(6, "0"), 148, 6, "ascii");
    header[154] = 0;
    header[155] = 0x20;
    parts.push(header, body);
    const padding = (512 - (body.length % 512)) % 512;
    if (padding > 0) parts.push(Buffer.alloc(padding));
  }
  parts.push(Buffer.alloc(1024));
  writeFileSync(target, gzipSync(Buffer.concat(parts)), { mode: 0o600 });
}

function privateFileTexts(root) {
  const values = [];
  const visit = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const target = join(directory, entry.name);
      if (entry.isDirectory()) visit(target);
      else if (entry.isFile()) values.push(readFileSync(target, "utf8"));
    }
  };
  visit(root);
  return values;
}

function emptyResidueSnapshot() {
  return {
    hosts: Object.fromEntries(
      SUPPORTED_HOSTS.map((host) => [
        host,
        {
        registrationPresent: false,
        unsupportedLegacyRegistrationPresent: false,
        managedRootPresent: false,
        cachePresent: false,
        cacheMarketplacePresent: false,
        liveInUse: false,
        pluginDataPresent: false,
        transactionResidueCount: 0,
        bridgePresent: false,
        bridgeMarkerPresent: false,
        },
      ]),
    ),
    stateResidue: {
      present: false,
      empty: true,
      desiredStatePresent: false,
      receiptPresent: false,
      lifecycleLockPresent: false,
      temporaryCount: 0,
      purgeTombstoneCount: 0,
      unknownLeafCount: 0,
    },
    launchAgentPlistPresent: false,
    launchAgentTemporaryCount: 0,
    launchAgentJobLoaded: false,
    codexTrustSectionCount: 0,
    trustTransactionResidueCount: 0,
    openCodeBridgeResidueCount: 0,
  };
}

test("every purge attempt is one combined all-host purge and trust reset", () =>
  withFixture((root) => {
    const candidate = candidateFixture(root);
    const args = purgeCommandArguments(candidate);
    assert.deepEqual(args, [
      "--yes",
      `--package=${candidate.packageArchive}`,
      "opensocrates",
      "remove",
      "--host",
      "all",
      "--purge",
      "--reset-trust",
    ]);
    assert.equal(args.filter((item) => item === "--reset-trust").length, 1);
  }));

test("packed lifecycle calls use a pinned npx and an operation-bound injection-free sandbox", () =>
  withFixture((root) => {
    const candidate = candidateFixture(root);
    const priorNodeOptions = process.env.NODE_OPTIONS;
    const priorToken = process.env.NPM_TOKEN;
    const priorClaudeBin = process.env.CLAUDE_BIN;
    const priorCodexBin = process.env.CODEX_BIN;
    process.env.NODE_OPTIONS = "--require=/private/injection-canary.js";
    process.env.NPM_TOKEN = "private-token-canary";
    process.env.CLAUDE_BIN = "/private/untrusted/claude";
    process.env.CODEX_BIN = "/private/untrusted/codex";
    try {
      const lifecycleOptions = {
        invocationMode: "account-home-lifecycle",
        lifecycleOperationKey: "purge-initial",
      };
      const first = packedNpxInvocation(
        candidate,
        purgeCommandArguments(candidate),
        lifecycleOptions,
      );
      const second = packedNpxInvocation(
        candidate,
        purgeCommandArguments(candidate),
        lifecycleOptions,
      );
      assert.equal(first.executable, candidate.execution.npxBinary);
      assert.notEqual(first.executable, "npx");
      for (const invocation of [first, second]) {
        assert.ok(invocation.options.cwd.startsWith(`${candidate.execution.runsRoot}/`));
        assert.ok(invocation.options.env.npm_config_cache.startsWith(`${candidate.execution.runsRoot}/`));
        assert.ok(invocation.options.env.npm_config_prefix.startsWith(`${candidate.execution.runsRoot}/`));
        assert.ok(invocation.options.env.npm_config_userconfig.startsWith(`${candidate.execution.runsRoot}/`));
        assert.equal(invocation.options.env.PATH.split(":")[0], dirname(process.execPath));
        assert.equal(Object.hasOwn(invocation.options.env, "NODE_OPTIONS"), false);
        assert.equal(Object.hasOwn(invocation.options.env, "NPM_TOKEN"), false);
        assert.equal(Object.hasOwn(invocation.options.env, "npm_config_registry"), false);
        assert.equal(invocation.options.env.CLAUDE_BIN, candidate.execution.claudeBinary);
        assert.equal(invocation.options.env.CODEX_BIN, candidate.execution.codexBinary);
        assert.equal(invocation.options.env.HOME, candidate.execution.accountHome);
        assert.equal(invocation.options.env.USER, candidate.execution.accountUser);
        const observedHome = spawnSync(
          process.execPath,
          ["-e", "process.stdout.write(require('node:os').homedir())"],
          { env: invocation.options.env, encoding: "utf8" },
        );
        assert.equal(observedHome.status, 0);
        assert.equal(observedHome.stdout, candidate.execution.accountHome);
      }
      assert.equal(first.options.cwd, second.options.cwd);
      assert.equal(first.options.env.npm_config_cache, second.options.env.npm_config_cache);
      assert.equal(first.options.env.npm_config_prefix, second.options.env.npm_config_prefix);
      assert.equal(first.options.env.npm_config_userconfig, second.options.env.npm_config_userconfig);
      const retry = packedNpxInvocation(candidate, purgeCommandArguments(candidate), {
        invocationMode: "account-home-lifecycle",
        lifecycleOperationKey: "purge-host-close-retry",
      });
      assert.notEqual(first.options.cwd, retry.options.cwd);

      const preflight = packedNpxInvocation(candidate, [
        "--yes",
        `--package=${candidate.packageArchive}`,
        "opensocrates",
        "help",
      ]);
      assert.notEqual(preflight.options.env.HOME, candidate.execution.accountHome);
      assert.ok(preflight.options.env.HOME.startsWith(`${candidate.execution.runsRoot}/`));
      assert.throws(
        () => packedNpxInvocation(candidate, purgeCommandArguments(candidate)),
        AcceptanceError,
      );
      assert.throws(
        () =>
          packedNpxInvocation(candidate, preflight.args, {
            invocationMode: "account-home-lifecycle",
          }),
        AcceptanceError,
      );
      assert.doesNotThrow(() =>
        packedNpxInvocation(candidate, installCommandArguments(candidate), {
          invocationMode: "account-home-lifecycle",
          lifecycleOperationKey: "install-initial",
        }));
      assert.doesNotThrow(() =>
        packedNpxInvocation(
          candidate,
          [
            "--yes",
            `--package=${candidate.packageArchive}`,
            "opensocrates",
            "status",
            "--host",
            "all",
          ],
          { invocationMode: "account-home-lifecycle" },
        ));
    } finally {
      if (priorNodeOptions === undefined) delete process.env.NODE_OPTIONS;
      else process.env.NODE_OPTIONS = priorNodeOptions;
      if (priorToken === undefined) delete process.env.NPM_TOKEN;
      else process.env.NPM_TOKEN = priorToken;
      if (priorClaudeBin === undefined) delete process.env.CLAUDE_BIN;
      else process.env.CLAUDE_BIN = priorClaudeBin;
      if (priorCodexBin === undefined) delete process.env.CODEX_BIN;
      else process.env.CODEX_BIN = priorCodexBin;
    }
  }));

test("real packed purge and install dispatch only through durable lifecycle receipts", () =>
  withFixture(async (root) => {
    const candidate = candidateFixture(root);
    candidate.sourceCommit = "a".repeat(40);
    candidate.packageSha256 = "1".repeat(64);
    candidate.rawArtifactSha256 = "2".repeat(64);
    candidate.buildSourceReceiptSha256 = "3".repeat(64);
    Object.assign(candidate.execution, {
      nodeBinarySha256: "4".repeat(64),
      npmBinarySha256: "5".repeat(64),
      npxBinarySha256: "6".repeat(64),
      pythonBinarySha256: "9".repeat(64),
      claudeBinarySha256: "7".repeat(64),
      codexBinarySha256: "8".repeat(64),
    });
    for (const [index, host] of ["claude", "codex"].entries()) {
      Object.assign(candidate.assets[host], {
        sha256: String(index + 7).repeat(64),
        checksumSha256: String(index + 1).repeat(64),
        payloadReceiptSha256: String(index + 3).repeat(64),
        releaseManifestSha256: String(index + 5).repeat(64),
      });
    }
    const traces = [];
    const recorder = {
      run: () => {
        throw new Error("destructive lifecycle unexpectedly used the generic recorder");
      },
      runLifecycle: async (label, executable, args, options) => {
        traces.push({ label, executable, args, options });
        return { status: 0, stdout: "", stderr: "", error: null };
      },
    };
    await acceptance.runPackedNpx(
      recorder,
      "purge fixture",
      candidate,
      purgeCommandArguments(candidate),
      {
        invocationMode: "account-home-lifecycle",
        lifecycleOperationKey: "purge-initial",
        timeout: 300_000,
      },
    );
    await acceptance.runPackedNpx(
      recorder,
      "install fixture",
      candidate,
      installCommandArguments(candidate),
      {
        invocationMode: "account-home-lifecycle",
        lifecycleOperationKey: "install-initial",
        timeout: 600_000,
      },
    );
    assert.deepEqual(traces.map((trace) => trace.options.operationKey), [
      "purge-initial",
      "install-initial",
    ]);
    assert.deepEqual(traces[0].args, purgeCommandArguments(candidate));
    assert.deepEqual(traces[1].args, installCommandArguments(candidate));
    for (const trace of traces) {
      assert.equal(trace.executable, candidate.execution.npxBinary);
      assert.match(trace.options.candidateIdentitySha256, /^[a-f0-9]{64}$/u);
      assert.equal(trace.options.env.HOME, candidate.execution.accountHome);
      assert.ok(trace.options.env.npm_config_cache.startsWith(candidate.execution.runsRoot));
      assert.equal(Object.hasOwn(trace.options.env, "NODE_OPTIONS"), false);
    }
    assert.throws(
      () =>
        acceptance.runPackedNpx(
          { run: () => ({ status: 0 }) },
          "unsafe purge fixture",
          candidate,
          purgeCommandArguments(candidate),
          {
            invocationMode: "account-home-lifecycle",
            lifecycleOperationKey: "purge-initial",
          },
        ),
      AcceptanceError,
    );
  }));

test("packed help and verify accept the exact minimal preflight candidate", () =>
  withFixture((root) => {
    const packageArchive = join(root, "opensocrates-1.2.1.tgz");
    const candidateForNpx = {
      packageArchive,
      execution: executionFixture(root),
    };
    const commands = [
      ["--yes", `--package=${packageArchive}`, "opensocrates", "help"],
      [
        "--yes",
        `--package=${packageArchive}`,
        "opensocrates",
        "verify",
        "--host",
        "all",
        "--asset-claude",
        join(root, "claude.zip"),
        "--checksum-claude",
        join(root, "claude.sha256"),
        "--asset-codex",
        join(root, "codex.zip"),
        "--checksum-codex",
        join(root, "codex.sha256"),
      ],
    ];
    for (const args of commands) {
      const invocation = packedNpxInvocation(candidateForNpx, args);
      assert.equal(invocation.executable, candidateForNpx.execution.npxBinary);
      assert.deepEqual(invocation.args, args);
      assert.notEqual(invocation.options.env.HOME, candidateForNpx.execution.accountHome);
      assert.ok(invocation.options.env.HOME.startsWith(`${candidateForNpx.execution.runsRoot}/`));
    }
  }));

test("lifecycle account HOME accepts canonical current-owner mode 0750 only", () =>
  withFixture((root) => {
    const accountHome = join(root, "account-home");
    const differentHome = join(root, "different-home");
    const linkedHome = join(root, "linked-home");
    mkdirSync(accountHome, { mode: 0o750 });
    mkdirSync(differentHome, { mode: 0o750 });
    chmodSync(accountHome, 0o750);
    chmodSync(differentHome, 0o750);
    symlinkSync(accountHome, linkedHome);
    const uid = process.getuid();
    assert.equal(
      acceptance.validateLifecycleAccountHome(accountHome, {
        expectedHome: accountHome,
        expectedUid: uid,
      }),
      realpathSync(accountHome),
    );
    assert.equal(lstatSync(accountHome).mode & 0o777, 0o750);
    for (const [candidateHome, expectedHome, expectedUid] of [
      [linkedHome, accountHome, uid],
      [accountHome, differentHome, uid],
      [accountHome, accountHome, uid + 1],
    ]) {
      assert.throws(
        () => acceptance.validateLifecycleAccountHome(candidateHome, {
          expectedHome,
          expectedUid,
        }),
        AcceptanceError,
      );
    }
  }));

test("lifecycle account username is pinned to the current POSIX user", () => {
  assert.equal(
    acceptance.validateLifecycleAccountUser("fixture-user", { expectedUser: "fixture-user" }),
    "fixture-user",
  );
  for (const candidate of ["", "other-user", "unsafe/user", null]) {
    assert.throws(
      () => acceptance.validateLifecycleAccountUser(candidate, { expectedUser: "fixture-user" }),
      AcceptanceError,
    );
  }
});

test("registration admission binds each CLI marketplace root to its canonical managed root", () =>
  withFixture((root) => {
    const claudeRoot = join(root, "managed-claude");
    const codexRoot = join(root, "managed-codex");
    const unmanaged = join(root, "unmanaged");
    for (const target of [claudeRoot, codexRoot, unmanaged]) mkdirSync(target, { mode: 0o700 });
    const targets = { claude: { root: claudeRoot }, codex: { root: codexRoot } };
    const exact = hostRegistrationSnapshot(
      registrationRecorder({ claudeRoot, codexRoot }),
      targets,
    );
    assert.equal(exact.claude.rootMatchesExpected, true);
    assert.equal(exact.codex.rootMatchesExpected, true);
    assert.throws(
      () => hostRegistrationSnapshot(
        registrationRecorder({ claudeRoot: unmanaged, codexRoot }),
        targets,
      ),
      AcceptanceError,
    );
  }));

test("pre-1.0 Claude registration case variants are manual conflicts and never mutation targets", () => {
  const calls = [];
  const recorder = {
    run: (label, executable, args, options) => {
      calls.push({ label, executable, args, options });
      if (label === "List Claude plugin marketplaces") {
        return {
          stdout: JSON.stringify([{ name: "OpenSocrates", path: "/legacy/not-opened" }]),
        };
      }
      if (label === "List Claude installed plugins") {
        return {
          stdout: JSON.stringify([{ id: "opensocrates@OpenSocrates", version: "0.9.0" }]),
        };
      }
      if (label === "List Codex plugin marketplaces") {
        return { stdout: JSON.stringify({ marketplaces: [] }) };
      }
      if (label === "List Codex OpenSocrates plugin state") {
        return { stdout: JSON.stringify({ installed: [] }) };
      }
      throw new Error(`unexpected fixture command: ${label}`);
    },
  };
  const snapshot = hostRegistrationSnapshot(recorder, {
    claude: { root: "/canonical/claude-not-opened" },
    codex: { root: "/canonical/codex-not-opened" },
  });
  assert.equal(snapshot.claude.marketplaceCount, 0);
  assert.equal(snapshot.claude.pluginCount, 0);
  assert.equal(snapshot.claude.unsupportedLegacyConflictCount, 2);
  assert.throws(
    () => acceptance.assertRegistrationState(snapshot, "absent"),
    /unsupported pre-1\.0/u,
  );
  assert.equal(calls.length, 4);
  assert.ok(calls.every((call) => call.options.persistRaw === false));
  assert.ok(
    calls.every(
      (call) => !new Set(["remove", "uninstall", "install"]).has(call.args[0]),
    ),
  );
});

test("actual registration, authentication, and Codex hook call sites suppress raw streams", () =>
  withFixture((root) => {
    const claudeRoot = join(root, "managed-claude");
    const codexRoot = join(root, "managed-codex");
    mkdirSync(claudeRoot, { mode: 0o700 });
    mkdirSync(codexRoot, { mode: 0o700 });
    const targets = { claude: { root: claudeRoot }, codex: { root: codexRoot } };
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const fixtureBin = writeSensitiveCliFixtures(root);
    const report = makeReport();
    const actualRecorder = new acceptance.CommandRecorder(privateDirectory, report);
    const calls = [];
    const recorder = {
      run: (label, executable, args, options) => {
        calls.push({ label, executable, args, options });
        return actualRecorder.run(label, executable, args, options);
      },
    };
    const canary = "UNRELATED_ACCOUNT_PLUGIN_CANARY_actual_calls_8aa1";
    const priorEnvironment = {
      PATH: process.env.PATH,
      PRIVATE_CANARY: process.env.PRIVATE_CANARY,
      FIXTURE_CLAUDE_ROOT: process.env.FIXTURE_CLAUDE_ROOT,
      FIXTURE_CODEX_ROOT: process.env.FIXTURE_CODEX_ROOT,
    };
    process.env.PATH = `${fixtureBin}:${process.env.PATH ?? ""}`;
    process.env.PRIVATE_CANARY = canary;
    process.env.FIXTURE_CLAUDE_ROOT = claudeRoot;
    process.env.FIXTURE_CODEX_ROOT = codexRoot;
    try {
      const registrations = hostRegistrationSnapshot(recorder, targets);
      assert.equal(registrations.claude.rootMatchesExpected, true);
      assert.equal(registrations.codex.rootMatchesExpected, true);
      acceptance.verifyGitHubAuthentication(recorder);
      acceptance.verifyHosts(recorder, report);
      const hooks = acceptance.codexHookInventory(recorder);
      assert.equal(hooks.hookCount, 7);
    } finally {
      for (const [key, value] of Object.entries(priorEnvironment)) {
        if (value === undefined) delete process.env[key];
        else process.env[key] = value;
      }
    }

    const inventoryCalls = calls.filter((call) => call.label.startsWith("List "));
    assert.deepEqual(
      inventoryCalls.map((call) => [call.options.persistRaw, call.options.projection]),
      [
        [false, "claude-marketplaces"],
        [false, "claude-plugins"],
        [false, "codex-marketplaces"],
        [false, "codex-plugins"],
      ],
    );
    const authenticationCalls = calls.filter((call) => call.label.includes("authentication"));
    assert.equal(authenticationCalls.length, 3);
    assert.deepEqual(
      authenticationCalls.map((call) => [call.options.persistRaw, call.options.projection]),
      [
        [false, "status-only"],
        [false, "claude-auth"],
        [false, "status-only"],
      ],
    );
    const hookCall = calls.find((call) => call.label.startsWith("Inspect Codex"));
    assert.equal(hookCall.options.persistRaw, false);
    const ledger = readFileSync(join(privateDirectory, "commands.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    assert.ok(ledger.every((entry) => entry.rawStreamsPersisted === false));
    assert.ok(ledger.every((entry) => entry.stdoutFile === null && entry.stderrFile === null));
    assert.deepEqual(readdirSync(join(privateDirectory, "commands")), []);
    assert.equal(privateFileTexts(privateDirectory).some((value) => value.includes(canary)), false);
    assert.equal(JSON.stringify(report).includes(canary), false);
  }));

test("lifecycle host authentication uses the pinned username and rejects logged-out Claude", () =>
  withFixture((root) => {
    const execution = executionFixture(root);
    const calls = [];
    const recorder = {
      run: (label, executable, args, options) => {
        calls.push({ label, executable, args, options });
        if (label.startsWith("Verify pinned Claude")) {
          return { stdout: JSON.stringify({ loggedIn: true }) };
        }
        return { stdout: JSON.stringify({ status: "ok" }) };
      },
    };
    assert.deepEqual(
      acceptance.verifyLifecycleHostAuthentication(recorder, execution),
      { claude: true, codex: true },
    );
    assert.equal(calls.length, 2);
    for (const call of calls) {
      assert.equal(call.options.env.HOME, execution.accountHome);
      assert.equal(call.options.env.USER, execution.accountUser);
      assert.equal(Object.hasOwn(call.options.env, "NPM_TOKEN"), false);
      assert.equal(call.options.persistRaw, false);
    }
    assert.equal(calls[0].options.projection, "claude-auth");
    assert.equal(calls[1].options.projection, "status-only");

    assert.throws(
      () => acceptance.verifyLifecycleHostAuthentication({
        run: (label) => ({
          stdout: JSON.stringify(label.startsWith("Verify pinned Claude")
            ? { loggedIn: false }
            : { status: "ok" }),
        }),
      }, execution),
      /not authenticated/u,
    );
  }));

test("host preflight parses Claude logged-in state instead of trusting exit zero", () => {
  const report = makeReport();
  const calls = [];
  const recorder = {
    run: (label, executable, args, options) => {
      calls.push({ label, executable, args, options });
      if (label === "Read Claude Code version") return { stdout: "2.1.205" };
      if (label === "Verify Claude authentication") {
        return { stdout: JSON.stringify({ loggedIn: false }) };
      }
      throw new Error(`unexpected command after logged-out Claude: ${label}`);
    },
  };
  assert.throws(() => acceptance.verifyHosts(recorder, report), /not authenticated/u);
  assert.equal(calls[1].options.projection, "claude-auth");
  assert.deepEqual(calls[1].args, ["auth", "status", "--json"]);
});

test("reinstall is one atomic all-host command using both exact host assets", () =>
  withFixture((root) => {
    const candidate = candidateFixture(root);
    assert.deepEqual(installCommandArguments(candidate), [
      "--yes",
      `--package=${candidate.packageArchive}`,
      "opensocrates",
      "install",
      "--host",
      "all",
      "--asset-claude",
      candidate.assets.claude.archivePath,
      "--checksum-claude",
      candidate.assets.claude.checksumPath,
      "--asset-codex",
      candidate.assets.codex.archivePath,
      "--checksum-codex",
      candidate.assets.codex.checksumPath,
    ]);
  }));

test("immutable artifact metadata pins workflow run and full head SHA", () => {
  const sha = "a".repeat(40);
  const digest = `sha256:${"b".repeat(64)}`;
  const metadata = {
    id: 77,
    name: "package-darwin-arm64-42-3",
    expired: false,
    digest,
    size_in_bytes: 4096,
    workflow_run: { id: 42, head_sha: sha },
  };
  assert.deepEqual(
    validateArtifactMetadata(metadata, {
      artifactName: metadata.name,
      runId: 42,
      runAttempt: 3,
      sourceCommit: sha,
    }),
    {
      id: 77,
      name: metadata.name,
      digest,
      sizeBytes: 4096,
      workflowRunId: 42,
      workflowRunHeadSha: sha,
    },
  );
  assert.throws(
    () =>
      validateArtifactMetadata(
        { ...metadata, workflow_run: { id: 42, head_sha: "c".repeat(40) } },
        { artifactName: metadata.name, runId: 42, runAttempt: 3, sourceCommit: sha },
      ),
    AcceptanceError,
  );
  assert.throws(
    () =>
      validateArtifactMetadata(metadata, {
        artifactName: metadata.name,
        runId: 42,
        runAttempt: 4,
        sourceCommit: sha,
      }),
    AcceptanceError,
  );
});

test("immutable artifact download uses only the exact artifact-ID API endpoint", async () => {
  const calls = [];
  const sizeBytes = 472_980_709;
  const recorder = {
    runToFile: async (...args) => {
      calls.push(args);
      return { outputSha256: "d".repeat(64), outputSizeBytes: 12 };
    },
  };
  const result = await downloadImmutableArtifact(
    recorder,
    "/private/pinned/bin/gh",
    77,
    "/private/evidence/artifact.zip",
    sizeBytes,
  );
  assert.equal(result.outputSizeBytes, 12);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1], "/private/pinned/bin/gh");
  assert.deepEqual(calls[0][2], [
    "api",
    "repos/ParkerHwang/OpenSocrates/actions/artifacts/77/zip",
  ]);
  assert.equal(
    calls[0][4].timeout,
    acceptance.artifactDownloadTimeoutMs(sizeBytes),
  );
  assert.ok(calls[0][4].timeout > 2_700_000);
  assert.ok(calls[0][4].timeout <= 10_800_000);
  for (const invalid of [0, -1, 1.5, 2 * 1024 * 1024 * 1024 + 1]) {
    assert.throws(
      () => acceptance.artifactDownloadTimeoutMs(invalid),
      AcceptanceError,
    );
  }
});

test("native package workflow and receipt pin the pull-request head commit and tree", () =>
  withFixture((root) => {
    const workflow = readFileSync(".github/workflows/ci.yml", "utf8");
    const exactRef = "${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}";
    const packageJob = workflow.slice(workflow.indexOf("  package:"));
    assert.match(packageJob, new RegExp(`ref: ${exactRef.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")}`, "u"));
    assert.match(packageJob, /node tools\/write_package_provenance\.mjs/u);
    assert.match(
      packageJob,
      /name: package-darwin-arm64-\$\{\{ github\.run_id \}\}-\$\{\{ github\.run_attempt \}\}/u,
    );
    assert.ok(
      packageJob.indexOf("node tools/write_package_provenance.mjs") <
        packageJob.indexOf("Upload native package evidence"),
    );

    const repository = join(root, "repository");
    mkdirSync(repository, { mode: 0o700 });
    assert.equal(spawnSync("git", ["init", "-q"], { cwd: repository }).status, 0);
    writeFileSync(join(repository, "tracked.txt"), "fixture\n", { mode: 0o600 });
    assert.equal(spawnSync("git", ["add", "tracked.txt"], { cwd: repository }).status, 0);
    assert.equal(
      spawnSync(
        "git",
        ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"],
        { cwd: repository },
      ).status,
      0,
    );
    const head = spawnSync("git", ["rev-parse", "HEAD"], { cwd: repository, encoding: "utf8" }).stdout.trim();
    const tree = spawnSync("git", ["rev-parse", "HEAD^{tree}"], { cwd: repository, encoding: "utf8" }).stdout.trim();
    const output = join(repository, "build", "evidence", "package-source-provenance.json");
    const writer = join(process.cwd(), "tools", "write_package_provenance.mjs");
    const completed = spawnSync(process.execPath, [writer, "--output", output], {
      cwd: repository,
      env: { ...process.env, OPENSOCRATES_EXPECTED_SOURCE_SHA: head },
      encoding: "utf8",
    });
    assert.equal(completed.status, 0, completed.stderr);
    const receipt = JSON.parse(readFileSync(output, "utf8"));
    assert.deepEqual(Object.keys(receipt).sort(), [
      "commit",
      "repository",
      "schema",
      "tree",
    ]);
    assert.equal(receipt.commit, head);
    assert.equal(receipt.tree, tree);
    assert.doesNotThrow(() =>
      acceptance.validateBuildSourceReceipt(receipt, {
        sourceCommit: head,
        sourceTree: tree,
      }));

    const rejectedOutput = join(repository, "rejected.json");
    const rejected = spawnSync(process.execPath, [writer, "--output", rejectedOutput], {
      cwd: repository,
      env: { ...process.env, OPENSOCRATES_EXPECTED_SOURCE_SHA: "f".repeat(40) },
      encoding: "utf8",
    });
    assert.notEqual(rejected.status, 0);
    assert.equal(existsSync(rejectedOutput), false);
  }));

test("npm pack metadata is an exact eight-file closed set", () => {
  const files = [
    "CHANGELOG.md",
    "LICENSE",
    "README.ko.md",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "installer/opensocrates.mjs",
    "package.json",
  ].map((path) => ({
    path,
    size: 1,
    mode: path === "installer/opensocrates.mjs" ? 0o755 : 0o644,
  }));
  const valid = {
    name: "opensocrates",
    version: "1.2.1",
    entryCount: files.length,
    files,
    bundled: [],
  };
  assert.doesNotThrow(() => validateNpmPackMetadata(valid));
  assert.throws(
    () =>
      validateNpmPackMetadata({
        ...valid,
        entryCount: files.length + 1,
        files: [...files, { path: "extra.txt", size: 1, mode: 0o644 }],
      }),
    AcceptanceError,
  );
});

test("the focused reinstall acceptance suite is registered in the closed npm test contract", () => {
  const manifest = JSON.parse(readFileSync("package.json", "utf8"));
  assert.match(
    manifest.scripts.test,
    /(?:^|\s)tools\/reinstall_cycle_acceptance\.test\.mjs(?:\s|$)/u,
  );
  assert.equal(
    manifest.scripts.test.split("tools/reinstall_cycle_acceptance.test.mjs").length,
    2,
  );
});

test("npm pack rejects lifecycle-script drift before spawn and uses a fresh minimal environment", () =>
  withFixture((root) => {
    const sourceRoot = join(root, "source");
    const packageDirectory = join(root, "packages");
    mkdirSync(sourceRoot, { mode: 0o700 });
    mkdirSync(packageDirectory, { mode: 0o700 });
    const manifest = JSON.parse(readFileSync(join(process.cwd(), "package.json"), "utf8"));
    manifest.scripts = {
      ...manifest.scripts,
      prepack: `node -e "require('node:fs').writeFileSync('${join(root, "script-ran")}', 'bad')"`,
    };
    writeFileSync(join(sourceRoot, "package.json"), `${JSON.stringify(manifest)}\n`, { mode: 0o600 });
    const execution = executionFixture(root);
    let spawnCount = 0;
    const recorder = {
      run: () => {
        spawnCount += 1;
        return { stdout: "[]" };
      },
    };
    assert.throws(
      () => acceptance.packSourceNpmCandidate(recorder, execution, sourceRoot, packageDirectory),
      AcceptanceError,
    );
    assert.equal(spawnCount, 0);
    assert.equal(existsSync(join(root, "script-ran")), false);

    delete manifest.scripts.prepack;
    writeFileSync(join(sourceRoot, "package.json"), `${JSON.stringify(manifest)}\n`, { mode: 0o600 });
    const calls = [];
    recorder.run = (...args) => {
      calls.push(args);
      return { stdout: "[]" };
    };
    const priorNodeOptions = process.env.NODE_OPTIONS;
    const priorToken = process.env.NPM_TOKEN;
    process.env.NODE_OPTIONS = "--require=/private/npm-pack-canary.js";
    process.env.NPM_TOKEN = "npm-pack-token-canary";
    try {
      acceptance.packSourceNpmCandidate(recorder, execution, sourceRoot, packageDirectory);
    } finally {
      if (priorNodeOptions === undefined) delete process.env.NODE_OPTIONS;
      else process.env.NODE_OPTIONS = priorNodeOptions;
      if (priorToken === undefined) delete process.env.NPM_TOKEN;
      else process.env.NPM_TOKEN = priorToken;
    }
    assert.equal(calls.length, 1);
    const [label, executable, args, options] = calls[0];
    assert.equal(label, "Pack exact candidate npm tarball");
    assert.equal(executable, execution.npmBinary);
    assert.deepEqual(args, [
      "pack",
      sourceRoot,
      "--silent",
      "--json",
      "--ignore-scripts",
      "--pack-destination",
      packageDirectory,
    ]);
    assert.ok(options.cwd.startsWith(`${execution.runsRoot}/`));
    assert.equal(options.env.PATH.split(":")[0], dirname(process.execPath));
    assert.equal(options.env.npm_config_ignore_scripts, "true");
    assert.equal(Object.hasOwn(options.env, "NODE_OPTIONS"), false);
    assert.equal(Object.hasOwn(options.env, "NPM_TOKEN"), false);
  }));

test("baseline payload checksum verifier rejects corrupt and undeclared files", () =>
  withFixture(async (root) => {
    const payload = join(root, "payload");
    mkdirSync(payload, { mode: 0o700 });
    const body = "owned payload\n";
    const digest = createHash("sha256").update(body).digest("hex");
    writeFileSync(join(payload, "owned.txt"), body, { mode: 0o600 });
    writeFileSync(join(payload, "checksums.sha256"), `${digest}  owned.txt\n`, { mode: 0o600 });
    await assert.doesNotReject(() =>
      acceptance.verifyChecksumInventory(payload, "baseline", "fixture payload"));

    writeFileSync(join(payload, "extra.txt"), "unowned\n", { mode: 0o600 });
    await assert.rejects(
      () => acceptance.verifyChecksumInventory(payload, "baseline", "fixture payload"),
      AcceptanceError,
    );
    rmSync(join(payload, "extra.txt"));
    writeFileSync(join(payload, "owned.txt"), "corrupt\n", { mode: 0o600 });
    await assert.rejects(
      () => acceptance.verifyChecksumInventory(payload, "baseline", "fixture payload"),
      AcceptanceError,
    );
  }));

test("pre-purge baseline recheck binds exact managed, cache, desired-state, and trust bytes", () =>
  withFixture(async (root) => {
    const publicInventory = { categorical: "unchanged" };
    const treeBinding = (seed) => ({
      entryCount: 4,
      fileCount: 3,
      aggregateSha256: seed.repeat(64),
    });
    const exactBindings = {
      schema: "opensocrates.reinstall-cycle-baseline-binding/1.0.0",
      managedRoots: {
        claude: treeBinding("1"),
        codex: treeBinding("2"),
      },
      caches: {
        claude: { present: true, ...treeBinding("3") },
        codex: { present: true, ...treeBinding("4") },
      },
      desiredStateSha256: "5".repeat(64),
      codexTrust: {
        present: true,
        exactSectionCount: 7,
        events: [
          "pre_tool_use",
          "post_tool_use",
          "pre_compact",
          "session_start",
          "session_end",
          "user_prompt_submit",
          "stop",
        ],
        removedSyntaxByteCount: 700,
        removedSyntaxSha256: "6".repeat(64),
      },
    };
    const mutations = [
      (value) => { value.managedRoots.claude.aggregateSha256 = "7".repeat(64); },
      (value) => { value.caches.codex.aggregateSha256 = "8".repeat(64); },
      (value) => { value.desiredStateSha256 = "9".repeat(64); },
      (value) => { value.codexTrust.removedSyntaxSha256 = "a".repeat(64); },
    ];
    for (const [index, mutate] of mutations.entries()) {
      const privateDirectory = join(root, `binding-${index}`);
      mkdirSync(privateDirectory, { mode: 0o700 });
      const report = makeReport();
      report.source.commit = "b".repeat(40);
      const checkpointValue = {
        phase: "ready-to-purge",
        sourceCommit: report.source.commit,
        baseline: {
          initialInventory: publicInventory,
          initialInventorySha256: createHash("sha256")
            .update(JSON.stringify(publicInventory))
            .digest("hex"),
          exactBindings,
          exactBindingsSha256: createHash("sha256")
            .update(JSON.stringify(exactBindings))
            .digest("hex"),
        },
        recovery: {
          hostCloseRetriesUsed: 0,
          reinstallRetriesUsed: 0,
          hostCloseRetryAdmission: null,
          reinstallRetryAdmission: null,
        },
        lastObservedState: { classification: "installed_baseline" },
      };
      const currentBindings = structuredClone(exactBindings);
      mutate(currentBindings);
      let lifecycleCalls = 0;
      await assert.rejects(
        () =>
          acceptance.runMutation(
            {}, report, {}, {}, privateDirectory, checkpointValue,
            {
              lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
              runtime: {
                verifyCandidateUnchanged: async () => {},
                baselineInventory: async () => ({
                  public: structuredClone(publicInventory),
                  exactBindings: currentBindings,
                }),
                inspectRecoveryState: async () => { throw new Error("not reached"); },
                assertFinalInstalled: async () => { lifecycleCalls += 1; },
                inspectFailureState: async () => { throw new Error("not reached"); },
                purgeCandidate: async () => { lifecycleCalls += 1; },
                assertClean: async () => { lifecycleCalls += 1; },
                installCandidate: async () => { lifecycleCalls += 1; },
              },
            },
          ),
        (error) =>
          error instanceof AcceptanceError &&
          error.category === "baseline" &&
          /exact admitted baseline bytes changed/u.test(error.message),
      );
      assert.equal(lifecycleCalls, 0);
    }
  }));

test("stable cache binding excludes only validated non-live in-use markers", () =>
  withFixture(async (root) => {
    const cacheRoot = join(root, "cache");
    const versionRoot = join(cacheRoot, "1.2.1");
    mkdirSync(versionRoot, { recursive: true, mode: 0o700 });
    writeFileSync(join(versionRoot, "payload"), "stable\n", { mode: 0o600 });
    const options = { ignoreCacheInUseMarkers: true };
    const before = await acceptance.exactOwnedTreeBinding(cacheRoot, "fixture cache", options);

    const marker = join(versionRoot, ".in_use");
    mkdirSync(marker, { mode: 0o700 });
    const afterEmptyMarker = await acceptance.exactOwnedTreeBinding(
      cacheRoot,
      "fixture cache",
      options,
    );
    assert.deepEqual(afterEmptyMarker, before);

    writeFileSync(join(marker, String(process.pid)), "", { mode: 0o600 });
    await assert.rejects(
      () => acceptance.exactOwnedTreeBinding(cacheRoot, "fixture cache", options),
      /became live/u,
    );
    unlinkSync(join(marker, String(process.pid)));

    const outside = join(root, "outside-marker");
    writeFileSync(outside, "", { mode: 0o600 });
    linkSync(outside, join(marker, "999999"));
    await assert.rejects(
      () => acceptance.exactOwnedTreeBinding(cacheRoot, "fixture cache", options),
      AcceptanceError,
    );
    unlinkSync(join(marker, "999999"));
    writeFileSync(join(marker, "999999"), "unexpected", { mode: 0o600 });
    await assert.rejects(
      () => acceptance.exactOwnedTreeBinding(cacheRoot, "fixture cache", options),
      /nonempty/u,
    );
  }));

test("Codex baseline binding changes with the owned trusted hash but excludes unrelated config", () => {
  const section = (hash) =>
    `[hooks.state."opensocrates@opensocrates:hooks/hooks.json:session_start:0:0"]\n` +
    `trusted_hash = "${hash}"\n`;
  const first = acceptance.codexTrustBindingForContents(
    `model = "first-unrelated"\n${section("sha256:first")}`,
  );
  const unrelatedChanged = acceptance.codexTrustBindingForContents(
    `model = "second-unrelated"\nunrelated = true\n${section("sha256:first")}`,
  );
  const trustChanged = acceptance.codexTrustBindingForContents(
    `model = "first-unrelated"\n${section("sha256:second")}`,
  );
  assert.deepEqual(first.public, {
    present: true,
    exactSectionCount: 1,
    events: ["session_start"],
  });
  assert.equal(
    first.binding.removedSyntaxSha256,
    unrelatedChanged.binding.removedSyntaxSha256,
  );
  assert.notEqual(
    first.binding.removedSyntaxSha256,
    trustChanged.binding.removedSyntaxSha256,
  );
});

test("candidate and final managed-root verification rejects outer drift", () =>
  withFixture(async (root) => {
    const fixture = writeClaudeManagedRootFixture(root);
    await acceptance.verifyManagedRootExact(
      "claude",
      fixture.managedRoot,
      fixture.pluginRoot,
      { category: "post-install" },
    );

    const extra = join(fixture.managedRoot, "undeclared.txt");
    writeFileSync(extra, "outer drift\n", { mode: 0o600 });
    await assert.rejects(
      () => acceptance.verifyManagedRootExact(
        "claude",
        fixture.managedRoot,
        fixture.pluginRoot,
        { category: "post-install" },
      ),
      AcceptanceError,
    );
    rmSync(extra);

    const marketplacePath = join(fixture.managedRoot, ".claude-plugin", "marketplace.json");
    writeFileSync(
      marketplacePath,
      `${JSON.stringify({ ...fixture.marketplace, unreviewed: true })}\n`,
      { mode: 0o600 },
    );
    await assert.rejects(
      () => acceptance.verifyManagedRootExact(
        "claude",
        fixture.managedRoot,
        fixture.pluginRoot,
        { category: "post-install" },
      ),
      AcceptanceError,
    );
  }));

test("installed topology rejects exact host transaction residue", () =>
  withFixture((root) => {
    const targets = emptyResidueTargets(root);
    const transactionParent = targets.allHosts.claude.transactionParent;
    mkdirSync(transactionParent, { recursive: true, mode: 0o700 });
    mkdirSync(
      join(transactionParent, ".opensocrates.staging-11111111-1111-4111-8111-111111111111"),
      { mode: 0o700 },
    );
    assert.throws(
      () => acceptance.assertNoKnownTransactionResidue(targets, "post-install"),
      AcceptanceError,
    );
  }));

test("installed topology rejects every OpenCode bridge transaction residue", () =>
  withFixture((root) => {
    const targets = emptyResidueTargets(root);
    const bridgeParent = targets.allHosts.opencode.bridgeParent;
    mkdirSync(bridgeParent, { recursive: true, mode: 0o700 });
    const uuid = "11111111-1111-4111-8111-111111111111";
    for (const leaf of [
      `.opensocrates.js.staging-${uuid}`,
      `.opensocrates.js.backup-${uuid}`,
      `.opensocrates.js.removed-${uuid}`,
      `.opensocrates-managed.json.staging-${uuid}`,
      `.opensocrates-managed.json.backup-${uuid}`,
      `.opensocrates-managed.json.removed-${uuid}`,
    ]) {
      const residue = join(bridgeParent, leaf);
      writeFileSync(residue, "bridge transaction residue\n", { mode: 0o600 });
      assert.throws(
        () => acceptance.assertNoKnownTransactionResidue(targets, "post-install"),
        AcceptanceError,
      );
      unlinkSync(residue);
    }
  }));

test("baseline cache marketplace preflight rejects an unknown exact child", () =>
  withFixture((root) => {
    const targets = emptyResidueTargets(root);
    const paths = targets.allHosts.claude;
    mkdirSync(paths.cacheMarketplaceRoot, { recursive: true, mode: 0o700 });
    assert.doesNotThrow(() =>
      acceptance.verifyCacheMarketplaceShape("claude", paths, "baseline"));
    mkdirSync(paths.cacheRoot, { mode: 0o700 });
    assert.doesNotThrow(() =>
      acceptance.verifyCacheMarketplaceShape("claude", paths, "baseline"));
    mkdirSync(join(paths.cacheMarketplaceRoot, "unknown-child"), { mode: 0o700 });
    assert.throws(
      () => acceptance.verifyCacheMarketplaceShape("claude", paths, "baseline"),
      AcceptanceError,
    );
  }));

test("exact LaunchAgent and trust transaction leaves block baseline and zero residue", () =>
  withFixture((root) => {
    const targets = emptyResidueTargets(root);
    const launchAgents = dirname(targets.state.launchAgent);
    mkdirSync(launchAgents, { recursive: true, mode: 0o700 });
    writeFileSync(
      join(
        launchAgents,
        ".com.opensocrates.auto-update.plist.11111111-1111-4111-8111-111111111111.tmp",
      ),
      "temporary\n",
      { mode: 0o600 },
    );
    mkdirSync(targets.codex.hostHome, { recursive: true, mode: 0o700 });
    writeFileSync(
      join(targets.codex.hostHome, ".config.toml.opensocrates-trust-reset-fixture.rollback"),
      "owned rollback\n",
      { mode: 0o600 },
    );
    writeFileSync(join(targets.codex.hostHome, "unrelated-private-config"), "not opened\n", {
      mode: 0o600,
    });
    assert.equal(acceptance.inspectLaunchAgentTemporaryResidue(targets.state), 1);
    writeFileSync(
      join(
        launchAgents,
        "Xcom.opensocrates.auto-updateYplistQ11111111-1111-4111-8111-111111111111Ztmp",
      ),
      "unrelated lookalike\n",
      { mode: 0o600 },
    );
    assert.equal(acceptance.inspectLaunchAgentTemporaryResidue(targets.state), 1);
    assert.equal(acceptance.inspectTrustTransactionResidue(targets.codex.hostHome), 1);
    const snapshot = acceptance.exactResidueSnapshot(
      targets,
      null,
      { loaded: false },
      { present: false, exactSectionCount: 0, events: [] },
    );
    assert.equal(snapshot.launchAgentTemporaryCount, 1);
    assert.equal(snapshot.trustTransactionResidueCount, 1);
    assert.equal(residueIsEmpty(snapshot), false);
  }));

test("Grok transaction residue uses the exceptional transaction parent", () =>
  withFixture((root) => {
    const grokHome = join(root, ".grok");
    const scannedParent = join(grokHome, "plugins");
    mkdirSync(scannedParent, { recursive: true });
    writeFileSync(join(grokHome, ".opensocrates.backup-fixture"), "owned\n");
    assert.equal(
      inspectKnownTransactionResidue("grok", {
        parent: scannedParent,
        transactionParent: grokHome,
      }),
      1,
    );
  }));

test("state residue inventories known temporary, tombstone, and lock leaves", () =>
  withFixture((root) => {
    const state = join(root, ".opensocrates");
    mkdirSync(state, { mode: 0o700 });
    const uuid = "11111111-1111-4111-8111-111111111111";
    writeFileSync(join(state, `.desired-state.json.${uuid}.tmp`), "temporary\n");
    writeFileSync(join(state, `.purge-finalize-${uuid}-desired-state.json`), "tombstone\n");
    writeFileSync(join(state, "lifecycle.lock"), "lock\n");
    const result = inspectStateResidue({ state: { directory: state } });
    assert.equal(result.temporaryCount, 1);
    assert.equal(result.purgeTombstoneCount, 1);
    assert.equal(result.lifecycleLockPresent, true);
    assert.equal(result.unknownLeafCount, 0);
  }));

test("state preflight rejects unsafe auto-update receipts before any lifecycle command", () =>
  withFixture((root) => {
    const stateDirectory = join(root, "state");
    const receiptPath = join(stateDirectory, "auto-update-receipt.json");
    const outsidePath = join(root, "outside-receipt.json");
    mkdirSync(stateDirectory, { mode: 0o700 });
    const targets = {
      state: {
        directory: stateDirectory,
        desiredState: join(stateDirectory, "desired-state.json"),
        receipt: receiptPath,
        launchAgent: join(root, "LaunchAgents", "com.opensocrates.auto-update.plist"),
      },
    };
    const validReceipt = `${JSON.stringify({
      schema: "opensocrates.auto-update-receipt/1.0.0",
      version: "1.2.1",
      checkedAt: "2026-08-15T00:00:00.000Z",
      hosts: [{ host: "claude", result: "updated" }],
      result: "updated",
      errorCategory: null,
    })}\n`;
    let lifecycleCommandCount = 0;

    writeFileSync(receiptPath, validReceipt, { mode: 0o600 });
    assert.equal(acceptance.inspectStateDirectory(targets).ownership, "verified");
    rmSync(receiptPath);

    const cases = [
      () => {
        writeFileSync(outsidePath, validReceipt, { mode: 0o600 });
        symlinkSync(outsidePath, receiptPath);
      },
      () => {
        writeFileSync(outsidePath, validReceipt, { mode: 0o600 });
        linkSync(outsidePath, receiptPath);
      },
      () => {
        const made = spawnSync("/usr/bin/mkfifo", [receiptPath], { encoding: "utf8" });
        assert.equal(made.status, 0, made.stderr);
      },
      () => writeFileSync(receiptPath, validReceipt, { mode: 0o644 }),
    ];
    for (const createUnsafeReceipt of cases) {
      rmSync(receiptPath, { force: true });
      rmSync(outsidePath, { force: true });
      createUnsafeReceipt();
      assert.throws(() => acceptance.inspectStateDirectory(targets), AcceptanceError);
      assert.equal(lifecycleCommandCount, 0);
    }
  }));

test("zero residue fails closed for every audited exact residue category", () => {
  const mutations = [
    (value) => { value.hosts.claude.unsupportedLegacyRegistrationPresent = true; },
    (value) => { value.hosts.claude.cacheMarketplacePresent = true; },
    (value) => { value.hosts.claude.transactionResidueCount = 1; },
    (value) => { value.stateResidue.present = true; },
    (value) => { value.launchAgentPlistPresent = true; },
    (value) => { value.launchAgentTemporaryCount = 1; },
    (value) => { value.launchAgentJobLoaded = true; },
    (value) => { value.codexTrustSectionCount = 1; },
    (value) => { value.trustTransactionResidueCount = 1; },
    (value) => { value.openCodeBridgeResidueCount = 1; },
  ];
  assert.equal(residueIsEmpty(emptyResidueSnapshot()), true);
  for (const mutate of mutations) {
    const snapshot = structuredClone(emptyResidueSnapshot());
    mutate(snapshot);
    assert.equal(residueIsEmpty(snapshot), false);
  }
});

test("zero residue requires the exact supported-host and field schema", () => {
  const exact = emptyResidueSnapshot();
  assert.equal(residueIsEmpty(exact), true);
  assert.equal(residueIsEmpty({ ...exact, unreviewedTopLevel: false }), false);
  assert.equal(residueIsEmpty({ ...exact, hosts: {} }), false);

  const extraHost = structuredClone(exact);
  extraHost.hosts.unknown = structuredClone(extraHost.hosts.claude);
  assert.equal(residueIsEmpty(extraHost), false);

  for (const host of SUPPORTED_HOSTS) {
    const missingHost = structuredClone(exact);
    delete missingHost.hosts[host];
    assert.equal(residueIsEmpty(missingHost), false);
    for (const field of Object.keys(exact.hosts[host])) {
      const missingField = structuredClone(exact);
      delete missingField.hosts[host][field];
      assert.equal(residueIsEmpty(missingField), false, `${host}.${field}`);
    }
  }
  for (const field of Object.keys(exact.stateResidue)) {
    const missingField = structuredClone(exact);
    delete missingField.stateResidue[field];
    assert.equal(residueIsEmpty(missingField), false, `stateResidue.${field}`);
  }
  for (const field of [
    "launchAgentPlistPresent",
    "launchAgentTemporaryCount",
    "launchAgentJobLoaded",
    "codexTrustSectionCount",
    "trustTransactionResidueCount",
    "openCodeBridgeResidueCount",
  ]) {
    const missingField = structuredClone(exact);
    delete missingField[field];
    assert.equal(residueIsEmpty(missingField), false, field);
  }

  const contradictoryStateMutations = [
    ["present", true],
    ["empty", false],
    ["desiredStatePresent", true],
    ["receiptPresent", true],
    ["lifecycleLockPresent", true],
    ["temporaryCount", 1],
    ["purgeTombstoneCount", 1],
    ["unknownLeafCount", 1],
  ];
  for (const [field, value] of contradictoryStateMutations) {
    const contradictory = structuredClone(exact);
    contradictory.stateResidue[field] = value;
    assert.equal(residueIsEmpty(contradictory), false, `contradictory state ${field}`);
  }
});

test("the real residue producer classifies a clean all-host topology as empty", () =>
  withFixture((root) => {
    const registrations = Object.fromEntries(
      ["claude", "codex"].map((host) => [
        host,
        {
          marketplaceCount: 0,
          pluginCount: 0,
          version: null,
          unsupportedLegacyConflictCount: 0,
          rootMatchesExpected: true,
        },
      ]),
    );
    const snapshot = acceptance.exactResidueSnapshot(
      emptyResidueTargets(root),
      registrations,
      { loaded: false },
      { present: false, exactSectionCount: 0, events: [] },
    );
    const summary = acceptance.publicResidueSummary(snapshot);
    assert.equal(summary.empty, true);
    assert.equal(residueIsEmpty(snapshot), true);
    for (const host of SUPPORTED_HOSTS.filter(
      (candidate) => !new Set(["claude", "codex"]).has(candidate),
    )) {
      assert.equal(snapshot.hosts[host].registrationPresent, false);
      assert.equal(snapshot.hosts[host].unsupportedLegacyRegistrationPresent, false);
    }
  }));

test("filesystem-only recovery residue preserves unknown target registrations", () =>
  withFixture((root) => {
    const targets = emptyResidueTargets(root);
    mkdirSync(targets.allHosts.claude.root, { recursive: true, mode: 0o700 });
    const snapshot = acceptance.exactResidueSnapshot(
      targets,
      null,
      { loaded: false },
      { present: false, exactSectionCount: 0, events: [] },
    );
    const summary = acceptance.publicResidueSummary(snapshot);
    assert.equal(summary.empty, false);
    for (const host of ["claude", "codex"]) {
      assert.equal(summary.hosts[host].registrationPresent, null);
      assert.equal(summary.hosts[host].unsupportedLegacyRegistrationPresent, null);
    }
    for (const host of SUPPORTED_HOSTS.filter(
      (candidate) => !new Set(["claude", "codex"]).has(candidate),
    )) {
      assert.equal(summary.hosts[host].registrationPresent, false);
      assert.equal(summary.hosts[host].unsupportedLegacyRegistrationPresent, false);
    }
  }));

test("fully clean recovery inventories unknown registrations before recording purged state", () =>
  withFixture(async (root) => {
    const calls = [];
    const recorder = {
      run: (label) => {
        calls.push(label);
        if (label === "Inspect OpenSocrates launchd job state") {
          return {
            status: 1,
            error: null,
            stdout: "",
            stderr: "Could not find service",
          };
        }
        if (label === "List Claude plugin marketplaces") return { stdout: "[]" };
        if (label === "List Claude installed plugins") return { stdout: "[]" };
        if (label === "List Codex plugin marketplaces") {
          return { stdout: JSON.stringify({ marketplaces: [] }) };
        }
        if (label === "List Codex OpenSocrates plugin state") {
          return { stdout: JSON.stringify({ installed: [] }) };
        }
        throw new Error(`unexpected fixture command: ${label}`);
      },
    };
    const outcome = await acceptance.inspectRecoveryState(
      recorder,
      emptyResidueTargets(root),
      {},
      { trustSnapshot: { present: false, exactSectionCount: 0, events: [] } },
    );
    assert.equal(outcome.classification, "purged_after_failure");
    assert.equal(outcome.actualStateRecorded, true);
    assert.equal(outcome.registrationInspection, "passed_without_installed_payload");
    assert.equal(outcome.residue.empty, true);
    for (const host of ["claude", "codex"]) {
      assert.equal(outcome.residue.hosts[host].registrationPresent, false);
      assert.equal(outcome.residue.hosts[host].unsupportedLegacyRegistrationPresent, false);
    }
    assert.deepEqual(calls, [
      "Inspect OpenSocrates launchd job state",
      "List Claude plugin marketplaces",
      "List Claude installed plugins",
      "List Codex plugin marketplaces",
      "List Codex OpenSocrates plugin state",
    ]);
  }));

test("filesystem-clean recovery records a remaining canonical registration as partial", () =>
  withFixture(async (root) => {
    const targets = emptyResidueTargets(root);
    const recorder = {
      run: (label) => {
        if (label === "Inspect OpenSocrates launchd job state") {
          return {
            status: 1,
            error: null,
            stdout: "",
            stderr: "Could not find service",
          };
        }
        if (label === "List Claude plugin marketplaces") {
          return {
            stdout: JSON.stringify([
              {
                name: "opensocrates",
                source: "directory",
                path: targets.claude.root,
                installLocation: targets.claude.root,
              },
            ]),
          };
        }
        if (label === "List Claude installed plugins") return { stdout: "[]" };
        if (label === "List Codex plugin marketplaces") {
          return { stdout: JSON.stringify({ marketplaces: [] }) };
        }
        if (label === "List Codex OpenSocrates plugin state") {
          return { stdout: JSON.stringify({ installed: [] }) };
        }
        throw new Error(`unexpected fixture command: ${label}`);
      },
    };
    const outcome = await acceptance.inspectRecoveryState(
      recorder,
      targets,
      {},
      { trustSnapshot: { present: false, exactSectionCount: 0, events: [] } },
    );
    assert.equal(outcome.classification, "partial_or_unverified");
    assert.equal(outcome.actualStateRecorded, true);
    assert.equal(outcome.residue.hosts.claude.registrationPresent, true);
    assert.equal(outcome.residue.hosts.codex.registrationPresent, false);
    assert.equal(outcome.residue.empty, false);
  }));

test("host-close retry permits only confirmed live-marker resolution with fixed bindings", () => {
  const previous = emptyResidueSnapshot();
  previous.hosts.claude.cachePresent = true;
  previous.hosts.claude.liveInUse = true;
  const current = structuredClone(previous);
  current.hosts.claude.liveInUse = false;
  const bindings = {
    sourceCommit: "a".repeat(40),
    packageSha256: "b".repeat(64),
    artifactDigest: `sha256:${"c".repeat(64)}`,
    desiredStateSha256: "d".repeat(64),
  };
  assert.doesNotThrow(() =>
    acceptance.assertHostCloseRetrySnapshot(
      previous,
      current,
      ["claude"],
      bindings,
      bindings,
    ));
  for (const mutate of [
    (value) => { value.hosts.claude.registrationPresent = true; },
    (value) => { value.hosts.claude.managedRootPresent = true; },
    (value) => { value.codexTrustSectionCount = 1; },
    (value) => { value.stateResidue.desiredStatePresent = true; },
  ]) {
    const drifted = structuredClone(current);
    mutate(drifted);
    assert.throws(
      () => acceptance.assertHostCloseRetrySnapshot(
        previous,
        drifted,
        ["claude"],
        bindings,
        bindings,
      ),
      AcceptanceError,
    );
  }
  assert.throws(
    () => acceptance.assertHostCloseRetrySnapshot(
      previous,
      current,
      ["claude"],
      bindings,
      { ...bindings, desiredStateSha256: "e".repeat(64) },
    ),
    AcceptanceError,
  );
});

test("host-close pause admits only a live target cache plus the exact deferred state", () => {
  const pure = emptyResidueSnapshot();
  const desired = deactivatedDesiredStateFixture();
  Object.assign(pure.hosts.claude, {
    cachePresent: true,
    cacheMarketplacePresent: true,
    liveInUse: true,
  });
  Object.assign(pure.stateResidue, {
    present: true,
    empty: false,
    desiredStatePresent: true,
  });
  assert.doesNotThrow(() =>
    acceptance.assertOnlyRetryableHostCloseResidue(pure, ["claude"], desired));
  for (const mutate of [
    (value) => { value.hosts.codex.registrationPresent = true; },
    (value) => { value.hosts.codex.managedRootPresent = true; },
    (value) => { value.hosts.codex.cacheMarketplacePresent = true; },
    (value) => { value.hosts.claude.pluginDataPresent = true; },
    (value) => { value.hosts.claude.transactionResidueCount = 1; },
    (value) => { value.codexTrustSectionCount = 1; },
    (value) => { value.stateResidue.receiptPresent = true; },
    (value) => { value.launchAgentJobLoaded = true; },
  ]) {
    const mixed = structuredClone(pure);
    mutate(mixed);
    assert.throws(
      () => acceptance.assertOnlyRetryableHostCloseResidue(mixed, ["claude"], desired),
      AcceptanceError,
    );
  }
  const notLive = structuredClone(pure);
  notLive.hosts.claude.liveInUse = false;
  assert.throws(
    () => acceptance.assertOnlyRetryableHostCloseResidue(notLive, ["claude"], desired),
    AcceptanceError,
  );
  const staleDesired = structuredClone(desired);
  staleDesired.installedHosts = ["claude", "codex"];
  staleDesired.activeVersion = "1.2.1";
  assert.throws(
    () => acceptance.assertOnlyRetryableHostCloseResidue(pure, ["claude"], staleDesired),
    AcceptanceError,
  );
});

test("host-close admission parses the exact deactivated desired-state file", () =>
  withFixture((root) => {
    const targets = emptyResidueTargets(root);
    mkdirSync(targets.state.directory, { mode: 0o700 });
    const writeDesired = (value) =>
      writeFileSync(targets.state.desiredState, `${JSON.stringify(value)}\n`, { mode: 0o600 });
    const exact = deactivatedDesiredStateFixture();
    writeDesired(exact);
    assert.deepEqual(acceptance.inspectDeactivatedDesiredState(targets), exact);
    for (const mutate of [
      (value) => { value.schema = "unsupported"; },
      (value) => { value.installedHosts = ["claude", "codex"]; },
      (value) => { value.activeVersion = "1.2.1"; },
      (value) => { value.autoUpdate.enabled = true; },
      (value) => { value.autoUpdate.hosts = ["claude"]; },
      (value) => { value.autoUpdate.nextCheckAt = "2026-08-15T00:00:00.000Z"; },
    ]) {
      const invalid = structuredClone(exact);
      mutate(invalid);
      writeDesired(invalid);
      assert.throws(
        () => acceptance.inspectDeactivatedDesiredState(targets),
        AcceptanceError,
      );
    }
  }));

test("durable host-close admission survives retry write-ahead resume without last-state loss", () =>
  withFixture(async (root) => {
    const initial = emptyResidueSnapshot();
    Object.assign(initial.hosts.claude, {
      cachePresent: true,
      cacheMarketplacePresent: true,
      liveInUse: true,
    });
    Object.assign(initial.stateResidue, {
      present: true,
      empty: false,
      desiredStatePresent: true,
    });
    const resolved = structuredClone(initial);
    resolved.hosts.claude.liveInUse = false;
    const bindings = {
      sourceCommit: "a".repeat(40),
      packageSha256: "b".repeat(64),
      artifactDigest: `sha256:${"c".repeat(64)}`,
      desiredStateSha256: "d".repeat(64),
    };
    const admission = {
      initialSnapshot: initial,
      confirmedHosts: ["claude"],
      bindings,
      deactivatedDesiredState: deactivatedDesiredStateFixture(),
      resolvedSnapshot: resolved,
    };
    const report = makeReport();
    report.source.commit = bindings.sourceCommit;
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const checkpointValue = {
      phase: "purge-retry-in-progress",
      sourceCommit: report.source.commit,
      recovery: {
        hostCloseRetriesUsed: 1,
        reinstallRetriesUsed: 0,
        hostCloseRetryAdmission: structuredClone(admission),
      },
      lastObservedState: {
        classification: "confirmed_live_marker_resolved_retry_in_progress",
        residue: acceptance.publicResidueSummary(resolved),
      },
    };
    assert.deepEqual(
      acceptance.requireHostCloseRetryAdmission(checkpointValue, { resolved: true }),
      admission,
    );
    let purgeCalls = 0;
    const outcome = await acceptance.runMutation(
      {}, report, {}, {}, privateDirectory, checkpointValue,
      {
        lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
        runtime: {
          verifyCandidateUnchanged: async () => {},
          inspectRecoveryState: async () => {
            throw new Error("retry admission should not be replaced by recovery inspection");
          },
          assertFinalInstalled: async () => {
            throw new Error("final should not run");
          },
          inspectFailureState: async () => ({
            classification: "unknown_unverified",
            actualStateRecorded: false,
            previousStateRestorationClaimed: false,
          }),
          purgeCandidate: async (_recorder, _report, _targets, _candidate, _directory, checkpoint) => {
            purgeCalls += 1;
            assert.deepEqual(
              acceptance.requireHostCloseRetryAdmission(checkpoint, { resolved: true }),
              admission,
            );
            return { status: "complete" };
          },
          assertClean: async () => {
            throw new AcceptanceError("residue", "fixture stop after retry dispatch");
          },
          installCandidate: async () => {
            throw new Error("install should not run");
          },
        },
      },
    );
    assert.equal(outcome.status, "failed");
    assert.equal(purgeCalls, 1);
    assert.equal(checkpointValue.recovery.hostCloseRetriesUsed, 1);
    assert.deepEqual(checkpointValue.recovery.hostCloseRetryAdmission, admission);
  }));

test("purge failure cannot classify clean when registration inventory is unavailable", () => {
  const snapshot = emptyResidueSnapshot();
  assert.deepEqual(
    acceptance.classifyPurgeFailureSnapshot(null, snapshot),
    {
      classification: "unknown_unverified",
      actualStateRecorded: false,
      registrationInspection: "failed",
      previousStateRestorationClaimed: false,
    },
  );
  const registrations = Object.fromEntries(
    ["claude", "codex"].map((host) => [
      host,
      {
        marketplaceCount: 0,
        pluginCount: 0,
        version: null,
        unsupportedLegacyConflictCount: 0,
        rootMatchesExpected: true,
      },
    ]),
  );
  assert.equal(
    acceptance.classifyPurgeFailureSnapshot(registrations, snapshot).classification,
    "purged_after_failure",
  );
});

test("specific purge failure classification cannot be overwritten by generic inspection", () => {
  for (const classification of [
    "partial_purge_after_bounded_retry",
    "installer_defect_residue_after_purge",
  ]) {
    const specific = {
      classification,
      residue: { exact: true },
      previousStateRestorationClaimed: false,
    };
    const selected = acceptance.selectFailureState(
      { phase: "purge-failed", lastObservedState: specific },
      {
        classification: "partial_or_unverified",
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      },
    );
    assert.equal(selected.classification, classification);
    assert.equal(selected.actualStateRecorded, true);
  }
});

test("recovery plans preserve exact inputs and bound retries", () => {
  assert.deepEqual(recoveryPlanForPhase(checkpoint("ready-to-purge")).stages, [
    "purge",
    "clean-assertion",
    "reinstall",
    "post-install",
  ]);
  assert.throws(
    () => recoveryPlanForPhase(checkpoint("awaiting-host-close")),
    AcceptanceError,
  );
  assert.equal(
    recoveryPlanForPhase(
      checkpoint("awaiting-host-close"),
      null,
      { hostAppsClosedConfirmed: true },
    ).hostCloseRetry,
    true,
  );
  assert.deepEqual(recoveryPlanForPhase(checkpoint("purged")).stages, [
    "clean-assertion",
    "reinstall",
    "post-install",
  ]);
  assert.throws(
    () =>
      recoveryPlanForPhase(
        checkpoint("awaiting-host-close", { hostCloseRetriesUsed: 1 }),
        null,
        { hostAppsClosedConfirmed: true },
      ),
    AcceptanceError,
  );
  assert.throws(
    () => recoveryPlanForPhase(checkpoint("reinstall-failed"), {
      classification: "candidate_partial_installed",
      missingHosts: ["codex"],
    }),
    AcceptanceError,
  );
  assert.deepEqual(
    recoveryPlanForPhase(checkpoint("reinstall-failed"), {
      classification: "purged_after_failure",
      missingHosts: ["claude", "codex"],
    }).stages,
    ["clean-assertion", "reinstall", "post-install"],
  );
  assert.throws(
    () =>
      recoveryPlanForPhase(checkpoint("post-install-failed"), {
        classification: "candidate_installed_unverified",
      }),
    AcceptanceError,
  );
  assert.deepEqual(
    recoveryPlanForPhase(checkpoint("post-install-checks"), {
      classification: "candidate_installed_unverified",
    }).stages,
    ["post-install"],
  );
  assert.deepEqual(
    recoveryPlanForPhase(checkpoint("purging"), {
      classification: "installed_baseline_unchanged",
    }).stages,
    ["purge", "clean-assertion", "reinstall", "post-install"],
  );
  assert.deepEqual(
    recoveryPlanForPhase(checkpoint("purging"), {
      classification: "purged_after_failure",
    }).stages,
    ["clean-assertion", "reinstall", "post-install"],
  );
  assert.deepEqual(
    recoveryPlanForPhase(checkpoint("purge-retry-in-progress"), {
      classification: "purged_after_failure",
    }).stages,
    ["clean-assertion", "reinstall", "post-install"],
  );
  assert.throws(
    () => recoveryPlanForPhase(checkpoint("purge-retry-in-progress"), {
      classification: "partial_or_unverified",
    }),
    AcceptanceError,
  );
  assert.throws(
    () => recoveryPlanForPhase(checkpoint("finalizing"), {
      classification: "candidate_installed_unverified",
    }),
    AcceptanceError,
  );
  assert.deepEqual(
    recoveryPlanForPhase(checkpoint("final-verified"), {
      classification: "candidate_installed_verified",
    }),
    {
      stages: [],
      finalizeOnly: true,
      hostCloseRetry: false,
      hostsToInstall: [],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    },
  );
});

test("reinstall retry consumption is durably bound before dispatch and survives that crash boundary", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    const checkpointValue = {
      phase: "reinstall-failed",
      sourceCommit: report.source.commit,
      ci: { artifact: { digest: `sha256:${"c".repeat(64)}` } },
      packageSha256: "b".repeat(64),
      recovery: {
        hostCloseRetriesUsed: 0,
        reinstallRetriesUsed: 0,
        hostCloseRetryAdmission: null,
        reinstallRetryAdmission: null,
      },
      lastObservedState: {
        classification: "purged_after_failure",
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      },
    };
    const runtime = {
      verifyCandidateUnchanged: async () => {},
      inspectRecoveryState: async () => ({
        classification: "purged_after_failure",
        installedHosts: [],
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      }),
      assertFinalInstalled: async () => {
        throw new Error("final must not run");
      },
      inspectFailureState: async () => ({
        classification: "purged_after_failure",
        installedHosts: [],
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      }),
      purgeCandidate: async () => {
        throw new Error("purge must not run");
      },
      assertClean: async () => {},
      installCandidate: async () => {
        throw new AcceptanceError("reinstall", "fixture stop after retry dispatch");
      },
    };
    await assert.rejects(
      () =>
        acceptance.runMutation(
          {}, report, {}, { packageSha256: checkpointValue.packageSha256 }, privateDirectory,
          checkpointValue,
          {
            lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
            runtime,
            testHooks: {
              afterReinstallRetryWriteAhead: () => {
                throw new Error("fixture retry write-ahead crash");
              },
            },
          },
        ),
      /fixture retry write-ahead crash/u,
    );
    assert.equal(checkpointValue.phase, "reinstall-retry-in-progress");
    assert.equal(checkpointValue.recovery.reinstallRetriesUsed, 1);
    assert.deepEqual(checkpointValue.recovery.reinstallRetryAdmission, {
      operationKey: "install-retry",
      attempt: 2,
      sourceCommit: checkpointValue.sourceCommit,
      packageSha256: checkpointValue.packageSha256,
      artifactDigest: checkpointValue.ci.artifact.digest,
    });

    let cleanCalls = 0;
    let installCalls = 0;
    runtime.assertClean = async () => { cleanCalls += 1; };
    runtime.installCandidate = async () => {
      installCalls += 1;
      throw new AcceptanceError("reinstall", "fixture stop after retry dispatch");
    };
    const outcome = await acceptance.runMutation(
      {}, report, {}, { packageSha256: checkpointValue.packageSha256 }, privateDirectory,
      checkpointValue,
      {
        lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
        runtime,
      },
    );
    assert.equal(outcome.status, "failed");
    assert.equal(cleanCalls, 1);
    assert.equal(installCalls, 1);
    assert.equal(checkpointValue.recovery.reinstallRetriesUsed, 1);
  }));

test("public mutation telemetry is reconstructed from lifecycle claims and durable retry counters", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const worker = join(root, "worker.mjs");
    writeFileSync(worker, "process.exit(0);\n", { mode: 0o600 });
    for (const operationKey of [
      "purge-initial",
      "purge-host-close-retry",
      "install-initial",
      "install-retry",
    ]) {
      const completed = await acceptance.executeLifecycleOperation({
        privateDirectory,
        operationKey,
        label: `Synthetic ${operationKey}`,
        executable: realpathSync(process.execPath),
        args: [worker],
        cwd: root,
        env: {
          HOME: root,
          PATH: dirname(realpathSync(process.execPath)),
          TMPDIR: root,
          LANG: "C",
          LC_ALL: "C",
        },
        timeout: 20_000,
        candidateIdentitySha256: "4".repeat(64),
      });
      assert.equal(completed.status, 0);
    }
    const report = makeReport();
    const telemetry = acceptance.reconcileMutationTelemetry(
      report,
      privateDirectory,
      {
        recovery: {
          hostCloseRetriesUsed: 1,
          reinstallRetriesUsed: 1,
        },
      },
    );
    assert.deepEqual(telemetry, {
      started: true,
      purgeCommandAttempts: 2,
      trustResetAttempts: 2,
      reinstallAttempts: 2,
      hostCloseRetriesUsed: 1,
      reinstallAttempted: true,
    });
    assert.deepEqual(
      Object.fromEntries(Object.keys(telemetry).map((key) => [key, report.mutation[key]])),
      telemetry,
    );
  }));

test("phase-aware resume never launches a host process before the one-shot Codex review", () => {
  const sensitivePhases = [
    "reinstalling",
    "reinstall-failed",
    "post-install-checks",
    "post-install-failed",
  ];
  for (const phase of sensitivePhases) {
    const calls = [];
    const result = acceptance.executePhaseAwareResumePreflight(phase, {
      verifyEnvironment: () => calls.push("environment"),
      verifyHosts: () => calls.push("hosts"),
      verifySource: () => calls.push("source"),
    });
    assert.equal(result, "source-only");
    assert.deepEqual(calls, ["environment", "source"]);
  }
  for (const phase of ["finalizing", "final-verified"]) {
    const calls = [];
    const action = () =>
      acceptance.executePhaseAwareResumePreflight(phase, {
        verifyEnvironment: () => calls.push("environment"),
        verifyHosts: () => calls.push("hosts"),
        verifySource: () => calls.push("source"),
      });
    if (phase === "finalizing") assert.throws(action, AcceptanceError);
    else assert.equal(action(), "finalize-only");
    assert.deepEqual(calls, []);
  }
});

test("actual final verification makes the hook inventory its first Codex-facing call", async () => {
  const calls = [];
  const hooks = [
    "postToolUse",
    "preCompact",
    "preToolUse",
    "sessionEnd",
    "sessionStart",
    "stop",
    "userPromptSubmit",
  ].map((eventName) => ({
    eventName,
    namespace: "opensocrates@opensocrates",
    trustStatus: "untrusted",
    timeoutSec: eventName === "sessionStart" ? 2 : null,
  }));
  const recorder = {
    run: (label) => {
      calls.push(label);
      if (calls.length === 1) {
        return {
          stdout: JSON.stringify({
            schema: "opensocrates.codex-hook-inventory/1.0.0",
            errorCount: 0,
            warningCount: 0,
            hooks,
          }),
        };
      }
      throw new Error("stop after the first-review probe");
    },
  };
  await assert.rejects(
    () => acceptance.assertFinalInstalled(
      recorder,
      makeReport(),
      {},
      {},
      "/private/not-used-after-first-probe",
    ),
    /stop after the first-review probe/u,
  );
  assert.equal(calls[0], "Inspect Codex OpenSocrates hook trust categorically");
});

test("first-approval inventory fails closed for count, duplicate, trust, namespace, and timeout drift", () => {
  const events = [
    "postToolUse",
    "preCompact",
    "preToolUse",
    "sessionEnd",
    "sessionStart",
    "stop",
    "userPromptSubmit",
  ];
  const baseHooks = events.map((eventName) => ({
    eventName,
    namespace: "opensocrates@opensocrates",
    timeoutSec: eventName === "sessionStart" ? 2 : 10,
    trustStatus: "untrusted",
  }));
  const inventory = (hooks) => acceptance.codexHookInventory({
    run: () => ({
      stdout: JSON.stringify({
        schema: "opensocrates.codex-hook-inventory/1.0.0",
        errorCount: 0,
        warningCount: 0,
        hooks,
      }),
    }),
  });
  for (const hooks of [
    baseHooks.slice(0, 6),
    [...baseHooks, { ...baseHooks[0] }],
    [...baseHooks.slice(0, 6), { ...baseHooks[0] }],
    baseHooks.map((hook) =>
      hook.eventName === "sessionStart" ? { ...hook, timeoutSec: 3 } : hook),
    baseHooks.map((hook, index) =>
      index === 0 ? { ...hook, namespace: "other@other" } : hook),
  ]) {
    assert.throws(() => inventory(hooks), AcceptanceError);
  }
  const trusted = inventory(
    baseHooks.map((hook) => ({ ...hook, trustStatus: "trusted" })),
  );
  assert.throws(
    () => acceptance.assertExactUntrustedHooks(trusted),
    AcceptanceError,
  );
  assert.doesNotThrow(() =>
    acceptance.assertExactUntrustedHooks(inventory(baseHooks)));
});

test("the real Codex hook inventory survives the closed public baseline schema", () =>
  withFixture((root) => {
    const events = [
      "postToolUse",
      "preCompact",
      "preToolUse",
      "sessionEnd",
      "sessionStart",
      "stop",
      "userPromptSubmit",
    ];
    const hooks = acceptance.codexHookInventory({
      run: () => ({
        stdout: JSON.stringify({
          schema: "opensocrates.codex-hook-inventory/1.0.0",
          errorCount: 0,
          warningCount: 0,
          hooks: events.map((eventName) => ({
            eventName,
            namespace: "opensocrates@opensocrates",
            timeoutSec: eventName === "sessionStart" ? 2 : 10,
            trustStatus: "trusted",
          })),
        }),
      }),
    });
    const report = makeReport();
    report.baseline.initialState = "installed";
    report.baseline.installedHosts = ["claude", "codex"];
    report.baseline.inventory = publicBaselineInventoryFixture(hooks);

    assert.doesNotThrow(() => writeReports(root, report));
    assert.equal(
      JSON.parse(readFileSync(join(root, "result.json"), "utf8"))
        .baseline.inventory.codexHooks.namespace,
      "opensocrates@opensocrates",
    );

    const changed = structuredClone(report);
    changed.baseline.inventory.codexHooks.namespace = "other@other";
    assert.throws(
      () => writeReports(root, changed),
      /Codex hook inventory identity/u,
    );
  }));

test("installed SessionStart measurement enforces 20 cold samples, 2000ms, and exact artifact identity", () =>
  withFixture((root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const releaseManifestSha256 = "d".repeat(64);
    const processModel =
      "new_process_per_sample; first_configured_hook_before_runtime_smoke; " +
      "hermetic_generated_input_and_selector_availability_metadata";
    const value = {
      target: "darwin-arm64",
      sample_count: 20,
      configured_timeout_ms: 2000,
      pass: true,
      process_model: processModel,
      artifact_identity: `sha256:${releaseManifestSha256}`,
      latency_ms: { first: 5, p95: 10, max: 12 },
    };
    const recorder = {
      run: (_label, executable, args, options) => {
        assert.equal(executable, realpathSync(process.execPath));
        assert.equal(args[0], "tools/measure_codex_hook_timing.py");
        assert.equal(args.includes("run"), false);
        assert.equal(options.env.HOME, privateDirectory);
        assert.equal(options.env.PYTHONNOUSERSITE, "1");
        assert.equal(Object.hasOwn(options.env, "NPM_TOKEN"), false);
        const reportPath = args[args.indexOf("--report") + 1];
        assert.equal(lstatSync(reportPath).mode & 0o777, 0o600);
        writeFileSync(reportPath, `${JSON.stringify(value)}\n`, { mode: 0o644 });
        assert.equal(lstatSync(reportPath).mode & 0o777, 0o600);
        return { status: 0 };
      },
    };
    const measured = acceptance.measureInstalledSessionStart(
      recorder,
      privateDirectory,
      join(root, "plugin-root-not-opened"),
      releaseManifestSha256,
      realpathSync(process.execPath),
    );
    assert.equal(measured.sampleCount, 20);
    assert.equal(measured.configuredTimeoutMs, 2000);
    assert.equal(measured.hardTimeoutMilliseconds, 2000);
    assert.equal(measured.coldProcessPerSample, true);
    assert.equal(measured.artifactIdentity, `sha256:${releaseManifestSha256}`);
    value.configured_timeout_ms = 1999;
    unlinkSync(join(privateDirectory, "codex-session-start-timing.json"));
    assert.throws(
      () => acceptance.measureInstalledSessionStart(
        recorder,
        privateDirectory,
        join(root, "plugin-root-not-opened"),
        releaseManifestSha256,
        realpathSync(process.execPath),
      ),
      AcceptanceError,
    );
  }));

test("installed runtime public identity matches the runtime version contract", () => {
  const identity = {
    product: "opensocrates",
    productVersion: "1.2.1",
    contentRevision: 1,
    architectures: ["arm64"],
    executable: true,
  };
  assert.doesNotThrow(() =>
    acceptance.validatePublicRuntimeIdentity(identity, "fixture.runtime"),
  );
  assert.throws(
    () =>
      acceptance.validatePublicRuntimeIdentity(
        { ...identity, product: "opensocrates-runtime" },
        "fixture.runtime",
      ),
    AcceptanceError,
  );
});

test("complete produced final assertions satisfy the public result contract", () => {
  const sha = "d".repeat(64);
  const registration = {
    marketplaceCount: 1,
    pluginCount: 1,
    version: "1.2.1",
    unsupportedLegacyConflictCount: 0,
    rootMatchesExpected: true,
  };
  const runtime = {
    product: "opensocrates",
    productVersion: "1.2.1",
    contentRevision: 1,
    architectures: ["arm64"],
    executable: true,
  };
  const payload = {
    version: "1.2.1",
    declaredFileCount: 1,
    checksumInventorySha256: sha,
    releaseManifestSha256: sha,
    runtimeSha256: sha,
    ciPayloadByteIdentity: "matched",
  };
  const absentHost = {
    managedRootPresent: false,
    bridgePresent: false,
    bridgeMarkerPresent: false,
  };
  const assertions = {
    finalRegistration: {
      status: "pass",
      hosts: { claude: registration, codex: registration },
    },
    finalStatus: {
      status: "pass",
      desiredVersion: "1.2.1",
      hostsInSync: ["claude", "codex"],
      drift: false,
    },
    finalVersion: {
      status: "pass",
      desiredVersion: "1.2.1",
      runtimes: { claude: runtime, codex: runtime },
    },
    finalChecksum: {
      status: "pass",
      payloads: { claude: payload, codex: payload },
    },
    finalManagedLayout: {
      status: "pass",
      claudePublicSkills: ["opensocrates"],
      claudeCommandsPresent: false,
      codexControllerPresent: true,
    },
    finalArchitecture: {
      status: "pass",
      hardware: "arm64",
      process: "arm64",
      installed: { claude: ["arm64"], codex: ["arm64"] },
    },
    finalPermissions: {
      status: "pass",
      stateDirectoryMode: "700",
      desiredStateMode: "600",
      managedRootsOwnedByEffectiveUser: true,
      runtimesExecutable: true,
    },
    finalDesiredState: {
      status: "pass",
      schema: "opensocrates.desired-state/1.0.0",
      activeVersion: "1.2.1",
      installedHosts: ["claude", "codex"],
      autoUpdateEnabled: false,
      launchAgentPresent: false,
      launchAgentJobLoaded: false,
    },
    codexFirstApproval: {
      status: "pass",
      exactHookCount: 7,
      events: [
        "postToolUse",
        "preCompact",
        "preToolUse",
        "sessionEnd",
        "sessionStart",
        "stop",
        "userPromptSubmit",
      ],
      namespace: "opensocrates@opensocrates",
      trustStatuses: ["untrusted"],
      sessionStartTimeoutSeconds: 2,
      observedBeforeOtherPostInstallCodexLaunch: true,
      manualApprovalRequired: true,
    },
    sessionStartBudget: {
      observationStatus: "pass",
      target: "darwin-arm64",
      sampleCount: 20,
      configuredTimeoutMs: 2000,
      hardTimeoutMilliseconds: 2000,
      clock: "performance.now_monotonic",
      monotonicStartMilliseconds: 1,
      monotonicEndMilliseconds: 2,
      coldProcessPerSample: true,
      hardTimeoutEnforced: true,
      processModel:
        "new_process_per_sample; first_configured_hook_before_runtime_smoke; " +
        "hermetic_generated_input_and_selector_availability_metadata",
      firstMs: 100,
      p95Ms: 110,
      maxMs: 120,
      pass: true,
      artifactIdentity: `sha256:${sha}`,
    },
    finalTopology: {
      status: "pass",
      sourceCommit: "a".repeat(40),
      installedHosts: ["claude", "codex"],
      version: "1.2.1",
      admittedTopology: "claude_and_codex_only; other_supported_hosts_absent",
      nonTargetHosts: Object.fromEntries(
        SUPPORTED_HOSTS.filter((host) => !["claude", "codex"].includes(host)).map((host) => [
          host,
          absentHost,
        ]),
      ),
      previousCacheDataTrustContentRestorationClaimed: false,
    },
  };
  assert.doesNotThrow(() => acceptance.validatePublicAssertions(assertions));
});

test("entering finalizing is an absorbing one-shot boundary after hook or later failures", () =>
  withFixture(async (root) => {
    for (const failurePoint of ["hook-probe", "later-status-or-timing"]) {
      const privateDirectory = join(root, failurePoint);
      mkdirSync(privateDirectory, { mode: 0o700 });
      const checkpoint = {
        phase: "post-install-checks",
        sourceCommit: "a".repeat(40),
        lastObservedState: null,
      };
      const testId = "00000000-0000-4000-8000-000000000001";
      let hookCalls = 0;
      const finalizationId = acceptance.beginFinalizationClaim(
        privateDirectory,
        checkpoint,
        { testId, sourceCommit: checkpoint.sourceCommit },
      );
      const durableClaim = JSON.parse(
        readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
      );
      assert.equal(durableClaim.phase, "finalizing");
      assert.equal(durableClaim.lastObservedState.finalizationId, finalizationId);
      assert.throws(
        () => acceptance.beginFinalizationClaim(
          privateDirectory,
          checkpoint,
          { testId, sourceCommit: checkpoint.sourceCommit },
        ),
        AcceptanceError,
      );
      assert.equal(checkpoint.lastObservedState.finalizationId, finalizationId);
      await assert.rejects(
        () => acceptance.runFinalVerificationOnce(
          privateDirectory,
          checkpoint,
          async () => {
            hookCalls += 1;
            assert.equal(
              JSON.parse(
                readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
              ).lastObservedState.finalizationId,
              finalizationId,
            );
            if (failurePoint === "hook-probe") throw new Error("probe failed");
            throw new Error("later status failed");
          },
          { testId, sourceCommit: checkpoint.sourceCommit, finalizationId },
        ),
        /failed/u,
      );
      assert.equal(hookCalls, 1);
      assert.equal(checkpoint.phase, "finalizing");
      assert.match(checkpoint.lastObservedState.finalizationId, /^[0-9a-f-]{36}$/u);
      assert.equal(checkpoint.lastObservedState.testId, testId);
      assert.equal(checkpoint.lastObservedState.sourceCommit, checkpoint.sourceCommit);
      assert.equal(checkpoint.lastObservedState.firstReviewReplayForbidden, true);
      const publicFailureState = acceptance.finalizationFailureState(checkpoint);
      assert.deepEqual(publicFailureState, {
        classification: "one_shot_final_verification_interrupted",
        installedHosts: ["claude", "codex"],
        actualStateRecorded: false,
        previousStateRestorationClaimed: false,
      });
      const failedReport = makeReport();
      failedReport.mutation.started = true;
      failedReport.mutation.purgeCommandAttempts = 1;
      failedReport.mutation.trustResetAttempts = 1;
      failedReport.mutation.reinstallAttempts = 1;
      applyMutationOutcome(failedReport, {
        status: "failed",
        phase: "finalizing",
        reinstallAttempted: true,
        failureState: publicFailureState,
        error: new AcceptanceError("session-start-budget", "fixture failure"),
      });
      const publicDirectory = join(privateDirectory, "public-failure");
      mkdirSync(publicDirectory, { mode: 0o700 });
      assert.doesNotThrow(() => writeReports(publicDirectory, failedReport));
      assert.throws(
        () => recoveryPlanForPhase(checkpoint, { classification: "candidate_installed_unverified" }),
        AcceptanceError,
      );
      assert.throws(
        () => acceptance.executePhaseAwareResumePreflight("finalizing", {
          verifyEnvironment: () => {},
          verifyHosts: () => { hookCalls += 1; },
          verifySource: () => {},
        }),
        AcceptanceError,
      );
      assert.equal(hookCalls, 1);
    }
  }));

test("final-verified receipt restores public state without replaying final checks", async () => {
  const report = makeReport();
  report.source.commit = "a".repeat(40);
  report.assertions = { zeroResidue: { bound: "fixture" } };
  report.commands = [{ id: 1, label: "fixture", exitStatus: 0 }];
  report.mutation.purgeCommandAttempts = 1;
  report.mutation.trustResetAttempts = 1;
  report.mutation.reinstallAttempts = 1;
  report.mutation.reinstallAttempted = true;
  const finalState = {
    status: "installed",
    version: "1.2.1",
    installedHosts: ["claude", "codex"],
  };
  const receipt = acceptance.makeFinalVerificationSnapshot(report, finalState);
  const checkpointValue = {
    phase: "final-verified",
    lastObservedState: {
      classification: "candidate_installed_verified",
      finalVerification: receipt,
    },
  };
  const restored = makeReport();
  const outcome = acceptance.restoreFinalVerificationSnapshot(restored, checkpointValue);
  assert.equal(outcome.status, "complete");
  assert.deepEqual(outcome.finalState, finalState);
  assert.deepEqual(restored.assertions, report.assertions);
  assert.deepEqual(restored.commands, report.commands);
  assert.equal(restored.mutation.reinstallAttempts, 1);

  let callbackCount = 0;
  const fresh = makeReport();
  const resumed = await acceptance.runMutation(
    { run: () => { callbackCount += 1; } },
    fresh,
    {},
    {},
    "/private/final-verified-must-not-be-read",
    checkpointValue,
    {
      runtime: {
        verifyCandidateUnchanged: async () => { callbackCount += 1; },
        inspectRecoveryState: async () => { callbackCount += 1; },
        assertFinalInstalled: async () => { callbackCount += 1; },
        inspectFailureState: async () => { callbackCount += 1; },
        purgeCandidate: async () => { callbackCount += 1; },
        assertClean: async () => { callbackCount += 1; },
        installCandidate: async () => { callbackCount += 1; },
        sealPublicResult: () => { callbackCount += 1; },
        commitFinalVerified: () => { callbackCount += 1; },
      },
    },
  );
  assert.equal(resumed.status, "complete");
  assert.equal(callbackCount, 0);
  assert.deepEqual(fresh.commands, report.commands);

  const tampered = structuredClone(checkpointValue);
  tampered.lastObservedState.finalVerification.value.assertions.extra = true;
  assert.throws(
    () => acceptance.restoreFinalVerificationSnapshot(makeReport(), tampered),
    AcceptanceError,
  );
});

test("sealed final-verified public bytes are immutable and publish idempotently", () =>
  withFixture(async (root) => {
    const publicDirectory = join(root, "public");
    const fakeHome = join(root, "home");
    const privateDirectory = join(
      fakeHome,
      ".opensocrates-acceptance-private",
      "reinstall-cycle-finalize",
    );
    mkdirSync(publicDirectory, { mode: 0o700 });
    mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    report.automatedResult = "passed";
    report.mutation.finalState = "installed";
    const finalState = {
      status: "installed",
      version: "1.2.1",
      installedHosts: ["claude", "codex"],
    };
    const checkpointValue = {
      phase: "post-install-checks",
      sourceCommit: report.source.commit,
      lastObservedState: null,
    };
    const finalizationId = acceptance.beginFinalizationClaim(
      privateDirectory,
      checkpointValue,
      { testId: report.testId, sourceCommit: report.source.commit },
    );
    await acceptance.runFinalVerificationOnce(
      privateDirectory,
      checkpointValue,
      async () => finalState,
      { testId: report.testId, sourceCommit: report.source.commit, finalizationId },
    );
    const finalVerification = acceptance.makeFinalVerificationSnapshot(report, finalState);
    const sealed = acceptance.createSealedPublicResult(
      privateDirectory,
      report,
      finalVerification,
      { finalizationId },
    );
    assert.equal(sealed.receipt.finalizationId, finalizationId);
    assert.equal(sealed.receipt.testId, checkpointValue.lastObservedState.testId);
    assert.equal(sealed.receipt.sourceCommit, checkpointValue.lastObservedState.sourceCommit);
    acceptance.publishSealedPublicResult(
      privateDirectory,
      publicDirectory,
      report.testId,
    );
    const first = Object.fromEntries(
      ["result.json", "result.md", "manual-observations.md"].map((name) => [
        name,
        readFileSync(join(publicDirectory, name)),
      ]),
    );

    report.steps.push({ id: "tamper", label: "tamper", status: "failed", durationMs: 0 });
    acceptance.publishSealedPublicResult(
      privateDirectory,
      publicDirectory,
      sealed.receipt.testId,
    );
    for (const [name, bytes] of Object.entries(first)) {
      assert.deepEqual(readFileSync(join(publicDirectory, name)), bytes);
    }
  }));

test("installed checkpoint is committed only after the public result persists", () =>
  withFixture(async (root) => {
    const publicDirectory = join(root, "public");
    const privateDirectory = join(root, "private");
    mkdirSync(publicDirectory, { mode: 0o700 });
    mkdirSync(privateDirectory, { mode: 0o700 });
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    report.automatedResult = "passed";
    report.mutation.finalState = "installed";
    acceptance.initializePrivateEvidenceManifest(
      privateDirectory,
      publicDirectory,
      report,
    );
    const finalState = {
      status: "installed",
      version: "1.2.1",
      installedHosts: ["claude", "codex"],
    };
    const checkpointValue = {
      phase: "post-install-checks",
      sourceCommit: report.source.commit,
      lastObservedState: null,
    };
    const finalizationId = acceptance.beginFinalizationClaim(
      privateDirectory,
      checkpointValue,
      { testId: report.testId, sourceCommit: report.source.commit },
    );
    await acceptance.runFinalVerificationOnce(
      privateDirectory,
      checkpointValue,
      async () => finalState,
      { testId: report.testId, sourceCommit: report.source.commit, finalizationId },
    );
    const finalVerification = acceptance.makeFinalVerificationSnapshot(report, finalState);
    const sealed = acceptance.createSealedPublicResult(
      privateDirectory,
      report,
      finalVerification,
      { finalizationId },
    );
    checkpointValue.phase = "final-verified";
    checkpointValue.lastObservedState = {
      classification: "candidate_installed_verified",
      finalizationId,
      testId: report.testId,
      sourceCommit: report.source.commit,
      finalVerification,
      sealedPublicResult: {
        receiptSha256: sealed.receiptSha256,
        sealSha256: sealed.receipt.sealSha256,
        resultJsonSha256: sealed.receipt.files["result.json"].sha256,
      },
    };
    assert.throws(
      () => acceptance.persistRunAndFinalizeCheckpoint(
        report,
        publicDirectory,
        privateDirectory,
        checkpointValue,
        {
          afterPublicPersist: () => {
            assert.equal(existsSync(join(publicDirectory, "result.json")), true);
            throw new Error("fixture crash after public persist");
          },
        },
      ),
      /fixture crash/u,
    );
    assert.equal(checkpointValue.phase, "final-verified");
    const firstBytes = readFileSync(join(publicDirectory, "result.json"));
    report.steps.push({ id: "must-not-persist", label: "must-not-persist", status: "failed", durationMs: 0 });
    acceptance.persistRunAndFinalizeCheckpoint(
      report,
      publicDirectory,
      privateDirectory,
      checkpointValue,
    );
    assert.equal(checkpointValue.phase, "installed");
    assert.deepEqual(readFileSync(join(publicDirectory, "result.json")), firstBytes);
    assert.equal(readFileSync(join(publicDirectory, "result.json"), "utf8").includes("must-not-persist"), false);
    const durable = JSON.parse(readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"));
    assert.equal(durable.phase, "installed");
    assert.equal(durable.lastObservedState.publicResultPersistedBeforeCompletion, true);
  }));

test("production mutation sealing survives a persist crash and fresh finalize-only resume", () =>
  withFixture(async (root) => {
    const publicDirectory = join(root, "public");
    const fakeHome = join(root, "home");
    const privateDirectory = join(
      fakeHome,
      ".opensocrates-acceptance-private",
      "reinstall-cycle-finalize",
    );
    mkdirSync(publicDirectory, { mode: 0o700 });
    mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    report.baseline.initialState = "installed";
    report.baseline.installedHosts = ["claude", "codex"];
    acceptance.initializePrivateEvidenceManifest(
      privateDirectory,
      publicDirectory,
      report,
    );
    writeReports(publicDirectory, report);
    acceptance.refreshPrivateEvidenceManifest(privateDirectory, publicDirectory, report);
    const checkpointValue = {
      schema: "opensocrates.reinstall-cycle-checkpoint/1.0.0",
      testId: report.testId,
      phase: "post-install-checks",
      reportDirectory: publicDirectory,
      sourceCommit: report.source.commit,
      baseline: {
        kind: "purged_same_machine",
        initialState: "installed",
        initialInstalledHosts: ["claude", "codex"],
      },
      recovery: { hostCloseRetriesUsed: 0, reinstallRetriesUsed: 0 },
      lastObservedState: {
        classification: "atomic_all_host_install_succeeded_post_checks_pending",
        installedHosts: ["claude", "codex"],
      },
    };
    writeFileSync(
      join(privateDirectory, "checkpoint.json"),
      `${JSON.stringify(checkpointValue, null, 2)}\n`,
      { mode: 0o600 },
    );
    const lifecycleWorker = join(root, "lifecycle-worker.mjs");
    writeFileSync(lifecycleWorker, "process.exit(0);\n", { mode: 0o600 });
    for (const operationKey of ["purge-initial", "install-initial"]) {
      const terminal = await acceptance.executeLifecycleOperation({
        privateDirectory,
        operationKey,
        label: `Synthetic ${operationKey}`,
        executable: realpathSync(process.execPath),
        args: [lifecycleWorker],
        cwd: root,
        env: {
          HOME: fakeHome,
          PATH: dirname(realpathSync(process.execPath)),
          TMPDIR: root,
          LANG: "C",
          LC_ALL: "C",
        },
        timeout: 20_000,
        candidateIdentitySha256: "5".repeat(64),
      });
      assert.equal(terminal.status, 0);
    }
    const runtime = {
      verifyCandidateUnchanged: async () => {},
      inspectRecoveryState: async () => ({
        classification: "candidate_installed_unverified",
        installedHosts: ["claude", "codex"],
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      }),
      assertFinalInstalled: async () => {
        const durableClaim = JSON.parse(
          readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
        );
        assert.equal(durableClaim.phase, "finalizing");
        assert.match(durableClaim.lastObservedState.finalizationId, /^[0-9a-f-]{36}$/u);
        assert.equal(
          durableClaim.lastObservedState.finalizationId,
          checkpointValue.lastObservedState.finalizationId,
        );
        return {
          status: "installed",
          version: "1.2.1",
          installedHosts: ["claude", "codex"],
        };
      },
      inspectFailureState: async () => ({
        classification: "unknown_unverified",
        actualStateRecorded: false,
        previousStateRestorationClaimed: false,
      }),
      sealPublicResult: (directory, prospective, finalVerification, options) => {
        assert.equal(
          options.finalizationId,
          checkpointValue.lastObservedState.finalizationId,
        );
        return acceptance.createSealedPublicResult(
          directory,
          prospective,
          finalVerification,
          options,
        );
      },
    };
    const outcome = await acceptance.runMutation(
      {},
      report,
      {},
      {},
      privateDirectory,
      checkpointValue,
      {
        lifecycleStep: {
          id: "lifecycle-resume",
          label: "Resume the existing exact-input lifecycle checkpoint",
          started: Date.now(),
        },
        runtime,
      },
    );
    assert.equal(outcome.status, "complete");
    assert.equal(outcome.reportSealed, true);
    assert.equal(report.automatedResult, "passed");
    assert.equal(checkpointValue.phase, "final-verified");
    assert.equal(existsSync(join(privateDirectory, "sealed-public-result", "receipt.json")), true);
    assert.throws(
      () =>
        acceptance.persistRunAndFinalizeCheckpoint(
          report,
          publicDirectory,
          privateDirectory,
          checkpointValue,
          { afterPublicPersist: () => { throw new Error("fixture persist crash"); } },
        ),
      /fixture persist crash/u,
    );
    assert.equal(checkpointValue.phase, "final-verified");

    const resumed = spawnSync(
      realpathSync(process.execPath),
      [join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"), "--resume", privateDirectory],
      { encoding: "utf8", env: { ...process.env, HOME: fakeHome } },
    );
    assert.equal(resumed.status, 0, `${resumed.stdout}\n${resumed.stderr}`);
    const durable = JSON.parse(readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"));
    assert.equal(durable.phase, "installed");
    const restored = JSON.parse(readFileSync(join(publicDirectory, "result.json"), "utf8"));
    assert.equal(restored.automatedResult, "passed");
    assert.equal(restored.steps.filter((step) => step.id === "lifecycle-resume").length, 1);
    assert.equal(restored.commands.length, 0);
    assert.deepEqual(
      {
        started: restored.mutation.started,
        purgeCommandAttempts: restored.mutation.purgeCommandAttempts,
        trustResetAttempts: restored.mutation.trustResetAttempts,
        reinstallAttempts: restored.mutation.reinstallAttempts,
        hostCloseRetriesUsed: restored.mutation.hostCloseRetriesUsed,
        reinstallAttempted: restored.mutation.reinstallAttempted,
      },
      {
        started: true,
        purgeCommandAttempts: 1,
        trustResetAttempts: 1,
        reinstallAttempts: 1,
        hostCloseRetriesUsed: 0,
        reinstallAttempted: true,
      },
    );
    const manualPath = join(publicDirectory, "manual-observations.md");
    const manualFields = [
      "Codex seven-hook first review",
      "Codex seven-hook approval completed",
      "Codex SessionStart live timeout absence",
      "Claude Local namespaced status",
      "Record and Replay capture reviewed",
    ];
    let manual = readFileSync(manualPath, "utf8");
    for (const field of manualFields) {
      manual = manual.replace(`${field}: PENDING\n`, `${field}: NOT_OBSERVED\n`);
    }
    writeFileSync(
      manualPath,
      manual,
      { mode: 0o600 },
    );
    const archive = packExisting(publicDirectory, privateDirectory);
    assert.equal(existsSync(archive), true);
  }));

test("finalizing resumes only from a complete seal with the exact durable identity", () =>
  withFixture(async (root) => {
    for (const failurePoint of [
      "seal-write",
      "checkpoint-write",
      "checkpoint-write-mismatch",
    ]) {
      const checkpointWriteFailure = failurePoint.startsWith("checkpoint-write");
      const fixtureRoot = join(root, failurePoint);
      const publicDirectory = join(fixtureRoot, "public");
      const fakeHome = join(fixtureRoot, "home");
      const privateDirectory = join(
        fakeHome,
        ".opensocrates-acceptance-private",
        "reinstall-cycle-finalize",
      );
      mkdirSync(publicDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      const report = makeReport();
      report.source.commit = "a".repeat(40);
      report.baseline.initialState = "installed";
      report.baseline.installedHosts = ["claude", "codex"];
      writeReports(publicDirectory, report);
      acceptance.initializePrivateEvidenceManifest(
        privateDirectory,
        publicDirectory,
        report,
      );
      acceptance.refreshPrivateEvidenceManifest(
        privateDirectory,
        publicDirectory,
        report,
      );
      const checkpointValue = {
        schema: "opensocrates.reinstall-cycle-checkpoint/1.0.0",
        testId: report.testId,
        phase: "post-install-checks",
        reportDirectory: publicDirectory,
        sourceCommit: report.source.commit,
        baseline: {
          kind: "purged_same_machine",
          initialState: "installed",
          initialInstalledHosts: ["claude", "codex"],
        },
        recovery: { hostCloseRetriesUsed: 0, reinstallRetriesUsed: 0 },
        lastObservedState: {
          classification: "atomic_all_host_install_succeeded_post_checks_pending",
          installedHosts: ["claude", "codex"],
        },
      };
      writeFileSync(
        join(privateDirectory, "checkpoint.json"),
        `${JSON.stringify(checkpointValue, null, 2)}\n`,
        { mode: 0o600 },
      );
      const runtime = {
        verifyCandidateUnchanged: async () => {},
        inspectRecoveryState: async () => ({
          classification: "candidate_installed_unverified",
          installedHosts: ["claude", "codex"],
          actualStateRecorded: true,
          previousStateRestorationClaimed: false,
        }),
        assertFinalInstalled: async () => ({
          status: "installed",
          version: "1.2.1",
          installedHosts: ["claude", "codex"],
        }),
        inspectFailureState: async () => ({
          classification: "unknown_unverified",
          actualStateRecorded: false,
          previousStateRestorationClaimed: false,
        }),
        ...(!checkpointWriteFailure
          ? {
              sealPublicResult: (directory, prospective, finalVerification, options) =>
                acceptance.createSealedPublicResult(
                  directory,
                  prospective,
                  finalVerification,
                  {
                    ...options,
                    afterFileWritten: (name) => {
                      if (name === "result.json") {
                        throw new Error("fixture seal write failure");
                      }
                    },
                  },
                ),
            }
          : {
              commitFinalVerified: () => {
                throw new Error("fixture checkpoint write failure");
              },
            }),
      };
      await assert.rejects(
        () =>
          acceptance.runMutation(
            {},
            report,
            {},
            {},
            privateDirectory,
            checkpointValue,
            {
              lifecycleStep: {
                id: "lifecycle-resume",
                label: "Resume the existing exact-input lifecycle checkpoint",
                started: Date.now(),
              },
              runtime,
            },
          ),
        new RegExp(
          checkpointWriteFailure
            ? "fixture checkpoint write failure"
            : "fixture seal write failure",
          "u",
        ),
      );
      assert.equal(report.automatedResult, "running");
      assert.notEqual(report.mutation.finalState, "installed");
      assert.notEqual(
        report.mutation.nextAction,
        "complete_record_and_replay_manual_observations",
      );
      assert.equal(checkpointValue.phase, "finalizing");
      assert.equal(checkpointValue.lastObservedState.actualStateRecorded, false);
      writeReports(publicDirectory, report);
      acceptance.refreshPrivateEvidenceManifest(
        privateDirectory,
        publicDirectory,
        report,
      );
      assert.throws(
        () => packExisting(publicDirectory, privateDirectory),
        AcceptanceError,
      );
      assert.equal(existsSync(`${publicDirectory}.zip`), false);

      if (failurePoint === "checkpoint-write-mismatch") {
        const durableCheckpoint = JSON.parse(
          readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
        );
        durableCheckpoint.lastObservedState.finalizationId =
          "00000000-0000-4000-8000-000000000099";
        writeFileSync(
          join(privateDirectory, "checkpoint.json"),
          `${JSON.stringify(durableCheckpoint, null, 2)}\n`,
          { mode: 0o600 },
        );
      }

      const resumed = spawnSync(
        realpathSync(process.execPath),
        [join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"), "--resume", privateDirectory],
        { encoding: "utf8", env: { ...process.env, HOME: fakeHome } },
      );
      const publicResult = JSON.parse(
        readFileSync(join(publicDirectory, "result.json"), "utf8"),
      );
      assert.equal(
        readFileSync(join(privateDirectory, "commands.jsonl"), "utf8"),
        "",
      );
      if (failurePoint !== "checkpoint-write") {
        assert.equal(resumed.status, 1);
        assert.match(
          resumed.stderr,
          /cannot be replayed|not bound to one complete matching sealed result/u,
        );
        assert.notEqual(publicResult.automatedResult, "passed");
        assert.notEqual(publicResult.mutation.finalState, "installed");
        continue;
      }

      assert.equal(resumed.status, 0, `${resumed.stdout}\n${resumed.stderr}`);
      assert.equal(publicResult.automatedResult, "passed");
      assert.equal(publicResult.mutation.finalState, "installed");
      const durableCheckpoint = JSON.parse(
        readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
      );
      const sealedReceipt = JSON.parse(
        readFileSync(
          join(privateDirectory, "sealed-public-result", "receipt.json"),
          "utf8",
        ),
      );
      assert.equal(durableCheckpoint.phase, "installed");
      assert.equal(
        durableCheckpoint.lastObservedState.finalizationId,
        sealedReceipt.finalizationId,
      );
      assert.equal(durableCheckpoint.lastObservedState.testId, sealedReceipt.testId);
      assert.equal(
        durableCheckpoint.lastObservedState.finalVerificationSha256,
        sealedReceipt.finalVerificationSha256,
      );
      const manualPath = join(publicDirectory, "manual-observations.md");
      let manual = readFileSync(manualPath, "utf8");
      for (const field of [
        "Codex seven-hook first review",
        "Codex seven-hook approval completed",
        "Codex SessionStart live timeout absence",
        "Claude Local namespaced status",
        "Record and Replay capture reviewed",
      ]) {
        manual = manual.replace(`${field}: PENDING\n`, `${field}: NOT_OBSERVED\n`);
      }
      writeFileSync(manualPath, manual, { mode: 0o600 });
      const archive = packExisting(publicDirectory, privateDirectory);
      assert.equal(existsSync(archive), true);
    }
  }));

test("lifecycle orchestrator rejects duplicate and out-of-order stages", async () => {
  const operations = {
    purge: async () => ({ status: "complete" }),
    assertClean: async () => {},
    install: async () => {},
    assertFinal: async () => ({ status: "installed" }),
  };
  for (const stages of [
    ["purge", "purge", "clean-assertion", "reinstall", "post-install"],
    ["reinstall", "clean-assertion", "post-install"],
    ["post-install", "reinstall"],
  ]) {
    await assert.rejects(() => executeMutationPlan(operations, stages), AcceptanceError);
  }
});

test("lifecycle plan blocks reinstall after purge or zero-residue failure", async () => {
  const calls = [];
  const purgeFailure = await executeMutationPlan({
    purge: async () => { throw new AcceptanceError("purge", "fixture failure"); },
    assertClean: async () => calls.push("clean"),
    install: async () => calls.push("install"),
    assertFinal: async () => calls.push("final"),
    inspectFailure: async () => ({ classification: "partial_or_unverified" }),
  });
  assert.equal(purgeFailure.status, "failed");
  assert.deepEqual(calls, []);

  const cleanFailure = await executeMutationPlan({
    purge: async () => ({ status: "complete" }),
    assertClean: async () => { throw new AcceptanceError("residue", "fixture residue"); },
    install: async () => calls.push("install"),
    assertFinal: async () => calls.push("final"),
    inspectFailure: async () => ({ classification: "partial_or_unverified" }),
  });
  assert.equal(cleanFailure.phase, "clean-assertion");
  assert.deepEqual(calls, []);
});

test("failure inspection errors return an explicit unknown state without stale claims", async () => {
  for (const [failedStage, expectedPhase, staleState] of [
    ["purge", "purge", "installed_baseline"],
    ["install", "reinstall", "purged_zero_residue"],
    ["final", "post-install", "candidate_installed_unverified"],
  ]) {
    const outcome = await executeMutationPlan({
      purge: async () => {
        if (failedStage === "purge") throw new AcceptanceError("purge", "fixture failure");
        return { status: "complete" };
      },
      assertClean: async () => {},
      install: async () => {
        if (failedStage === "install") throw new AcceptanceError("reinstall", "fixture failure");
      },
      assertFinal: async () => {
        if (failedStage === "final") throw new AcceptanceError("post-install", "fixture failure");
        return { status: "installed" };
      },
      inspectFailure: async () => {
        throw new Error("fixture classifier failure");
      },
    });
    assert.equal(outcome.status, "failed");
    assert.equal(outcome.phase, expectedPhase);
    assert.deepEqual(outcome.failureState, {
      classification: "unknown_unverified",
      actualStateRecorded: false,
      previousStateRestorationClaimed: false,
    });

    const report = makeReport();
    report.mutation.finalState = staleState;
    applyMutationOutcome(report, outcome);
    assert.equal(report.mutation.lifecycleOutcome, "failed_with_state_unclassified");
    assert.equal(report.mutation.finalState, "unknown_unverified");
    assert.equal(report.assertions.failureState.actualStateRecorded, false);
    assert.notEqual(report.mutation.finalState, staleState);
  }
});

test("archive lexical safety rejects traversal and metadata sidecars", () => {
  assert.doesNotThrow(() => assertSafeArchiveEntry("package/README.md", "fixture"));
  for (const entry of ["../escape", "/absolute", "package/.DS_Store", "__MACOSX/item", "package/._README.md"]) {
    assert.throws(() => assertSafeArchiveEntry(entry, "fixture"), AcceptanceError);
  }
});

test("verified ZIP extraction uses the bounded plan for stored and deflated members without spawning unzip", () =>
  withFixture((root) => {
    const archive = join(root, "valid.zip");
    const extraction = join(root, "extraction");
    mkdirSync(extraction, { mode: 0o700 });
    const deflatedBody = Buffer.alloc(2048, 0x41);
    writeZipFixture(archive, [
      { name: "artifact/" },
      { name: "artifact/stored.txt", body: "stored payload" },
      { name: "artifact/deflated.bin", body: deflatedBody, method: 8 },
    ]);
    let commandCount = 0;
    const result = acceptance.extractVerifiedZip(
      { run: () => { commandCount += 1; } },
      archive,
      extraction,
      { label: "valid fixture", category: "artifact-integrity" },
    );
    assert.deepEqual(result, {
      entryCount: 3,
      totalUncompressedBytes: Buffer.byteLength("stored payload") + deflatedBody.length,
    });
    assert.equal(commandCount, 0);
    assert.equal(readFileSync(join(extraction, "artifact", "stored.txt"), "utf8"), "stored payload");
    assert.deepEqual(readFileSync(join(extraction, "artifact", "deflated.bin")), deflatedBody);
  }));

test("immutable GitHub artifact transport accepts only its exact signed-descriptor ASCII profile", () =>
  withFixture((root) => {
    const archive = join(root, "github-artifact.zip");
    const extraction = join(root, "extraction");
    mkdirSync(extraction, { mode: 0o700 });
    const transportEntry = {
      name: "package-darwin-arm64.zip",
      body: "verified transport payload",
      method: 8,
      flags: 0x0008,
      madeBy: 0x032d,
      externalAttributes: (((0o100644 << 16) >>> 0) | 0x20) >>> 0,
      localCrc32: 0,
      localCompressedSize: 0,
      localUncompressedSize: 0,
      dataDescriptor: true,
    };
    writeZipFixture(archive, [transportEntry]);
    assert.throws(
      () =>
        acceptance.extractVerifiedZip({}, archive, extraction, {
          label: "strict package fixture",
          category: "artifact-integrity",
        }),
      AcceptanceError,
    );
    const result = acceptance.extractVerifiedZip({}, archive, extraction, {
      label: "GitHub artifact fixture",
      category: "artifact-integrity",
      profile: "github-artifact-container",
    });
    assert.deepEqual(result, {
      entryCount: 1,
      totalUncompressedBytes: Buffer.byteLength("verified transport payload"),
    });

    const rejected = [
      { name: "non-ascii", entry: { ...transportEntry, name: "café.zip" } },
      { name: "wrong-descriptor", entry: { ...transportEntry, descriptorCrc32: 1 } },
      { name: "missing-descriptor", entry: { ...transportEntry, dataDescriptor: false } },
      { name: "wrong-creator", entry: { ...transportEntry, madeBy: 0x0314 } },
      {
        name: "wrong-dos-attributes",
        entry: {
          ...transportEntry,
          externalAttributes: ((0o100644 << 16) >>> 0),
        },
      },
      { name: "stored-method", entry: { ...transportEntry, method: 0 } },
    ];
    for (const item of rejected) {
      const rejectedArchive = join(root, `${item.name}.zip`);
      const rejectedExtraction = join(root, `extract-${item.name}`);
      mkdirSync(rejectedExtraction, { mode: 0o700 });
      writeZipFixture(rejectedArchive, [item.entry]);
      assert.throws(
        () =>
          acceptance.extractVerifiedZip({}, rejectedArchive, rejectedExtraction, {
            label: item.name,
            category: "artifact-integrity",
            profile: "github-artifact-container",
          }),
        AcceptanceError,
        item.name,
      );
      assert.deepEqual(readdirSync(rejectedExtraction), [], item.name);
    }
  }));

test("native release ZIP writer emits the strict UTF-8 Unix regular-file contract", () =>
  withFixture((root) => {
    const source = join(root, "source");
    const archive = join(root, "release.zip");
    const extraction = join(root, "extraction");
    mkdirSync(source, { mode: 0o700 });
    mkdirSync(extraction, { mode: 0o700 });
    writeFileSync(join(source, "payload.txt"), "release payload", { mode: 0o600 });
    const completed = spawnSync(
      process.env.OPENSOCRATES_PYTHON ?? "python3",
      [
        "-c",
        "from pathlib import Path; import sys; from release_check import _write_deterministic_zip; " +
          "_write_deterministic_zip(Path(sys.argv[1]), Path(sys.argv[2]))",
        source,
        archive,
      ],
      {
        cwd: process.cwd(),
        encoding: "utf8",
        env: {
          PATH: process.env.PATH ?? "/usr/bin:/bin",
          PYTHONPATH: join(process.cwd(), "tools"),
          LANG: "C",
          LC_ALL: "C",
        },
      },
    );
    assert.equal(completed.status, 0, `${completed.stdout}\n${completed.stderr}`);
    chmodSync(archive, 0o600);
    assert.deepEqual(
      acceptance.extractVerifiedZip({}, archive, extraction, {
        label: "native release writer fixture",
        category: "artifact-integrity",
      }),
      { entryCount: 1, totalUncompressedBytes: Buffer.byteLength("release payload") },
    );
  }));

test("public native asset identities commit atomically only after both receipts are complete", () => {
  const asset = (host, seed) => ({
    archivePath: `/private/candidate/${host}.zip`,
    name: `opensocrates-1.2.1-${host}-plugin.zip`,
    sha256: seed.repeat(64),
    checksumProvenance: "locally_derived_from_verified_manifest",
    aggregatePackageFileCount: 2,
    aggregatePackageChecksumFile: `${host}/checksums.sha256`,
    payloadFileCount: 1,
    checksumInventorySha256: "c".repeat(64),
    releaseManifestSha256: "d".repeat(64),
    runtimeSha256: "e".repeat(64),
    runtimeArchitecture: "arm64",
  });
  const complete = { claude: asset("claude", "a"), codex: asset("codex", "b") };
  const partial = structuredClone(complete);
  delete partial.claude.runtimeArchitecture;
  const failedReport = makeReport();
  assert.throws(
    () => acceptance.commitPublicAssetIdentities(failedReport, partial),
    AcceptanceError,
  );
  assert.deepEqual(failedReport.source.assets, {});

  const report = makeReport();
  const projected = acceptance.commitPublicAssetIdentities(report, complete);
  assert.deepEqual(report.source.assets, projected);
  assert.deepEqual(Object.keys(projected), ["claude", "codex"]);
  assert.equal(Object.hasOwn(projected.claude, "archivePath"), false);
  assert.equal(projected.codex.runtimeArchitecture, "arm64");
});

test("ZIP verification rejects ambiguous metadata, path aliases, and declared-size overflow before extraction", () =>
  withFixture((root) => {
    const extraction = join(root, "extraction");
    mkdirSync(extraction, { mode: 0o700 });
    const cases = [
      {
        name: "link-descendant",
        entries: [
          { name: "link", mode: 0o120777 },
          { name: "link/descendant.txt", mode: 0o100600 },
        ],
      },
      {
        name: "duplicate",
        entries: [
          { name: "duplicate.txt" },
          { name: "duplicate.txt" },
        ],
      },
      {
        name: "case-collision",
        entries: [
          { name: "Evidence.json" },
          { name: "evidence.json" },
        ],
      },
      {
        name: "segment-case-collision",
        entries: [
          { name: "Evidence/one.json" },
          { name: "evidence/two.json" },
        ],
      },
      {
        name: "nfc-collision",
        entries: [
          { name: "caf\u00e9.json" },
          { name: "cafe\u0301.json" },
        ],
      },
      {
        name: "directory-file-alias",
        entries: [
          { name: "alias/" },
          { name: "alias" },
        ],
      },
      {
        name: "file-ancestor",
        entries: [
          { name: "ancestor" },
          { name: "ancestor/descendant.txt" },
        ],
      },
      { name: "special", entries: [{ name: "pipe", mode: 0o010600 }] },
      {
        name: "ratio",
        entries: [{ name: "bomb.bin", body: Buffer.alloc(1), uncompressedSize: 10_000_000 }],
      },
      {
        name: "declared-small-actual-overflow",
        entries: [{ name: "overflow.bin", body: Buffer.alloc(4096, 0x41), method: 8, uncompressedSize: 32 }],
      },
      { name: "data-descriptor", entries: [{ name: "descriptor", flags: 0x0808 }] },
      { name: "legacy-name-flags", entries: [{ name: "legacy", flags: 0 }] },
      { name: "reserved-flags", entries: [{ name: "reserved", flags: 0x0801 }] },
      { name: "unsupported-method", entries: [{ name: "method", method: 12, body: "data" }] },
      { name: "central-extra", entries: [{ name: "central-extra", centralExtra: Buffer.from([1, 0, 0, 0]) }] },
      { name: "local-extra", entries: [{ name: "local-extra", localExtra: Buffer.from([1, 0, 0, 0]) }] },
      { name: "comment", entries: [{ name: "comment", comment: Buffer.from("x") }] },
      { name: "non-unix-creator", entries: [{ name: "creator", madeBy: 0x0014 }] },
      { name: "unexpected-creator-version", entries: [{ name: "creator-version", madeBy: 0x0315 }] },
      {
        name: "external-dos-attributes",
        entries: [{ name: "attributes", externalAttributes: (((0o100600 << 16) >>> 0) | 1) >>> 0 }],
      },
      { name: "local-flags-mismatch", entries: [{ name: "flags", localFlags: 0x0801 }] },
      { name: "local-method-mismatch", entries: [{ name: "method-mismatch", method: 8, localMethod: 0, body: "payload" }] },
      { name: "local-name-mismatch", entries: [{ name: "central-name", localNameBytes: Buffer.from("local-name") }] },
    ];
    const previousUnzip = process.env.UNZIP;
    const previousUnzipOpt = process.env.UNZIPOPT;
    process.env.UNZIP = "-qq";
    process.env.UNZIPOPT = "-d /tmp/hostile-unzip-option";
    try {
      for (const item of cases) {
        const archive = join(root, `${item.name}.zip`);
        writeZipFixture(archive, item.entries);
        let commandCount = 0;
        assert.throws(
          () =>
            acceptance.extractVerifiedZip(
              { run: () => { commandCount += 1; } },
              archive,
              extraction,
              { label: item.name, category: "artifact-integrity" },
            ),
          AcceptanceError,
          item.name,
        );
        assert.equal(commandCount, 0, item.name);
        assert.deepEqual(readdirSync(extraction), [], item.name);
      }
    } finally {
      if (previousUnzip === undefined) delete process.env.UNZIP;
      else process.env.UNZIP = previousUnzip;
      if (previousUnzipOpt === undefined) delete process.env.UNZIPOPT;
      else process.env.UNZIPOPT = previousUnzipOpt;
    }
  }));

test("npm tar metadata rejects links, special files, and name collisions before extraction", () =>
  withFixture((root) => {
    const extraction = join(root, "tar-extraction");
    mkdirSync(extraction, { mode: 0o700 });
    const cases = [
      {
        name: "symlink-descendant",
        entries: [
          { name: "package/link", type: "2", linkName: "outside" },
          { name: "package/link/descendant", type: "0" },
        ],
      },
      { name: "hardlink", entries: [{ name: "package/hard", type: "1", linkName: "package/file" }] },
      { name: "special", entries: [{ name: "package/pipe", type: "6" }] },
      {
        name: "duplicate",
        entries: [
          { name: "package/file" },
          { name: "package/file" },
        ],
      },
      {
        name: "case-collision",
        entries: [
          { name: "package/File" },
          { name: "package/file" },
        ],
      },
    ];
    for (const item of cases) {
      const archive = join(root, `${item.name}.tgz`);
      writeTarGzipFixture(archive, item.entries);
      let commandCount = 0;
      assert.throws(
        () =>
          acceptance.extractVerifiedTarGzip(
            { run: () => { commandCount += 1; } },
            archive,
            extraction,
            { label: item.name, category: "npm-package", requiredPrefix: "package" },
          ),
        AcceptanceError,
      );
      assert.equal(commandCount, 0);
      assert.deepEqual(readdirSync(extraction), []);
    }
  }));

test("suppressed command streams leave account and unrelated-plugin canaries out of private and public evidence", () =>
  withFixture((root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const report = makeReport();
    const recorder = new acceptance.CommandRecorder(privateDirectory, report);
    const canary = "UNRELATED_ACCOUNT_PLUGIN_CANARY_7f2d";
    const completed = recorder.run(
      "Project only categorical OpenSocrates state",
      process.execPath,
      [
        "-e",
        "process.stdout.write(JSON.stringify([{name:'unrelated',path:process.env.PRIVATE_CANARY},{name:'opensocrates',path:'/managed/root',installLocation:'/managed/root',source:'directory',ignored:process.env.PRIVATE_CANARY}])); process.stderr.write(process.env.PRIVATE_CANARY)",
      ],
      {
        env: { ...process.env, PRIVATE_CANARY: canary },
        projection: "claude-marketplaces",
        persistRaw: false,
      },
    );
    assert.deepEqual(JSON.parse(completed.stdout), [
      {
        name: "opensocrates",
        source: "directory",
        path: "/managed/root",
        installLocation: "/managed/root",
      },
    ]);
    assert.equal(completed.stderr, "");
    assert.equal(privateFileTexts(privateDirectory).some((value) => value.includes(canary)), false);
    assert.equal(JSON.stringify(report).includes(canary), false);
    assert.deepEqual(readdirSync(join(privateDirectory, "commands")), []);
  }));

test("private command ledger rejects mode, link, and hash drift and never follows a precreated output symlink", () =>
  withFixture((root) => {
    const makePrivate = (name) => {
      const target = join(root, name);
      mkdirSync(target, { mode: 0o700 });
      return target;
    };

    const hashDirectory = makePrivate("hash");
    const hashReport = makeReport();
    const hashRecorder = new acceptance.CommandRecorder(hashDirectory, hashReport);
    hashRecorder.run("Safe projection", process.execPath, ["-e", "process.stdout.write('safe')"]);
    assert.doesNotThrow(() => new acceptance.CommandRecorder(hashDirectory, makeReport()));
    writeFileSync(join(hashDirectory, "commands", "command-001.stdout"), "changed", { mode: 0o600 });
    assert.throws(
      () => new acceptance.CommandRecorder(hashDirectory, makeReport()),
      AcceptanceError,
    );

    const modeDirectory = makePrivate("mode");
    const modeRecorder = new acceptance.CommandRecorder(modeDirectory, makeReport());
    modeRecorder.run("Safe projection", process.execPath, ["-e", "process.stdout.write('safe')"]);
    chmodSync(join(modeDirectory, "commands.jsonl"), 0o644);
    assert.throws(
      () => new acceptance.CommandRecorder(modeDirectory, makeReport()),
      AcceptanceError,
    );

    const linkDirectory = makePrivate("hardlink");
    const linkRecorder = new acceptance.CommandRecorder(linkDirectory, makeReport());
    linkRecorder.run("Safe projection", process.execPath, ["-e", "process.stdout.write('safe')"]);
    const output = join(linkDirectory, "commands", "command-001.stdout");
    linkSync(output, join(linkDirectory, "commands", "alias.stdout"));
    assert.throws(
      () => new acceptance.CommandRecorder(linkDirectory, makeReport()),
      AcceptanceError,
    );

    const symlinkDirectory = makePrivate("symlink");
    const symlinkRecorder = new acceptance.CommandRecorder(symlinkDirectory, makeReport());
    const outside = join(root, "outside.txt");
    writeFileSync(outside, "untouched", { mode: 0o600 });
    symlinkSync(outside, join(symlinkDirectory, "commands", "command-001.stdout"));
    assert.throws(
      () => symlinkRecorder.run("Unsafe target probe", process.execPath, ["-e", "process.stdout.write('changed')"]),
      AcceptanceError,
    );
    assert.equal(readFileSync(outside, "utf8"), "untouched");
  }));

test("private evidence manifest binds test, public result, command ledger, and retention state", () =>
  withFixture((root) => {
    const privateDirectory = join(root, "private-manifest");
    const outputDirectory = join(root, "public-result");
    mkdirSync(privateDirectory, { mode: 0o700 });
    mkdirSync(outputDirectory, { mode: 0o700 });
    const report = makeReport();
    writeReports(outputDirectory, report);
    acceptance.initializePrivateEvidenceManifest(
      privateDirectory,
      outputDirectory,
      report,
    );
    const recorder = new acceptance.CommandRecorder(privateDirectory, report);
    recorder.run("Categorical command", process.execPath, ["-e", "process.stdout.write('{}')"], {
      persistRaw: false,
    });
    acceptance.refreshPrivateEvidenceManifest(privateDirectory, outputDirectory, report);
    const validated = acceptance.validatePrivateEvidenceManifest(
      privateDirectory,
      outputDirectory,
      report.testId,
    );
    assert.equal(validated.testId, report.testId);
    assert.equal(validated.commandLedger.entryCount, 1);
    assert.match(validated.commandLedger.sha256, /^[a-f0-9]{64}$/u);
    assert.match(validated.publicResult.resultJsonSha256, /^[a-f0-9]{64}$/u);
    assert.equal(validated.retention.status, "active");
    assert.equal(validated.retention.cleanupAuthorized, false);
    assert.equal(validated.recording.status, "pending");

    const manifestPath = join(privateDirectory, "private-evidence-manifest.json");
    chmodSync(manifestPath, 0o644);
    assert.throws(
      () => acceptance.validatePrivateEvidenceManifest(
        privateDirectory,
        outputDirectory,
        report.testId,
      ),
      AcceptanceError,
    );
    chmodSync(manifestPath, 0o600);
    writeFileSync(join(privateDirectory, "commands.jsonl"), "{}\n", { mode: 0o600 });
    assert.throws(
      () => acceptance.validatePrivateEvidenceManifest(
        privateDirectory,
        outputDirectory,
        report.testId,
      ),
      AcceptanceError,
    );
  }));

test("command-ledger and manifest crash boundaries recover one exact committed generation", () =>
  withFixture((root) => {
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    for (const boundary of ["journal", "command-ledger", "private-manifest"]) {
      const fixtureRoot = join(root, boundary);
      const privateDirectory = join(fixtureRoot, "private");
      const outputDirectory = join(fixtureRoot, "public");
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(outputDirectory, { mode: 0o700 });
      const report = makeReport();
      writeReports(outputDirectory, report);
      acceptance.initializePrivateEvidenceManifest(
        privateDirectory,
        outputDirectory,
        report,
      );
      const recorder = new acceptance.CommandRecorder(privateDirectory, report, {
        evidenceTestHooks: {
          afterJournalPublished: () => {
            if (boundary === "journal") throw new Error("fixture journal crash");
          },
          afterRolePublished: (role) => {
            if (boundary === role) throw new Error(`fixture ${role} crash`);
          },
        },
      });
      assert.throws(
        () =>
          recorder.run(
            "Categorical generation command",
            process.execPath,
            ["-e", "process.stdout.write('{}')"],
            { persistRaw: false },
          ),
        /fixture/u,
      );
      assert.equal(
        existsSync(join(privateDirectory, "evidence-transaction.json")),
        true,
      );
      const marker = join(fixtureRoot, "recovered.json");
      const driver = join(fixtureRoot, "recover-command-generation.mjs");
      writeFileSync(
        driver,
        `import { readFileSync, writeFileSync } from "node:fs";\n` +
          `import { CommandRecorder } from ${JSON.stringify(moduleUrl)};\n` +
          `const report = JSON.parse(readFileSync(process.argv[2], "utf8"));\n` +
          `new CommandRecorder(process.argv[3], report);\n` +
          `writeFileSync(process.argv[4], JSON.stringify(report.commands));\n`,
        { mode: 0o600 },
      );
      const recovered = spawnSync(
        realpathSync(process.execPath),
        [
          driver,
          join(outputDirectory, "result.json"),
          privateDirectory,
          marker,
        ],
        { encoding: "utf8" },
      );
      assert.equal(recovered.status, 0, `${recovered.stdout}\n${recovered.stderr}`);
      assert.equal(JSON.parse(readFileSync(marker, "utf8")).length, 1);
      assert.equal(
        readFileSync(join(privateDirectory, "commands.jsonl"), "utf8")
          .split(/\r?\n/u)
          .filter(Boolean).length,
        1,
      );
      assert.equal(
        acceptance.validatePrivateEvidenceManifest(
          privateDirectory,
          outputDirectory,
          report.testId,
        ).commandLedger.entryCount,
        1,
      );
      assert.equal(
        existsSync(join(privateDirectory, "evidence-transaction.json")),
        false,
      );
    }
  }));

test("every public publish boundary recovers the exact report and manifest generation", () =>
  withFixture((root) => {
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    for (const boundary of [
      "journal",
      "result-json",
      "result-markdown",
      "manual-observations",
      "private-manifest",
    ]) {
      const fixtureRoot = join(root, boundary);
      const privateDirectory = join(fixtureRoot, "private");
      const outputDirectory = join(fixtureRoot, "public");
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(outputDirectory, { mode: 0o700 });
      const report = makeReport();
      writeReports(outputDirectory, report);
      acceptance.initializePrivateEvidenceManifest(
        privateDirectory,
        outputDirectory,
        report,
      );
      writeFileSync(
        join(outputDirectory, "manual-observations.md"),
        "fixture prior-generation manual bytes\n",
        { mode: 0o600 },
      );
      report.steps.push({
        id: "generation-boundary",
        label: `Generation boundary ${boundary}`,
        status: "passed",
        durationMs: 1,
      });
      assert.throws(
        () =>
          acceptance.persistRun(report, outputDirectory, privateDirectory, {
            evidenceTestHooks: {
              afterJournalPublished: () => {
                if (boundary === "journal") throw new Error("fixture journal crash");
              },
              afterRolePublished: (role) => {
                if (boundary === role) throw new Error(`fixture ${role} crash`);
              },
            },
          }),
        /fixture/u,
      );
      const driver = join(fixtureRoot, "recover-public-generation.mjs");
      writeFileSync(
        driver,
        `import { recoverEvidenceTransaction, validatePrivateEvidenceManifest } from ${JSON.stringify(moduleUrl)};\n` +
          `recoverEvidenceTransaction(process.argv[2]);\n` +
          `validatePrivateEvidenceManifest(process.argv[2], process.argv[3], process.argv[4]);\n`,
        { mode: 0o600 },
      );
      const recovered = spawnSync(
        realpathSync(process.execPath),
        [driver, privateDirectory, outputDirectory, report.testId],
        { encoding: "utf8" },
      );
      assert.equal(recovered.status, 0, `${recovered.stdout}\n${recovered.stderr}`);
      assert.deepEqual(
        JSON.parse(readFileSync(join(outputDirectory, "result.json"), "utf8")),
        report,
      );
      assert.match(
        readFileSync(join(outputDirectory, "result.md"), "utf8"),
        new RegExp(`Generation boundary ${boundary}`, "u"),
      );
      assert.equal(
        existsSync(join(privateDirectory, "evidence-transaction.json")),
        false,
      );
    }
  }));

test("public result schema rejects unknown fields instead of relying on a blacklist", () =>
  withFixture((root) => {
    const report = makeReport();
    report.unreviewedExtension = "looks harmless";
    assert.throws(
      () => writeReports(root, report, { privateValues: [] }),
      (error) => error instanceof AcceptanceError && error.category === "privacy",
    );
  }));

test("environment evidence is unclaimed before verification and mandatory for PASS", () =>
  withFixture((root) => {
    const report = makeRuntimeReport();
    assert.deepEqual(
      {
        platform: report.environment.platform,
        hardwareArchitecture: report.environment.hardwareArchitecture,
        processArchitecture: report.environment.processArchitecture,
        identity: report.environment.identity,
      },
      {
        platform: null,
        hardwareArchitecture: null,
        processArchitecture: null,
        identity: null,
      },
    );
    writeReports(root, report);
    report.automatedResult = "passed";
    assert.throws(
      () => writeReports(root, report),
      /passed result requires verified target environment evidence/u,
    );
  }));

test("public report persistence validates every existing target before any no-follow publish", () =>
  withFixture((root) => {
    const report = makeReport();
    writeReports(root, report);
    const originalJson = readFileSync(join(root, "result.json"));
    const external = join(dirname(root), `${report.testId}-external-result.md`);
    writeFileSync(external, "external-canary\n", { mode: 0o600 });
    try {
      unlinkSync(join(root, "result.md"));
      symlinkSync(external, join(root, "result.md"));
      report.steps.push({
        id: "must-not-publish",
        label: "Must not publish",
        status: "passed",
        durationMs: 1,
      });
      assert.throws(
        () => writeReports(root, report),
        /public result file result\.md/u,
      );
      assert.deepEqual(readFileSync(join(root, "result.json")), originalJson);
      assert.equal(readFileSync(external, "utf8"), "external-canary\n");
    } finally {
      rmSync(external, { force: true });
    }
  }));

test("resume public prevalidation rejects link and nested-schema tampering without writes", () =>
  withFixture((root) => {
    const report = makeReport();
    writeReports(root, report);
    assert.deepEqual(acceptance.validateExistingPublicReports(root), report);

    const resultPath = join(root, "result.json");
    const tampered = structuredClone(report);
    tampered.source.ci = {
      repository: "ParkerHwang/OpenSocrates",
      workflowPath: ".github/workflows/ci.yml",
      workflowId: 1,
      runId: 1,
      runAttempt: 1,
      conclusion: "success",
      headSha: "a".repeat(40),
      artifact: {
        id: 1,
        name: "native-packages-1-1",
        digest: `sha256:${"b".repeat(64)}`,
        sizeBytes: 1,
        rawContainerSha256: "b".repeat(64),
        workflowRunId: 1,
        workflowRunHeadSha: "a".repeat(40),
        target: "darwin-arm64",
        nestedCanary: "neutral",
      },
      buildSource: {
        headSha: "a".repeat(40),
        treeSha: "c".repeat(40),
        receiptSha256: "d".repeat(64),
      },
    };
    writeFileSync(resultPath, `${JSON.stringify(tampered, null, 2)}\n`, { mode: 0o600 });
    assert.throws(
      () => acceptance.validateExistingPublicReports(root),
      /typed allowlist/u,
    );

    writeReports(root, report);
    const external = join(dirname(root), `${report.testId}-resume-canary`);
    writeFileSync(external, "unchanged\n", { mode: 0o600 });
    try {
      unlinkSync(join(root, "manual-observations.md"));
      symlinkSync(external, join(root, "manual-observations.md"));
      assert.throws(
        () => acceptance.validateExistingPublicReports(root),
        /public result file manual-observations\.md/u,
      );
      assert.equal(readFileSync(external, "utf8"), "unchanged\n");
    } finally {
      rmSync(external, { force: true });
    }
  }));

test("public result schema rejects unknown nested objects and raw/path canaries", () =>
  withFixture((root) => {
    for (const mutate of [
      (report) => {
        report.baseline.inventory = { untypedExtension: { value: "/opt/private/canary" } };
      },
      (report) => {
        report.source.ci = { actorDisplayName: "fixture-username" };
      },
      (report) => {
        report.assertions.finalStatus = { status: "pass", detail: "stdout: PRIVATE_CANARY" };
      },
    ]) {
      const report = makeReport();
      mutate(report);
      assert.throws(
        () => writeReports(root, report, { privateValues: [] }),
        (error) => error instanceof AcceptanceError && error.category === "privacy",
      );
      assert.deepEqual(readdirSync(root), []);
    }
  }));

test("public failure leaves reject nested values, Anthropic-like tokens, and single-segment paths", () =>
  withFixture((root) => {
    const mutations = [
      (report) => {
        report.failure = {
          category: { neutral: "nested-canary" },
          message: "safe",
          commandId: null,
        };
      },
      (report) => {
        report.failure = {
          category: "harness",
          message: { neutral: "nested-canary" },
          commandId: null,
        };
      },
      (report) => {
        report.failure = {
          category: "harness",
          message: "sk-ant-api03-0123456789abcdefghijklmnop",
          commandId: null,
        };
      },
      (report) => {
        report.failure = {
          category: "harness",
          message: "/secret",
          commandId: null,
        };
      },
    ];
    for (const [index, mutate] of mutations.entries()) {
      const directory = join(root, String(index));
      mkdirSync(directory, { mode: 0o700 });
      const report = makeReport();
      mutate(report);
      assert.throws(
        () => writeReports(directory, report, { privateValues: [] }),
        (error) => error instanceof AcceptanceError && error.category === "privacy",
      );
      assert.deepEqual(readdirSync(directory), []);
    }
  }));

test("public scalar contracts reject malformed UUID, URL, range, digest, and assertion enums", () =>
  withFixture((root) => {
    const mutations = [
      (report) => { report.testId = "not-a-uuid"; },
      (report) => {
        report.source.pullRequest = 83;
        report.source.pullRequestUrl = "https://example.invalid/private/83";
      },
      (report) => { report.mutation.purgeCommandAttempts = -1; },
      (report) => {
        report.commands.push({
          id: 1,
          label: "Synthetic command",
          exitStatus: 0,
          durationMs: 1,
          stdoutSha256: "not-a-digest",
          stderrSha256: "0".repeat(64),
        });
      },
      (report) => {
        report.assertions.finalStatus = {
          status: "neutral",
          desiredVersion: "1.2.1",
          hostsInSync: ["claude", "codex"],
          drift: false,
        };
      },
    ];
    for (const [index, mutate] of mutations.entries()) {
      const directory = join(root, `scalar-${index}`);
      mkdirSync(directory, { mode: 0o700 });
      const report = makeReport();
      mutate(report);
      assert.throws(
        () => writeReports(directory, report),
        (error) => error instanceof AcceptanceError && error.category === "privacy",
      );
      assert.deepEqual(readdirSync(directory), []);
    }
  }));

test("host version producer stores only an anchored canonical version token", () => {
  const runFixture = (claudeVersion, codexVersion) => {
    const report = makeReport();
    const recorder = {
      run: (label) => {
        if (label === "Read Claude Code version") return { stdout: claudeVersion };
        if (label === "Verify Claude authentication") {
          return { stdout: JSON.stringify({ loggedIn: true }) };
        }
        if (label === "Read Codex CLI version") return { stdout: codexVersion };
        return { stdout: "", status: 0 };
      },
    };
    return { report, value: acceptance.verifyHosts(recorder, report) };
  };
  const valid = runFixture("2.1.205 (Claude Code)\n", "codex-cli 0.99.0\n");
  assert.deepEqual(valid.value, {
    claudeVersion: "2.1.205",
    codexVersion: "0.99.0",
  });
  assert.equal(valid.report.environment.claudeVersion, "2.1.205");
  assert.equal(valid.report.environment.codexVersion, "0.99.0");
  assert.throws(
    () => runFixture("2.1.205 private-account-canary", "codex-cli 0.99.0"),
    AcceptanceError,
  );
  assert.throws(
    () => runFixture("2.1.205 (Claude Code)", "codex 0.99.0 value=/opt/private"),
    AcceptanceError,
  );
});

test("artifact step keeps private candidate values out of public steps", () =>
  withFixture(async (root) => {
    const report = makeReport();
    const candidate = {
      packageArchive: "/private/evidence/opensocrates.tgz",
      rawArtifactPath: "/private/evidence/native.zip",
      assets: { claude: { archivePath: "/private/evidence/claude.zip" } },
      execution: { cwd: "/private/evidence/isolated/cwd" },
    };
    const returned = await performStep(
      report,
      "artifact-gate",
      "Prepare exact candidate",
      async () => candidate,
    );
    assert.strictEqual(returned, candidate);
    assert.deepEqual(Object.keys(report.steps[0]).sort(), [
      "durationMs",
      "id",
      "label",
      "status",
    ]);
    assert.doesNotThrow(() => writeReports(root, report));
    const serialized = readFileSync(join(root, "result.json"), "utf8");
    for (const forbidden of [
      "packageArchive",
      "rawArtifactPath",
      "archivePath",
      "/private/evidence",
    ]) {
      assert.equal(serialized.includes(forbidden), false);
    }
  }));

test("public ZIP staging rejects extra entries and symbolic links", () =>
  withFixture((root) => {
    for (const name of ["result.json", "result.md", "manual-observations.md"]) {
      writeFileSync(join(root, name), `${name}\n`, { mode: 0o600 });
    }
    writeFileSync(join(root, "extra.txt"), "must fail\n", { mode: 0o600 });
    assert.throws(() => zipReports(root), AcceptanceError);
    assert.equal(existsSync(`${root}.zip`), false);
    rmSync(join(root, "extra.txt"));
    rmSync(join(root, "result.md"));
    symlinkSync(join(root, "result.json"), join(root, "result.md"));
    assert.throws(() => zipReports(root), AcceptanceError);
    assert.equal(existsSync(`${root}.zip`), false);
  }));

test("public ZIP contains exactly three regular owner-only files", () =>
  withFixture((root) => {
    for (const name of ["result.json", "result.md", "manual-observations.md"]) {
      writeFileSync(join(root, name), `${name}\n`, { mode: 0o600 });
    }
    const archive = zipReports(root);
    assert.equal(lstatSync(archive).isFile(), true);
    assert.equal(lstatSync(archive).mode & 0o077, 0);
    const listing = spawnSync("/usr/bin/unzip", ["-Z1", archive], { encoding: "utf8" });
    assert.equal(listing.status, 0);
    assert.deepEqual(listing.stdout.trim().split(/\r?\n/u).sort(), [
      "manual-observations.md",
      "result.json",
      "result.md",
    ]);
  }));

test("manual observations accept only fixed final enums without free-form text", () =>
  withFixture(async (root) => {
    const outputDirectory = join(root, "public");
    const privateDirectory = join(root, "private");
    mkdirSync(outputDirectory, { mode: 0o700 });
    mkdirSync(privateDirectory, { mode: 0o700 });
    const report = makeReport();
    await prepareInstalledSealedFixture(outputDirectory, privateDirectory, report);
    const recording = join(privateDirectory, "recording.capture");
    writeFileSync(recording, "reviewed", { mode: 0o600 });
    acceptance.bindRecordingReceipt(privateDirectory, recording, report.testId);
    const manualPath = join(outputDirectory, "manual-observations.md");
    const finalized = manualTemplate(report)
      .replace("Codex seven-hook first review: PENDING", "Codex seven-hook first review: PASS")
      .replace("Codex seven-hook approval completed: PENDING", "Codex seven-hook approval completed: BLOCKED")
      .replace("Codex SessionStart live timeout absence: PENDING", "Codex SessionStart live timeout absence: NOT_OBSERVED")
      .replace("Claude Local namespaced status: PENDING", "Claude Local namespaced status: FAIL")
      .replace("Record and Replay capture reviewed: PENDING", "Record and Replay capture reviewed: PASS");
    writeFileSync(manualPath, finalized, { mode: 0o600 });
    const archive = packExisting(outputDirectory, privateDirectory);
    assert.equal(lstatSync(archive).isFile(), true);
    assert.deepEqual(readdirSync(outputDirectory).sort(), [
      "manual-observations.md",
      "result.json",
      "result.md",
    ]);
    const packed = JSON.parse(readFileSync(join(outputDirectory, "result.json"), "utf8"));
    assert.equal(packed.manualResult, "failed");

    const badOutput = join(root, "bad-public");
    const badPrivate = join(root, "bad-private");
    mkdirSync(badOutput, { mode: 0o700 });
    mkdirSync(badPrivate, { mode: 0o700 });
    const badReport = makeReport();
    await prepareInstalledSealedFixture(badOutput, badPrivate, badReport);
    writeFileSync(
      join(badOutput, "manual-observations.md"),
      `${manualTemplate(badReport)
        .replaceAll(": PENDING\n", ": FAIL\n")}free-form note\n`,
      { mode: 0o600 },
    );
    assert.throws(() => packExisting(badOutput, badPrivate), AcceptanceError);
  }));

test("help maps resume, recording, pack, and cleanup to their exact command positions", () => {
  const completed = spawnSync(
    realpathSync(process.execPath),
    [join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"), "--help"],
    { encoding: "utf8" },
  );
  assert.equal(completed.status, 0, completed.stderr);
  assert.match(
    completed.stdout,
    /the third is the explicit single retry after closing\nonly the named host apps/u,
  );
  assert.match(completed.stdout, /The fourth binds the reviewed private Record & Replay\ncapture/u);
  assert.match(
    completed.stdout,
    /the fifth\ncreates the sanitized final ZIP/u,
  );
  assert.match(completed.stdout, /PASS, FAIL, NOT_OBSERVED, or BLOCKED/u);
  assert.match(completed.stdout, /--public-bundle BUNDLE_FILE \| --allow-missing-public-bundle/u);
});

test("pack preflight is zero-write for a symlinked result and an existing ZIP", () =>
  withFixture((root) => {
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    report.automatedResult = "passed";
    report.mutation.finalState = "installed";
    writeReports(root, report);
    const manualPath = join(root, "manual-observations.md");
    const finalized = manualTemplate(report)
      .replace("Codex seven-hook first review: PENDING", "Codex seven-hook first review: PASS")
      .replace("Codex seven-hook approval completed: PENDING", "Codex seven-hook approval completed: PASS")
      .replace("Codex SessionStart live timeout absence: PENDING", "Codex SessionStart live timeout absence: PASS")
      .replace("Claude Local namespaced status: PENDING", "Claude Local namespaced status: PASS")
      .replace("Record and Replay capture reviewed: PENDING", "Record and Replay capture reviewed: PASS");
    writeFileSync(manualPath, finalized, { mode: 0o600 });

    const resultPath = join(root, "result.json");
    const outside = join(root, "outside.json");
    const original = readFileSync(resultPath, "utf8");
    writeFileSync(outside, original, { mode: 0o600 });
    rmSync(resultPath);
    symlinkSync(outside, resultPath);
    assert.throws(() => packExisting(root), AcceptanceError);
    assert.equal(readFileSync(outside, "utf8"), original);

    rmSync(resultPath);
    rmSync(outside);
    writeFileSync(resultPath, original, { mode: 0o600 });
    writeFileSync(`${root}.zip`, "existing\n", { mode: 0o600 });
    const before = readFileSync(resultPath, "utf8");
    assert.throws(() => packExisting(root), AcceptanceError);
    assert.equal(readFileSync(resultPath, "utf8"), before);
  }));

test("pack rejects forged PASS, checkpoint drift, seal drift, and manifest drift before ZIP writes", () =>
  withFixture(async (root) => {
    const finalizeManual = (outputDirectory) => {
      const manualPath = join(outputDirectory, "manual-observations.md");
      writeFileSync(
        manualPath,
        readFileSync(manualPath, "utf8").replaceAll(": PENDING\n", ": NOT_OBSERVED\n"),
        { mode: 0o600 },
      );
    };
    const prepare = async (name) => {
      const outputDirectory = join(root, name, "public");
      const privateDirectory = join(root, name, "private");
      mkdirSync(outputDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      const report = makeReport();
      await prepareInstalledSealedFixture(outputDirectory, privateDirectory, report);
      finalizeManual(outputDirectory);
      return { outputDirectory, privateDirectory, report };
    };

    const forgedOutput = join(root, "forged", "public");
    const forgedPrivate = join(root, "forged", "private");
    mkdirSync(forgedOutput, { recursive: true, mode: 0o700 });
    mkdirSync(forgedPrivate, { recursive: true, mode: 0o700 });
    const forgedReport = makeReport();
    forgedReport.source.commit = "a".repeat(40);
    forgedReport.automatedResult = "passed";
    forgedReport.mutation.finalState = "installed";
    writeReports(forgedOutput, forgedReport);
    acceptance.initializePrivateEvidenceManifest(
      forgedPrivate,
      forgedOutput,
      forgedReport,
    );
    finalizeManual(forgedOutput);
    assert.throws(() => packExisting(forgedOutput, forgedPrivate), AcceptanceError);
    assert.equal(existsSync(`${forgedOutput}.zip`), false);

    const wrongCheckpoint = await prepare("wrong-checkpoint");
    const checkpointPath = join(wrongCheckpoint.privateDirectory, "checkpoint.json");
    const checkpoint = JSON.parse(readFileSync(checkpointPath, "utf8"));
    checkpoint.lastObservedState.finalizationId =
      "00000000-0000-4000-8000-000000000077";
    writeFileSync(checkpointPath, `${JSON.stringify(checkpoint, null, 2)}\n`, {
      mode: 0o600,
    });
    assert.throws(
      () => packExisting(wrongCheckpoint.outputDirectory, wrongCheckpoint.privateDirectory),
      AcceptanceError,
    );
    assert.equal(existsSync(`${wrongCheckpoint.outputDirectory}.zip`), false);

    const sealDrift = await prepare("seal-drift");
    writeFileSync(
      join(sealDrift.privateDirectory, "sealed-public-result", "result.md"),
      "drift\n",
      { mode: 0o600 },
    );
    assert.throws(
      () => packExisting(sealDrift.outputDirectory, sealDrift.privateDirectory),
      AcceptanceError,
    );
    assert.equal(existsSync(`${sealDrift.outputDirectory}.zip`), false);

    const manifestDrift = await prepare("manifest-drift");
    const manifestPath = join(
      manifestDrift.privateDirectory,
      "private-evidence-manifest.json",
    );
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    manifest.publicResult.finalizationId =
      "00000000-0000-4000-8000-000000000088";
    writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, {
      mode: 0o600,
    });
    assert.throws(
      () => packExisting(manifestDrift.outputDirectory, manifestDrift.privateDirectory),
      AcceptanceError,
    );
    assert.equal(existsSync(`${manifestDrift.outputDirectory}.zip`), false);
  }));

test("pack is bound to the automated digest and a same-test Record and Replay receipt", () =>
  withFixture(async (root) => {
    const prepare = async (name) => {
      const privateDirectory = join(root, name, "private");
      const outputDirectory = join(root, name, "public");
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(outputDirectory, { recursive: true, mode: 0o700 });
      chmodSync(privateDirectory, 0o700);
      chmodSync(outputDirectory, 0o700);
      const report = makeReport();
      await prepareInstalledSealedFixture(outputDirectory, privateDirectory, report);
      const recording = join(privateDirectory, "record-and-replay.capture");
      writeFileSync(recording, "private categorical capture receipt fixture", { mode: 0o600 });
      return { privateDirectory, outputDirectory, report, recording };
    };

    const success = await prepare("success");
    assert.throws(
      () => acceptance.bindRecordingReceipt(
        success.privateDirectory,
        success.recording,
        "different-test-id",
      ),
      AcceptanceError,
    );
    acceptance.bindRecordingReceipt(
      success.privateDirectory,
      success.recording,
      success.report.testId,
    );
    const manualPath = join(success.outputDirectory, "manual-observations.md");
    writeFileSync(
      manualPath,
      readFileSync(manualPath, "utf8").replaceAll(": PENDING\n", ": PASS\n"),
      { mode: 0o600 },
    );
    const archive = packExisting(success.outputDirectory, success.privateDirectory);
    const finalManifest = acceptance.validatePrivateEvidenceManifest(
      success.privateDirectory,
      success.outputDirectory,
      success.report.testId,
    );
    assert.equal(finalManifest.recording.status, "verified");
    assert.equal(finalManifest.recording.reviewStatus, "reviewed");
    assert.match(finalManifest.recording.recordingSha256, /^[a-f0-9]{64}$/u);
    assert.equal(finalManifest.publicResult.publicZipSha256, createHash("sha256").update(readFileSync(archive)).digest("hex"));
    assert.equal(finalManifest.retention.status, "public_bundle_ready");

    const tampered = await prepare("tampered");
    const tamperedResultPath = join(tampered.outputDirectory, "result.json");
    const changed = JSON.parse(readFileSync(tamperedResultPath, "utf8"));
    changed.source.commit = "b".repeat(40);
    writeFileSync(tamperedResultPath, `${JSON.stringify(changed, null, 2)}\n`, { mode: 0o600 });
    const tamperedManualPath = join(tampered.outputDirectory, "manual-observations.md");
    writeFileSync(
      tamperedManualPath,
      readFileSync(tamperedManualPath, "utf8").replaceAll(": PENDING\n", ": PASS\n"),
      { mode: 0o600 },
    );
    assert.throws(
      () => packExisting(tampered.outputDirectory, tampered.privateDirectory),
      AcceptanceError,
    );
    assert.equal(existsSync(`${tampered.outputDirectory}.zip`), false);

    assert.throws(
      () => acceptance.cleanupPrivateEvidence(
        success.privateDirectory,
        success.report.testId,
        "0".repeat(64),
        { expectedParent: join(root, "success"), requiredPrefix: "private" },
      ),
      AcceptanceError,
    );
    assert.equal(existsSync(success.privateDirectory), true);

    const npmModules = join(
      success.privateDirectory,
      "isolated-npx",
      "runs",
      "call-Ab12Cd",
      "cache",
      "_npx",
      "a".repeat(16),
      "node_modules",
    );
    const npmBin = join(npmModules, ".bin");
    const npmInstaller = join(npmModules, "opensocrates", "installer");
    mkdirSync(npmBin, { recursive: true, mode: 0o755 });
    mkdirSync(npmInstaller, { recursive: true, mode: 0o755 });
    writeFileSync(join(npmModules, "cache-entry.json"), "{}\n", { mode: 0o644 });
    writeFileSync(join(npmInstaller, "opensocrates.mjs"), "#!/usr/bin/env node\n", {
      mode: 0o755,
    });
    symlinkSync(
      "../opensocrates/installer/opensocrates.mjs",
      join(npmBin, "opensocrates"),
    );
    const outside = join(root, "outside-cleanup-canary");
    writeFileSync(outside, "preserve\n", { mode: 0o600 });
    const unsafeLink = join(success.privateDirectory, "unexpected-link");
    symlinkSync(outside, unsafeLink);
    assert.throws(
      () => acceptance.cleanupPrivateEvidence(
        success.privateDirectory,
        success.report.testId,
        finalManifest.publicResult.publicZipSha256,
        { expectedParent: join(root, "success"), requiredPrefix: "private" },
      ),
      /unsafe link/u,
    );
    assert.equal(readFileSync(outside, "utf8"), "preserve\n");
    unlinkSync(unsafeLink);
    acceptance.cleanupPrivateEvidence(
      success.privateDirectory,
      success.report.testId,
      finalManifest.publicResult.publicZipSha256,
      { expectedParent: join(root, "success"), requiredPrefix: "private" },
    );
    assert.equal(existsSync(success.privateDirectory), false);
  }));

test("pack retries converge after report, ZIP, receipt, and bundle-marker crash boundaries", () =>
  withFixture(async (root) => {
    for (const boundary of [
      "report",
      "archive",
      "archive-receipt",
      "bundle-marker",
    ]) {
      const fixtureRoot = join(root, boundary);
      const outputDirectory = join(fixtureRoot, "public");
      const privateDirectory = join(fixtureRoot, "private");
      mkdirSync(outputDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(privateDirectory, { mode: 0o700 });
      const { report } = await prepareInstalledSealedFixture(
        outputDirectory,
        privateDirectory,
      );
      let manual = readFileSync(
        join(outputDirectory, "manual-observations.md"),
        "utf8",
      );
      for (const field of [
        "Codex seven-hook first review",
        "Codex seven-hook approval completed",
        "Codex SessionStart live timeout absence",
        "Claude Local namespaced status",
        "Record and Replay capture reviewed",
      ]) {
        manual = manual.replace(`${field}: PENDING\n`, `${field}: NOT_OBSERVED\n`);
      }
      writeFileSync(
        join(outputDirectory, "manual-observations.md"),
        manual,
        { mode: 0o600 },
      );
      assert.throws(
        () =>
          packExisting(outputDirectory, privateDirectory, {
            testHooks: {
              afterReportPersisted: () => {
                if (boundary === "report") throw new Error("fixture report crash");
              },
              afterArchivePublished: () => {
                if (boundary === "archive") throw new Error("fixture archive crash");
              },
              afterArchiveReceipt: () => {
                if (boundary === "archive-receipt") {
                  throw new Error("fixture archive receipt crash");
                }
              },
              afterBundleMarker: () => {
                if (boundary === "bundle-marker") {
                  throw new Error("fixture bundle marker crash");
                }
              },
            },
          }),
        /fixture/u,
      );
      const archive = packExisting(outputDirectory, privateDirectory);
      assert.equal(existsSync(archive), true);
      const finalReport = JSON.parse(
        readFileSync(join(outputDirectory, "result.json"), "utf8"),
      );
      assert.equal(finalReport.testId, report.testId);
      assert.equal(finalReport.manualResult, "not_observed");
      assert.equal(finalReport.overallResult, "not_observed");
      assert.equal(
        existsSync(join(privateDirectory, "pack-transaction.json")),
        false,
      );
      const manifest = acceptance.validatePrivateEvidenceManifest(
        privateDirectory,
        outputDirectory,
        report.testId,
      );
      assert.equal(manifest.retention.status, "public_bundle_ready");
      assert.equal(manifest.publicResult.publicZipSha256.length, 64);
    }
  }));

test("diagnostic and moved final bundles authorize idempotent guarded private cleanup", () =>
  withFixture(async (root) => {
    const failureOutput = join(root, "failure-public");
    const failurePrivate = join(root, "private-failure");
    mkdirSync(failureOutput, { mode: 0o700 });
    mkdirSync(failurePrivate, { mode: 0o700 });
    const failureReport = makeReport();
    failureReport.automatedResult = "failed";
    failureReport.manualResult = "not-run";
    failureReport.overallResult = "failed";
    failureReport.completedAt = new Date().toISOString();
    failureReport.mutation.lifecycleOutcome = "preflight_failed_without_mutation";
    failureReport.failure = {
      category: "harness",
      message: "Synthetic sanitized failure",
      commandId: null,
    };
    writeReports(failureOutput, failureReport);
    acceptance.initializePrivateEvidenceManifest(
      failurePrivate,
      failureOutput,
      failureReport,
    );
    const diagnostic = acceptance.createDiagnosticBundle(
      failurePrivate,
      failureOutput,
    );
    assert.equal(diagnostic, `${failureOutput}.diagnostic.zip`);
    assert.equal(existsSync(`${failureOutput}.zip`), false);
    const failureManifest = acceptance.validatePrivateEvidenceManifest(
      failurePrivate,
      failureOutput,
      failureReport.testId,
    );
    assert.equal(failureManifest.retention.status, "diagnostic_bundle_ready");
    assert.match(failureManifest.publicResult.diagnosticZipSha256, /^[a-f0-9]{64}$/u);
    assert.throws(
      () => acceptance.cleanupPrivateEvidence(
        failurePrivate,
        failureReport.testId,
        failureManifest.publicResult.diagnosticZipSha256,
        {
          expectedParent: root,
          requiredPrefix: "private-",
          publicBundlePath: diagnostic,
          afterCleanupAuthorized: () => {
            throw new Error("fixture crash after cleanup tombstone");
          },
        },
      ),
      /fixture crash after cleanup tombstone/u,
    );
    assert.equal(existsSync(failurePrivate), true);
    const tombstone = JSON.parse(
      readFileSync(join(failurePrivate, "private-evidence-manifest.json"), "utf8"),
    );
    assert.equal(tombstone.retention.status, "cleanup_authorized");
    assert.equal(tombstone.retention.cleanupAuthorized, true);
    acceptance.cleanupPrivateEvidence(
      failurePrivate,
      failureReport.testId,
      failureManifest.publicResult.diagnosticZipSha256,
      {
        expectedParent: root,
        requiredPrefix: "private-",
        publicBundlePath: diagnostic,
      },
    );
    assert.equal(existsSync(failurePrivate), false);

    const successRoot = join(root, "success");
    const successOutput = join(successRoot, "public");
    const successPrivate = join(successRoot, "private-success");
    mkdirSync(successOutput, { recursive: true, mode: 0o700 });
    mkdirSync(successPrivate, { mode: 0o700 });
    const { report } = await prepareInstalledSealedFixture(
      successOutput,
      successPrivate,
    );
    const successDiagnostic = acceptance.createDiagnosticBundle(
      successPrivate,
      successOutput,
    );
    const recording = join(successPrivate, "recording.bin");
    writeFileSync(recording, "private reviewed capture\n", { mode: 0o600 });
    acceptance.bindRecordingReceipt(successPrivate, recording, report.testId);
    const manualPath = join(successOutput, "manual-observations.md");
    writeFileSync(
      manualPath,
      readFileSync(manualPath, "utf8").replaceAll(": PENDING\n", ": PASS\n"),
      { mode: 0o600 },
    );
    const finalArchive = packExisting(successOutput, successPrivate);
    assert.notEqual(finalArchive, successDiagnostic);
    const finalManifest = acceptance.validatePrivateEvidenceManifest(
      successPrivate,
      successOutput,
      report.testId,
    );
    const movedArchive = join(successRoot, "shared-result.zip");
    renameSync(finalArchive, movedArchive);
    acceptance.cleanupPrivateEvidence(
      successPrivate,
      report.testId,
      finalManifest.publicResult.publicZipSha256,
      {
        expectedParent: successRoot,
        requiredPrefix: "private-",
        publicBundlePath: movedArchive,
      },
    );
    assert.equal(existsSync(successPrivate), false);
  }));

test("paused host-close state resumes from disk to one sealed final pack without diagnostic collision", () =>
  withFixture(async (root) => {
    const publicDirectory = join(root, "public");
    const privateDirectory = join(root, "private");
    mkdirSync(publicDirectory, { mode: 0o700 });
    mkdirSync(privateDirectory, { mode: 0o700 });
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    report.baseline.initialState = "installed";
    report.baseline.installedHosts = ["claude", "codex"];
    const treeBinding = (seed, present = undefined) => ({
      ...(present === undefined ? {} : { present }),
      entryCount: present === false ? 0 : 1,
      fileCount: present === false ? 0 : 1,
      aggregateSha256: seed.repeat(64),
    });
    const exactBindings = {
      schema: "opensocrates.reinstall-cycle-baseline-binding/1.0.0",
      managedRoots: {
        claude: treeBinding("1"),
        codex: treeBinding("2"),
      },
      caches: {
        claude: treeBinding("3", true),
        codex: treeBinding("4", true),
      },
      desiredStateSha256: "5".repeat(64),
      codexTrust: {
        present: false,
        exactSectionCount: 0,
        events: [],
        removedSyntaxByteCount: 0,
        removedSyntaxSha256: "6".repeat(64),
      },
    };
    const initialInventory = { categorical: "installed-two-host-baseline" };
    const pausedResidue = emptyResidueSnapshot();
    Object.assign(pausedResidue.hosts.claude, {
      cachePresent: true,
      cacheMarketplacePresent: true,
      liveInUse: true,
    });
    Object.assign(pausedResidue.stateResidue, {
      present: true,
      empty: false,
      desiredStatePresent: true,
    });
    const resolvedResidue = structuredClone(pausedResidue);
    resolvedResidue.hosts.claude.liveInUse = false;
    const retryBindings = {
      sourceCommit: report.source.commit,
      packageSha256: "7".repeat(64),
      artifactDigest: `sha256:${"8".repeat(64)}`,
      desiredStateSha256: "9".repeat(64),
    };
    const checkpoint = {
      schema: "opensocrates.reinstall-cycle-checkpoint/1.0.0",
      testId: report.testId,
      phase: "ready-to-purge",
      reportDirectory: publicDirectory,
      sourceCommit: report.source.commit,
      baseline: {
        kind: "purged_same_machine",
        initialState: "installed",
        initialInstalledHosts: ["claude", "codex"],
        initialInventory,
        initialInventorySha256: createHash("sha256")
          .update(JSON.stringify(initialInventory))
          .digest("hex"),
        exactBindings,
        exactBindingsSha256: createHash("sha256")
          .update(JSON.stringify(exactBindings))
          .digest("hex"),
      },
      recovery: {
        hostCloseRetriesUsed: 0,
        reinstallRetriesUsed: 0,
        hostCloseRetryAdmission: null,
        reinstallRetryAdmission: null,
      },
      lastObservedState: {
        classification: "installed_baseline",
        installedHosts: ["claude", "codex"],
      },
    };
    writeReports(publicDirectory, report);
    acceptance.initializePrivateEvidenceManifest(
      privateDirectory,
      publicDirectory,
      report,
    );
    const persistCheckpoint = (value) => writeFileSync(
      join(privateDirectory, "checkpoint.json"),
      `${JSON.stringify(value, null, 2)}\n`,
      { mode: 0o600 },
    );
    persistCheckpoint(checkpoint);
    const worker = join(root, "lifecycle-worker.mjs");
    writeFileSync(
      worker,
      "process.exit(Number(process.argv[2]));\n",
      { mode: 0o600 },
    );
    const lifecycleReceipt = (operationKey, status) =>
      acceptance.executeLifecycleOperation({
        privateDirectory,
        operationKey,
        label: `Synthetic ${operationKey}`,
        executable: realpathSync(process.execPath),
        args: [worker, String(status)],
        cwd: root,
        env: {
          HOME: root,
          PATH: dirname(realpathSync(process.execPath)),
          TMPDIR: root,
          LANG: "C",
          LC_ALL: "C",
        },
        timeout: 20_000,
        candidateIdentitySha256: "a".repeat(64),
      });
    assert.equal((await lifecycleReceipt("purge-initial", 23)).status, 23);
    const pausedOutcome = await acceptance.runMutation(
      {},
      report,
      {},
      {},
      privateDirectory,
      checkpoint,
      {
        lifecycleStep: { id: "lifecycle", label: "Synthetic lifecycle", started: Date.now() },
        runtime: {
          verifyCandidateUnchanged: async () => {},
          baselineInventory: async () => ({
            public: structuredClone(initialInventory),
            exactBindings: structuredClone(exactBindings),
          }),
          inspectRecoveryState: async () => { throw new Error("not reached"); },
          assertFinalInstalled: async () => { throw new Error("not reached"); },
          inspectFailureState: async () => { throw new Error("not reached"); },
          purgeCandidate: async () => {
            checkpoint.recovery.hostCloseRetryAdmission = {
              initialSnapshot: structuredClone(pausedResidue),
              confirmedHosts: ["claude"],
              bindings: structuredClone(retryBindings),
              deactivatedDesiredState: deactivatedDesiredStateFixture(),
              resolvedSnapshot: null,
            };
            checkpoint.phase = "awaiting-host-close";
            checkpoint.lastObservedState = {
              classification: "partial_purge_host_in_use",
              confirmedHostCloseCandidates: ["claude"],
              residue: acceptance.publicResidueSummary(pausedResidue),
              retryBindings: structuredClone(retryBindings),
              actualStateRecorded: true,
              previousStateRestorationClaimed: false,
            };
            persistCheckpoint(checkpoint);
            return {
              status: "awaiting-host-close",
              residue: acceptance.publicResidueSummary(pausedResidue),
            };
          },
          assertClean: async () => { throw new Error("not reached"); },
          installCandidate: async () => { throw new Error("not reached"); },
        },
      },
    );
    acceptance.applyMutationOutcome(report, pausedOutcome);
    acceptance.persistRun(report, publicDirectory, privateDirectory);
    const diagnosticArchive = acceptance.createDiagnosticBundle(
      privateDirectory,
      publicDirectory,
    );
    assert.equal(report.automatedResult, "paused");
    assert.equal(existsSync(diagnosticArchive), true);
    assert.equal(existsSync(`${publicDirectory}.zip`), false);

    const resumedReport = JSON.parse(
      readFileSync(join(publicDirectory, "result.json"), "utf8"),
    );
    const resumedCheckpoint = JSON.parse(
      readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
    );
    assert.equal((await lifecycleReceipt("purge-host-close-retry", 0)).status, 0);
    assert.equal((await lifecycleReceipt("install-initial", 0)).status, 0);
    let retryCalls = 0;
    let installCalls = 0;
    const resumeOutcome = await acceptance.runMutation(
      {},
      resumedReport,
      {},
      {},
      privateDirectory,
      resumedCheckpoint,
      {
        hostAppsClosedConfirmed: true,
        lifecycleStep: {
          id: "lifecycle-resume",
          label: "Resume the synthetic exact-input lifecycle checkpoint",
          started: Date.now(),
        },
        runtime: {
          verifyCandidateUnchanged: async () => {},
          baselineInventory: async () => { throw new Error("not reached"); },
          inspectRecoveryState: async () => { throw new Error("not reached"); },
          purgeCandidate: async (_recorder, currentReport, _targets, _candidate, _directory, currentCheckpoint, options) => {
            retryCalls += 1;
            assert.equal(options.hostCloseRetry, true);
            assert.equal(
              acceptance.requireHostCloseRetryAdmission(currentCheckpoint).confirmedHosts[0],
              "claude",
            );
            currentCheckpoint.recovery.hostCloseRetriesUsed = 1;
            currentCheckpoint.recovery.hostCloseRetryAdmission.resolvedSnapshot =
              structuredClone(resolvedResidue);
            currentCheckpoint.phase = "purge-complete-unverified";
            currentCheckpoint.lastObservedState = {
              classification: "purge_commands_completed_zero_residue_unverified",
              actualStateRecorded: true,
              previousStateRestorationClaimed: false,
            };
            currentReport.mutation.hostCloseRetriesUsed = 1;
            persistCheckpoint(currentCheckpoint);
            return { status: "complete" };
          },
          assertClean: async (_recorder, _report, _targets, _directory, currentCheckpoint) => {
            currentCheckpoint.phase = "purged";
            currentCheckpoint.lastObservedState = {
              classification: "purged_zero_residue",
              installedHosts: [],
              actualStateRecorded: true,
              previousStateRestorationClaimed: false,
            };
            persistCheckpoint(currentCheckpoint);
          },
          installCandidate: async (_recorder, currentReport, _candidate, _directory, currentCheckpoint) => {
            installCalls += 1;
            currentReport.mutation.reinstallAttempted = true;
            currentCheckpoint.phase = "post-install-checks";
            currentCheckpoint.lastObservedState = {
              classification: "atomic_all_host_install_succeeded_post_checks_pending",
              installedHosts: ["claude", "codex"],
              actualStateRecorded: true,
              previousStateRestorationClaimed: false,
            };
            persistCheckpoint(currentCheckpoint);
          },
          assertFinalInstalled: async () => {
            const durableClaim = JSON.parse(
              readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
            );
            assert.equal(durableClaim.phase, "finalizing");
            assert.equal(
              durableClaim.lastObservedState.finalizationId,
              resumedCheckpoint.lastObservedState.finalizationId,
            );
            return {
              status: "installed",
              version: "1.2.1",
              installedHosts: ["claude", "codex"],
            };
          },
          inspectFailureState: async () => ({
            classification: "unknown_unverified",
            actualStateRecorded: false,
            previousStateRestorationClaimed: false,
          }),
        },
      },
    );
    assert.equal(retryCalls, 1);
    assert.equal(installCalls, 1);
    assert.equal(resumeOutcome.status, "complete");
    assert.equal(resumeOutcome.reportSealed, true);
    acceptance.persistRunAndFinalizeCheckpoint(
      resumedReport,
      publicDirectory,
      privateDirectory,
      resumedCheckpoint,
    );
    assert.equal(resumedCheckpoint.phase, "installed");
    assert.deepEqual(
      {
        purgeCommandAttempts: resumedReport.mutation.purgeCommandAttempts,
        trustResetAttempts: resumedReport.mutation.trustResetAttempts,
        reinstallAttempts: resumedReport.mutation.reinstallAttempts,
        hostCloseRetriesUsed: resumedReport.mutation.hostCloseRetriesUsed,
      },
      {
        purgeCommandAttempts: 2,
        trustResetAttempts: 2,
        reinstallAttempts: 1,
        hostCloseRetriesUsed: 1,
      },
    );
    const recording = join(privateDirectory, "recording.bin");
    writeFileSync(recording, "private reviewed capture\n", { mode: 0o600 });
    acceptance.bindRecordingReceipt(privateDirectory, recording, report.testId);
    const manualPath = join(publicDirectory, "manual-observations.md");
    let manual = readFileSync(manualPath, "utf8");
    for (const field of [
      "Codex seven-hook first review",
      "Codex seven-hook approval completed",
      "Codex SessionStart live timeout absence",
      "Claude Local namespaced status",
      "Record and Replay capture reviewed",
    ]) {
      manual = manual.replace(`${field}: PENDING\n`, `${field}: NOT_OBSERVED\n`);
    }
    writeFileSync(manualPath, manual, { mode: 0o600 });
    const finalArchive = packExisting(publicDirectory, privateDirectory);
    assert.equal(finalArchive, `${publicDirectory}.zip`);
    assert.notEqual(finalArchive, diagnosticArchive);
    assert.equal(existsSync(diagnosticArchive), true);
    assert.equal(existsSync(finalArchive), true);
    const finalManifest = acceptance.validatePrivateEvidenceManifest(
      privateDirectory,
      publicDirectory,
      report.testId,
    );
    assert.equal(finalManifest.retention.status, "public_bundle_ready");
    assert.match(finalManifest.publicResult.diagnosticZipSha256, /^[a-f0-9]{64}$/u);
    assert.match(finalManifest.publicResult.publicZipSha256, /^[a-f0-9]{64}$/u);
  }));

test("durable lifecycle capsule survives a parent SIGKILL without overlapping the claimed child group", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const worker = join(root, "worker.mjs");
    const driver = join(root, "driver.mjs");
    const configPath = join(root, "operation.json");
    const mutationMarker = join(root, "mutation-count");
    const releaseMarker = join(root, "release");
    writeFileSync(
      worker,
      `import { existsSync, readFileSync, writeFileSync } from "node:fs";\n` +
        `const [countPath, releasePath] = process.argv.slice(2);\n` +
        `const count = existsSync(countPath) ? Number(readFileSync(countPath, "utf8")) : 0;\n` +
        `writeFileSync(countPath, String(count + 1));\n` +
        `process.stdout.write("claimed lifecycle stream\\n");\n` +
        `while (!existsSync(releasePath)) await new Promise((resolve) => setTimeout(resolve, 20));\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "purge-initial",
      label: "Synthetic destructive purge",
      executable: realpathSync(process.execPath),
      args: [worker, mutationMarker, releaseMarker],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "a".repeat(64),
    };
    writeFileSync(configPath, `${JSON.stringify(operation)}\n`, { mode: 0o600 });
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    writeFileSync(
      driver,
      `import { readFileSync } from "node:fs";\n` +
        `import { executeLifecycleOperation } from ${JSON.stringify(moduleUrl)};\n` +
        `await executeLifecycleOperation(JSON.parse(readFileSync(process.argv[2], "utf8")));\n`,
      { mode: 0o600 },
    );
    const parent = spawn(realpathSync(process.execPath), [driver, configPath], {
      stdio: "ignore",
    });
    try {
      await waitUntil(() => existsSync(mutationMarker), "the synthetic lifecycle did not mutate");
      const active = acceptance.inspectLifecycleOperation(
        privateDirectory,
        "purge-initial",
      );
      assert.equal(active.state, "claimed_active");
      assert.equal(active.attempt, 1);
      process.kill(parent.pid, "SIGKILL");
      await assert.rejects(
        () => acceptance.executeLifecycleOperation(operation),
        AcceptanceError,
      );
      assert.equal(readFileSync(mutationMarker, "utf8"), "1");
      writeFileSync(releaseMarker, "release\n", { mode: 0o600 });
      await waitUntil(
        () =>
          acceptance.inspectLifecycleOperation(privateDirectory, "purge-initial").state ===
          "terminal",
        "the detached lifecycle capsule did not commit a terminal receipt",
      );
      const recovered = await acceptance.executeLifecycleOperation(operation);
      assert.equal(recovered.status, 0);
      assert.equal(recovered.recovered, true);
      assert.equal(readFileSync(mutationMarker, "utf8"), "1");
      assert.equal(
        readdirSync(join(privateDirectory, "lifecycle-operations")).length,
        1,
      );
    } finally {
      if (!existsSync(releaseMarker)) writeFileSync(releaseMarker, "release\n", { mode: 0o600 });
      try {
        process.kill(parent.pid, "SIGKILL");
      } catch {}
    }
  }));

test("lifecycle intent staging survives the pre-intent crash window without poisoning replay", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const worker = join(root, "worker.mjs");
    const countPath = join(root, "child-count");
    const configPath = join(root, "operation.json");
    const driver = join(root, "driver.mjs");
    writeFileSync(
      worker,
      `import { existsSync, readFileSync, writeFileSync } from "node:fs";\n` +
        `const target = process.argv[2];\n` +
        `const count = existsSync(target) ? Number(readFileSync(target, "utf8")) : 0;\n` +
        `writeFileSync(target, String(count + 1));\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "purge-initial",
      label: "Synthetic staged lifecycle",
      executable: realpathSync(process.execPath),
      args: [worker, countPath],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "a".repeat(64),
    };
    await assert.rejects(
      () =>
        acceptance.executeLifecycleOperation(operation, {
          testHooks: {
            afterStagingDirectoryCreated: () => {
              throw new Error("fixture crash before intent");
            },
          },
        }),
      /fixture crash before intent/u,
    );
    const staging = join(
      privateDirectory,
      ".lifecycle-operation-001-purge-initial.preparing",
    );
    assert.equal(existsSync(staging), true);
    assert.deepEqual(readdirSync(staging), []);
    assert.deepEqual(
      readdirSync(join(privateDirectory, "lifecycle-operations")),
      [],
    );
    assert.equal(existsSync(countPath), false);

    writeFileSync(configPath, `${JSON.stringify(operation)}\n`, { mode: 0o600 });
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    writeFileSync(
      driver,
      `import { readFileSync } from "node:fs";\n` +
        `import { executeLifecycleOperation } from ${JSON.stringify(moduleUrl)};\n` +
        `await executeLifecycleOperation(JSON.parse(readFileSync(process.argv[2], "utf8")));\n`,
      { mode: 0o600 },
    );
    const resumed = spawnSync(realpathSync(process.execPath), [driver, configPath], {
      encoding: "utf8",
    });
    assert.equal(resumed.status, 0, `${resumed.stdout}\n${resumed.stderr}`);
    assert.equal(readFileSync(countPath, "utf8"), "1");
    assert.equal(existsSync(staging), false);
    assert.equal(
      acceptance.inspectLifecycleOperation(privateDirectory, "purge-initial").state,
      "terminal",
    );
    assert.deepEqual(
      readdirSync(join(privateDirectory, "lifecycle-operations")),
      ["001-purge-initial"],
    );
  }));

test("capsule receipts publish atomically and a claim has exactly one winner", () =>
  withFixture((root) => {
    const target = join(root, "claimed.json");
    const value = { schema: "fixture", value: 1 };
    let observedStaging = null;
    publishExclusiveJson(target, value, {
      singleWinner: true,
      afterPublish: ({ staging }) => {
        observedStaging = staging;
        assert.deepEqual(JSON.parse(readFileSync(target, "utf8")), value);
        assert.equal(lstatSync(target).nlink, 2);
        assert.equal(lstatSync(staging).nlink, 2);
        assert.equal(lstatSync(target).ino, lstatSync(staging).ino);
      },
    });
    assert.equal(lstatSync(target).nlink, 1);
    assert.equal(existsSync(observedStaging), false);
    const original = readFileSync(target);
    assert.throws(
      () => publishExclusiveJson(target, { schema: "fixture", value: 2 }, { singleWinner: true }),
      /EEXIST/u,
    );
    assert.deepEqual(readFileSync(target), original);
    assert.deepEqual(
      readdirSync(root).filter((name) => name.startsWith(".claimed.json.")),
      [],
    );
  }));

test("claim inspection accepts only the atomic hardlink publish converging to one link", () =>
  withFixture((root) => {
    for (const removalPoint of ["stage-inspection", "target-recheck"]) {
      const directory = join(root, removalPoint);
      mkdirSync(directory, { mode: 0o700 });
      const target = join(directory, "claimed.json");
      const staging = join(
        directory,
        `.claimed.json.${process.pid}.11111111-1111-4111-8111-111111111111.tmp`,
      );
      writeFileSync(staging, "{}\n", { mode: 0o600 });
      linkSync(staging, target);
      let targetInspections = 0;
      let removed = false;
      const info = acceptance.requireLifecycleJsonEntry(target, "synthetic lifecycle claim", {
        inspectEntry: (entry) => {
          if (entry === target) targetInspections += 1;
          if (
            !removed &&
            ((removalPoint === "stage-inspection" && entry === staging) ||
              (removalPoint === "target-recheck" &&
                entry === target &&
                targetInspections === 2))
          ) {
            removed = true;
            unlinkSync(staging);
          }
          return lstatSync(entry);
        },
      });
      assert.equal(removed, true);
      assert.equal(info.nlink, 1);
      assert.equal(lstatSync(target).nlink, 1);

      writeFileSync(staging, "{}\n", { mode: 0o600 });
      assert.throws(
        () => acceptance.requireLifecycleJsonEntry(target, "synthetic lifecycle claim"),
        AcceptanceError,
      );
    }
  }));

test("non-claim lifecycle receipts ignore a concurrent valid claim publication stage", () =>
  withFixture((root) => {
    const intent = join(root, "intent.json");
    const claimStage = join(
      root,
      `.claimed.json.${process.pid}.22222222-2222-4222-8222-222222222222.tmp`,
    );
    writeFileSync(intent, "{}\n", { mode: 0o600 });
    writeFileSync(claimStage, "{}\n", { mode: 0o600 });
    assert.doesNotThrow(() =>
      acceptance.requireLifecycleJsonEntry(intent, "synthetic lifecycle intent"));
    assert.equal(lstatSync(intent).nlink, 1);
    assert.equal(lstatSync(claimStage).nlink, 1);
  }));

test("concurrent capsules share one durable claim and launch exactly one child", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const countPath = join(root, "child-count");
    const worker = join(root, "worker.mjs");
    writeFileSync(
      worker,
      `import { appendFileSync } from "node:fs";\n` +
        `appendFileSync(process.argv[2], String(process.pid) + "\\n");\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "purge-initial",
      label: "Synthetic concurrent claim",
      executable: realpathSync(process.execPath),
      args: [worker, countPath],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "e".repeat(64),
    };
    let operationDirectory = null;
    await assert.rejects(
      () =>
        acceptance.executeLifecycleOperation(operation, {
          testHooks: {
            afterOperationPublished: (directory) => {
              operationDirectory = directory;
              throw new Error("fixture stop after prepared publish");
            },
          },
        }),
      /fixture stop after prepared publish/u,
    );
    const prepared = acceptance.inspectLifecycleOperation(
      privateDirectory,
      "purge-initial",
    );
    assert.equal(prepared.state, "prepared");
    assert.equal(prepared.operationDirectory, operationDirectory);
    const capsulePath = join(
      process.cwd(),
      "tools",
      "reinstall_cycle_operation_capsule.mjs",
    );
    const capsules = [0, 1].map(() =>
      spawn(realpathSync(process.execPath), [capsulePath, operationDirectory], {
        detached: true,
        stdio: "ignore",
      }),
    );
    const statuses = await Promise.all(
      capsules.map(
        (child) =>
          new Promise((resolvePromise, rejectPromise) => {
            child.once("error", rejectPromise);
            child.once("exit", (code) => resolvePromise(code));
          }),
      ),
    );
    assert.deepEqual(statuses.sort((left, right) => left - right), [0, 92]);
    const terminal = acceptance.inspectLifecycleOperation(
      privateDirectory,
      "purge-initial",
    );
    assert.equal(terminal.state, "terminal");
    assert.equal(terminal.operationId, prepared.operationId);
    assert.equal(readFileSync(countPath, "utf8").trim().split(/\r?\n/u).length, 1);
    assert.deepEqual(
      readdirSync(operationDirectory).filter((name) => name.startsWith(".claimed.json.")),
      [],
    );
  }));

test("a capsule that exits before claim leaves one prepared operation for safe relaunch", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const countPath = join(root, "child-count");
    const worker = join(root, "worker.mjs");
    writeFileSync(
      worker,
      `import { appendFileSync } from "node:fs";\n` +
        `appendFileSync(process.argv[2], "child\\n");\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "install-initial",
      label: "Synthetic prepared relaunch",
      executable: realpathSync(process.execPath),
      args: [worker, countPath],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "f".repeat(64),
    };
    await assert.rejects(
      () =>
        acceptance.executeLifecycleOperation(operation, {
          testHooks: {
            launchCapsule: () =>
              spawn(realpathSync(process.execPath), ["-e", "process.exit(0)"], {
                detached: true,
                stdio: "ignore",
              }),
          },
        }),
      /exited before claim/u,
    );
    const prepared = acceptance.inspectLifecycleOperation(
      privateDirectory,
      "install-initial",
    );
    assert.equal(prepared.state, "prepared");
    assert.equal(prepared.attempt, 1);
    assert.equal(existsSync(countPath), false);
    const completed = await acceptance.executeLifecycleOperation(operation);
    assert.equal(completed.status, 0);
    assert.equal(completed.operationId, prepared.operationId);
    assert.equal(completed.attempt, 1);
    assert.equal(readFileSync(countPath, "utf8"), "child\n");
  }));

test("reinstalling none or prepared state must reassert zero residue before any install", () =>
  withFixture(async (root) => {
    for (const [operationState, clean] of [
      ["none", false],
      ["prepared", false],
      ["none", true],
      ["prepared", true],
    ]) {
      const fixtureRoot = join(root, `${operationState}-${clean ? "clean" : "drift"}`);
      const privateDirectory = join(fixtureRoot, "private");
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      if (operationState === "prepared") {
        const worker = join(fixtureRoot, "worker.mjs");
        writeFileSync(worker, "process.exit(0);\n", { mode: 0o600 });
        await assert.rejects(
          () =>
            acceptance.executeLifecycleOperation(
              {
                privateDirectory,
                operationKey: "install-initial",
                label: "Synthetic prepared install",
                executable: realpathSync(process.execPath),
                args: [worker],
                cwd: fixtureRoot,
                env: {
                  HOME: fixtureRoot,
                  PATH: dirname(realpathSync(process.execPath)),
                  TMPDIR: fixtureRoot,
                  LANG: "C",
                  LC_ALL: "C",
                },
                timeout: 20_000,
                candidateIdentitySha256: "1".repeat(64),
              },
              {
                testHooks: {
                  afterOperationPublished: () => {
                    throw new Error("fixture prepared boundary");
                  },
                },
              },
            ),
          /fixture prepared boundary/u,
        );
      }
      const report = makeReport();
      report.source.commit = "a".repeat(40);
      const checkpoint = {
        phase: "reinstalling",
        sourceCommit: report.source.commit,
        recovery: { hostCloseRetriesUsed: 0, reinstallRetriesUsed: 0 },
        lastObservedState: { classification: "purged_before_atomic_all_host_reinstall" },
      };
      const calls = [];
      const outcome = await acceptance.runMutation(
        {},
        report,
        {},
        {},
        privateDirectory,
        checkpoint,
        {
          lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
          runtime: {
            verifyCandidateUnchanged: async () => calls.push("verify-candidate"),
            inspectRecoveryState: async () => {
              throw new Error("recovery inspection must not replace the clean assertion");
            },
            assertFinalInstalled: async () => {
              calls.push("final");
              throw new Error("must not reach final");
            },
            inspectFailureState: async () => ({
              classification: "unknown_unverified",
              actualStateRecorded: false,
              previousStateRestorationClaimed: false,
            }),
            purgeCandidate: async () => calls.push("purge"),
            assertClean: async () => {
              calls.push("clean");
              if (!clean) throw new AcceptanceError("residue", "fixture drift");
            },
            installCandidate: async () => {
              calls.push("install");
              throw new AcceptanceError("reinstall", "fixture stop after install dispatch");
            },
          },
        },
      );
      assert.equal(outcome.status, "failed");
      assert.deepEqual(
        calls,
        clean
          ? ["verify-candidate", "clean", "install"]
          : ["verify-candidate", "clean"],
      );
    }
  }));

test("a non-success install terminal is absorbing even when topology looks installed", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const worker = join(root, "worker.mjs");
    const countPath = join(root, "child-count");
    writeFileSync(
      worker,
      `import { appendFileSync } from "node:fs";\n` +
        `appendFileSync(process.argv[2], "child\\n");\n` +
        `process.exit(7);\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "install-initial",
      label: "Synthetic failed install terminal",
      executable: realpathSync(process.execPath),
      args: [worker, countPath],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "2".repeat(64),
    };
    const terminal = await acceptance.executeLifecycleOperation(operation);
    assert.equal(terminal.status, 7);
    const report = makeReport();
    report.source.commit = "a".repeat(40);
    const checkpoint = {
      phase: "reinstalling",
      sourceCommit: report.source.commit,
      recovery: { hostCloseRetriesUsed: 0, reinstallRetriesUsed: 0 },
      lastObservedState: { classification: "purged_before_atomic_all_host_reinstall" },
    };
    const calls = { inspect: 0, install: 0, final: 0 };
    const runtime = {
      verifyCandidateUnchanged: async () => {},
      inspectRecoveryState: async () => {
        calls.inspect += 1;
        return {
          classification: "candidate_installed_unverified",
          installedHosts: ["claude", "codex"],
          actualStateRecorded: true,
          previousStateRestorationClaimed: false,
        };
      },
      assertFinalInstalled: async () => {
        calls.final += 1;
        return { status: "installed", installedHosts: ["claude", "codex"] };
      },
      inspectFailureState: async () => ({
        classification: "candidate_installed_unverified",
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      }),
      purgeCandidate: async () => {
        throw new Error("purge must not run");
      },
      assertClean: async () => {
        throw new Error("clean must not convert the failed terminal");
      },
      installCandidate: async () => {
        calls.install += 1;
      },
    };
    await assert.rejects(
      () =>
        acceptance.runMutation(
          {}, report, {}, {}, privateDirectory, checkpoint,
          {
            lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
            runtime,
          },
        ),
      /non-success/u,
    );
    assert.equal(checkpoint.phase, "reinstall-failed");
    assert.equal(
      checkpoint.lastObservedState.classification,
      "atomic_all_host_install_terminal_failed",
    );
    assert.equal(checkpoint.lastObservedState.observedClassification, "candidate_installed_unverified");
    await assert.rejects(
      () =>
        acceptance.runMutation(
          {}, report, {}, {}, privateDirectory, checkpoint,
          {
            lifecycleStep: { id: "fixture", label: "fixture", started: Date.now() },
            runtime,
          },
        ),
      /observation-only/u,
    );
    assert.deepEqual(calls, { inspect: 1, install: 0, final: 0 });
    assert.equal(report.automatedResult, "running");
    assert.equal(readFileSync(countPath, "utf8"), "child\n");
  }));

test("unknown nonempty lifecycle staging remains fail-closed before child spawn", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const countPath = join(root, "child-count");
    const worker = join(root, "worker.mjs");
    writeFileSync(worker, `import { writeFileSync } from "node:fs"; writeFileSync(process.argv[2], "1");\n`, {
      mode: 0o600,
    });
    const operation = {
      privateDirectory,
      operationKey: "purge-initial",
      label: "Synthetic staged lifecycle",
      executable: realpathSync(process.execPath),
      args: [worker, countPath],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "b".repeat(64),
    };
    await assert.rejects(
      () =>
        acceptance.executeLifecycleOperation(operation, {
          testHooks: {
            afterStagingDirectoryCreated: () => {
              throw new Error("fixture crash before intent");
            },
          },
        }),
      /fixture crash before intent/u,
    );
    const staging = join(
      privateDirectory,
      ".lifecycle-operation-001-purge-initial.preparing",
    );
    writeFileSync(join(staging, "unknown.bin"), "unknown", { mode: 0o600 });
    await assert.rejects(
      () => acceptance.executeLifecycleOperation(operation),
      /partial or unknown lifecycle staging/u,
    );
    assert.equal(existsSync(countPath), false);
    assert.deepEqual(readdirSync(join(privateDirectory, "lifecycle-operations")), []);
  }));

test("a claimed lifecycle without a terminal receipt is absorbing blocked_unverifiable", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const worker = join(root, "worker.mjs");
    const driver = join(root, "driver.mjs");
    const configPath = join(root, "operation.json");
    const mutationMarker = join(root, "mutation");
    writeFileSync(
      worker,
      `import { writeFileSync } from "node:fs";\n` +
        `writeFileSync(process.argv[2], "mutated");\n` +
        `process.stdout.write("stream-before-terminal\\n");\n` +
        `await new Promise((resolve) => setTimeout(resolve, 60000));\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "install-initial",
      label: "Synthetic destructive install",
      executable: realpathSync(process.execPath),
      args: [worker, mutationMarker],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 120_000,
      candidateIdentitySha256: "b".repeat(64),
    };
    writeFileSync(configPath, `${JSON.stringify(operation)}\n`, { mode: 0o600 });
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    writeFileSync(
      driver,
      `import { readFileSync } from "node:fs";\n` +
        `import { executeLifecycleOperation } from ${JSON.stringify(moduleUrl)};\n` +
        `await executeLifecycleOperation(JSON.parse(readFileSync(process.argv[2], "utf8")));\n`,
      { mode: 0o600 },
    );
    const parent = spawn(realpathSync(process.execPath), [driver, configPath], {
      stdio: "ignore",
    });
    try {
      await waitUntil(() => existsSync(mutationMarker), "the synthetic install did not mutate");
      const active = acceptance.inspectLifecycleOperation(
        privateDirectory,
        "install-initial",
      );
      assert.equal(active.state, "claimed_active");
      process.kill(-active.processGroupId, "SIGKILL");
      await waitUntil(
        () =>
          acceptance.inspectLifecycleOperation(privateDirectory, "install-initial").state ===
          "blocked_unverifiable",
        "the dead claimed operation was not made absorbing",
      );
      const blocked = acceptance.inspectLifecycleOperation(
        privateDirectory,
        "install-initial",
      );
      assert.equal(blocked.terminalReceiptPresent, false);
      assert.equal(blocked.streamsRetained, true);
      await assert.rejects(
        () => acceptance.executeLifecycleOperation(operation),
        AcceptanceError,
      );
      assert.equal(readFileSync(mutationMarker, "utf8"), "mutated");

      const publicDirectory = join(root, "public");
      mkdirSync(publicDirectory, { mode: 0o700 });
      const report = makeReport();
      report.source.commit = "a".repeat(40);
      writeReports(publicDirectory, report);
      acceptance.initializePrivateEvidenceManifest(
        privateDirectory,
        publicDirectory,
        report,
      );
      acceptance.refreshPrivateEvidenceManifest(
        privateDirectory,
        publicDirectory,
        report,
      );
      const checkpoint = {
        schema: "opensocrates.reinstall-cycle-checkpoint/1.0.0",
        testId: report.testId,
        phase: "reinstalling",
        reportDirectory: publicDirectory,
        sourceCommit: report.source.commit,
        lastObservedState: {
          classification: "purged_before_atomic_all_host_reinstall",
          actualStateRecorded: true,
          previousStateRestorationClaimed: false,
        },
      };
      writeFileSync(
        join(privateDirectory, "checkpoint.json"),
        `${JSON.stringify(checkpoint, null, 2)}\n`,
        { mode: 0o600 },
      );
      const blockedDriver = join(root, "blocked-resume-driver.mjs");
      writeFileSync(
        blockedDriver,
        `import { readFileSync } from "node:fs";\n` +
          `import { persistBlockedLifecycleJournalOutcome } from ${JSON.stringify(moduleUrl)};\n` +
          `const checkpoint = JSON.parse(readFileSync(process.argv[2], "utf8"));\n` +
          `const report = JSON.parse(readFileSync(process.argv[3], "utf8"));\n` +
          `persistBlockedLifecycleJournalOutcome(process.argv[4], checkpoint, report, process.argv[5]);\n`,
        { mode: 0o600 },
      );
      const resumed = spawnSync(
        realpathSync(process.execPath),
        [
          blockedDriver,
          join(privateDirectory, "checkpoint.json"),
          join(publicDirectory, "result.json"),
          privateDirectory,
          publicDirectory,
        ],
        { encoding: "utf8" },
      );
      assert.equal(resumed.status, 0, `${resumed.stdout}\n${resumed.stderr}`);
      const publicResult = JSON.parse(
        readFileSync(join(publicDirectory, "result.json"), "utf8"),
      );
      const durableCheckpoint = JSON.parse(
        readFileSync(join(privateDirectory, "checkpoint.json"), "utf8"),
      );
      assert.equal(publicResult.automatedResult, "failed");
      assert.equal(publicResult.mutation.lifecycleOutcome, "blocked_unverifiable");
      assert.equal(publicResult.mutation.finalState, "unknown_unverified");
      assert.deepEqual(publicResult.commands, []);
      assert.equal(
        publicResult.steps.some((step) => step.id === "lifecycle-resume"),
        false,
      );
      assert.equal(
        publicResult.assertions.lifecycleRecovery.operationKey,
        "install-initial",
      );
      assert.equal(publicResult.assertions.lifecycleRecovery.attempt, 1);
      assert.match(
        publicResult.assertions.lifecycleRecovery.receiptSha256,
        /^[a-f0-9]{64}$/u,
      );
      assert.equal(durableCheckpoint.phase, "blocked-unverifiable");
      assert.equal(
        durableCheckpoint.lastObservedState.operationSha256,
        publicResult.assertions.lifecycleRecovery.receiptSha256,
      );
      assert.equal(readFileSync(mutationMarker, "utf8"), "mutated");
    } finally {
      try {
        process.kill(parent.pid, "SIGKILL");
      } catch {}
    }
  }));

test("a lingering lifecycle grandchild prevents a false terminal receipt and any replay", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const grandchild = join(root, "grandchild.mjs");
    const worker = join(root, "worker.mjs");
    const driver = join(root, "driver.mjs");
    const configPath = join(root, "operation.json");
    const childMarker = join(root, "grandchild-live");
    const releaseMarker = join(root, "release-grandchild");
    writeFileSync(
      grandchild,
      `import { existsSync, writeFileSync } from "node:fs";\n` +
        `writeFileSync(process.argv[2], String(process.pid));\n` +
        `while (!existsSync(process.argv[3])) await new Promise((resolve) => setTimeout(resolve, 20));\n`,
      { mode: 0o600 },
    );
    writeFileSync(
      worker,
      `import { spawn } from "node:child_process";\n` +
        `const child = spawn(process.execPath, process.argv.slice(2), { detached: false, stdio: "ignore" });\n` +
        `child.unref();\n` +
        `process.stdout.write("direct-child-complete\\n");\n`,
      { mode: 0o600 },
    );
    const operation = {
      privateDirectory,
      operationKey: "purge-initial",
      label: "Synthetic purge with a lingering descendant",
      executable: realpathSync(process.execPath),
      args: [worker, grandchild, childMarker, releaseMarker],
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 20_000,
      candidateIdentitySha256: "c".repeat(64),
    };
    writeFileSync(configPath, `${JSON.stringify(operation)}\n`, { mode: 0o600 });
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    writeFileSync(
      driver,
      `import { readFileSync } from "node:fs";\n` +
        `import { executeLifecycleOperation } from ${JSON.stringify(moduleUrl)};\n` +
        `await executeLifecycleOperation(JSON.parse(readFileSync(process.argv[2], "utf8")));\n`,
      { mode: 0o600 },
    );
    const parent = spawn(realpathSync(process.execPath), [driver, configPath], {
      stdio: "ignore",
    });
    try {
      await waitUntil(() => existsSync(childMarker), "the lingering grandchild did not start");
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 2500));
      const claimed = acceptance.inspectLifecycleOperation(
        privateDirectory,
        "purge-initial",
      );
      assert.equal(claimed.state, "claimed_active");
      assert.equal(claimed.terminalReceiptPresent, false);
      await assert.rejects(
        () => acceptance.executeLifecycleOperation(operation),
        AcceptanceError,
      );
      writeFileSync(releaseMarker, "release\n", { mode: 0o600 });
      await waitUntil(
        () =>
          acceptance.inspectLifecycleOperation(privateDirectory, "purge-initial").state ===
          "blocked_unverifiable",
        "the nonterminal claimed descendant did not become absorbing after quiescence",
      );
      assert.equal(
        acceptance.inspectLifecycleOperation(privateDirectory, "purge-initial")
          .terminalReceiptPresent,
        false,
      );
    } finally {
      if (!existsSync(releaseMarker)) {
        writeFileSync(releaseMarker, "release\n", { mode: 0o600 });
      }
      try {
        process.kill(parent.pid, "SIGKILL");
      } catch {}
    }
  }));

test("CommandRecorder imports one exact lifecycle terminal receipt idempotently", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    mkdirSync(privateDirectory, { mode: 0o700 });
    const worker = join(root, "worker.mjs");
    const countPath = join(root, "count");
    writeFileSync(
      worker,
      `import { existsSync, readFileSync, writeFileSync } from "node:fs";\n` +
        `const target = process.argv[2];\n` +
        `const count = existsSync(target) ? Number(readFileSync(target, "utf8")) : 0;\n` +
        `writeFileSync(target, String(count + 1));\n` +
        `process.stdout.write("terminal output\\n");\n`,
      { mode: 0o600 },
    );
    const options = {
      cwd: root,
      env: {
        HOME: root,
        PATH: dirname(realpathSync(process.execPath)),
        TMPDIR: root,
        LANG: "C",
        LC_ALL: "C",
      },
      timeout: 10_000,
      allowFailure: false,
      persistRaw: true,
      operationKey: "install-initial",
      candidateIdentitySha256: "d".repeat(64),
    };
    const firstReport = makeReport();
    const firstRecorder = new acceptance.CommandRecorder(privateDirectory, firstReport);
    const first = await firstRecorder.runLifecycle(
      "Synthetic exact install",
      realpathSync(process.execPath),
      [worker, countPath],
      options,
    );
    assert.equal(first.status, 0);
    assert.equal(firstReport.commands.length, 1);
    assert.equal(readFileSync(countPath, "utf8"), "1");

    const resumedReport = makeReport();
    const resumedRecorder = new acceptance.CommandRecorder(privateDirectory, resumedReport);
    const resumed = await resumedRecorder.runLifecycle(
      "Synthetic exact install",
      realpathSync(process.execPath),
      [worker, countPath],
      options,
    );
    assert.equal(resumed.recovered, true);
    assert.equal(resumed.id, first.id);
    assert.equal(resumedReport.commands.length, 1);
    assert.equal(readFileSync(countPath, "utf8"), "1");
  }));

test("real packed wrapper reuses its durable lifecycle sandbox when importing a terminal", () =>
  withFixture(async (root) => {
    const privateDirectory = join(root, "private");
    const executionRoot = join(privateDirectory, "isolated-npx");
    const runsRoot = join(executionRoot, "runs");
    mkdirSync(runsRoot, { recursive: true, mode: 0o700 });
    const marker = join(root, "started");
    const release = join(root, "release");
    const count = join(root, "count");
    const fakeNpx = join(root, "fake-npx.mjs");
    writeFileSync(
      fakeNpx,
      `#!${realpathSync(process.execPath)}\n` +
        `import { existsSync, readFileSync, writeFileSync } from "node:fs";\n` +
        `const countPath = ${JSON.stringify(count)};\n` +
        `const current = existsSync(countPath) ? Number(readFileSync(countPath, "utf8")) : 0;\n` +
        `writeFileSync(countPath, String(current + 1));\n` +
        `writeFileSync(${JSON.stringify(marker)}, "started");\n` +
        `while (!existsSync(${JSON.stringify(release)})) await new Promise((resolve) => setTimeout(resolve, 20));\n`,
      { mode: 0o700 },
    );
    chmodSync(fakeNpx, 0o700);
    const checkpointValue = {
      sourceCommit: "a".repeat(40),
      packageArchive: join(root, "opensocrates-1.2.1.tgz"),
      packageSha256: "b".repeat(64),
      manifestSha256: "c".repeat(64),
      rawArtifactPath: join(root, "native.zip"),
      rawArtifactSha256: "d".repeat(64),
      rawArtifactSizeBytes: 1,
      buildSourceReceiptPath: join(root, "build-source.json"),
      buildSourceReceiptSha256: "e".repeat(64),
      sourceTree: "f".repeat(40),
      ciRunId: 1,
      execution: {
        root: executionRoot,
        runsRoot,
        accountHome: realpathSync(homedir()),
        accountUser: userInfo().username,
        npxBinary: realpathSync(fakeNpx),
        npmBinary: realpathSync(process.execPath),
        nodeBinary: realpathSync(process.execPath),
        pythonBinary: realpathSync(process.execPath),
        claudeBinary: realpathSync(process.execPath),
        codexBinary: realpathSync(process.execPath),
        npxBinarySha256: "1".repeat(64),
        npmBinarySha256: "2".repeat(64),
        nodeBinarySha256: "3".repeat(64),
        pythonBinarySha256: "6".repeat(64),
        claudeBinarySha256: "4".repeat(64),
        codexBinarySha256: "5".repeat(64),
      },
      assets: Object.fromEntries(
        ["claude", "codex"].map((host, index) => [
          host,
          {
            archivePath: join(root, `${host}.zip`),
            checksumPath: join(root, `${host}.sha256`),
            sha256: String(index + 4).repeat(64),
            checksumSha256: String(index + 6).repeat(64),
            payloadReceiptSha256: String(index + 8).repeat(64),
            releaseManifestSha256: index === 0 ? "a".repeat(64) : "b".repeat(64),
          },
        ]),
      ),
    };
    const checkpointPath = join(root, "candidate.json");
    writeFileSync(checkpointPath, `${JSON.stringify(checkpointValue)}\n`, { mode: 0o600 });
    const moduleUrl = pathToFileURL(
      join(process.cwd(), "tools", "reinstall_cycle_acceptance.mjs"),
    ).href;
    const driver = join(root, "packed-driver.mjs");
    writeFileSync(
      driver,
      `import { readFileSync } from "node:fs";\n` +
        `import { candidateFromCheckpoint, CommandRecorder, makeReport, purgeCommandArguments, runPackedNpx } from ${JSON.stringify(moduleUrl)};\n` +
        `const checkpoint = JSON.parse(readFileSync(process.argv[2], "utf8"));\n` +
        `const candidate = candidateFromCheckpoint(checkpoint);\n` +
        `const report = makeReport();\n` +
        `const recorder = new CommandRecorder(${JSON.stringify(privateDirectory)}, report);\n` +
        `await runPackedNpx(recorder, "Synthetic real packed purge", candidate, purgeCommandArguments(candidate), { allowFailure: true, invocationMode: "account-home-lifecycle", lifecycleOperationKey: "purge-initial", timeout: 20000 });\n`,
      { mode: 0o600 },
    );
    const parent = spawn(realpathSync(process.execPath), [driver, checkpointPath], {
      stdio: "ignore",
    });
    const priorPath = process.env.PATH;
    try {
      await waitUntil(() => existsSync(marker), "the real packed wrapper did not start");
      process.kill(parent.pid, "SIGKILL");
      writeFileSync(release, "release\n", { mode: 0o600 });
      await waitUntil(
        () =>
          acceptance.inspectLifecycleOperation(privateDirectory, "purge-initial").state ===
          "terminal",
        "the real packed wrapper did not leave an importable terminal",
      );
      process.env.PATH = "/private/path-drift-canary:/usr/bin:/bin";

      const resumedCandidate = acceptance.candidateFromCheckpoint(
        JSON.parse(readFileSync(checkpointPath, "utf8")),
      );
      const resumedReport = makeReport();
      const resumedRecorder = new acceptance.CommandRecorder(privateDirectory, resumedReport);
      const resumed = await acceptance.runPackedNpx(
        resumedRecorder,
        "Synthetic real packed purge",
        resumedCandidate,
        purgeCommandArguments(resumedCandidate),
        {
          allowFailure: true,
          invocationMode: "account-home-lifecycle",
          lifecycleOperationKey: "purge-initial",
          timeout: 20_000,
        },
      );
      assert.equal(resumed.recovered, true);
      assert.equal(readFileSync(count, "utf8"), "1");
      assert.equal(resumedReport.commands.length, 1);
      assert.equal(
        readFileSync(join(privateDirectory, "commands.jsonl"), "utf8")
          .split(/\r?\n/u)
          .filter(Boolean).length,
        1,
      );
    } finally {
      if (priorPath === undefined) delete process.env.PATH;
      else process.env.PATH = priorPath;
      if (!existsSync(release)) writeFileSync(release, "release\n", { mode: 0o600 });
      try {
        process.kill(parent.pid, "SIGKILL");
      } catch {}
    }
  }));

test("machine-wide acceptance lease blocks a second run before its lifecycle callback", () =>
  withFixture((root) => {
    const parent = join(root, "private-parent");
    const firstPrivate = join(parent, "reinstall-cycle-first");
    const secondPrivate = join(parent, "reinstall-cycle-second");
    mkdirSync(firstPrivate, { recursive: true, mode: 0o700 });
    mkdirSync(secondPrivate, { mode: 0o700 });
    const firstTestId = makeReport().testId;
    const secondTestId = makeReport().testId;
    const first = new acceptance.MachineAcceptanceLease(
      parent,
      firstPrivate,
      firstTestId,
      { processId: 41001, processIsLive: (pid) => pid === 41001 },
    );
    first.acquire();

    let lifecycleCallbacks = 0;
    const second = new acceptance.MachineAcceptanceLease(
      parent,
      secondPrivate,
      secondTestId,
      { processId: 41002, processIsLive: () => false },
    );
    assert.throws(() => {
      second.acquire();
      lifecycleCallbacks += 1;
    }, /machine-wide acceptance lease belongs to a different run/u);
    assert.equal(lifecycleCallbacks, 0);
    first.releaseCompleted();
  }));

test("machine-wide acceptance lease preserves pause and permits only the same dead owner resume", () =>
  withFixture((root) => {
    const parent = join(root, "private-parent");
    const privateDirectory = join(parent, "reinstall-cycle-bound");
    mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
    const testId = makeReport().testId;
    const checkpointIdentity = {
      schema: "opensocrates.reinstall-cycle-checkpoint/1.0.0",
      testId,
      sourceCommit: "a".repeat(40),
      reportDirectory: join(root, "public"),
    };
    const first = new acceptance.MachineAcceptanceLease(
      parent,
      privateDirectory,
      testId,
      { processId: 42001, processIsLive: () => false },
    );
    first.acquire();
    first.bindCheckpoint(checkpointIdentity);
    first.markPaused();

    const resumed = new acceptance.MachineAcceptanceLease(
      parent,
      privateDirectory,
      testId,
      { processId: 42002, processIsLive: () => false },
    );
    resumed.acquire(checkpointIdentity);
    assert.equal(resumed.receipt.status, "active");
    assert.equal(resumed.receipt.generation, 2);
    resumed.releaseCompleted(checkpointIdentity);
    assert.equal(existsSync(join(parent, "machine-acceptance-lease.json")), false);
  }));

test("an exact no-mutation preflight abort preserves and retires its machine lease", () =>
  withFixture((root) => {
    const parent = join(root, "private-parent");
    const privateDirectory = join(parent, "reinstall-cycle-aborted");
    const outputDirectory = join(root, "opensocrates-reinstall-cycle-result-aborted");
    mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
    mkdirSync(outputDirectory, { mode: 0o700 });
    const report = makeReport();
    acceptance.initializePrivateEvidenceManifest(
      privateDirectory,
      outputDirectory,
      report,
    );
    new acceptance.CommandRecorder(privateDirectory, report);
    const first = new acceptance.MachineAcceptanceLease(
      parent,
      privateDirectory,
      report.testId,
      { processId: 42501, processIsLive: () => false },
    );
    first.acquire();

    const recovery = new acceptance.MachineAcceptanceLease(
      parent,
      privateDirectory,
      report.testId,
      { processId: 42502, processIsLive: () => false },
    );
    const retired = recovery.recoverAbortedPreflight();
    assert.equal(retired.status, "retired_preflight_without_lifecycle");
    assert.equal(existsSync(join(parent, "machine-acceptance-lease.json")), false);
    const archive = join(privateDirectory, "aborted-machine-lease.json");
    assert.equal(lstatSync(archive).isFile(), true);
    assert.equal(lstatSync(archive).mode & 0o777, 0o600);
    const archived = JSON.parse(readFileSync(archive, "utf8"));
    assert.equal(archived.testId, report.testId);
    assert.equal(archived.receipt.holderPid, 42501);

    const nextPrivate = join(parent, "reinstall-cycle-next");
    mkdirSync(nextPrivate, { mode: 0o700 });
    const next = new acceptance.MachineAcceptanceLease(
      parent,
      nextPrivate,
      makeReport().testId,
      { processId: 42503, processIsLive: () => false },
    );
    let lifecycleCallbacks = 0;
    next.acquire();
    lifecycleCallbacks += 1;
    assert.equal(lifecycleCallbacks, 1);
    next.releaseCompleted();

    const currentParent = join(root, "private-parent-current");
    const currentPrivate = join(currentParent, "reinstall-cycle-current");
    const currentOutput = join(
      root,
      "opensocrates-reinstall-cycle-result-current",
    );
    mkdirSync(currentPrivate, { recursive: true, mode: 0o700 });
    mkdirSync(currentOutput, { mode: 0o700 });
    const currentReport = makeReport();
    acceptance.initializePrivateEvidenceManifest(
      currentPrivate,
      currentOutput,
      currentReport,
    );
    new acceptance.CommandRecorder(currentPrivate, currentReport);
    writeFileSync(
      join(currentPrivate, "run.lock"),
      `${JSON.stringify({ pid: 42504, createdAt: new Date().toISOString() })}\n`,
      { mode: 0o600 },
    );
    const current = new acceptance.MachineAcceptanceLease(
      currentParent,
      currentPrivate,
      currentReport.testId,
      { processId: 42504, processIsLive: () => true },
    );
    current.acquire();
    assert.equal(
      current.releaseAbortedPreflight().status,
      "retired_preflight_without_lifecycle",
    );
    assert.equal(
      existsSync(join(currentParent, "machine-acceptance-lease.json")),
      false,
    );
  }));

test("aborted-preflight lease recovery rejects every ambiguous durable state", () =>
  withFixture((root) => {
    const cases = [
      {
        name: "checkpoint",
        mutate: ({ privateDirectory }) =>
          writeFileSync(join(privateDirectory, "checkpoint.json"), "{}\n", { mode: 0o600 }),
        restore: ({ privateDirectory }) => unlinkSync(join(privateDirectory, "checkpoint.json")),
      },
      {
        name: "lifecycle",
        mutate: ({ privateDirectory }) =>
          mkdirSync(join(privateDirectory, "lifecycle-operations"), { mode: 0o700 }),
        restore: ({ privateDirectory }) =>
          rmSync(join(privateDirectory, "lifecycle-operations"), { recursive: true }),
      },
      {
        name: "public-result",
        mutate: ({ outputDirectory }) =>
          writeFileSync(join(outputDirectory, "result.json"), "{}\n", { mode: 0o600 }),
        restore: ({ outputDirectory }) => unlinkSync(join(outputDirectory, "result.json")),
      },
      {
        name: "live-holder",
        processIsLive: (pid) => pid === 42601,
        mutate: () => {},
        restore: () => {},
      },
    ];
    for (const item of cases) {
      const parent = join(root, `private-parent-${item.name}`);
      const privateDirectory = join(parent, `reinstall-cycle-${item.name}`);
      const outputDirectory = join(
        root,
        `opensocrates-reinstall-cycle-result-${item.name}`,
      );
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      mkdirSync(outputDirectory, { mode: 0o700 });
      const report = makeReport();
      acceptance.initializePrivateEvidenceManifest(
        privateDirectory,
        outputDirectory,
        report,
      );
      new acceptance.CommandRecorder(privateDirectory, report);
      const first = new acceptance.MachineAcceptanceLease(
        parent,
        privateDirectory,
        report.testId,
        { processId: 42601, processIsLive: () => false },
      );
      first.acquire();
      item.mutate({ privateDirectory, outputDirectory });
      const recovery = new acceptance.MachineAcceptanceLease(
        parent,
        privateDirectory,
        report.testId,
        {
          processId: 42602,
          processIsLive: item.processIsLive ?? (() => false),
        },
      );
      assert.throws(
        () => recovery.recoverAbortedPreflight(),
        /cannot be proven to have stopped before lifecycle mutation/u,
      );
      assert.equal(existsSync(join(parent, "machine-acceptance-lease.json")), true);
      assert.equal(
        existsSync(join(privateDirectory, "aborted-machine-lease.json")),
        false,
      );
      item.restore({ privateDirectory, outputDirectory });
      first.releaseCompleted();
    }
  }));

test("machine-wide acceptance lease rejects unsafe and foreign or stale competing receipts", () =>
  withFixture((root) => {
    const makeLayout = (name) => {
      const parent = join(root, name);
      const privateDirectory = join(parent, "reinstall-cycle-owner");
      mkdirSync(privateDirectory, { recursive: true, mode: 0o700 });
      return { parent, privateDirectory, target: join(parent, "machine-acceptance-lease.json") };
    };
    const testId = makeReport().testId;

    {
      const layout = makeLayout("symlink");
      const canary = join(root, "symlink-canary");
      writeFileSync(canary, "unchanged\n", { mode: 0o600 });
      symlinkSync(canary, layout.target);
      const lease = new acceptance.MachineAcceptanceLease(
        layout.parent,
        layout.privateDirectory,
        testId,
      );
      assert.throws(() => lease.acquire(), /not controlled by the current account/u);
      assert.equal(readFileSync(canary, "utf8"), "unchanged\n");
    }

    {
      const layout = makeLayout("hardlink");
      const source = join(root, "hardlink-source");
      writeFileSync(source, "{}\n", { mode: 0o600 });
      linkSync(source, layout.target);
      const lease = new acceptance.MachineAcceptanceLease(
        layout.parent,
        layout.privateDirectory,
        testId,
      );
      assert.throws(() => lease.acquire(), /single-link regular file/u);
    }

    {
      const layout = makeLayout("foreign-owner");
      const lease = new acceptance.MachineAcceptanceLease(
        layout.parent,
        layout.privateDirectory,
        testId,
        { expectedUid: process.getuid() + 1 },
      );
      assert.throws(() => lease.acquire(), /current account/u);
      assert.equal(existsSync(layout.target), false);
    }

    {
      const layout = makeLayout("stale-competing");
      const first = new acceptance.MachineAcceptanceLease(
        layout.parent,
        layout.privateDirectory,
        makeReport().testId,
        { processId: 43001, processIsLive: () => false },
      );
      first.acquire();
      const competingPrivate = join(layout.parent, "reinstall-cycle-competing");
      mkdirSync(competingPrivate, { mode: 0o700 });
      const competing = new acceptance.MachineAcceptanceLease(
        layout.parent,
        competingPrivate,
        makeReport().testId,
        { processId: 43002, processIsLive: () => false },
      );
      assert.throws(
        () => competing.acquire(),
        /machine-wide acceptance lease belongs to a different run/u,
      );
      first.releaseCompleted();
    }
  }));
