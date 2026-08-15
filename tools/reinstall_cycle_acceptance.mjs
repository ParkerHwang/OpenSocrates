#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  accessSync,
  appendFileSync,
  chmodSync,
  closeSync,
  constants as fsConstants,
  copyFileSync,
  createReadStream,
  existsSync,
  fsyncSync,
  linkSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  openSync,
  readSync,
  readFileSync,
  readlinkSync,
  readdirSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir, tmpdir, userInfo } from "node:os";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { gunzipSync, inflateRawSync } from "node:zlib";

import {
  CODEX_TRUST_EVENTS,
  markerMatches,
  PRODUCT_VERSION,
  SUPPORTED_HOSTS,
  purgePathsFor,
  statePaths,
  stripCodexOpenSocratesTrustSections,
  transientPathsFor,
} from "../installer/opensocrates.mjs";
import { inspectManagedLayout } from "./clean_machine_acceptance.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPOSITORY = "ParkerHwang/OpenSocrates";
const RESULT_SCHEMA = "opensocrates.reinstall-cycle-acceptance/1.0.0";
const CHECKPOINT_SCHEMA = "opensocrates.reinstall-cycle-checkpoint/1.0.0";
const PRIVATE_MANIFEST_SCHEMA = "opensocrates.reinstall-cycle-private-evidence/1.0.0";
const DESIRED_STATE_SCHEMA = "opensocrates.desired-state/1.0.0";
const BASELINE = "purged_same_machine";
const HOSTS = Object.freeze(["claude", "codex"]);
const RESULT_FILES = Object.freeze([
  "result.json",
  "result.md",
  "manual-observations.md",
]);
const MANUAL_FIELDS = Object.freeze([
  "Codex seven-hook first review",
  "Codex seven-hook approval completed",
  "Codex SessionStart live timeout absence",
  "Claude Local namespaced status",
  "Record and Replay capture reviewed",
]);
const EXPECTED_CODEX_EVENTS = Object.freeze([
  "postToolUse",
  "preCompact",
  "preToolUse",
  "sessionEnd",
  "sessionStart",
  "stop",
  "userPromptSubmit",
]);
const SESSION_START_PROCESS_MODEL =
  "new_process_per_sample; first_configured_hook_before_runtime_smoke; " +
  "hermetic_generated_input_and_selector_availability_metadata";
const RESULT_DIRECTORY_PREFIX = "opensocrates-reinstall-cycle-result-";
const PRIVATE_PARENT = join(homedir(), ".opensocrates-acceptance-private");
const PRIVATE_DIRECTORY_PREFIX = "reinstall-cycle-";
const CHECKPOINT_NAME = "checkpoint.json";
const COMMAND_LOG_NAME = "commands.jsonl";
const PROJECTION_HELPER = join(ROOT, "tools", "reinstall_cycle_projector.mjs");
const LIFECYCLE_CAPSULE = join(ROOT, "tools", "reinstall_cycle_operation_capsule.mjs");
const LIFECYCLE_OPERATIONS_NAME = "lifecycle-operations";
const LIFECYCLE_INTENT_SCHEMA = "opensocrates.lifecycle-operation-intent/1.0.0";
const LIFECYCLE_CLAIM_SCHEMA = "opensocrates.lifecycle-operation-claim/1.0.0";
const LIFECYCLE_TERMINAL_SCHEMA = "opensocrates.lifecycle-operation-terminal/1.0.0";
const LIFECYCLE_BLOCKED_SCHEMA = "opensocrates.lifecycle-operation-blocked/1.0.0";
const RUN_LOCK_NAME = "run.lock";
const MACHINE_LEASE_NAME = "machine-acceptance-lease.json";
const MACHINE_LEASE_SCHEMA = "opensocrates.reinstall-cycle-machine-lease/1.0.0";
const ABORTED_MACHINE_LEASE_NAME = "aborted-machine-lease.json";
const ABORTED_MACHINE_LEASE_SCHEMA =
  "opensocrates.reinstall-cycle-aborted-machine-lease/1.0.0";
const PRIVATE_MANIFEST_NAME = "private-evidence-manifest.json";
const EVIDENCE_TRANSACTION_NAME = "evidence-transaction.json";
const EVIDENCE_TRANSACTION_SCHEMA = "opensocrates.evidence-transaction/1.0.0";
const PACK_TRANSACTION_NAME = "pack-transaction.json";
const PACK_TRANSACTION_SCHEMA = "opensocrates.pack-transaction/1.0.0";
const SEALED_PUBLIC_DIRECTORY_NAME = "sealed-public-result";
const SEALED_PUBLIC_RECEIPT_NAME = "receipt.json";
const SEALED_PUBLIC_SCHEMA = "opensocrates.sealed-public-result/1.0.0";
const AUTO_UPDATE_LABEL = "com.opensocrates.auto-update";
const UUID_V4_FRAGMENT =
  "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
const UUID_V4_PATTERN = new RegExp(`^${UUID_V4_FRAGMENT}$`, "u");
const STATE_TEMP_PATTERN = new RegExp(
  `^\\.(?:desired-state|auto-update-receipt)\\.json\\.${UUID_V4_FRAGMENT}\\.tmp$`,
  "u",
);
const STATE_PURGE_TOMBSTONE_PATTERN = new RegExp(
  `^\\.purge-finalize-${UUID_V4_FRAGMENT}-(?:desired-state\\.json|auto-update-receipt\\.json|` +
    `\\.(?:desired-state|auto-update-receipt)\\.json\\.${UUID_V4_FRAGMENT}\\.tmp)$`,
  "u",
);
const LAUNCH_AGENT_TEMP_PATTERN = new RegExp(
  `^\\.${AUTO_UPDATE_LABEL.replaceAll(".", "\\.")}\\.plist\\.${UUID_V4_FRAGMENT}\\.tmp$`,
  "u",
);
const TRUST_TRANSACTION_PATTERN =
  /^\.config\.toml\.opensocrates-trust-reset-[A-Za-z0-9-]+\.(?:tmp|rollback)$/u;
const CLAIM_PUBLISH_STAGE_PATTERN = new RegExp(
  `^\\.claimed\\.json\\.[1-9][0-9]*\\.${UUID_V4_FRAGMENT}\\.tmp$`,
  "u",
);
const MAX_COMMAND_OUTPUT_BYTES = 16 * 1024 * 1024;
const MAX_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024;
const ARTIFACT_DOWNLOAD_MIN_BYTES_PER_SECOND = 192 * 1024;
const ARTIFACT_DOWNLOAD_OVERHEAD_MS = 5 * 60 * 1_000;
const MAX_ARTIFACT_DOWNLOAD_TIMEOUT_MS = 3 * 60 * 60 * 1_000;
const MAX_ARCHIVE_ENTRIES = 10_000;
const MAX_ZIP_CENTRAL_DIRECTORY_BYTES = 64 * 1024 * 1024;
const MAX_ZIP_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024;
const MAX_ZIP_ENTRY_BYTES = 2 * 1024 * 1024 * 1024;
const MAX_ZIP_COMPRESSION_RATIO = 1_000;
const ZIP_PROFILES = new Set(["strict-package", "github-artifact-container"]);
const MAX_NPM_TARBALL_BYTES = 64 * 1024 * 1024;
const MAX_NPM_TAR_UNCOMPRESSED_BYTES = 256 * 1024 * 1024;
const MAX_HOST_CLOSE_RETRIES = 1;
const MAX_REINSTALL_RETRIES = 1;
const NPM_INVOCATION_MODES = new Set([
  "isolated-preflight",
  "account-home-lifecycle",
]);
const NPM_PACKAGE_FILES = Object.freeze([
  "CHANGELOG.md",
  "LICENSE",
  "README.ko.md",
  "README.md",
  "SECURITY.md",
  "VERSION",
  "installer/opensocrates.mjs",
  "package.json",
]);
const NPM_PACKAGE_FILES_FIELD = Object.freeze([
  "installer/opensocrates.mjs",
  "CHANGELOG.md",
  "SECURITY.md",
  "VERSION",
]);
const NPM_PACKAGE_SCRIPTS = Object.freeze({
  test: "node --test installer/opensocrates.test.mjs installer/lifecycle.test.mjs tools/clean_machine_acceptance.test.mjs tools/reinstall_cycle_acceptance.test.mjs tools/opencode_bridge.test.mjs tools/release_gate.test.mjs && npm run test:npx",
  "test:npx": "node installer/package-smoke.mjs",
  "pack:check": "npm pack --dry-run",
  prepublishOnly: "npm test",
});
const CHECKPOINT_PHASES = new Set([
  "ready-to-purge",
  "purging",
  "awaiting-host-close",
  "purge-retry-in-progress",
  "purge-complete-unverified",
  "purged",
  "reinstalling",
  "reinstall-retry-in-progress",
  "reinstall-failed",
  "post-install-checks",
  "post-install-failed",
  "purge-failed",
  "blocked-unverifiable",
  "finalizing",
  "final-verified",
  "installed",
]);
const FORBIDDEN_PUBLIC_KEYS = new Set([
  "absolutePath",
  "account",
  "args",
  "command",
  "credential",
  "cwd",
  "eventsPath",
  "metadataPath",
  "path",
  "prompt",
  "rawOutput",
  "stderr",
  "stdout",
  "transcript",
  "user",
  "username",
  "hostname",
  "computerName",
]);
const PUBLIC_REPORT_KEYS = new Set([
  "schema",
  "testId",
  "generatedAt",
  "completedAt",
  "source",
  "environment",
  "baseline",
  "mutation",
  "commands",
  "steps",
  "assertions",
  "automatedResult",
  "manualResult",
  "overallResult",
  "manualObservations",
  "limitations",
  "failure",
  "privacy",
]);
const PUBLIC_SOURCE_KEYS = new Set([
  "repository",
  "pullRequest",
  "pullRequestUrl",
  "version",
  "commit",
  "tree",
  "ciRunId",
  "ciRunUrl",
  "ci",
  "npmPackage",
  "assets",
  "publicReleaseV121",
]);
const PUBLIC_ENVIRONMENT_KEYS = new Set([
  "platform",
  "nodeVersion",
  "hardwareArchitecture",
  "processArchitecture",
  "identity",
  "claudeVersion",
  "codexVersion",
]);
const PUBLIC_BASELINE_KEYS = new Set([
  "kind",
  "expectedInitialState",
  "expectedFinalState",
  "initialState",
  "installedHosts",
  "inventory",
]);
const PUBLIC_MUTATION_KEYS = new Set([
  "started",
  "phase",
  "lifecycleOutcome",
  "purgeCommandAttempts",
  "trustResetAttempts",
  "reinstallAttempts",
  "hostCloseRetriesUsed",
  "reinstallAttempted",
  "finalState",
  "nextAction",
  "originalCacheDataTrustRestorationClaimed",
]);
const PUBLIC_LIMITATION_KEYS = new Set([
  "claudeChatStandaloneV121",
  "cleanMachineClaimed",
  "publicRegistryPathVerified",
]);
const PUBLIC_PRIVACY_KEYS = new Set([
  "privateCommandLogRecorded",
  "rawCommandOutputIncluded",
  "rawRecordingIncluded",
  "accessibilitySnapshotIncluded",
  "promptsIncluded",
  "transcriptsIncluded",
  "sidebarTextIncluded",
  "authenticationIdentityIncluded",
  "credentialsIncluded",
  "absoluteLocalPathsIncluded",
  "unrelatedHistoryContentRead",
  "unrelatedHistoryMutationAttempted",
]);
const PUBLIC_ASSERTION_KEYS = new Set([
  "codexFirstApproval",
  "deferredInUse",
  "deferredResidue",
  "failureState",
  "finalArchitecture",
  "finalChecksum",
  "finalDesiredState",
  "finalManagedLayout",
  "finalPermissions",
  "finalRegistration",
  "finalStatus",
  "finalTopology",
  "finalVersion",
  "lifecycleRecovery",
  "sessionStartBudget",
  "zeroResidue",
]);
const PUBLIC_COMMAND_KEYS = new Set([
  "id",
  "label",
  "exitStatus",
  "durationMs",
  "stdoutSha256",
  "stderrSha256",
]);
const PUBLIC_STEP_KEYS = new Set([
  "id",
  "label",
  "status",
  "durationMs",
  "category",
  "commandId",
]);

const CODEX_HOOK_PROBE_SOURCE = String.raw`
import { spawn } from "node:child_process";
import readline from "node:readline";

const child = spawn("codex", ["app-server", "--stdio"], {
  cwd: process.cwd(),
  env: process.env,
  stdio: ["pipe", "pipe", "pipe"],
});
const output = [];
const errors = [];
let response = null;
let initialized = false;
let settled = false;
let deadline;

function finish(code) {
  if (settled) return;
  settled = true;
  clearTimeout(deadline);
  try { child.stdin.end(); } catch {}
  if (code !== 0) {
    try { child.kill("SIGTERM"); } catch {}
  }
  process.exitCode = code;
}

const lines = readline.createInterface({ input: child.stdout });
lines.on("line", (line) => {
  output.push(line);
  let message;
  try { message = JSON.parse(line); } catch { return finish(1); }
  if (message.id === 1 && !initialized) {
    initialized = true;
    child.stdin.write(JSON.stringify({
      id: 2,
      method: "hooks/list",
      params: { cwds: [process.cwd()] },
    }) + "\n");
    return;
  }
  if (message.id === 2) {
    response = message;
    const entries = Array.isArray(message?.result?.data) ? message.result.data : null;
    if (entries === null) return finish(1);
    const hooks = entries.flatMap((entry) => Array.isArray(entry?.hooks) ? entry.hooks : []);
    const selected = hooks
      .filter((hook) => hook?.pluginId === "opensocrates@opensocrates")
      .map((hook) => ({
        eventName: hook.eventName,
        namespace: hook.pluginId,
        timeoutSec: hook.timeoutSec,
        trustStatus: hook.trustStatus,
      }));
    const errorCount = entries.reduce(
      (count, entry) => count + (Array.isArray(entry?.errors) ? entry.errors.length : 0),
      0,
    );
    const warningCount = entries.reduce(
      (count, entry) => count + (Array.isArray(entry?.warnings) ? entry.warnings.length : 0),
      0,
    );
    process.stdout.write(JSON.stringify({
      schema: "opensocrates.codex-hook-inventory/1.0.0",
      errorCount,
      warningCount,
      hooks: selected,
    }) + "\n");
    finish(0);
  }
});
child.stderr.on("data", (chunk) => errors.push(Buffer.from(chunk)));
child.once("error", () => finish(1));
child.once("close", (code) => {
  if (!settled) finish(code === 0 && response !== null ? 0 : 1);
});
child.stdin.write(JSON.stringify({
  id: 1,
  method: "initialize",
  params: {
    clientInfo: {
      name: "opensocrates_reinstall_acceptance",
      title: "OpenSocrates Reinstall Acceptance",
      version: "1.0.0",
    },
    capabilities: { experimentalApi: true },
  },
}) + "\n");
deadline = setTimeout(() => finish(1), 15000);
`;

class AcceptanceError extends Error {
  constructor(category, message, commandId = null) {
    super(message);
    this.name = "AcceptanceError";
    this.category = category;
    this.commandId = commandId;
  }
}

function fail(category, message, commandId = null) {
  throw new AcceptanceError(category, message, commandId);
}

function sorted(values) {
  return [...values].sort();
}

function sameStrings(left, right) {
  return JSON.stringify(sorted(left)) === JSON.stringify(sorted(right));
}

function parseJson(text, category, message) {
  try {
    return JSON.parse(text);
  } catch {
    fail(category, message);
  }
}

function pathPresent(target) {
  try {
    lstatSync(target);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

function writePrivate(target, contents) {
  writeFileSync(target, contents, { encoding: "utf8", mode: 0o600 });
  chmodSync(target, 0o600);
}

function syncEntry(target) {
  const descriptor = openSync(target, "r");
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

function atomicWritePrivate(target, contents) {
  const parent = dirname(target);
  requireCanonicalOwnedEntry(parent, "private atomic-write parent", "directory");
  requireOwnerOnly(parent, "the private atomic-write parent");
  if (pathPresent(target)) requireCanonicalOwnedEntry(target, "private atomic-write target", "file");
  const temporary = join(parent, `.${basename(target)}.${randomUUID()}.tmp`);
  try {
    writeFileSync(temporary, contents, { encoding: "utf8", mode: 0o600, flag: "wx" });
    chmodSync(temporary, 0o600);
    syncEntry(temporary);
    renameSync(temporary, target);
    syncEntry(parent);
  } finally {
    if (pathPresent(temporary)) {
      const info = lstatSync(temporary);
      if (!info.isSymbolicLink() && info.isFile() && info.uid === currentUid()) unlinkSync(temporary);
    }
  }
}

function ensurePrivateDirectory(target) {
  if (!pathPresent(target)) mkdirSync(target, { recursive: true, mode: 0o700 });
  const info = lstatSync(target);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail("private-evidence", "the private evidence directory is unsafe");
  }
  chmodSync(target, 0o700);
}

class SingleRunLock {
  constructor(privateDirectory) {
    this.target = join(privateDirectory, RUN_LOCK_NAME);
    this.identity = null;
  }

  acquire() {
    if (pathPresent(this.target)) {
      requireCanonicalOwnedEntry(this.target, "private acceptance run lock", "file");
      requireOwnerOnly(this.target, "the private acceptance run lock");
      const existing = parseJson(
        readFileSync(this.target, "utf8"),
        "run-lock",
        "the private acceptance run lock is invalid",
      );
      if (!Number.isSafeInteger(existing?.pid) || existing.pid <= 0) {
        fail("run-lock", "the private acceptance run lock has an invalid process identity");
      }
      let live = false;
      try {
        process.kill(existing.pid, 0);
        live = true;
      } catch (error) {
        if (error?.code === "EPERM") live = true;
        else if (error?.code !== "ESRCH") fail("run-lock", "the existing run lock cannot be checked safely");
      }
      if (live) fail("run-lock", "another acceptance process still owns this private run");
      unlinkSync(this.target);
    }
    const descriptor = openSync(this.target, "wx", 0o600);
    try {
      writeFileSync(descriptor, `${JSON.stringify({ pid: process.pid, createdAt: new Date().toISOString() })}\n`);
      fsyncSync(descriptor);
    } finally {
      closeSync(descriptor);
    }
    chmodSync(this.target, 0o600);
    const info = lstatSync(this.target);
    this.identity = { dev: info.dev, ino: info.ino };
    syncEntry(dirname(this.target));
  }

  release() {
    if (this.identity === null || !pathPresent(this.target)) return;
    const info = requireCanonicalOwnedEntry(this.target, "private acceptance run lock", "file");
    if (info.dev !== this.identity.dev || info.ino !== this.identity.ino) {
      fail("run-lock", "the private acceptance run lock changed while active");
    }
    unlinkSync(this.target);
    syncEntry(dirname(this.target));
    this.identity = null;
  }
}

function processIdentityIsLive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error?.code === "EPERM") return true;
    if (error?.code === "ESRCH") return false;
    fail("machine-lease", "the machine-wide acceptance lease owner cannot be checked safely");
  }
}

function checkpointLeaseIdentity(checkpoint) {
  if (
    checkpoint?.schema !== CHECKPOINT_SCHEMA ||
    !UUID_V4_PATTERN.test(checkpoint?.testId ?? "") ||
    !/^[a-f0-9]{40}$/u.test(checkpoint?.sourceCommit ?? "") ||
    typeof checkpoint?.reportDirectory !== "string" ||
    resolve(checkpoint.reportDirectory) !== checkpoint.reportDirectory
  ) {
    fail("machine-lease", "the checkpoint cannot be bound to the machine-wide acceptance lease");
  }
  return sha256Buffer(
    JSON.stringify({
      schema: checkpoint.schema,
      testId: checkpoint.testId,
      sourceCommit: checkpoint.sourceCommit,
      reportDirectory: checkpoint.reportDirectory,
    }),
  );
}

export class MachineAcceptanceLease {
  constructor(
    parent,
    privateDirectory,
    testId,
    {
      processId = process.pid,
      processIsLive = processIdentityIsLive,
      expectedUid = currentUid(),
    } = {},
  ) {
    if (
      !UUID_V4_PATTERN.test(testId ?? "") ||
      !Number.isSafeInteger(processId) ||
      processId <= 1 ||
      typeof processIsLive !== "function" ||
      !Number.isSafeInteger(expectedUid) ||
      expectedUid < 0
    ) {
      fail("machine-lease", "the machine-wide acceptance lease identity is invalid");
    }
    this.parent = resolve(parent);
    this.privateDirectory = resolve(privateDirectory);
    this.target = join(this.parent, MACHINE_LEASE_NAME);
    this.testId = testId;
    this.processId = processId;
    this.processIsLive = processIsLive;
    this.expectedUid = expectedUid;
    this.holderId = randomUUID();
    this.currentReceipt = null;
  }

  get receipt() {
    return this.currentReceipt === null ? null : structuredClone(this.currentReceipt);
  }

  #requireEntry(target, label, expectedKind, expectedMode) {
    const info = lstatSync(target);
    if (info.isSymbolicLink() || info.uid !== this.expectedUid) {
      fail("machine-lease", `${label} is not controlled by the current account`);
    }
    if (expectedKind === "directory" && !info.isDirectory()) {
      fail("machine-lease", `${label} is not an owner-controlled canonical entry`);
    }
    if (expectedKind === "file" && (!info.isFile() || info.nlink !== 1)) {
      fail("machine-lease", `${label} is not a single-link regular file`);
    }
    if ((info.mode & 0o777) !== expectedMode || realpathSync(target) !== resolve(target)) {
      fail("machine-lease", `${label} is not an owner-controlled canonical entry`);
    }
    return info;
  }

  #requireLayout() {
    this.#requireEntry(this.parent, "the machine-wide acceptance parent", "directory", 0o700);
    this.#requireEntry(
      this.privateDirectory,
      "the bound private acceptance directory",
      "directory",
      0o700,
    );
    if (
      dirname(this.privateDirectory) !== this.parent ||
      !basename(this.privateDirectory).startsWith(PRIVATE_DIRECTORY_PREFIX)
    ) {
      fail("machine-lease", "the machine-wide lease is not bound to one acceptance run directory");
    }
  }

  #validateReceipt() {
    this.#requireEntry(this.target, "the machine-wide acceptance lease", "file", 0o600);
    const raw = readFileSync(this.target, "utf8");
    const receipt = parseJson(
      raw,
      "machine-lease",
      "the machine-wide acceptance lease receipt is invalid",
    );
    requireExactObjectKeys(
      receipt,
      [
        "schema",
        "testId",
        "privateDirectory",
        "checkpointIdentitySha256",
        "status",
        "holderId",
        "holderPid",
        "generation",
        "createdAt",
        "updatedAt",
        "previousReceiptSha256",
      ],
      "machine-lease",
      "the machine-wide acceptance lease receipt",
    );
    const validTime = (value) =>
      typeof value === "string" &&
      Number.isFinite(Date.parse(value)) &&
      new Date(value).toISOString() === value;
    if (
      receipt.schema !== MACHINE_LEASE_SCHEMA ||
      !UUID_V4_PATTERN.test(receipt.testId ?? "") ||
      typeof receipt.privateDirectory !== "string" ||
      resolve(receipt.privateDirectory) !== receipt.privateDirectory ||
      !(
        receipt.checkpointIdentitySha256 === null ||
        /^[a-f0-9]{64}$/u.test(receipt.checkpointIdentitySha256 ?? "")
      ) ||
      !new Set(["active", "paused"]).has(receipt.status) ||
      !UUID_V4_PATTERN.test(receipt.holderId ?? "") ||
      !Number.isSafeInteger(receipt.generation) ||
      receipt.generation < 1 ||
      !validTime(receipt.createdAt) ||
      !validTime(receipt.updatedAt) ||
      !(
        receipt.previousReceiptSha256 === null ||
        /^[a-f0-9]{64}$/u.test(receipt.previousReceiptSha256 ?? "")
      ) ||
      (receipt.status === "active" &&
        (!Number.isSafeInteger(receipt.holderPid) || receipt.holderPid <= 1)) ||
      (receipt.status === "paused" && receipt.holderPid !== null)
    ) {
      fail("machine-lease", "the machine-wide acceptance lease receipt is invalid");
    }
    return { receipt, sha256: sha256Buffer(raw) };
  }

  #publishExclusive(receipt) {
    const staging = join(this.parent, `.${MACHINE_LEASE_NAME}.${randomUUID()}.tmp`);
    let descriptor = null;
    try {
      descriptor = openSync(
        staging,
        fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
        0o600,
      );
      writeFileSync(descriptor, `${JSON.stringify(receipt, null, 2)}\n`);
      fsyncSync(descriptor);
      closeSync(descriptor);
      descriptor = null;
      chmodSync(staging, 0o600);
      this.#requireEntry(staging, "the staged machine-wide acceptance lease", "file", 0o600);
      try {
        linkSync(staging, this.target);
      } catch (error) {
        if (error?.code === "EEXIST") {
          fail("machine-lease", "another run won the machine-wide acceptance lease");
        }
        throw error;
      }
      syncEntry(this.parent);
      unlinkSync(staging);
      syncEntry(this.parent);
      this.currentReceipt = this.#validateReceipt().receipt;
    } finally {
      if (descriptor !== null) closeSync(descriptor);
      if (pathPresent(staging)) {
        const info = lstatSync(staging);
        if (
          !info.isSymbolicLink() &&
          info.isFile() &&
          info.uid === this.expectedUid &&
          resolve(staging) === realpathSync(staging)
        ) {
          unlinkSync(staging);
          syncEntry(this.parent);
        }
      }
    }
  }

  #replace(receipt) {
    atomicWritePrivate(this.target, `${JSON.stringify(receipt, null, 2)}\n`);
    this.currentReceipt = this.#validateReceipt().receipt;
  }

  #requireCurrentHolder() {
    const existing = this.#validateReceipt();
    if (
      existing.receipt.testId !== this.testId ||
      existing.receipt.privateDirectory !== this.privateDirectory ||
      existing.receipt.holderId !== this.holderId ||
      existing.receipt.holderPid !== this.processId ||
      existing.receipt.status !== "active"
    ) {
      fail("machine-lease", "the machine-wide acceptance lease changed owners");
    }
    return existing;
  }

  #abortedPreflightCannotBeProven() {
    fail(
      "machine-lease",
      "the abandoned acceptance lease cannot be proven to have stopped before lifecycle mutation",
    );
  }

  #validateAbortedPreflightEvidence(existing, { allowCurrentRunLock = false } = {}) {
    const reject = () => this.#abortedPreflightCannotBeProven();
    const receipt = existing.receipt;
    if (
      receipt.testId !== this.testId ||
      receipt.privateDirectory !== this.privateDirectory ||
      receipt.status !== "active" ||
      receipt.checkpointIdentitySha256 !== null
    ) {
      reject();
    }
    for (const name of [
      CHECKPOINT_NAME,
      EVIDENCE_TRANSACTION_NAME,
      PACK_TRANSACTION_NAME,
      SEALED_PUBLIC_DIRECTORY_NAME,
      LIFECYCLE_OPERATIONS_NAME,
    ]) {
      if (pathPresent(join(this.privateDirectory, name))) reject();
    }
    const runLock = join(this.privateDirectory, RUN_LOCK_NAME);
    if (pathPresent(runLock)) {
      if (!allowCurrentRunLock) reject();
      requireExactPrivateMode(runLock, "the current aborted-preflight run lock", "file", 0o600);
      const lock = parseJson(
        readFileSync(runLock, "utf8"),
        "machine-lease",
        "the current aborted-preflight run lock is invalid",
      );
      requireExactObjectKeys(
        lock,
        ["pid", "createdAt"],
        "machine-lease",
        "the current aborted-preflight run lock",
      );
      if (lock.pid !== this.processId) reject();
    }
    const manifest = readPrivateEvidenceManifest(this.privateDirectory);
    const absentPublicLinkage = [
      manifest.publicResult.resultJsonSha256,
      manifest.publicResult.automatedResultSha256,
      manifest.publicResult.sealedReceiptSha256,
      manifest.publicResult.finalizationId,
      manifest.publicResult.finalVerificationSha256,
      manifest.publicResult.diagnosticZipSha256,
      manifest.publicResult.publicZipSha256,
    ];
    if (
      manifest.testId !== this.testId ||
      absentPublicLinkage.some((value) => value !== null) ||
      manifest.recording.status !== "pending" ||
      manifest.recording.receiptRelativePath !== null ||
      manifest.recording.receiptSha256 !== null ||
      manifest.recording.recordingSha256 !== null ||
      manifest.recording.reviewStatus !== "pending" ||
      manifest.retention.status !== "active" ||
      manifest.retention.cleanupAuthorized !== false
    ) {
      reject();
    }
    const outputDirectory = manifest.publicResult.directory;
    if (
      typeof outputDirectory !== "string" ||
      resolve(outputDirectory) !== outputDirectory ||
      !basename(outputDirectory).startsWith(RESULT_DIRECTORY_PREFIX)
    ) {
      reject();
    }
    requireExactPrivateMode(
      outputDirectory,
      "the aborted-preflight public result directory",
      "directory",
      0o700,
    );
    if (readdirSync(outputDirectory).length !== 0) reject();

    const ledgerPath = join(this.privateDirectory, COMMAND_LOG_NAME);
    requireExactPrivateMode(ledgerPath, "the aborted-preflight command ledger", "file", 0o600);
    const ledgerContents = readFileSync(ledgerPath, "utf8");
    const ledger = commandLedgerStateFromContents(ledgerContents);
    if (
      ledger.sha256 !== manifest.commandLedger.sha256 ||
      ledger.entryCount !== manifest.commandLedger.entryCount
    ) {
      reject();
    }
    const entries = ledgerContents
      .split(/\r?\n/u)
      .filter(Boolean)
      .map((line) =>
        parseJson(
          line,
          "machine-lease",
          "the aborted-preflight command ledger is invalid",
        ),
      );
    if (
      entries.some(
        (entry) =>
          entry.lifecycleOperation !== null && entry.lifecycleOperation !== undefined,
      ) ||
      entries.some(
        (entry) =>
          !Array.isArray(entry.args) ||
          entry.args.some((argument) => argument === "remove" || argument === "install"),
      )
    ) {
      reject();
    }
    const commandDirectory = join(this.privateDirectory, "commands");
    requireExactPrivateMode(
      commandDirectory,
      "the aborted-preflight command output directory",
      "directory",
      0o700,
    );
    new CommandRecorder(this.privateDirectory, { commands: [] });
    return { manifest, ledger };
  }

  #archiveAndRetireAbortedPreflight(existing) {
    const archivePath = join(this.privateDirectory, ABORTED_MACHINE_LEASE_NAME);
    let archive;
    if (pathPresent(archivePath)) {
      requireExactPrivateMode(
        archivePath,
        "the archived aborted-preflight machine lease",
        "file",
        0o600,
      );
      archive = parseJson(
        readFileSync(archivePath, "utf8"),
        "machine-lease",
        "the archived aborted-preflight machine lease is invalid",
      );
    } else {
      archive = {
        schema: ABORTED_MACHINE_LEASE_SCHEMA,
        testId: existing.receipt.testId,
        privateDirectory: existing.receipt.privateDirectory,
        leaseReceiptSha256: existing.sha256,
        retiredAt: new Date().toISOString(),
        status: "retired_preflight_without_lifecycle",
        receipt: existing.receipt,
      };
      atomicWritePrivate(archivePath, `${JSON.stringify(archive, null, 2)}\n`);
    }
    requireExactObjectKeys(
      archive,
      [
        "schema",
        "testId",
        "privateDirectory",
        "leaseReceiptSha256",
        "retiredAt",
        "status",
        "receipt",
      ],
      "machine-lease",
      "the archived aborted-preflight machine lease",
    );
    if (
      archive.schema !== ABORTED_MACHINE_LEASE_SCHEMA ||
      archive.testId !== existing.receipt.testId ||
      archive.privateDirectory !== existing.receipt.privateDirectory ||
      archive.leaseReceiptSha256 !== existing.sha256 ||
      archive.status !== "retired_preflight_without_lifecycle" ||
      !Number.isFinite(Date.parse(archive.retiredAt ?? "")) ||
      new Date(archive.retiredAt).toISOString() !== archive.retiredAt ||
      sha256Buffer(`${JSON.stringify(archive.receipt, null, 2)}\n`) !== existing.sha256
    ) {
      this.#abortedPreflightCannotBeProven();
    }
    unlinkSync(this.target);
    syncEntry(this.parent);
    this.currentReceipt = null;
    return {
      status: archive.status,
      leaseReceiptSha256: archive.leaseReceiptSha256,
      archiveSha256: sha256FileSync(archivePath),
    };
  }

  releaseAbortedPreflight() {
    const existing = this.#requireCurrentHolder();
    this.#validateAbortedPreflightEvidence(existing, { allowCurrentRunLock: true });
    return this.#archiveAndRetireAbortedPreflight(existing);
  }

  recoverAbortedPreflight() {
    this.#requireLayout();
    const existing = this.#validateReceipt();
    if (
      existing.receipt.testId !== this.testId ||
      existing.receipt.privateDirectory !== this.privateDirectory ||
      existing.receipt.status !== "active" ||
      this.processIsLive(existing.receipt.holderPid)
    ) {
      this.#abortedPreflightCannotBeProven();
    }
    this.#validateAbortedPreflightEvidence(existing);
    return this.#archiveAndRetireAbortedPreflight(existing);
  }

  acquire(checkpoint = null) {
    this.#requireLayout();
    const checkpointIdentitySha256 =
      checkpoint === null ? null : checkpointLeaseIdentity(checkpoint);
    if (!pathPresent(this.target)) {
      const now = new Date().toISOString();
      this.#publishExclusive({
        schema: MACHINE_LEASE_SCHEMA,
        testId: this.testId,
        privateDirectory: this.privateDirectory,
        checkpointIdentitySha256,
        status: "active",
        holderId: this.holderId,
        holderPid: this.processId,
        generation: 1,
        createdAt: now,
        updatedAt: now,
        previousReceiptSha256: null,
      });
      return this.receipt;
    }
    const existing = this.#validateReceipt();
    if (
      existing.receipt.testId !== this.testId ||
      existing.receipt.privateDirectory !== this.privateDirectory
    ) {
      fail("machine-lease", "the machine-wide acceptance lease belongs to a different run");
    }
    if (
      existing.receipt.checkpointIdentitySha256 !== null &&
      checkpointIdentitySha256 !== existing.receipt.checkpointIdentitySha256
    ) {
      fail("machine-lease", "the machine-wide acceptance lease checkpoint binding changed");
    }
    if (
      existing.receipt.status === "active" &&
      this.processIsLive(existing.receipt.holderPid)
    ) {
      fail("machine-lease", "the machine-wide acceptance lease owner is still active");
    }
    this.#replace({
      ...existing.receipt,
      checkpointIdentitySha256:
        existing.receipt.checkpointIdentitySha256 ?? checkpointIdentitySha256,
      status: "active",
      holderId: this.holderId,
      holderPid: this.processId,
      generation: existing.receipt.generation + 1,
      updatedAt: new Date().toISOString(),
      previousReceiptSha256: existing.sha256,
    });
    return this.receipt;
  }

  bindCheckpoint(checkpoint) {
    const checkpointIdentitySha256 = checkpointLeaseIdentity(checkpoint);
    const existing = this.#requireCurrentHolder();
    if (
      existing.receipt.checkpointIdentitySha256 !== null &&
      existing.receipt.checkpointIdentitySha256 !== checkpointIdentitySha256
    ) {
      fail("machine-lease", "the machine-wide acceptance lease checkpoint binding changed");
    }
    this.#replace({
      ...existing.receipt,
      checkpointIdentitySha256,
      updatedAt: new Date().toISOString(),
      previousReceiptSha256: existing.sha256,
    });
    return this.receipt;
  }

  markPaused() {
    const existing = this.#requireCurrentHolder();
    if (existing.receipt.checkpointIdentitySha256 === null) {
      fail("machine-lease", "an unbound machine-wide acceptance lease cannot be paused");
    }
    this.#replace({
      ...existing.receipt,
      status: "paused",
      holderPid: null,
      updatedAt: new Date().toISOString(),
      previousReceiptSha256: existing.sha256,
    });
    return this.receipt;
  }

  releaseCompleted(checkpoint = null) {
    const existing = this.#validateReceipt();
    const expectedCheckpoint =
      checkpoint === null ? existing.receipt.checkpointIdentitySha256 : checkpointLeaseIdentity(checkpoint);
    if (
      existing.receipt.testId !== this.testId ||
      existing.receipt.privateDirectory !== this.privateDirectory ||
      existing.receipt.holderId !== this.holderId ||
      existing.receipt.status !== "active" ||
      existing.receipt.holderPid !== this.processId ||
      existing.receipt.checkpointIdentitySha256 !== expectedCheckpoint
    ) {
      fail("machine-lease", "the completed run no longer owns its exact machine-wide lease");
    }
    unlinkSync(this.target);
    syncEntry(this.parent);
    this.currentReceipt = null;
  }
}

async function sha256File(target) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(target)) hash.update(chunk);
  return hash.digest("hex");
}

function sha256Buffer(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sanitizedMessage(error, replacements = []) {
  let value = error instanceof Error ? error.message : String(error);
  for (const [target, replacement] of [
    [homedir(), "$HOME"],
    [ROOT, "$CHECKOUT"],
    ...replacements,
  ]) {
    if (target) value = value.split(target).join(replacement);
  }
  return value
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/giu, "[redacted-email]")
    .replace(/\b(?:gh[opusr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/gu, "[redacted-token]")
    .replace(/\/(?:Users|private|var|tmp|Volumes)(?:\/[^\s`'"]+)+/gu, "[redacted-path]")
    .replace(/[\r\n]+/gu, " ")
    .slice(0, 500);
}

function assertNoForbiddenPublicKeys(value, trail = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoForbiddenPublicKeys(item, [...trail, String(index)]));
    return;
  }
  if (value === null || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    if (FORBIDDEN_PUBLIC_KEYS.has(key)) {
      fail("privacy", `public evidence contains a forbidden field: ${[...trail, key].join(".")}`);
    }
    assertNoForbiddenPublicKeys(item, [...trail, key]);
  }
}

function publicValueKind(value) {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function containsPublicAbsolutePath(value) {
  const scrubbed = value.replace(
    /\/opensocrates(?::opensocrates)?(?=$|[\s`"'.,)])/gu,
    "[allowed-opensocrates-command]",
  );
  return /(?:^|[\s("'`=])\/(?!\/)[^\s"'`]+/u.test(scrubbed);
}

function requirePublicKind(value, allowedKinds, trail) {
  const kind = publicValueKind(value);
  if (!allowedKinds.includes(kind)) {
    fail("privacy", `public evidence field ${trail} has an unsupported type`);
  }
}

function requirePublicObject(value, trail) {
  requirePublicKind(value, ["object"], trail);
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    fail("privacy", `public evidence field ${trail} is not a plain object`);
  }
}

function requirePublicKeys(value, allowed, trail, { exact = true } = {}) {
  requirePublicObject(value, trail);
  const keys = Object.keys(value);
  const unknown = keys.filter((key) => !allowed.has(key));
  const missing = exact ? [...allowed].filter((key) => !Object.hasOwn(value, key)) : [];
  if (unknown.length > 0 || missing.length > 0) {
    fail("privacy", `public evidence field ${trail} does not match the typed allowlist`);
  }
}

function validatePublicJsonTypes(value, trail = "result", seen = new WeakSet()) {
  const kind = publicValueKind(value);
  if (kind === "undefined" || kind === "function" || kind === "symbol" || kind === "bigint") {
    fail("privacy", `public evidence field ${trail} is not a JSON value`);
  }
  if (kind === "number" && !Number.isFinite(value)) {
    fail("privacy", `public evidence field ${trail} is not a finite number`);
  }
  if (kind === "string") {
    if (containsPublicAbsolutePath(value)) {
      fail("privacy", `public evidence field ${trail} contains an absolute local path`);
    }
    if (/(?:^|\s)(?:stdout|stderr)\s*:/iu.test(value)) {
      fail("privacy", `public evidence field ${trail} contains a raw-stream marker`);
    }
    if (/\bsk-ant-[A-Za-z0-9_-]{12,}\b/u.test(value)) {
      fail("privacy", `public evidence field ${trail} contains a credential-like token`);
    }
  }
  if (kind === "array") {
    if (seen.has(value)) fail("privacy", "public evidence contains a cyclic array");
    seen.add(value);
    value.forEach((item, index) => validatePublicJsonTypes(item, `${trail}.${index}`, seen));
    seen.delete(value);
    return;
  }
  if (kind !== "object") return;
  requirePublicObject(value, trail);
  if (seen.has(value)) fail("privacy", "public evidence contains a cyclic object");
  seen.add(value);
  for (const [key, item] of Object.entries(value)) {
    validatePublicJsonTypes(item, `${trail}.${key}`, seen);
  }
  seen.delete(value);
}

function requirePublicFields(value, required, optional, trail) {
  const allowed = new Set([...required, ...optional]);
  requirePublicKeys(value, allowed, trail, { exact: false });
  for (const key of required) {
    if (!Object.hasOwn(value, key)) {
      fail("privacy", `public evidence field ${trail}.${key} is missing`);
    }
  }
}

function requirePublicScalar(value, kinds, trail) {
  requirePublicKind(value, kinds, trail);
}

function requirePublicStringArray(value, trail) {
  requirePublicKind(value, ["array"], trail);
  value.forEach((item, index) => requirePublicScalar(item, ["string"], `${trail}.${index}`));
}

function requirePublicHostMap(value, hosts, trail, validator) {
  requirePublicKeys(value, new Set(hosts), trail);
  for (const host of hosts) validator(value[host], `${trail}.${host}`, host);
}

function validatePublicRegistration(value, trail) {
  requirePublicFields(
    value,
    [
      "marketplaceCount",
      "pluginCount",
      "version",
      "unsupportedLegacyConflictCount",
      "rootMatchesExpected",
    ],
    [],
    trail,
  );
  requirePublicScalar(value.marketplaceCount, ["number"], `${trail}.marketplaceCount`);
  requirePublicScalar(value.pluginCount, ["number"], `${trail}.pluginCount`);
  requirePublicScalar(value.version, ["string", "null"], `${trail}.version`);
  requirePublicScalar(
    value.unsupportedLegacyConflictCount,
    ["number"],
    `${trail}.unsupportedLegacyConflictCount`,
  );
  requirePublicScalar(value.rootMatchesExpected, ["boolean"], `${trail}.rootMatchesExpected`);
  if (
    !publicNonnegativeInteger(value.marketplaceCount, 1) ||
    !publicNonnegativeInteger(value.pluginCount, 1) ||
    !(value.version === null || publicSemver(value.version)) ||
    !publicNonnegativeInteger(value.unsupportedLegacyConflictCount)
  ) {
    fail("privacy", `${trail} violates the registration scalar contract`);
  }
}

function validatePublicPayloadIdentity(value, trail) {
  requirePublicKeys(
    value,
    new Set([
      "version",
      "declaredFileCount",
      "checksumInventorySha256",
      "releaseManifestSha256",
      "runtimeSha256",
      "ciPayloadByteIdentity",
    ]),
    trail,
  );
  requirePublicScalar(value.version, ["string"], `${trail}.version`);
  requirePublicScalar(value.declaredFileCount, ["number"], `${trail}.declaredFileCount`);
  for (const key of ["checksumInventorySha256", "releaseManifestSha256", "runtimeSha256", "ciPayloadByteIdentity"]) {
    requirePublicScalar(value[key], ["string"], `${trail}.${key}`);
  }
  if (
    value.version !== PRODUCT_VERSION ||
    !publicNonnegativeInteger(value.declaredFileCount, MAX_ARCHIVE_ENTRIES) ||
    value.declaredFileCount < 1 ||
    !publicSha256(value.checksumInventorySha256) ||
    !publicSha256(value.releaseManifestSha256) ||
    !publicSha256(value.runtimeSha256) ||
    value.ciPayloadByteIdentity !== "matched"
  ) {
    fail("privacy", `${trail} violates the installed payload identity contract`);
  }
}

function validatePublicRuntimeIdentity(value, trail) {
  requirePublicKeys(
    value,
    new Set([
      "product",
      "productVersion",
      "contentRevision",
      "architectures",
      "executable",
    ]),
    trail,
  );
  for (const key of ["product", "productVersion", "contentRevision"]) {
    requirePublicScalar(value[key], ["string", "number", "null"], `${trail}.${key}`);
  }
  requirePublicStringArray(value.architectures, `${trail}.architectures`);
  requirePublicScalar(value.executable, ["boolean"], `${trail}.executable`);
  if (
    value.product !== "opensocrates" ||
    value.productVersion !== PRODUCT_VERSION ||
    !Number.isSafeInteger(value.contentRevision) ||
    value.contentRevision < 1 ||
    !sameStrings(value.architectures, ["arm64"]) ||
    value.executable !== true
  ) {
    fail("privacy", `${trail} violates the installed runtime identity contract`);
  }
}

function validatePublicStateResidue(value, trail) {
  requirePublicKeys(
    value,
    new Set([
      "present",
      "empty",
      "desiredStatePresent",
      "receiptPresent",
      "lifecycleLockPresent",
      "temporaryCount",
      "purgeTombstoneCount",
      "unknownLeafCount",
    ]),
    trail,
  );
  for (const key of [
    "present",
    "empty",
    "desiredStatePresent",
    "receiptPresent",
    "lifecycleLockPresent",
  ]) {
    requirePublicScalar(value[key], ["boolean"], `${trail}.${key}`);
  }
  for (const key of ["temporaryCount", "purgeTombstoneCount", "unknownLeafCount"]) {
    requirePublicScalar(value[key], ["number"], `${trail}.${key}`);
    if (!publicNonnegativeInteger(value[key])) {
      fail("privacy", `${trail}.${key} violates the residue count contract`);
    }
  }
}

function validatePublicResidue(value, trail) {
  requirePublicKeys(
    value,
    new Set([
      "hosts",
      "stateResidue",
      "launchAgentPlistPresent",
      "launchAgentTemporaryCount",
      "launchAgentJobLoaded",
      "codexTrustSectionCount",
      "trustTransactionResidueCount",
      "openCodeBridgeResidueCount",
      "empty",
    ]),
    trail,
  );
  requirePublicHostMap(value.hosts, SUPPORTED_HOSTS, `${trail}.hosts`, (item, itemTrail) => {
    requirePublicKeys(
      item,
      new Set([
        "registrationPresent",
        "unsupportedLegacyRegistrationPresent",
        "managedRootPresent",
        "cachePresent",
        "cacheMarketplacePresent",
        "liveInUse",
        "pluginDataPresent",
        "transactionResidueCount",
        "bridgePresent",
        "bridgeMarkerPresent",
      ]),
      itemTrail,
    );
    for (const key of [
      "registrationPresent",
      "unsupportedLegacyRegistrationPresent",
    ]) {
      requirePublicScalar(item[key], ["boolean", "null"], `${itemTrail}.${key}`);
    }
    for (const key of [
      "managedRootPresent",
      "cachePresent",
      "cacheMarketplacePresent",
      "liveInUse",
      "pluginDataPresent",
      "bridgePresent",
      "bridgeMarkerPresent",
    ]) {
      requirePublicScalar(item[key], ["boolean"], `${itemTrail}.${key}`);
    }
    requirePublicScalar(item.transactionResidueCount, ["number"], `${itemTrail}.transactionResidueCount`);
    if (!publicNonnegativeInteger(item.transactionResidueCount)) {
      fail("privacy", `${itemTrail}.transactionResidueCount violates the residue count contract`);
    }
  });
  validatePublicStateResidue(value.stateResidue, `${trail}.stateResidue`);
  for (const key of ["launchAgentPlistPresent", "launchAgentJobLoaded", "empty"]) {
    requirePublicScalar(value[key], ["boolean"], `${trail}.${key}`);
  }
  for (const key of [
    "launchAgentTemporaryCount",
    "codexTrustSectionCount",
    "trustTransactionResidueCount",
    "openCodeBridgeResidueCount",
  ]) {
    requirePublicScalar(value[key], ["number"], `${trail}.${key}`);
    if (!publicNonnegativeInteger(value[key])) {
      fail("privacy", `${trail}.${key} violates the residue count contract`);
    }
  }
}

function validatePublicSource(source) {
  requirePublicScalar(source.repository, ["string"], "result.source.repository");
  requirePublicScalar(source.pullRequest, ["number", "null"], "result.source.pullRequest");
  requirePublicScalar(source.pullRequestUrl, ["string", "null"], "result.source.pullRequestUrl");
  requirePublicScalar(source.version, ["string"], "result.source.version");
  requirePublicScalar(source.commit, ["string", "null"], "result.source.commit");
  requirePublicScalar(source.tree, ["string", "null"], "result.source.tree");
  requirePublicScalar(source.ciRunId, ["number", "null"], "result.source.ciRunId");
  requirePublicScalar(source.ciRunUrl, ["string", "null"], "result.source.ciRunUrl");
  requirePublicScalar(source.publicReleaseV121, ["string"], "result.source.publicReleaseV121");
  if (source.ci !== null) {
    requirePublicKeys(
      source.ci,
      new Set([
        "repository",
        "workflowPath",
        "workflowId",
        "runId",
        "runAttempt",
        "conclusion",
        "headSha",
        "artifact",
        "buildSource",
      ]),
      "result.source.ci",
    );
    for (const key of ["repository", "workflowPath", "conclusion", "headSha"]) {
      requirePublicScalar(source.ci[key], ["string"], `result.source.ci.${key}`);
    }
    for (const key of ["workflowId", "runId", "runAttempt"]) {
      requirePublicScalar(source.ci[key], ["number"], `result.source.ci.${key}`);
    }
    requirePublicKeys(
      source.ci.artifact,
      new Set([
        "id",
        "name",
        "digest",
        "sizeBytes",
        "rawContainerSha256",
        "workflowRunId",
        "workflowRunHeadSha",
        "target",
      ]),
      "result.source.ci.artifact",
    );
    for (const key of ["id", "sizeBytes", "workflowRunId"]) {
      requirePublicScalar(source.ci.artifact[key], ["number"], `result.source.ci.artifact.${key}`);
    }
    for (const key of ["name", "digest", "rawContainerSha256", "workflowRunHeadSha", "target"]) {
      requirePublicScalar(source.ci.artifact[key], ["string"], `result.source.ci.artifact.${key}`);
    }
    requirePublicKeys(
      source.ci.buildSource,
      new Set(["headSha", "treeSha", "receiptSha256"]),
      "result.source.ci.buildSource",
    );
    for (const key of ["headSha", "treeSha", "receiptSha256"]) {
      requirePublicScalar(source.ci.buildSource[key], ["string"], `result.source.ci.buildSource.${key}`);
    }
  }
  if (source.npmPackage !== null) {
    requirePublicKeys(
      source.npmPackage,
      new Set([
        "name",
        "version",
        "sha256",
        "manifestSha256",
        "installerSha256",
        "bin",
        "entryCount",
        "files",
        "sourceFileHashes",
        "bundledCount",
        "execution",
      ]),
      "result.source.npmPackage",
    );
    for (const key of ["name", "version", "sha256", "manifestSha256", "installerSha256", "bin"]) {
      requirePublicScalar(source.npmPackage[key], ["string"], `result.source.npmPackage.${key}`);
    }
    for (const key of ["entryCount", "bundledCount"]) {
      requirePublicScalar(source.npmPackage[key], ["number"], `result.source.npmPackage.${key}`);
    }
    requirePublicStringArray(source.npmPackage.files, "result.source.npmPackage.files");
    requirePublicKeys(
      source.npmPackage.sourceFileHashes,
      new Set(NPM_PACKAGE_FILES),
      "result.source.npmPackage.sourceFileHashes",
    );
    for (const key of NPM_PACKAGE_FILES) {
      requirePublicScalar(
        source.npmPackage.sourceFileHashes[key],
        ["string"],
        `result.source.npmPackage.sourceFileHashes.${key}`,
      );
    }
    requirePublicKeys(
      source.npmPackage.execution,
      new Set([
        "nodeVersion",
        "npmVersion",
        "npxVersion",
        "pythonVersion",
        "npmBinarySha256",
        "npxBinarySha256",
        "nodeBinarySha256",
        "pythonBinarySha256",
      ]),
      "result.source.npmPackage.execution",
    );
    for (const key of Object.keys(source.npmPackage.execution)) {
      requirePublicScalar(source.npmPackage.execution[key], ["string"], `result.source.npmPackage.execution.${key}`);
    }
  }
  const assetKeys = Object.keys(source.assets);
  if (assetKeys.length !== 0) {
    requirePublicHostMap(source.assets, HOSTS, "result.source.assets", (asset, trail) => {
      requirePublicKeys(
        asset,
        new Set([
          "name",
          "sha256",
          "checksumProvenance",
          "aggregatePackageFileCount",
          "aggregatePackageChecksumFile",
          "payloadFileCount",
          "checksumInventorySha256",
          "releaseManifestSha256",
          "runtimeSha256",
          "runtimeArchitecture",
        ]),
        trail,
      );
      for (const key of [
        "name",
        "sha256",
        "checksumProvenance",
        "aggregatePackageChecksumFile",
        "checksumInventorySha256",
        "releaseManifestSha256",
        "runtimeSha256",
        "runtimeArchitecture",
      ]) {
        requirePublicScalar(asset[key], ["string"], `${trail}.${key}`);
      }
      for (const key of ["aggregatePackageFileCount", "payloadFileCount"]) {
        requirePublicScalar(asset[key], ["number"], `${trail}.${key}`);
      }
    });
  }
}

function validatePublicBaseline(baseline) {
  for (const key of ["kind", "expectedInitialState", "expectedFinalState", "initialState"]) {
    requirePublicScalar(baseline[key], ["string"], `result.baseline.${key}`);
  }
  requirePublicStringArray(baseline.installedHosts, "result.baseline.installedHosts");
  if (Object.keys(baseline.inventory).length === 0) return;
  requirePublicKeys(
    baseline.inventory,
    new Set([
      "registrations",
      "managedRootsPresent",
      "caches",
      "managedPayloadIntegrity",
      "cachePayloadIntegrity",
      "pluginData",
      "statePresent",
      "launchAgentPresent",
      "launchAgentTemporaryCount",
      "launchAgentJobLoaded",
      "codexTrust",
      "trustTransactionResidueCount",
      "codexHooks",
      "nonTargetHosts",
      "transactionResidue",
      "openCodeBridgeResidueCount",
      "ownership",
    ]),
    "result.baseline.inventory",
  );
  requirePublicHostMap(
    baseline.inventory.registrations,
    HOSTS,
    "result.baseline.inventory.registrations",
    validatePublicRegistration,
  );
  requirePublicHostMap(
    baseline.inventory.managedRootsPresent,
    HOSTS,
    "result.baseline.inventory.managedRootsPresent",
    (value, trail) => requirePublicScalar(value, ["boolean"], trail),
  );
  requirePublicHostMap(baseline.inventory.caches, HOSTS, "result.baseline.inventory.caches", (value, trail) => {
    requirePublicKeys(value, new Set(["present", "ownership", "versionCount", "liveInUse"]), trail);
    requirePublicScalar(value.present, ["boolean"], `${trail}.present`);
    requirePublicScalar(value.ownership, ["string"], `${trail}.ownership`);
    requirePublicScalar(value.versionCount, ["number"], `${trail}.versionCount`);
    requirePublicScalar(value.liveInUse, ["boolean"], `${trail}.liveInUse`);
  });
  for (const field of ["managedPayloadIntegrity", "cachePayloadIntegrity"]) {
    requirePublicHostMap(
      baseline.inventory[field],
      HOSTS,
      `result.baseline.inventory.${field}`,
      (value, trail) => requirePublicScalar(value, ["string"], trail),
    );
  }
  requirePublicKind(baseline.inventory.pluginData, ["array"], "result.baseline.inventory.pluginData");
  baseline.inventory.pluginData.forEach((item, index) => {
    const trail = `result.baseline.inventory.pluginData.${index}`;
    requirePublicKeys(item, new Set(["present", "ownership", "empty"]), trail);
    requirePublicScalar(item.present, ["boolean"], `${trail}.present`);
    requirePublicScalar(item.ownership, ["string"], `${trail}.ownership`);
    requirePublicScalar(item.empty, ["boolean"], `${trail}.empty`);
  });
  for (const key of ["statePresent", "launchAgentPresent", "launchAgentJobLoaded"]) {
    requirePublicScalar(baseline.inventory[key], ["boolean"], `result.baseline.inventory.${key}`);
  }
  for (const key of ["launchAgentTemporaryCount", "trustTransactionResidueCount"]) {
    requirePublicScalar(baseline.inventory[key], ["number"], `result.baseline.inventory.${key}`);
  }
  requirePublicKeys(
    baseline.inventory.codexTrust,
    new Set(["present", "exactSectionCount", "events"]),
    "result.baseline.inventory.codexTrust",
  );
  requirePublicScalar(baseline.inventory.codexTrust.present, ["boolean"], "result.baseline.inventory.codexTrust.present");
  requirePublicScalar(baseline.inventory.codexTrust.exactSectionCount, ["number"], "result.baseline.inventory.codexTrust.exactSectionCount");
  requirePublicStringArray(baseline.inventory.codexTrust.events, "result.baseline.inventory.codexTrust.events");
  requirePublicKeys(
    baseline.inventory.codexHooks,
    new Set([
      "hookCount",
      "events",
      "namespace",
      "trustStatuses",
      "sessionStartTimeoutSeconds",
    ]),
    "result.baseline.inventory.codexHooks",
  );
  requirePublicScalar(baseline.inventory.codexHooks.hookCount, ["number"], "result.baseline.inventory.codexHooks.hookCount");
  requirePublicStringArray(baseline.inventory.codexHooks.events, "result.baseline.inventory.codexHooks.events");
  requirePublicScalar(baseline.inventory.codexHooks.namespace, ["string"], "result.baseline.inventory.codexHooks.namespace");
  requirePublicStringArray(baseline.inventory.codexHooks.trustStatuses, "result.baseline.inventory.codexHooks.trustStatuses");
  requirePublicScalar(baseline.inventory.codexHooks.sessionStartTimeoutSeconds, ["number"], "result.baseline.inventory.codexHooks.sessionStartTimeoutSeconds");
  const hookTrustStatuses = baseline.inventory.codexHooks.trustStatuses;
  if (
    baseline.inventory.codexHooks.hookCount !== EXPECTED_CODEX_EVENTS.length ||
    !sameStrings(baseline.inventory.codexHooks.events, EXPECTED_CODEX_EVENTS) ||
    baseline.inventory.codexHooks.namespace !== "opensocrates@opensocrates" ||
    hookTrustStatuses.length === 0 ||
    !sameStrings(hookTrustStatuses, [...new Set(hookTrustStatuses)]) ||
    hookTrustStatuses.some(
      (status) => !new Set(["managed", "modified", "trusted", "untrusted"]).has(status),
    ) ||
    baseline.inventory.codexHooks.sessionStartTimeoutSeconds !== 2
  ) {
    fail("privacy", "the public Codex hook inventory identity is invalid");
  }
  const nonTargetHosts = SUPPORTED_HOSTS.filter((host) => !HOSTS.includes(host));
  requirePublicHostMap(
    baseline.inventory.nonTargetHosts,
    nonTargetHosts,
    "result.baseline.inventory.nonTargetHosts",
    (value, trail) => {
      requirePublicKeys(value, new Set(["managedRootPresent", "bridgePresent", "bridgeMarkerPresent"]), trail);
      for (const key of Object.keys(value)) requirePublicScalar(value[key], ["boolean"], `${trail}.${key}`);
    },
  );
  requirePublicHostMap(
    baseline.inventory.transactionResidue,
    SUPPORTED_HOSTS,
    "result.baseline.inventory.transactionResidue",
    (value, trail) => requirePublicScalar(value, ["number"], trail),
  );
  requirePublicScalar(baseline.inventory.openCodeBridgeResidueCount, ["number"], "result.baseline.inventory.openCodeBridgeResidueCount");
  requirePublicScalar(baseline.inventory.ownership, ["string"], "result.baseline.inventory.ownership");
}

function validatePublicAssertions(assertions) {
  for (const [key, value] of Object.entries(assertions)) {
    const trail = `result.assertions.${key}`;
    if (key === "deferredInUse") {
      requirePublicKeys(value, new Set(["detected", "hosts", "reinstallBlocked"]), trail);
      requirePublicScalar(value.detected, ["boolean"], `${trail}.detected`);
      requirePublicStringArray(value.hosts, `${trail}.hosts`);
      requirePublicScalar(value.reinstallBlocked, ["boolean"], `${trail}.reinstallBlocked`);
    } else if (key === "deferredResidue" || key === "zeroResidue") {
      validatePublicResidue(value, trail);
    } else if (key === "failureState") {
      requirePublicFields(
        value,
        ["classification", "actualStateRecorded", "previousStateRestorationClaimed"],
        [
          "installedHosts",
          "missingHosts",
          "registrationInspection",
          "candidatePayloads",
          "residue",
        ],
        trail,
      );
      requirePublicScalar(value.classification, ["string"], `${trail}.classification`);
      requirePublicScalar(value.actualStateRecorded, ["boolean"], `${trail}.actualStateRecorded`);
      requirePublicScalar(value.previousStateRestorationClaimed, ["boolean"], `${trail}.previousStateRestorationClaimed`);
      for (const listKey of ["installedHosts", "missingHosts"]) {
        if (Object.hasOwn(value, listKey)) requirePublicStringArray(value[listKey], `${trail}.${listKey}`);
      }
      if (Object.hasOwn(value, "registrationInspection")) requirePublicScalar(value.registrationInspection, ["string"], `${trail}.registrationInspection`);
      if (Object.hasOwn(value, "candidatePayloads")) {
        const hosts = Object.keys(value.candidatePayloads);
        requirePublicKeys(value.candidatePayloads, new Set(hosts.filter((host) => HOSTS.includes(host))), `${trail}.candidatePayloads`);
        for (const host of hosts) {
          if (!HOSTS.includes(host)) fail("privacy", `${trail}.candidatePayloads has an unsupported host`);
          validatePublicPayloadIdentity(value.candidatePayloads[host], `${trail}.candidatePayloads.${host}`);
        }
      }
      if (Object.hasOwn(value, "residue") && value.residue !== null) validatePublicResidue(value.residue, `${trail}.residue`);
    } else if (key === "finalRegistration") {
      requirePublicKeys(value, new Set(["status", "hosts"]), trail);
      requirePublicScalar(value.status, ["string"], `${trail}.status`);
      requirePublicHostMap(value.hosts, HOSTS, `${trail}.hosts`, validatePublicRegistration);
      if (value.status !== "pass") fail("privacy", `${trail}.status must be pass`);
    } else if (key === "finalStatus") {
      requirePublicKeys(value, new Set(["status", "desiredVersion", "hostsInSync", "drift"]), trail);
      requirePublicScalar(value.status, ["string"], `${trail}.status`);
      requirePublicScalar(value.desiredVersion, ["string"], `${trail}.desiredVersion`);
      requirePublicStringArray(value.hostsInSync, `${trail}.hostsInSync`);
      requirePublicScalar(value.drift, ["boolean"], `${trail}.drift`);
      if (
        value.status !== "pass" ||
        value.desiredVersion !== PRODUCT_VERSION ||
        !sameStrings(value.hostsInSync, HOSTS) ||
        value.drift !== false
      ) {
        fail("privacy", `${trail} violates the packaged status contract`);
      }
    } else if (key === "finalVersion") {
      requirePublicKeys(value, new Set(["status", "desiredVersion", "runtimes"]), trail);
      requirePublicScalar(value.status, ["string"], `${trail}.status`);
      requirePublicScalar(value.desiredVersion, ["string"], `${trail}.desiredVersion`);
      requirePublicHostMap(value.runtimes, HOSTS, `${trail}.runtimes`, validatePublicRuntimeIdentity);
      if (value.status !== "pass" || value.desiredVersion !== PRODUCT_VERSION) {
        fail("privacy", `${trail} violates the final version contract`);
      }
    } else if (key === "finalChecksum") {
      requirePublicKeys(value, new Set(["status", "payloads"]), trail);
      requirePublicScalar(value.status, ["string"], `${trail}.status`);
      requirePublicHostMap(value.payloads, HOSTS, `${trail}.payloads`, validatePublicPayloadIdentity);
      if (value.status !== "pass") fail("privacy", `${trail}.status must be pass`);
    } else if (key === "finalManagedLayout") {
      requirePublicKeys(value, new Set(["status", "claudePublicSkills", "claudeCommandsPresent", "codexControllerPresent"]), trail);
      requirePublicScalar(value.status, ["string"], `${trail}.status`);
      requirePublicStringArray(value.claudePublicSkills, `${trail}.claudePublicSkills`);
      requirePublicScalar(value.claudeCommandsPresent, ["boolean"], `${trail}.claudeCommandsPresent`);
      requirePublicScalar(value.codexControllerPresent, ["boolean"], `${trail}.codexControllerPresent`);
      if (
        value.status !== "pass" ||
        value.claudePublicSkills.some((item) => !/^[a-z0-9-]{1,80}$/u.test(item)) ||
        value.claudeCommandsPresent !== false ||
        value.codexControllerPresent !== true
      ) {
        fail("privacy", `${trail} violates the final managed-layout contract`);
      }
    } else if (key === "finalArchitecture") {
      requirePublicKeys(value, new Set(["status", "hardware", "process", "installed"]), trail);
      for (const item of ["status", "hardware", "process"]) requirePublicScalar(value[item], ["string"], `${trail}.${item}`);
      requirePublicHostMap(value.installed, HOSTS, `${trail}.installed`, requirePublicStringArray);
      if (
        value.status !== "pass" ||
        value.hardware !== "arm64" ||
        value.process !== "arm64" ||
        HOSTS.some((host) => !sameStrings(value.installed[host], ["arm64"]))
      ) {
        fail("privacy", `${trail} violates the final architecture contract`);
      }
    } else if (key === "finalPermissions") {
      requirePublicKeys(value, new Set(["status", "stateDirectoryMode", "desiredStateMode", "managedRootsOwnedByEffectiveUser", "runtimesExecutable"]), trail);
      for (const item of ["status", "stateDirectoryMode", "desiredStateMode"]) requirePublicScalar(value[item], ["string"], `${trail}.${item}`);
      for (const item of ["managedRootsOwnedByEffectiveUser", "runtimesExecutable"]) requirePublicScalar(value[item], ["boolean"], `${trail}.${item}`);
      if (
        value.status !== "pass" ||
        value.stateDirectoryMode !== "700" ||
        value.desiredStateMode !== "600" ||
        value.managedRootsOwnedByEffectiveUser !== true ||
        value.runtimesExecutable !== true
      ) {
        fail("privacy", `${trail} violates the final permission contract`);
      }
    } else if (key === "finalDesiredState") {
      requirePublicKeys(value, new Set(["status", "schema", "activeVersion", "installedHosts", "autoUpdateEnabled", "launchAgentPresent", "launchAgentJobLoaded"]), trail);
      for (const item of ["status", "schema", "activeVersion"]) requirePublicScalar(value[item], ["string"], `${trail}.${item}`);
      requirePublicStringArray(value.installedHosts, `${trail}.installedHosts`);
      for (const item of ["autoUpdateEnabled", "launchAgentPresent", "launchAgentJobLoaded"]) requirePublicScalar(value[item], ["boolean"], `${trail}.${item}`);
      if (
        value.status !== "pass" ||
        value.schema !== DESIRED_STATE_SCHEMA ||
        value.activeVersion !== PRODUCT_VERSION ||
        !sameStrings(value.installedHosts, HOSTS) ||
        value.autoUpdateEnabled !== false ||
        value.launchAgentPresent !== false ||
        value.launchAgentJobLoaded !== false
      ) {
        fail("privacy", `${trail} violates the final desired-state contract`);
      }
    } else if (key === "codexFirstApproval") {
      requirePublicKeys(value, new Set(["status", "exactHookCount", "events", "namespace", "trustStatuses", "sessionStartTimeoutSeconds", "observedBeforeOtherPostInstallCodexLaunch", "manualApprovalRequired"]), trail);
      requirePublicScalar(value.status, ["string"], `${trail}.status`);
      requirePublicScalar(value.exactHookCount, ["number"], `${trail}.exactHookCount`);
      requirePublicStringArray(value.events, `${trail}.events`);
      requirePublicScalar(value.namespace, ["string"], `${trail}.namespace`);
      requirePublicStringArray(value.trustStatuses, `${trail}.trustStatuses`);
      requirePublicScalar(value.sessionStartTimeoutSeconds, ["number"], `${trail}.sessionStartTimeoutSeconds`);
      requirePublicScalar(value.observedBeforeOtherPostInstallCodexLaunch, ["boolean"], `${trail}.observedBeforeOtherPostInstallCodexLaunch`);
      requirePublicScalar(value.manualApprovalRequired, ["boolean"], `${trail}.manualApprovalRequired`);
      if (
        value.status !== "pass" ||
        value.exactHookCount !== EXPECTED_CODEX_EVENTS.length ||
        !sameStrings(value.events, EXPECTED_CODEX_EVENTS) ||
        value.namespace !== "opensocrates@opensocrates" ||
        !sameStrings(value.trustStatuses, ["untrusted"]) ||
        value.sessionStartTimeoutSeconds !== 2 ||
        value.observedBeforeOtherPostInstallCodexLaunch !== true ||
        value.manualApprovalRequired !== true
      ) {
        fail("privacy", `${trail} violates the first-approval contract`);
      }
    } else if (key === "sessionStartBudget") {
      requirePublicKeys(value, new Set(["observationStatus", "target", "sampleCount", "configuredTimeoutMs", "hardTimeoutMilliseconds", "clock", "monotonicStartMilliseconds", "monotonicEndMilliseconds", "coldProcessPerSample", "hardTimeoutEnforced", "processModel", "firstMs", "p95Ms", "maxMs", "pass", "artifactIdentity"]), trail);
      for (const item of ["observationStatus", "target", "clock", "processModel", "artifactIdentity"]) requirePublicScalar(value[item], ["string"], `${trail}.${item}`);
      for (const item of ["sampleCount", "configuredTimeoutMs", "hardTimeoutMilliseconds", "monotonicStartMilliseconds", "monotonicEndMilliseconds", "firstMs", "p95Ms", "maxMs"]) requirePublicScalar(value[item], ["number"], `${trail}.${item}`);
      for (const item of ["coldProcessPerSample", "hardTimeoutEnforced", "pass"]) requirePublicScalar(value[item], ["boolean"], `${trail}.${item}`);
      if (
        value.observationStatus !== "pass" ||
        value.target !== "darwin-arm64" ||
        value.sampleCount !== 20 ||
        value.configuredTimeoutMs !== 2000 ||
        value.hardTimeoutMilliseconds !== 2000 ||
        value.clock !== "performance.now_monotonic" ||
        !Number.isFinite(value.monotonicStartMilliseconds) ||
        !Number.isFinite(value.monotonicEndMilliseconds) ||
        value.monotonicStartMilliseconds < 0 ||
        value.monotonicEndMilliseconds < value.monotonicStartMilliseconds ||
        value.coldProcessPerSample !== true ||
        value.hardTimeoutEnforced !== true ||
        value.processModel !== SESSION_START_PROCESS_MODEL ||
        ![value.firstMs, value.p95Ms, value.maxMs].every(
          (item) => Number.isFinite(item) && item >= 0 && item < 2000,
        ) ||
        value.firstMs > value.maxMs ||
        value.p95Ms > value.maxMs ||
        value.p95Ms > 1000 ||
        value.pass !== true ||
        !publicSha256(value.artifactIdentity, { prefixed: true })
      ) {
        fail("privacy", `${trail} violates the SessionStart timing contract`);
      }
    } else if (key === "finalTopology") {
      requirePublicKeys(value, new Set(["status", "sourceCommit", "installedHosts", "version", "admittedTopology", "nonTargetHosts", "previousCacheDataTrustContentRestorationClaimed"]), trail);
      for (const item of ["status", "sourceCommit", "version", "admittedTopology"]) requirePublicScalar(value[item], ["string"], `${trail}.${item}`);
      requirePublicStringArray(value.installedHosts, `${trail}.installedHosts`);
      const otherHosts = SUPPORTED_HOSTS.filter((host) => !HOSTS.includes(host));
      requirePublicHostMap(value.nonTargetHosts, otherHosts, `${trail}.nonTargetHosts`, (item, itemTrail) => {
        requirePublicKeys(item, new Set(["managedRootPresent", "bridgePresent", "bridgeMarkerPresent"]), itemTrail);
        for (const field of Object.keys(item)) requirePublicScalar(item[field], ["boolean"], `${itemTrail}.${field}`);
      });
      requirePublicScalar(value.previousCacheDataTrustContentRestorationClaimed, ["boolean"], `${trail}.previousCacheDataTrustContentRestorationClaimed`);
      if (
        value.status !== "pass" ||
        !/^[a-f0-9]{40}$/u.test(value.sourceCommit) ||
        !sameStrings(value.installedHosts, HOSTS) ||
        value.version !== PRODUCT_VERSION ||
        value.admittedTopology !== "claude_and_codex_only; other_supported_hosts_absent" ||
        value.previousCacheDataTrustContentRestorationClaimed !== false
      ) {
        fail("privacy", `${trail} violates the final topology contract`);
      }
    } else if (key === "lifecycleRecovery") {
      requirePublicKeys(
        value,
        new Set(["classification", "operationKey", "attempt", "receiptSha256"]),
        trail,
      );
      if (
        value.classification !== "blocked_unverifiable" ||
        !new Set([
          "purge-initial",
          "purge-host-close-retry",
          "install-initial",
          "install-retry",
        ]).has(value.operationKey) ||
        !new Set([1, 2]).has(value.attempt) ||
        !/^[a-f0-9]{64}$/u.test(value.receiptSha256 ?? "")
      ) {
        fail("privacy", `${trail} has an unsupported blocked lifecycle identity`);
      }
    }
  }
}

function publicIsoTimestamp(value) {
  return (
    typeof value === "string" &&
    Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString() === value
  );
}

function publicSemver(value, { nodePrefix = false } = {}) {
  return typeof value === "string" && new RegExp(
    `^${nodePrefix ? "v" : ""}\\d+\\.\\d+\\.\\d+(?:[-+][0-9A-Za-z.-]+)?$`,
    "u",
  ).test(value);
}

function publicSha256(value, { prefixed = false } = {}) {
  return typeof value === "string" && new RegExp(
    `^${prefixed ? "sha256:" : ""}[a-f0-9]{64}$`,
    "u",
  ).test(value);
}

function publicNonnegativeInteger(value, maximum = Number.MAX_SAFE_INTEGER) {
  return Number.isSafeInteger(value) && value >= 0 && value <= maximum;
}

function publicAssetIdentityIsValid(host, asset) {
  return (
    /^[A-Za-z0-9._-]{1,160}$/u.test(asset?.name ?? "") &&
    publicSha256(asset?.sha256) &&
    asset?.checksumProvenance === "locally_derived_from_verified_manifest" &&
    publicNonnegativeInteger(asset?.aggregatePackageFileCount, MAX_ARCHIVE_ENTRIES) &&
    asset?.aggregatePackageChecksumFile === `${host}/checksums.sha256` &&
    publicNonnegativeInteger(asset?.payloadFileCount, MAX_ARCHIVE_ENTRIES) &&
    publicSha256(asset?.checksumInventorySha256) &&
    publicSha256(asset?.releaseManifestSha256) &&
    publicSha256(asset?.runtimeSha256) &&
    asset?.runtimeArchitecture === "arm64"
  );
}

function commitPublicAssetIdentities(report, assets) {
  if (
    report?.source === null ||
    typeof report?.source !== "object" ||
    report.source.assets === null ||
    typeof report.source.assets !== "object" ||
    Object.keys(report.source.assets).length !== 0 ||
    assets === null ||
    typeof assets !== "object" ||
    !sameStrings(Object.keys(assets), HOSTS)
  ) {
    fail("artifact-integrity", "the public native asset receipt commit has invalid inputs");
  }
  const projected = Object.fromEntries(
    HOSTS.map((host) => {
      const asset = assets[host];
      const identity = {
        name: asset?.name,
        sha256: asset?.sha256,
        checksumProvenance: asset?.checksumProvenance,
        aggregatePackageFileCount: asset?.aggregatePackageFileCount,
        aggregatePackageChecksumFile: asset?.aggregatePackageChecksumFile,
        payloadFileCount: asset?.payloadFileCount,
        checksumInventorySha256: asset?.checksumInventorySha256,
        releaseManifestSha256: asset?.releaseManifestSha256,
        runtimeSha256: asset?.runtimeSha256,
        runtimeArchitecture: asset?.runtimeArchitecture,
      };
      if (!publicAssetIdentityIsValid(host, identity)) {
        fail("artifact-integrity", `${host} public native asset receipt is incomplete`);
      }
      return [host, identity];
    }),
  );
  report.source.assets = projected;
  return structuredClone(projected);
}

function publicSafeLabel(value, maximum = 160) {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maximum &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function validatePublicSemanticContracts(report) {
  if (
    report.schema !== RESULT_SCHEMA ||
    !UUID_V4_PATTERN.test(report.testId) ||
    !publicIsoTimestamp(report.generatedAt) ||
    !(report.completedAt === null || publicIsoTimestamp(report.completedAt)) ||
    !new Set(["running", "paused", "passed", "failed"]).has(report.automatedResult) ||
    !new Set(["pending", "not-run", "passed", "failed", "blocked", "not_observed"]).has(report.manualResult) ||
    !new Set(["pending", "passed", "failed", "blocked", "not_observed"]).has(report.overallResult)
  ) {
    fail("privacy", "public result identity or outcome fields violate their closed contract");
  }
  const source = report.source;
  if (
    source.repository !== REPOSITORY ||
    !publicSemver(source.version) ||
    source.version !== PRODUCT_VERSION ||
    !(source.commit === null || /^[a-f0-9]{40}$/u.test(source.commit)) ||
    !(source.tree === null || /^[a-f0-9]{40}$/u.test(source.tree)) ||
    !(source.pullRequest === null || (Number.isSafeInteger(source.pullRequest) && source.pullRequest > 0)) ||
    !(source.ciRunId === null || (Number.isSafeInteger(source.ciRunId) && source.ciRunId > 0)) ||
    source.publicReleaseV121 !== "unavailable"
  ) {
    fail("privacy", "public source identity violates its closed contract");
  }
  if (
    source.pullRequestUrl !== null &&
    source.pullRequestUrl !==
      `https://github.com/${REPOSITORY}/pull/${source.pullRequest}`
  ) {
    fail("privacy", "public pull-request URL is not bound to its exact repository and number");
  }
  if (
    source.ciRunUrl !== null &&
    source.ciRunUrl !== `https://github.com/${REPOSITORY}/actions/runs/${source.ciRunId}`
  ) {
    fail("privacy", "public CI URL is not bound to its exact repository and run");
  }
  if (source.ci !== null) {
    const ci = source.ci;
    if (
      ci.repository !== REPOSITORY ||
      ci.workflowPath !== ".github/workflows/ci.yml" ||
      !Number.isSafeInteger(ci.workflowId) ||
      ci.workflowId < 1 ||
      !Number.isSafeInteger(ci.runId) ||
      ci.runId < 1 ||
      !Number.isSafeInteger(ci.runAttempt) ||
      ci.runAttempt < 1 ||
      ci.conclusion !== "success" ||
      !/^[a-f0-9]{40}$/u.test(ci.headSha) ||
      ci.runId !== source.ciRunId ||
      ci.headSha !== source.commit ||
      !Number.isSafeInteger(ci.artifact.id) ||
      ci.artifact.id < 1 ||
      ci.artifact.name !== nativeArtifactName(ci.runId, ci.runAttempt) ||
      !publicSha256(ci.artifact.digest, { prefixed: true }) ||
      !publicNonnegativeInteger(ci.artifact.sizeBytes, MAX_ARTIFACT_BYTES) ||
      ci.artifact.sizeBytes < 1 ||
      !publicSha256(ci.artifact.rawContainerSha256) ||
      ci.artifact.workflowRunId !== ci.runId ||
      ci.artifact.workflowRunHeadSha !== ci.headSha ||
      ci.artifact.target !== "darwin-arm64" ||
      ci.buildSource.headSha !== source.commit ||
      !/^[a-f0-9]{40}$/u.test(ci.buildSource.treeSha) ||
      !publicSha256(ci.buildSource.receiptSha256)
    ) {
      fail("privacy", "public CI provenance violates its closed contract");
    }
  }
  if (source.npmPackage !== null) {
    const npmPackage = source.npmPackage;
    if (
      npmPackage.name !== "opensocrates" ||
      npmPackage.version !== PRODUCT_VERSION ||
      !publicSha256(npmPackage.sha256) ||
      !publicSha256(npmPackage.manifestSha256) ||
      !publicSha256(npmPackage.installerSha256) ||
      npmPackage.bin !== "opensocrates=installer/opensocrates.mjs" ||
      npmPackage.entryCount !== NPM_PACKAGE_FILES.length ||
      !sameStrings(npmPackage.files, NPM_PACKAGE_FILES) ||
      npmPackage.bundledCount !== 0 ||
      Object.values(npmPackage.sourceFileHashes).some((value) => !publicSha256(value)) ||
      !publicSemver(npmPackage.execution.nodeVersion, { nodePrefix: true }) ||
      !publicSemver(npmPackage.execution.npmVersion) ||
      !publicSemver(npmPackage.execution.npxVersion) ||
      !/^3\.12\.\d+$/u.test(npmPackage.execution.pythonVersion) ||
      !publicSha256(npmPackage.execution.npmBinarySha256) ||
      !publicSha256(npmPackage.execution.npxBinarySha256) ||
      !publicSha256(npmPackage.execution.nodeBinarySha256) ||
      !publicSha256(npmPackage.execution.pythonBinarySha256)
    ) {
      fail("privacy", "public npm provenance violates its closed contract");
    }
  }
  for (const [host, asset] of Object.entries(source.assets)) {
    if (!publicAssetIdentityIsValid(host, asset)) {
      fail("privacy", "public native asset identity violates its closed contract");
    }
  }
  const environment = report.environment;
  if (
    !(environment.platform === null || environment.platform === "darwin") ||
    !publicSemver(environment.nodeVersion, { nodePrefix: true }) ||
    !(environment.hardwareArchitecture === null || environment.hardwareArchitecture === "arm64") ||
    !(environment.processArchitecture === null || environment.processArchitecture === "arm64") ||
    !(environment.claudeVersion === null || publicSemver(environment.claudeVersion)) ||
    !(environment.codexVersion === null || publicSemver(environment.codexVersion)) ||
    (environment.identity !== null &&
      (environment.identity.uidMatchesEffectiveUid !== true ||
        environment.identity.homeOwnedByEffectiveUid !== true ||
        environment.identity.sudo !== false))
  ) {
    fail("privacy", "public environment evidence violates its closed contract");
  }
  if (
    report.automatedResult === "passed" &&
    (environment.platform !== "darwin" ||
      environment.hardwareArchitecture !== "arm64" ||
      environment.processArchitecture !== "arm64" ||
      environment.identity?.uidMatchesEffectiveUid !== true ||
      environment.identity?.homeOwnedByEffectiveUid !== true ||
      environment.identity?.sudo !== false)
  ) {
    fail("privacy", "a passed result requires verified target environment evidence");
  }
  if (
    report.baseline.kind !== BASELINE ||
    report.baseline.expectedInitialState !== "installed" ||
    report.baseline.expectedFinalState !== "installed" ||
    !new Set(["not-checked", "installed"]).has(report.baseline.initialState) ||
    report.baseline.installedHosts.some((host) => !HOSTS.includes(host)) ||
    new Set(report.baseline.installedHosts).size !== report.baseline.installedHosts.length
  ) {
    fail("privacy", "public baseline identity violates its closed contract");
  }
  const mutation = report.mutation;
  if (
    !/^[a-z][a-z0-9_-]{0,79}$/u.test(mutation.phase) ||
    !/^[a-z][a-z0-9_-]{0,99}$/u.test(mutation.lifecycleOutcome) ||
    !publicNonnegativeInteger(mutation.purgeCommandAttempts, 2) ||
    !publicNonnegativeInteger(mutation.trustResetAttempts, 2) ||
    mutation.purgeCommandAttempts !== mutation.trustResetAttempts ||
    !publicNonnegativeInteger(mutation.reinstallAttempts, 2) ||
    !publicNonnegativeInteger(mutation.hostCloseRetriesUsed, MAX_HOST_CLOSE_RETRIES) ||
    !/^[a-z][a-z0-9_-]{0,99}$/u.test(mutation.finalState) ||
    !(mutation.nextAction === null || /^[a-z][a-z0-9_]{0,159}$/u.test(mutation.nextAction)) ||
    mutation.originalCacheDataTrustRestorationClaimed !== false
  ) {
    fail("privacy", "public mutation telemetry violates its closed contract");
  }
  report.commands.forEach((command, index) => {
    if (
      command.id !== index + 1 ||
      !publicSafeLabel(command.label) ||
      !(command.exitStatus === null || Number.isSafeInteger(command.exitStatus)) ||
      !Number.isFinite(command.durationMs) ||
      command.durationMs < 0 ||
      !publicSha256(command.stdoutSha256) ||
      !publicSha256(command.stderrSha256)
    ) {
      fail("privacy", "public command evidence violates its closed scalar contract");
    }
  });
  report.steps.forEach((step) => {
    if (
      !/^[a-z][a-z0-9-]{0,63}$/u.test(step.id) ||
      !publicSafeLabel(step.label) ||
      !new Set(["passed", "paused", "failed"]).has(step.status) ||
      !Number.isFinite(step.durationMs) ||
      step.durationMs < 0 ||
      !(step.category === undefined || step.category === null || /^[a-z][a-z0-9-]{0,63}$/u.test(step.category)) ||
      !(step.commandId === undefined || step.commandId === null ||
        (Number.isSafeInteger(step.commandId) && step.commandId > 0))
    ) {
      fail("privacy", "public step evidence violates its closed scalar contract");
    }
  });
  if (
    report.limitations.claudeChatStandaloneV121 !== "pending_public_artifact" ||
    report.limitations.cleanMachineClaimed !== false ||
    report.limitations.publicRegistryPathVerified !== false ||
    report.privacy.privateCommandLogRecorded !== true ||
    Object.entries(report.privacy).some(
      ([key, value]) => key !== "privateCommandLogRecorded" && value !== false,
    )
  ) {
    fail("privacy", "public limitation or privacy claims violate their closed contract");
  }
}

function validatePublicResultShape(report) {
  validatePublicJsonTypes(report);
  requirePublicKeys(report, PUBLIC_REPORT_KEYS, "result");
  requirePublicKeys(report.source, PUBLIC_SOURCE_KEYS, "result.source");
  requirePublicKeys(report.environment, PUBLIC_ENVIRONMENT_KEYS, "result.environment");
  requirePublicKeys(report.baseline, PUBLIC_BASELINE_KEYS, "result.baseline");
  requirePublicKeys(report.mutation, PUBLIC_MUTATION_KEYS, "result.mutation");
  requirePublicKeys(report.limitations, PUBLIC_LIMITATION_KEYS, "result.limitations");
  requirePublicKeys(report.privacy, PUBLIC_PRIVACY_KEYS, "result.privacy");
  requirePublicKeys(report.assertions, PUBLIC_ASSERTION_KEYS, "result.assertions", {
    exact: false,
  });
  validatePublicSource(report.source);
  validatePublicBaseline(report.baseline);
  validatePublicAssertions(report.assertions);
  for (const [key, kinds] of [
    ["platform", ["string", "null"]],
    ["nodeVersion", ["string"]],
    ["hardwareArchitecture", ["string", "null"]],
    ["processArchitecture", ["string", "null"]],
    ["claudeVersion", ["string", "null"]],
    ["codexVersion", ["string", "null"]],
  ]) {
    requirePublicScalar(report.environment[key], kinds, `result.environment.${key}`);
  }
  if (report.environment.identity !== null) {
    requirePublicKeys(
      report.environment.identity,
      new Set(["uidMatchesEffectiveUid", "homeOwnedByEffectiveUid", "sudo"]),
      "result.environment.identity",
    );
    for (const key of Object.keys(report.environment.identity)) {
      requirePublicScalar(report.environment.identity[key], ["boolean"], `result.environment.identity.${key}`);
    }
  }
  for (const key of ["started", "reinstallAttempted", "originalCacheDataTrustRestorationClaimed"]) {
    requirePublicScalar(report.mutation[key], ["boolean"], `result.mutation.${key}`);
  }
  for (const key of ["purgeCommandAttempts", "trustResetAttempts", "reinstallAttempts", "hostCloseRetriesUsed"]) {
    requirePublicScalar(report.mutation[key], ["number"], `result.mutation.${key}`);
  }
  for (const key of ["phase", "lifecycleOutcome", "finalState"]) {
    requirePublicScalar(report.mutation[key], ["string"], `result.mutation.${key}`);
  }
  requirePublicScalar(report.mutation.nextAction, ["string", "null"], "result.mutation.nextAction");
  for (const key of PUBLIC_LIMITATION_KEYS) {
    requirePublicScalar(report.limitations[key], [key === "claudeChatStandaloneV121" ? "string" : "boolean"], `result.limitations.${key}`);
  }
  for (const key of PUBLIC_PRIVACY_KEYS) {
    requirePublicScalar(report.privacy[key], ["boolean"], `result.privacy.${key}`);
  }
  requirePublicKeys(
    report.manualObservations,
    new Set(MANUAL_FIELDS),
    "result.manualObservations",
  );
  for (const [label, value] of Object.entries(report.manualObservations)) {
    if (!new Set(["pending", "pass", "fail", "not_observed", "blocked"]).has(value)) {
      fail("privacy", `public manual observation ${label} has an unsupported enum`);
    }
  }
  requirePublicKind(report.commands, ["array"], "result.commands");
  report.commands.forEach((command, index) => {
    requirePublicKeys(command, PUBLIC_COMMAND_KEYS, `result.commands.${index}`);
    requirePublicKind(command.id, ["number"], `result.commands.${index}.id`);
    requirePublicKind(command.label, ["string"], `result.commands.${index}.label`);
    requirePublicKind(command.exitStatus, ["number", "null"], `result.commands.${index}.exitStatus`);
    requirePublicKind(command.durationMs, ["number"], `result.commands.${index}.durationMs`);
    requirePublicKind(command.stdoutSha256, ["string"], `result.commands.${index}.stdoutSha256`);
    requirePublicKind(command.stderrSha256, ["string"], `result.commands.${index}.stderrSha256`);
  });
  requirePublicKind(report.steps, ["array"], "result.steps");
  report.steps.forEach((step, index) => {
    requirePublicKeys(step, PUBLIC_STEP_KEYS, `result.steps.${index}`, { exact: false });
    for (const required of ["id", "label", "status", "durationMs"]) {
      if (!Object.hasOwn(step, required)) {
        fail("privacy", `public evidence field result.steps.${index}.${required} is missing`);
      }
    }
    requirePublicKind(step.id, ["string"], `result.steps.${index}.id`);
    requirePublicKind(step.label, ["string"], `result.steps.${index}.label`);
    requirePublicKind(step.status, ["string"], `result.steps.${index}.status`);
    requirePublicKind(step.durationMs, ["number"], `result.steps.${index}.durationMs`);
    if (Object.hasOwn(step, "category")) {
      requirePublicKind(step.category, ["string", "null"], `result.steps.${index}.category`);
    }
    if (Object.hasOwn(step, "commandId")) {
      requirePublicKind(step.commandId, ["number", "null"], `result.steps.${index}.commandId`);
    }
  });
  if (report.failure !== null) {
    requirePublicKeys(
      report.failure,
      new Set(["category", "message", "commandId"]),
      "result.failure",
    );
    requirePublicKind(report.failure.category, ["string"], "result.failure.category");
    requirePublicKind(report.failure.message, ["string"], "result.failure.message");
    requirePublicKind(report.failure.commandId, ["number", "null"], "result.failure.commandId");
    if (
      !/^[a-z][a-z0-9-]{0,63}$/u.test(report.failure.category) ||
      report.failure.message.length === 0 ||
      report.failure.message.length > 500 ||
      /[\u0000-\u001f\u007f]/u.test(report.failure.message) ||
      (report.failure.commandId !== null &&
        (!Number.isSafeInteger(report.failure.commandId) || report.failure.commandId < 1))
    ) {
      fail("privacy", "public failure evidence has an unsupported scalar value");
    }
  }
  for (const [key, kinds] of [
    ["schema", ["string"]],
    ["testId", ["string"]],
    ["generatedAt", ["string"]],
    ["completedAt", ["string", "null"]],
    ["automatedResult", ["string"]],
    ["manualResult", ["string"]],
    ["overallResult", ["string"]],
  ]) {
    requirePublicKind(report[key], kinds, `result.${key}`);
  }
  validatePublicSemanticContracts(report);
}

function validatePublicText(text, knownPrivateValues = []) {
  const forbiddenValues = [homedir(), ROOT, ...knownPrivateValues].filter(Boolean);
  if (forbiddenValues.some((item) => text.includes(item))) {
    fail("privacy", "public evidence contains an absolute local path");
  }
  if (/\/(?:Users|private|var|tmp|Volumes)(?:\/[^\s`'"]+)+/u.test(text)) {
    fail("privacy", "public evidence contains an absolute local path");
  }
  if (/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/iu.test(text)) {
    fail("privacy", "public evidence contains an email-like identity");
  }
  if (/\b(?:gh[opusr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/u.test(text)) {
    fail("privacy", "public evidence contains a credential-like token");
  }
  if (/\bsk-ant-[A-Za-z0-9_-]{12,}\b/u.test(text)) {
    fail("privacy", "public evidence contains a credential-like token");
  }
  if (containsPublicAbsolutePath(text)) {
    fail("privacy", "public evidence contains an absolute local path");
  }
}

function makeReport() {
  return {
    schema: RESULT_SCHEMA,
    testId: randomUUID(),
    generatedAt: new Date().toISOString(),
    completedAt: null,
    source: {
      repository: REPOSITORY,
      pullRequest: null,
      pullRequestUrl: null,
      version: PRODUCT_VERSION,
      commit: null,
      tree: null,
      ciRunId: null,
      ciRunUrl: null,
      ci: null,
      npmPackage: null,
      assets: {},
      publicReleaseV121: "unavailable",
    },
    environment: {
      platform: null,
      nodeVersion: process.version,
      hardwareArchitecture: null,
      processArchitecture: null,
      identity: null,
      claudeVersion: null,
      codexVersion: null,
    },
    baseline: {
      kind: BASELINE,
      expectedInitialState: "installed",
      expectedFinalState: "installed",
      initialState: "not-checked",
      installedHosts: [],
      inventory: {},
    },
    mutation: {
      started: false,
      phase: "preflight",
      lifecycleOutcome: "not_started",
      purgeCommandAttempts: 0,
      trustResetAttempts: 0,
      reinstallAttempts: 0,
      hostCloseRetriesUsed: 0,
      reinstallAttempted: false,
      finalState: "not-checked",
      nextAction: null,
      originalCacheDataTrustRestorationClaimed: false,
    },
    commands: [],
    steps: [],
    assertions: {},
    automatedResult: "running",
    manualResult: "pending",
    overallResult: "pending",
    manualObservations: Object.fromEntries(MANUAL_FIELDS.map((label) => [label, "pending"])),
    limitations: {
      claudeChatStandaloneV121: "pending_public_artifact",
      cleanMachineClaimed: false,
      publicRegistryPathVerified: false,
    },
    failure: null,
    privacy: {
      privateCommandLogRecorded: true,
      rawCommandOutputIncluded: false,
      rawRecordingIncluded: false,
      accessibilitySnapshotIncluded: false,
      promptsIncluded: false,
      transcriptsIncluded: false,
      sidebarTextIncluded: false,
      authenticationIdentityIncluded: false,
      credentialsIncluded: false,
      absoluteLocalPathsIncluded: false,
      unrelatedHistoryContentRead: false,
      unrelatedHistoryMutationAttempted: false,
    },
  };
}

function manualTemplate(report) {
  const automated = report.automatedResult.toUpperCase().replaceAll("_", "-");
  const defaultCheck = report.automatedResult === "passed" ? "PENDING" : "NOT_RUN";
  return `# OpenSocrates purged-same-machine manual observations

Automated result: ${automated}
${MANUAL_FIELDS.map((label) => `${label}: ${defaultCheck}`).join("\n")}
Claude Chat standalone v1.2.1: PENDING_PUBLIC_ARTIFACT

Change every \`PENDING\` value to one fixed final enum only after completing the
matching check in a Record & Replay capture. Use \`PASS\` or \`FAIL\` for an
observed outcome, \`NOT_OBSERVED\` when no
qualifying observation was captured and \`BLOCKED\` when authentication,
approval, or safe app control prevented the check. Do not change fixed fields.

- Codex first review: after reinstall, confirm that Codex presents exactly seven
  OpenSocrates plugin hooks as new/untrusted items.
- Codex approval: approve those exact seven hooks, then confirm that all seven
  are trusted. Do not approve unrelated hooks.
- Codex SessionStart: start a fresh Codex task and record categorically whether
  the OpenSocrates SessionStart hook finishes without a two-second timeout.
- Claude Local: in a fresh Claude Code Local task, run the canonical
  \`/opensocrates:opensocrates status\` plugin command and confirm version
  \`${PRODUCT_VERSION}\`. A bare \`/opensocrates\` is not Local plugin evidence.
- Recording review: mark PASS only after the private Record & Replay event stream
  has been stopped and reviewed without copying raw events into public evidence.

The standalone Claude Chat command remains \`/opensocrates\`, but public Chat
${PRODUCT_VERSION} is pending because the public artifact is unavailable. It is
not inferred from Claude Local.

Do not add notes, prompts, transcripts, sidebar text, account names, credentials,
raw accessibility data, raw command output, or local paths. Packing rejects any
other edit.
`;
}

function markdownReport(report) {
  const rows = report.steps
    .map(
      (step) =>
        `| ${step.label} | ${step.status} | ${step.durationMs} ms | ${step.category ?? "-"} |`,
    )
    .join("\n");
  const failure = report.failure
    ? `\nFailure category: \`${report.failure.category}\`\n\nFailure summary: ${report.failure.message}\n`
    : "";
  return `# OpenSocrates purged-same-machine reinstall result

- Baseline: **${report.baseline.kind}**
- Overall: **${report.overallResult}**
- Automated: **${report.automatedResult}**
- Manual: **${report.manualResult}**
- Final state: **${report.mutation.finalState}**
- Product version: \`${report.source.version}\`
- Pull request: ${report.source.pullRequestUrl ?? "not recorded"}
- Source commit: \`${report.source.commit ?? "not recorded"}\`
- CI run: ${report.source.ciRunUrl ?? "not recorded"}
- Public v1.2.1 release path: **unavailable / not tested**
- Claude Chat standalone v1.2.1: **pending public artifact**
${failure}
| Check | Result | Duration | Failure category |
| --- | --- | ---: | --- |
${rows || "| No checks completed | failed | 0 ms | harness |"}

This is a previously used Mac after an exact purge, not a new or clean machine.
The report excludes prompts, transcripts, sidebar text, identities, credentials,
absolute local paths, raw command output, raw recordings, and accessibility data.
`;
}

function publicReportFileBytes(report) {
  validatePublicResultShape(report);
  assertNoForbiddenPublicKeys(report);
  const values = {
    "result.json": `${JSON.stringify(report, null, 2)}\n`,
    "result.md": markdownReport(report),
    "manual-observations.md": manualTemplate(report),
  };
  for (const value of Object.values(values)) validatePublicText(value);
  return Object.fromEntries(
    Object.entries(values).map(([name, value]) => [name, Buffer.from(value, "utf8")]),
  );
}

function atomicWriteOwnerFile(target, contents, category = "result-persist") {
  const parent = dirname(target);
  requireExactPrivateMode(parent, "owner-only publish parent", "directory", 0o700);
  if (pathPresent(target)) {
    requireExactPrivateMode(target, "owner-only publish target", "file", 0o600);
  }
  const temporary = join(parent, `.${basename(target)}.${randomUUID()}.tmp`);
  let descriptor = null;
  try {
    descriptor = openSync(
      temporary,
      fsConstants.O_CREAT |
        fsConstants.O_EXCL |
        fsConstants.O_WRONLY |
        fsConstants.O_NOFOLLOW,
      0o600,
    );
    writeFileSync(descriptor, contents);
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = null;
    chmodSync(temporary, 0o600);
    renameSync(temporary, target);
    syncEntry(parent);
  } catch (error) {
    if (error instanceof AcceptanceError) throw error;
    fail(category, "an owner-only evidence file could not be published atomically");
  } finally {
    if (descriptor !== null) closeSync(descriptor);
    if (pathPresent(temporary)) {
      const info = lstatSync(temporary);
      if (!info.isSymbolicLink() && info.isFile() && info.uid === currentUid()) {
        unlinkSync(temporary);
      }
    }
  }
}

function sealedPublicDirectory(privateDirectory) {
  return join(privateDirectory, SEALED_PUBLIC_DIRECTORY_NAME);
}

function createSealedPublicResult(
  privateDirectory,
  report,
  finalVerification,
  { finalizationId, afterFileWritten = () => {} } = {},
) {
  if (
    !UUID_V4_PATTERN.test(finalizationId ?? "") ||
    typeof afterFileWritten !== "function"
  ) {
    fail("finalizing", "the sealed result writer hook is invalid");
  }
  if (
    report.automatedResult !== "passed" ||
    report.manualResult !== "pending" ||
    report.overallResult !== "pending" ||
    report.mutation.finalState !== "installed" ||
    finalVerification?.sha256 !== sha256Buffer(JSON.stringify(finalVerification?.value))
  ) {
    fail("finalizing", "only the complete automated installed result can be sealed");
  }
  const directory = sealedPublicDirectory(privateDirectory);
  if (pathPresent(directory)) {
    const existing = validateSealedPublicResult(privateDirectory, report.testId);
    if (
      existing.receipt.finalizationId !== finalizationId ||
      existing.receipt.sourceCommit !== report.source.commit ||
      existing.receipt.finalVerificationSha256 !== finalVerification.sha256 ||
      JSON.stringify(existing.report) !== JSON.stringify(report)
    ) {
      fail("finalizing", "the existing sealed result belongs to a different finalization");
    }
    return existing;
  }
  const staging = join(
    privateDirectory,
    `.sealed-public-result.${randomUUID()}.tmp`,
  );
  mkdirSync(staging, { mode: 0o700 });
  chmodSync(staging, 0o700);
  syncEntry(privateDirectory);
  try {
    const files = publicReportFileBytes(report);
    const fileReceipts = {};
    for (const name of RESULT_FILES) {
      const bytes = files[name];
      writeExclusivePrivateBytes(join(staging, name), bytes, "finalizing");
      fileReceipts[name] = {
        sha256: sha256Buffer(bytes),
        sizeBytes: bytes.length,
      };
      afterFileWritten(name);
    }
    const receiptBase = {
      schema: SEALED_PUBLIC_SCHEMA,
      testId: report.testId,
      sourceCommit: report.source.commit,
      finalizationId,
      finalState: "installed",
      installedHosts: [...HOSTS],
      automatedResult: "passed",
      manualResult: "pending",
      overallResult: "pending",
      finalVerification: structuredClone(finalVerification),
      finalVerificationSha256: finalVerification.sha256,
      files: fileReceipts,
    };
    const receipt = {
      ...receiptBase,
      sealSha256: sha256Buffer(JSON.stringify(receiptBase)),
    };
    writeExclusivePrivateBytes(
      join(staging, SEALED_PUBLIC_RECEIPT_NAME),
      Buffer.from(`${JSON.stringify(receipt, null, 2)}\n`),
      "finalizing",
    );
    syncEntry(staging);
    validateSealedPublicDirectory(staging, report.testId);
    renameSync(staging, directory);
    syncEntry(privateDirectory);
  } finally {
    if (pathPresent(staging)) {
      requireExactPrivateMode(staging, "sealed public staging directory", "directory", 0o700);
      rmSync(staging, { recursive: true, force: false });
      syncEntry(privateDirectory);
    }
  }
  return validateSealedPublicResult(privateDirectory, report.testId);
}

function validateSealedPublicDirectory(directory, expectedTestId = null) {
  requireExactPrivateMode(directory, "sealed public result directory", "directory", 0o700);
  if (!sameStrings(readdirSync(directory), [...RESULT_FILES, SEALED_PUBLIC_RECEIPT_NAME])) {
    fail("finalizing", "the sealed public result member set is not exact");
  }
  const receiptPath = join(directory, SEALED_PUBLIC_RECEIPT_NAME);
  const receiptRecord = parseLifecycleJson(
    receiptPath,
    SEALED_PUBLIC_SCHEMA,
    [
      "schema",
      "testId",
      "sourceCommit",
      "finalizationId",
      "finalState",
      "installedHosts",
      "automatedResult",
      "manualResult",
      "overallResult",
      "finalVerification",
      "finalVerificationSha256",
      "files",
      "sealSha256",
    ],
    "sealed public result receipt",
  );
  const receipt = receiptRecord.value;
  requireExactObjectKeys(receipt.files, RESULT_FILES, "finalizing", "sealed public files");
  const receiptBase = { ...receipt };
  delete receiptBase.sealSha256;
  if (
    (expectedTestId !== null && receipt.testId !== expectedTestId) ||
    !/^[0-9a-f-]{36}$/u.test(receipt.testId ?? "") ||
    !/^[a-f0-9]{40}$/u.test(receipt.sourceCommit ?? "") ||
    !UUID_V4_PATTERN.test(receipt.finalizationId ?? "") ||
    receipt.finalState !== "installed" ||
    !sameStrings(receipt.installedHosts ?? [], HOSTS) ||
    receipt.automatedResult !== "passed" ||
    receipt.manualResult !== "pending" ||
    receipt.overallResult !== "pending" ||
    receipt.finalVerification === null ||
    typeof receipt.finalVerification !== "object" ||
    Array.isArray(receipt.finalVerification) ||
    receipt.finalVerification.sha256 !==
      sha256Buffer(JSON.stringify(receipt.finalVerification.value)) ||
    receipt.finalVerification.sha256 !== receipt.finalVerificationSha256 ||
    !/^[a-f0-9]{64}$/u.test(receipt.finalVerificationSha256 ?? "") ||
    receipt.sealSha256 !== sha256Buffer(JSON.stringify(receiptBase))
  ) {
    fail("finalizing", "the sealed public result identity is invalid");
  }
  for (const name of RESULT_FILES) {
    requireExactObjectKeys(
      receipt.files[name],
      ["sha256", "sizeBytes"],
      "finalizing",
      `sealed public file ${name}`,
    );
    const target = join(directory, name);
    requireExactPrivateMode(target, `sealed public file ${name}`, "file", 0o600);
    if (
      !/^[a-f0-9]{64}$/u.test(receipt.files[name].sha256 ?? "") ||
      !Number.isSafeInteger(receipt.files[name].sizeBytes) ||
      receipt.files[name].sizeBytes < 0 ||
      statSync(target).size !== receipt.files[name].sizeBytes ||
      sha256FileSync(target) !== receipt.files[name].sha256
    ) {
      fail("finalizing", `sealed public file ${name} changed after sealing`);
    }
  }
  const report = parseJson(
    readFileSync(join(directory, "result.json"), "utf8"),
    "finalizing",
    "the sealed public result JSON is invalid",
  );
  validatePublicResultShape(report);
  assertNoForbiddenPublicKeys(report);
  if (
    report.testId !== receipt.testId ||
    report.source.commit !== receipt.sourceCommit ||
    report.automatedResult !== "passed" ||
    report.manualResult !== "pending" ||
    report.overallResult !== "pending" ||
    report.mutation.finalState !== "installed" ||
    markdownReport(report) !== readFileSync(join(directory, "result.md"), "utf8") ||
    manualTemplate(report) !==
      readFileSync(join(directory, "manual-observations.md"), "utf8")
  ) {
    fail("finalizing", "the sealed public result files do not describe one exact report");
  }
  return {
    directory,
    receipt,
    receiptSha256: receiptRecord.sha256,
    report,
  };
}

function validateSealedPublicResult(privateDirectory, expectedTestId = null) {
  return validateSealedPublicDirectory(
    sealedPublicDirectory(privateDirectory),
    expectedTestId,
  );
}

function publishSealedPublicResult(privateDirectory, outputDirectory, expectedTestId) {
  const sealed = validateSealedPublicResult(privateDirectory, expectedTestId);
  requireExactPrivateMode(outputDirectory, "public result directory", "directory", 0o700);
  for (const name of RESULT_FILES) {
    const source = join(sealed.directory, name);
    const target = join(outputDirectory, name);
    if (
      pathPresent(target) &&
      sha256FileSync(target) === sealed.receipt.files[name].sha256 &&
      statSync(target).size === sealed.receipt.files[name].sizeBytes
    ) {
      requireExactPrivateMode(target, `public result file ${name}`, "file", 0o600);
      continue;
    }
    atomicWriteOwnerFile(target, readFileSync(source), "finalizing");
  }
  return sealed;
}

function publicReportBytesForWrite(
  outputDirectory,
  report,
  { preserveManual = false, privateValues = [] } = {},
) {
  validatePublicResultShape(report);
  assertNoForbiddenPublicKeys(report);
  requireExactPrivateMode(outputDirectory, "public result directory", "directory", 0o700);
  const entries = readdirSync(outputDirectory);
  if (entries.some((name) => !RESULT_FILES.includes(name))) {
    fail("result-persist", "the public result directory contains an unexpected entry");
  }
  for (const name of entries) {
    requireExactPrivateMode(join(outputDirectory, name), `public result file ${name}`, "file", 0o600);
  }
  const json = Buffer.from(`${JSON.stringify(report, null, 2)}\n`);
  const markdown = Buffer.from(markdownReport(report));
  validatePublicText(json.toString("utf8"), privateValues);
  validatePublicText(markdown.toString("utf8"), privateValues);
  const manual = join(outputDirectory, "manual-observations.md");
  const manualBytes =
    preserveManual && pathPresent(manual)
      ? readFileSync(manual)
      : Buffer.from(manualTemplate(report));
  validatePublicText(manualBytes.toString("utf8"), privateValues);
  return {
    "result.json": json,
    "result.md": markdown,
    "manual-observations.md": manualBytes,
  };
}

function writeReports(outputDirectory, report, options = {}) {
  const files = publicReportBytesForWrite(outputDirectory, report, options);
  for (const name of RESULT_FILES) {
    atomicWriteOwnerFile(join(outputDirectory, name), files[name], "result-persist");
  }
}

function validatePublicResultDirectory(outputDirectory, { requireArchiveAbsent = false } = {}) {
  requireCanonicalOwnedEntry(outputDirectory, "public result directory", "directory");
  if (requireOwnerOnly(outputDirectory, "the public result directory") !== "700") {
    fail("permissions", "the public result directory must have mode 0700");
  }
  const sourceEntries = readdirSync(outputDirectory);
  if (!sameStrings(sourceEntries, RESULT_FILES)) {
    fail("result-bundle", "the result directory must contain exactly the three public files");
  }
  for (const name of RESULT_FILES) {
    requireCanonicalOwnedEntry(join(outputDirectory, name), `public result file ${name}`, "file");
    if (requireOwnerOnly(join(outputDirectory, name), `the public result file ${name}`) !== "600") {
      fail("permissions", `the public result file ${name} must have mode 0600`);
    }
  }
  const archive = `${outputDirectory}.zip`;
  if (requireArchiveAbsent && pathPresent(archive)) {
    fail("result-bundle", "the public result ZIP target already exists");
  }
  return archive;
}

export function validateExistingPublicReports(outputDirectory) {
  validatePublicResultDirectory(outputDirectory);
  const resultBytes = readFileSync(join(outputDirectory, "result.json"));
  const markdown = readFileSync(join(outputDirectory, "result.md"), "utf8");
  const manual = readFileSync(join(outputDirectory, "manual-observations.md"), "utf8");
  const report = parseJson(
    resultBytes.toString("utf8"),
    "result-persist",
    "the existing public result JSON is invalid",
  );
  validatePublicResultShape(report);
  assertNoForbiddenPublicKeys(report);
  for (const value of [resultBytes.toString("utf8"), markdown, manual]) {
    validatePublicText(value);
  }
  if (markdown !== markdownReport(report) || manual !== manualTemplate(report)) {
    fail("result-persist", "the existing public result files do not describe one exact report");
  }
  return report;
}

function zipReports(outputDirectory, { archivePath = null } = {}) {
  const defaultArchive = validatePublicResultDirectory(outputDirectory);
  const parent = dirname(outputDirectory);
  const archive = archivePath === null ? defaultArchive : resolve(archivePath);
  if (
    dirname(archive) !== parent ||
    (archive !== defaultArchive &&
      basename(archive) !== `${basename(outputDirectory)}.diagnostic.zip`) ||
    pathPresent(archive)
  ) {
    fail("result-bundle", "the public result ZIP target is unsafe or already exists");
  }
  const staging = realpathSync(
    mkdtempSync(join(parent, ".opensocrates-public-result-stage-")),
  );
  chmodSync(staging, 0o700);
  const temporaryArchive = join(
    parent,
    `.${basename(outputDirectory)}.${randomUUID()}.tmp.zip`,
  );
  try {
    for (const name of RESULT_FILES) {
      const staged = join(staging, name);
      copyFileSync(join(outputDirectory, name), staged, fsConstants.COPYFILE_EXCL);
      chmodSync(staged, 0o600);
      requireCanonicalOwnedEntry(staged, `staged public result file ${name}`, "file");
      requireOwnerOnly(staged, `the staged public result file ${name}`);
    }
    if (!sameStrings(readdirSync(staging), RESULT_FILES)) {
      fail("result-bundle", "the fresh public ZIP staging directory is not exact");
    }
    const completed = spawnSync(
      "/usr/bin/zip",
      ["-q", "-X", temporaryArchive, ...RESULT_FILES],
      {
        cwd: staging,
        encoding: "utf8",
        maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
        env: {
          HOME: tmpdir(),
          PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
          TMPDIR: tmpdir(),
          LANG: "C",
          LC_ALL: "C",
        },
      },
    );
    if (completed.error || completed.status !== 0) {
      fail("result-bundle", "the privacy-safe result ZIP could not be created");
    }
    chmodSync(temporaryArchive, 0o600);
    requireCanonicalOwnedEntry(temporaryArchive, "temporary public result ZIP", "file");
    requireOwnerOnly(temporaryArchive, "the temporary public result ZIP");
    const listing = spawnSync("/usr/bin/unzip", ["-Z1", temporaryArchive], {
      encoding: "utf8",
      maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
      env: {
        HOME: tmpdir(),
        PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
        TMPDIR: tmpdir(),
        LANG: "C",
        LC_ALL: "C",
      },
    });
    const members = listing.stdout?.split(/\r?\n/u).filter(Boolean) ?? [];
    if (listing.error || listing.status !== 0 || !sameStrings(members, RESULT_FILES)) {
      fail("result-bundle", "the public result ZIP member set is not exact");
    }
    syncEntry(temporaryArchive);
    renameSync(temporaryArchive, archive);
    syncEntry(parent);
    return archive;
  } finally {
    if (pathPresent(temporaryArchive)) {
      requireCanonicalOwnedEntry(temporaryArchive, "temporary public result ZIP", "file");
      unlinkSync(temporaryArchive);
    }
    if (pathPresent(staging)) {
      requireCanonicalOwnedEntry(staging, "public ZIP staging directory", "directory");
      rmSync(staging, { recursive: true, force: true });
    }
  }
}

function validatePublicResultZip(archive, outputDirectory) {
  requireExactPrivateMode(archive, "public result ZIP", "file", 0o600);
  const environment = {
    HOME: tmpdir(),
    PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
    TMPDIR: tmpdir(),
    LANG: "C",
    LC_ALL: "C",
  };
  const listing = spawnSync("/usr/bin/unzip", ["-Z1", archive], {
    encoding: "utf8",
    maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
    env: environment,
  });
  const members = listing.stdout?.split(/\r?\n/u).filter(Boolean) ?? [];
  if (listing.error || listing.status !== 0 || !sameStrings(members, RESULT_FILES)) {
    fail("result-bundle", "the existing public ZIP member set is invalid");
  }
  for (const name of RESULT_FILES) {
    const extracted = spawnSync("/usr/bin/unzip", ["-p", archive, name], {
      encoding: null,
      maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
      env: environment,
    });
    const stdout = Buffer.isBuffer(extracted.stdout) ? extracted.stdout : Buffer.alloc(0);
    if (
      extracted.error ||
      extracted.status !== 0 ||
      !stdout.equals(readFileSync(join(outputDirectory, name)))
    ) {
      fail("result-bundle", `the existing public ZIP member ${name} changed`);
    }
  }
  return sha256FileSync(archive);
}

function markPublicBundleReady(privateDirectory, outputDirectory, archive) {
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  requireExactPrivateMode(archive, "public result ZIP", "file", 0o600);
  const archiveSha256 = sha256FileSync(archive);
  if (
    manifest.publicResult.directory === resolve(outputDirectory) &&
    manifest.retention.status === "public_bundle_ready" &&
    manifest.publicResult.publicZipSha256 === archiveSha256
  ) {
    return manifest;
  }
  if (
    manifest.publicResult.directory !== resolve(outputDirectory) ||
    !new Set(["active", "diagnostic_bundle_ready"]).has(manifest.retention.status) ||
    manifest.publicResult.publicZipSha256 !== null
  ) {
    fail("private-evidence", "the private retention state cannot accept this public bundle");
  }
  manifest.publicResult.publicZipSha256 = archiveSha256;
  manifest.retention.status = "public_bundle_ready";
  manifest.updatedAt = new Date().toISOString();
  atomicWritePrivate(
    join(privateDirectory, PRIVATE_MANIFEST_NAME),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
  return manifest;
}

function markDiagnosticBundleReady(privateDirectory, outputDirectory, archive) {
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  requireExactPrivateMode(archive, "diagnostic public result ZIP", "file", 0o600);
  const archiveSha256 = sha256FileSync(archive);
  if (
    manifest.publicResult.directory === resolve(outputDirectory) &&
    new Set(["diagnostic_bundle_ready", "public_bundle_ready"]).has(
      manifest.retention.status,
    ) &&
    manifest.publicResult.diagnosticZipSha256 === archiveSha256
  ) {
    return manifest;
  }
  if (
    manifest.publicResult.directory !== resolve(outputDirectory) ||
    manifest.retention.status !== "active" ||
    manifest.publicResult.diagnosticZipSha256 !== null
  ) {
    fail("private-evidence", "the private retention state cannot accept this diagnostic bundle");
  }
  manifest.publicResult.diagnosticZipSha256 = archiveSha256;
  manifest.retention.status = "diagnostic_bundle_ready";
  manifest.updatedAt = new Date().toISOString();
  atomicWritePrivate(
    join(privateDirectory, PRIVATE_MANIFEST_NAME),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
  return manifest;
}

export function createDiagnosticBundle(privateDirectoryArgument, outputDirectoryArgument) {
  const privateDirectory = resolve(privateDirectoryArgument);
  const outputDirectory = resolve(outputDirectoryArgument);
  const report = validateExistingPublicReports(outputDirectory);
  const manifest = validatePrivateEvidenceManifest(
    privateDirectory,
    outputDirectory,
    report.testId,
  );
  const archive = `${outputDirectory}.diagnostic.zip`;
  if (manifest.publicResult.diagnosticZipSha256 !== null) {
    requireExactPrivateMode(archive, "diagnostic public result ZIP", "file", 0o600);
    if (sha256FileSync(archive) !== manifest.publicResult.diagnosticZipSha256) {
      fail("result-bundle", "the diagnostic public result ZIP changed after its durable linkage");
    }
    return archive;
  }
  if (pathPresent(archive)) {
    requireExactPrivateMode(archive, "diagnostic public result ZIP", "file", 0o600);
  } else {
    zipReports(outputDirectory, { archivePath: archive });
  }
  validatePublicResultZip(archive, outputDirectory);
  markDiagnosticBundleReady(privateDirectory, outputDirectory, archive);
  return archive;
}

function validateInstalledSealedPackState(
  privateDirectory,
  outputDirectory,
  report,
  manifest,
  { requireAutomatedPublicBytes = true } = {},
) {
  const sealed = validateSealedPublicResult(privateDirectory, report.testId);
  const checkpointPath = join(privateDirectory, CHECKPOINT_NAME);
  requireExactPrivateMode(checkpointPath, "installed acceptance checkpoint", "file", 0o600);
  const checkpoint = parseJson(
    readFileSync(checkpointPath, "utf8"),
    "result-bundle",
    "the installed checkpoint is invalid",
  );
  const observed = checkpoint?.lastObservedState;
  const binding = observed?.sealedPublicResult;
  const expectedBinding = {
    receiptSha256: sealed.receiptSha256,
    sealSha256: sealed.receipt.sealSha256,
    resultJsonSha256: sealed.receipt.files["result.json"].sha256,
  };
  if (
    checkpoint?.schema !== CHECKPOINT_SCHEMA ||
    checkpoint.phase !== "installed" ||
    resolve(checkpoint.reportDirectory ?? "") !== resolve(outputDirectory) ||
    checkpoint.sourceCommit !== sealed.receipt.sourceCommit ||
    report.source.commit !== sealed.receipt.sourceCommit ||
    observed?.classification !== "candidate_installed_verified" ||
    observed?.finalizationId !== sealed.receipt.finalizationId ||
    observed?.testId !== sealed.receipt.testId ||
    observed?.sourceCommit !== sealed.receipt.sourceCommit ||
    observed?.finalVerificationSha256 !== sealed.receipt.finalVerificationSha256 ||
    binding?.receiptSha256 !== expectedBinding.receiptSha256 ||
    binding?.sealSha256 !== expectedBinding.sealSha256 ||
    binding?.resultJsonSha256 !== expectedBinding.resultJsonSha256 ||
    manifest.publicResult.automatedResultSha256 !==
      sealed.receipt.files["result.json"].sha256 ||
    manifest.publicResult.sealedReceiptSha256 !== sealed.receiptSha256 ||
    manifest.publicResult.finalizationId !== sealed.receipt.finalizationId ||
    manifest.publicResult.finalVerificationSha256 !==
      sealed.receipt.finalVerificationSha256
  ) {
    fail(
      "result-bundle",
      "the automated result is not bound to one installed checkpoint and sealed receipt",
    );
  }
  if (requireAutomatedPublicBytes) {
    for (const name of ["result.json", "result.md"]) {
      const target = join(outputDirectory, name);
      if (
        statSync(target).size !== sealed.receipt.files[name].sizeBytes ||
        sha256FileSync(target) !== sealed.receipt.files[name].sha256
      ) {
        fail("result-bundle", `the automated public ${name} changed after sealing`);
      }
    }
  }
  return sealed;
}

function fixedManualObservations(manual, sealedReport) {
  let normalizedManual = manual;
  const observations = {};
  for (const label of MANUAL_FIELDS) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
    const matches = [
      ...manual.matchAll(
        new RegExp(`^${escaped}: (PASS|FAIL|NOT_OBSERVED|BLOCKED|PENDING)$`, "gmu"),
      ),
    ];
    if (matches.length !== 1 || matches[0][1] === "PENDING") {
      fail(
        "result-bundle",
        `set '${label}' to PASS, FAIL, NOT_OBSERVED, or BLOCKED before packing`,
      );
    }
    observations[label] = matches[0][1].toLowerCase();
    normalizedManual = normalizedManual.replace(matches[0][0], `${label}: PENDING`);
  }
  if (normalizedManual !== manualTemplate(sealedReport)) {
    fail("result-bundle", "restore the manual checklist template and do not add free-form text");
  }
  return observations;
}

function manualWithObservations(sealedReport, observations) {
  let manual = manualTemplate(sealedReport);
  for (const label of MANUAL_FIELDS) {
    const value = observations[label];
    const replacement =
      value === "not_observed" ? "NOT_OBSERVED" : value.toUpperCase();
    manual = manual.replace(`${label}: PENDING`, `${label}: ${replacement}`);
  }
  return manual;
}

function finalManualResult(observations) {
  const values = Object.values(observations);
  return values.includes("fail")
    ? "failed"
    : values.includes("blocked")
      ? "blocked"
      : values.includes("not_observed")
        ? "not_observed"
        : "passed";
}

function finalPackReport(sealedReport, observations, completedAt) {
  const report = structuredClone(sealedReport);
  report.manualObservations = structuredClone(observations);
  report.manualResult = finalManualResult(observations);
  report.overallResult = report.manualResult;
  report.completedAt = completedAt;
  validatePublicResultShape(report);
  assertNoForbiddenPublicKeys(report);
  return report;
}

function packTransactionPath(privateDirectory) {
  return join(privateDirectory, PACK_TRANSACTION_NAME);
}

function readPackTransaction(privateDirectory) {
  const target = packTransactionPath(privateDirectory);
  requireExactPrivateMode(target, "private pack transaction", "file", 0o600);
  const receipt = parseJson(
    readFileSync(target, "utf8"),
    "result-bundle",
    "the private pack transaction is invalid",
  );
  requireExactObjectKeys(
    receipt,
    [
      "schema",
      "transactionId",
      "testId",
      "outputDirectory",
      "sealedReceiptSha256",
      "observations",
      "completedAt",
      "finalReportSha256",
      "finalMarkdownSha256",
      "finalManualSha256",
      "status",
      "archiveSha256",
      "createdAt",
    ],
    "result-bundle",
    "the private pack transaction",
  );
  requireExactObjectKeys(
    receipt.observations,
    MANUAL_FIELDS,
    "result-bundle",
    "the private pack observations",
  );
  if (
    receipt.schema !== PACK_TRANSACTION_SCHEMA ||
    !UUID_V4_PATTERN.test(receipt.transactionId ?? "") ||
    !UUID_V4_PATTERN.test(receipt.testId ?? "") ||
    typeof receipt.outputDirectory !== "string" ||
    resolve(receipt.outputDirectory) !== receipt.outputDirectory ||
    !/^[a-f0-9]{64}$/u.test(receipt.sealedReceiptSha256 ?? "") ||
    Object.values(receipt.observations).some(
      (value) => !new Set(["pass", "fail", "not_observed", "blocked"]).has(value),
    ) ||
    !Number.isFinite(Date.parse(receipt.completedAt)) ||
    !/^[a-f0-9]{64}$/u.test(receipt.finalReportSha256 ?? "") ||
    !/^[a-f0-9]{64}$/u.test(receipt.finalMarkdownSha256 ?? "") ||
    !/^[a-f0-9]{64}$/u.test(receipt.finalManualSha256 ?? "") ||
    !new Set(["prepared", "archive_ready"]).has(receipt.status) ||
    !(
      (receipt.status === "prepared" && receipt.archiveSha256 === null) ||
      (receipt.status === "archive_ready" &&
        /^[a-f0-9]{64}$/u.test(receipt.archiveSha256 ?? ""))
    )
  ) {
    fail("result-bundle", "the private pack transaction identity is invalid");
  }
  return receipt;
}

function validatePackTransaction(privateDirectory, outputDirectory) {
  const receipt = readPackTransaction(privateDirectory);
  const sealed = validateSealedPublicResult(privateDirectory, receipt.testId);
  if (
    receipt.outputDirectory !== resolve(outputDirectory) ||
    receipt.sealedReceiptSha256 !== sealed.receiptSha256
  ) {
    fail("result-bundle", "the private pack transaction binds a different automated result");
  }
  const report = finalPackReport(
    sealed.report,
    receipt.observations,
    receipt.completedAt,
  );
  const manual = manualWithObservations(sealed.report, receipt.observations);
  if (
    sha256Buffer(`${JSON.stringify(report, null, 2)}\n`) !== receipt.finalReportSha256 ||
    sha256Buffer(markdownReport(report)) !== receipt.finalMarkdownSha256 ||
    sha256Buffer(manual) !== receipt.finalManualSha256
  ) {
    fail("result-bundle", "the private pack transaction final bytes changed");
  }
  return { receipt, sealed, report, manual };
}

function writePackTransaction(privateDirectory, receipt) {
  atomicWritePrivate(
    packTransactionPath(privateDirectory),
    `${JSON.stringify(receipt, null, 2)}\n`,
  );
}

function resumePackTransaction(
  privateDirectory,
  outputDirectory,
  {
    afterReportPersisted = () => {},
    afterArchivePublished = () => {},
    afterArchiveReceipt = () => {},
    afterBundleMarker = () => {},
  } = {},
) {
  for (const hook of [
    afterReportPersisted,
    afterArchivePublished,
    afterArchiveReceipt,
    afterBundleMarker,
  ]) {
    if (typeof hook !== "function") {
      fail("result-bundle", "the pack transaction hook contract is invalid");
    }
  }
  const transaction = validatePackTransaction(privateDirectory, outputDirectory);
  const manifest = validatePrivateEvidenceManifest(
    privateDirectory,
    outputDirectory,
    transaction.receipt.testId,
  );
  validateInstalledSealedPackState(
    privateDirectory,
    outputDirectory,
    transaction.sealed.report,
    manifest,
    { requireAutomatedPublicBytes: false },
  );
  const currentJsonSha256 = sha256FileSync(join(outputDirectory, "result.json"));
  const currentMarkdownSha256 = sha256FileSync(join(outputDirectory, "result.md"));
  const sealedGeneration =
    currentJsonSha256 === transaction.sealed.receipt.files["result.json"].sha256 &&
    currentMarkdownSha256 === transaction.sealed.receipt.files["result.md"].sha256;
  const finalGeneration =
    currentJsonSha256 === transaction.receipt.finalReportSha256 &&
    currentMarkdownSha256 === transaction.receipt.finalMarkdownSha256;
  if (!sealedGeneration && !finalGeneration) {
    fail("result-bundle", "the pack transaction public report generation is mixed or changed");
  }
  const currentManual = readFileSync(join(outputDirectory, "manual-observations.md"), "utf8");
  if (currentManual !== transaction.manual) {
    fail("result-bundle", "the manual observations changed during the pack transaction");
  }
  persistRun(transaction.report, outputDirectory, privateDirectory, {
    preserveManual: true,
  });
  afterReportPersisted();
  const archive = `${outputDirectory}.zip`;
  let archiveSha256;
  if (pathPresent(archive)) {
    archiveSha256 = validatePublicResultZip(archive, outputDirectory);
  } else {
    archiveSha256 = validatePublicResultZip(zipReports(outputDirectory), outputDirectory);
  }
  afterArchivePublished();
  let receipt = readPackTransaction(privateDirectory);
  if (receipt.status === "prepared") {
    receipt = {
      ...receipt,
      status: "archive_ready",
      archiveSha256,
    };
    writePackTransaction(privateDirectory, receipt);
  } else if (receipt.archiveSha256 !== archiveSha256) {
    fail("result-bundle", "the public ZIP changed after its durable pack receipt");
  }
  afterArchiveReceipt();
  markPublicBundleReady(privateDirectory, outputDirectory, archive);
  afterBundleMarker();
  requireExactPrivateMode(
    packTransactionPath(privateDirectory),
    "private pack transaction",
    "file",
    0o600,
  );
  unlinkSync(packTransactionPath(privateDirectory));
  syncEntry(privateDirectory);
  console.log(`Share this privacy-safe result ZIP: ${archive}`);
  return archive;
}

function packExisting(
  directoryArgument,
  privateDirectoryArgument = null,
  { testHooks = {} } = {},
) {
  if (!directoryArgument) {
    fail("usage", "--pack requires the result directory printed by the automated test");
  }
  const outputDirectory = resolve(directoryArgument);
  if (!pathPresent(outputDirectory) || !lstatSync(outputDirectory).isDirectory()) {
    fail("usage", "--pack requires an existing result directory");
  }
  if (!privateDirectoryArgument) {
    fail("usage", "--pack requires the matching private evidence directory");
  }
  const privateDirectory = resolve(privateDirectoryArgument);
  recoverEvidenceTransaction(privateDirectory);
  validatePublicResultDirectory(outputDirectory);
  if (pathPresent(packTransactionPath(privateDirectory))) {
    return resumePackTransaction(
      privateDirectory,
      outputDirectory,
      testHooks,
    );
  }
  const resultPath = join(outputDirectory, "result.json");
  const manualPath = join(outputDirectory, "manual-observations.md");
  const report = parseJson(
    readFileSync(resultPath, "utf8"),
    "result-bundle",
    "result.json is invalid",
  );
  if (
    report?.schema !== RESULT_SCHEMA ||
    report?.automatedResult !== "passed" ||
    report?.baseline?.kind !== BASELINE ||
    report?.mutation?.finalState !== "installed"
  ) {
    fail("result-bundle", "only a passed installed purged-same-machine result can be packed");
  }
  validatePublicResultShape(report);
  assertNoForbiddenPublicKeys(report);
  if (readFileSync(join(outputDirectory, "result.md"), "utf8") !== markdownReport(report)) {
    fail("result-bundle", "result.md does not match result.json");
  }
  const privateManifest = validatePrivateEvidenceManifest(
    privateDirectory,
    outputDirectory,
    report.testId,
  );
  const archive = `${outputDirectory}.zip`;
  if (privateManifest.retention.status === "public_bundle_ready") {
    if (!pathPresent(archive)) {
      fail("result-bundle", "the durable public bundle marker has no local ZIP");
    }
    const sealed = validateInstalledSealedPackState(
      privateDirectory,
      outputDirectory,
      report,
      privateManifest,
      { requireAutomatedPublicBytes: false },
    );
    const observations = fixedManualObservations(
      readFileSync(manualPath, "utf8"),
      sealed.report,
    );
    const expectedReport = finalPackReport(
      sealed.report,
      observations,
      report.completedAt,
    );
    if (
      JSON.stringify(expectedReport) !== JSON.stringify(report) ||
      JSON.stringify(observations) !== JSON.stringify(report.manualObservations) ||
      validatePublicResultZip(archive, outputDirectory) !==
        privateManifest.publicResult.publicZipSha256
    ) {
      fail("result-bundle", "the completed public bundle changed after its durable marker");
    }
    return archive;
  }
  if (pathPresent(archive)) {
    fail("result-bundle", "an unbound public result ZIP already occupies the final handoff path");
  }
  const automatedDigest = sha256FileSync(resultPath);
  if (
    privateManifest.publicResult.resultJsonSha256 !== automatedDigest ||
    privateManifest.publicResult.automatedResultSha256 !== automatedDigest
  ) {
    fail("result-bundle", "result.json changed after the automated acceptance result was sealed");
  }
  const sealed = validateInstalledSealedPackState(
    privateDirectory,
    outputDirectory,
    report,
    privateManifest,
  );
  const manual = readFileSync(manualPath, "utf8");
  const observations = fixedManualObservations(manual, sealed.report);
  if (
    observations["Record and Replay capture reviewed"] === "pass" &&
    privateManifest.recording.status !== "verified"
  ) {
    fail("result-bundle", "Record and Replay PASS requires its same-test private receipt");
  }
  const completedAt = new Date().toISOString();
  const finalReport = finalPackReport(sealed.report, observations, completedAt);
  const receipt = {
    schema: PACK_TRANSACTION_SCHEMA,
    transactionId: randomUUID(),
    testId: report.testId,
    outputDirectory,
    sealedReceiptSha256: sealed.receiptSha256,
    observations,
    completedAt,
    finalReportSha256: sha256Buffer(`${JSON.stringify(finalReport, null, 2)}\n`),
    finalMarkdownSha256: sha256Buffer(markdownReport(finalReport)),
    finalManualSha256: sha256Buffer(manual),
    status: "prepared",
    archiveSha256: null,
    createdAt: new Date().toISOString(),
  };
  writePackTransaction(privateDirectory, receipt);
  return resumePackTransaction(
    privateDirectory,
    outputDirectory,
    testHooks,
  );
}

function requireExactPrivateMode(target, label, expectedKind, expectedMode) {
  const info = requireCanonicalOwnedEntry(target, label, expectedKind);
  if ((info.mode & 0o777) !== expectedMode) {
    fail("private-evidence", `${label} does not have the exact owner-only mode`);
  }
  return info;
}

function writeExclusivePrivateBytes(target, contents, category = "private-evidence") {
  const parent = dirname(target);
  requireExactPrivateMode(parent, "private output parent", "directory", 0o700);
  let descriptor = null;
  try {
    descriptor = openSync(
      target,
      fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
      0o600,
    );
    writeFileSync(descriptor, contents);
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = null;
    chmodSync(target, 0o600);
    requireExactPrivateMode(target, "private command output", "file", 0o600);
    syncEntry(parent);
  } catch (error) {
    if (descriptor !== null) closeSync(descriptor);
    if (error instanceof AcceptanceError) throw error;
    fail(category, "a private command output target was not exclusively creatable");
  }
}

function sha256FileSync(target) {
  const descriptor = openSync(target, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW);
  const hash = createHash("sha256");
  const buffer = Buffer.alloc(64 * 1024);
  try {
    while (true) {
      const count = readSync(descriptor, buffer, 0, buffer.length, null);
      if (count === 0) break;
      hash.update(buffer.subarray(0, count));
    }
  } finally {
    closeSync(descriptor);
  }
  return hash.digest("hex");
}

function requireExactObjectKeys(value, keys, category, label) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.getPrototypeOf(value) !== Object.prototype ||
    !sameStrings(Object.keys(value), keys)
  ) {
    fail(category, `${label} has an unsupported schema`);
  }
}

function readPrivateEvidenceManifest(privateDirectory) {
  requireExactPrivateMode(privateDirectory, "private evidence directory", "directory", 0o700);
  const target = join(privateDirectory, PRIVATE_MANIFEST_NAME);
  requireExactPrivateMode(target, "private evidence manifest", "file", 0o600);
  const manifest = parseJson(
    readFileSync(target, "utf8"),
    "private-evidence",
    "the private evidence manifest is invalid JSON",
  );
  requireExactObjectKeys(
    manifest,
    [
      "schema",
      "testId",
      "createdAt",
      "updatedAt",
      "ownerUid",
      "publicResult",
      "commandLedger",
      "recording",
      "retention",
    ],
    "private-evidence",
    "the private evidence manifest",
  );
  requireExactObjectKeys(
    manifest.publicResult,
    [
      "directory",
      "resultJsonSha256",
      "automatedResultSha256",
      "sealedReceiptSha256",
      "finalizationId",
      "finalVerificationSha256",
      "diagnosticZipSha256",
      "publicZipSha256",
    ],
    "private-evidence",
    "the private public-result linkage",
  );
  requireExactObjectKeys(
    manifest.commandLedger,
    ["relativePath", "sha256", "entryCount"],
    "private-evidence",
    "the private command-ledger linkage",
  );
  requireExactObjectKeys(
    manifest.recording,
    [
      "status",
      "testId",
      "receiptRelativePath",
      "receiptSha256",
      "recordingSha256",
      "reviewStatus",
    ],
    "private-evidence",
    "the private recording linkage",
  );
  requireExactObjectKeys(
    manifest.retention,
    ["status", "policy", "cleanupAuthorized"],
    "private-evidence",
    "the private retention policy",
  );
  if (
    manifest.schema !== PRIVATE_MANIFEST_SCHEMA ||
    typeof manifest.testId !== "string" ||
    manifest.testId.length === 0 ||
    manifest.ownerUid !== currentUid() ||
    manifest.commandLedger.relativePath !== COMMAND_LOG_NAME ||
    !Number.isSafeInteger(manifest.commandLedger.entryCount) ||
    manifest.commandLedger.entryCount < 0 ||
    manifest.recording.testId !== manifest.testId ||
    !new Set(["pending", "verified"]).has(manifest.recording.status) ||
    !new Set([
      "active",
      "diagnostic_bundle_ready",
      "public_bundle_ready",
      "cleanup_authorized",
    ]).has(manifest.retention.status) ||
    manifest.retention.policy !== "owner_guarded_exact_cleanup_after_public_handoff" ||
    typeof manifest.retention.cleanupAuthorized !== "boolean"
  ) {
    fail("private-evidence", "the private evidence manifest identity or retention state is invalid");
  }
  const sealedLinkage = [
    manifest.publicResult.sealedReceiptSha256,
    manifest.publicResult.finalizationId,
    manifest.publicResult.finalVerificationSha256,
  ];
  if (
    sealedLinkage.some((value) => value === null) !==
      sealedLinkage.every((value) => value === null) ||
    (sealedLinkage[0] !== null &&
      (!/^[a-f0-9]{64}$/u.test(sealedLinkage[0]) ||
        !UUID_V4_PATTERN.test(sealedLinkage[1]) ||
        !/^[a-f0-9]{64}$/u.test(sealedLinkage[2])))
  ) {
    fail("private-evidence", "the sealed automated-result linkage is incomplete");
  }
  const diagnosticDigest = manifest.publicResult.diagnosticZipSha256;
  const publicDigest = manifest.publicResult.publicZipSha256;
  if (
    !(diagnosticDigest === null || /^[a-f0-9]{64}$/u.test(diagnosticDigest)) ||
    !(publicDigest === null || /^[a-f0-9]{64}$/u.test(publicDigest)) ||
    (manifest.retention.status === "active" &&
      (diagnosticDigest !== null || publicDigest !== null || manifest.retention.cleanupAuthorized)) ||
    (manifest.retention.status === "diagnostic_bundle_ready" &&
      (diagnosticDigest === null || publicDigest !== null || manifest.retention.cleanupAuthorized)) ||
    (manifest.retention.status === "public_bundle_ready" &&
      (publicDigest === null || manifest.retention.cleanupAuthorized)) ||
    (manifest.retention.status === "cleanup_authorized" &&
      (!manifest.retention.cleanupAuthorized ||
        (diagnosticDigest === null && publicDigest === null)))
  ) {
    fail("private-evidence", "the private bundle retention linkage is inconsistent");
  }
  return manifest;
}

function commandLedgerStateFromContents(contents) {
  if (typeof contents !== "string") {
    fail("private-evidence", "the private command ledger bytes are invalid");
  }
  const entries = contents.split(/\r?\n/u).filter(Boolean);
  entries.forEach((line, index) => {
    const entry = parseJson(line, "private-evidence", "the private command ledger is invalid");
    if (entry?.schema !== "opensocrates.acceptance-command/1.0.0" || entry?.id !== index + 1) {
      fail("private-evidence", "the private command ledger sequence is invalid");
    }
  });
  return { sha256: sha256Buffer(contents), entryCount: entries.length };
}

function commandLedgerState(privateDirectory) {
  const ledgerPath = join(privateDirectory, COMMAND_LOG_NAME);
  requireExactPrivateMode(ledgerPath, "private command ledger", "file", 0o600);
  return commandLedgerStateFromContents(readFileSync(ledgerPath, "utf8"));
}

function initializePrivateEvidenceManifest(privateDirectory, outputDirectory, report) {
  requireExactPrivateMode(privateDirectory, "private evidence directory", "directory", 0o700);
  requireExactPrivateMode(outputDirectory, "public result directory", "directory", 0o700);
  const target = join(privateDirectory, PRIVATE_MANIFEST_NAME);
  if (pathPresent(target)) fail("private-evidence", "the private evidence manifest already exists");
  const ledgerPath = join(privateDirectory, COMMAND_LOG_NAME);
  if (!pathPresent(ledgerPath)) atomicWritePrivate(ledgerPath, "");
  const resultPath = join(outputDirectory, "result.json");
  const resultJsonSha256 = pathPresent(resultPath) ? sha256FileSync(resultPath) : null;
  const now = new Date().toISOString();
  const manifest = {
    schema: PRIVATE_MANIFEST_SCHEMA,
    testId: report.testId,
    createdAt: now,
    updatedAt: now,
    ownerUid: currentUid(),
    publicResult: {
      directory: resolve(outputDirectory),
      resultJsonSha256,
      automatedResultSha256: null,
      sealedReceiptSha256: null,
      finalizationId: null,
      finalVerificationSha256: null,
      diagnosticZipSha256: null,
      publicZipSha256: null,
    },
    commandLedger: {
      relativePath: COMMAND_LOG_NAME,
      ...commandLedgerState(privateDirectory),
    },
    recording: {
      status: "pending",
      testId: report.testId,
      receiptRelativePath: null,
      receiptSha256: null,
      recordingSha256: null,
      reviewStatus: "pending",
    },
    retention: {
      status: "active",
      policy: "owner_guarded_exact_cleanup_after_public_handoff",
      cleanupAuthorized: false,
    },
  };
  atomicWritePrivate(target, `${JSON.stringify(manifest, null, 2)}\n`);
  return manifest;
}

function refreshedPrivateEvidenceManifest(
  privateDirectory,
  outputDirectory = null,
  report = null,
  {
    ledgerContents = null,
    updatedAt = new Date().toISOString(),
    resultOverride = false,
  } = {},
) {
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  const expectedOutput = resolve(outputDirectory ?? manifest.publicResult.directory);
  if (resolve(manifest.publicResult.directory) !== expectedOutput) {
    fail("private-evidence", "the private evidence manifest points to a different public result");
  }
  if (report !== null && report.testId !== manifest.testId) {
    fail("private-evidence", "the private and public test identities do not match");
  }
  const resultPath = join(expectedOutput, "result.json");
  if ((report !== null && resultOverride) || pathPresent(resultPath)) {
    let result;
    let resultBytes;
    if (report !== null && resultOverride) {
      result = structuredClone(report);
      resultBytes = publicReportFileBytes(result)["result.json"];
    } else {
      requireExactPrivateMode(resultPath, "public result JSON", "file", 0o600);
      resultBytes = readFileSync(resultPath);
      result = parseJson(
        resultBytes.toString("utf8"),
        "private-evidence",
        "the linked public result JSON is invalid",
      );
    }
    if (result?.testId !== manifest.testId) {
      fail("private-evidence", "the linked public result has a different test identity");
    }
    const digest = sha256Buffer(resultBytes);
    manifest.publicResult.resultJsonSha256 = digest;
    if (
      result.automatedResult === "passed" &&
      result.manualResult === "pending" &&
      result.overallResult === "pending" &&
      result.mutation?.finalState === "installed"
    ) {
      if (!pathPresent(sealedPublicDirectory(privateDirectory))) {
        fail("private-evidence", "a passed automated result is missing its sealed receipt");
      }
      const sealed = validateSealedPublicResult(privateDirectory, manifest.testId);
      if (
        sealed.receipt.files["result.json"].sha256 !== digest ||
        JSON.stringify(sealed.report) !== JSON.stringify(result)
      ) {
        fail("private-evidence", "the passed automated result differs from its sealed bytes");
      }
      const existingLinkage = [
        manifest.publicResult.automatedResultSha256,
        manifest.publicResult.sealedReceiptSha256,
        manifest.publicResult.finalizationId,
        manifest.publicResult.finalVerificationSha256,
      ];
      const nextLinkage = [
        digest,
        sealed.receiptSha256,
        sealed.receipt.finalizationId,
        sealed.receipt.finalVerificationSha256,
      ];
      if (
        existingLinkage.some(
          (value, index) => value !== null && value !== nextLinkage[index],
        )
      ) {
        fail("private-evidence", "the sealed automated-result linkage changed");
      }
      [
        manifest.publicResult.automatedResultSha256,
        manifest.publicResult.sealedReceiptSha256,
        manifest.publicResult.finalizationId,
        manifest.publicResult.finalVerificationSha256,
      ] = nextLinkage;
    }
  }
  manifest.commandLedger = {
    relativePath: COMMAND_LOG_NAME,
    ...(ledgerContents === null
      ? commandLedgerState(privateDirectory)
      : commandLedgerStateFromContents(ledgerContents)),
  };
  manifest.updatedAt = updatedAt;
  return manifest;
}

function refreshPrivateEvidenceManifest(privateDirectory, outputDirectory = null, report = null) {
  const manifest = refreshedPrivateEvidenceManifest(
    privateDirectory,
    outputDirectory,
    report,
  );
  atomicWritePrivate(
    join(privateDirectory, PRIVATE_MANIFEST_NAME),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
  return manifest;
}

function evidenceFileDigest(target, label) {
  if (!pathPresent(target)) return null;
  requireExactPrivateMode(target, label, "file", 0o600);
  return sha256FileSync(target);
}

function evidenceTransactionDestination(privateDirectory, outputDirectory, role) {
  if (role === "command-ledger") return join(privateDirectory, COMMAND_LOG_NAME);
  if (role === "private-manifest") return join(privateDirectory, PRIVATE_MANIFEST_NAME);
  if (role === "result-json") return join(outputDirectory, "result.json");
  if (role === "result-markdown") return join(outputDirectory, "result.md");
  if (role === "manual-observations") return join(outputDirectory, "manual-observations.md");
  fail("evidence-transaction", "the evidence transaction contains an unsupported role");
}

function validateEvidenceTransaction(privateDirectory) {
  const target = join(privateDirectory, EVIDENCE_TRANSACTION_NAME);
  requireExactPrivateMode(target, "private evidence transaction", "file", 0o600);
  const receipt = parseJson(
    readFileSync(target, "utf8"),
    "evidence-transaction",
    "the private evidence transaction is invalid JSON",
  );
  requireExactObjectKeys(
    receipt,
    [
      "schema",
      "transactionId",
      "kind",
      "testId",
      "outputDirectory",
      "createdAt",
      "files",
    ],
    "evidence-transaction",
    "the private evidence transaction",
  );
  if (
    receipt.schema !== EVIDENCE_TRANSACTION_SCHEMA ||
    !UUID_V4_PATTERN.test(receipt.transactionId ?? "") ||
    !new Set(["command-ledger", "public-report"]).has(receipt.kind) ||
    !UUID_V4_PATTERN.test(receipt.testId ?? "") ||
    typeof receipt.outputDirectory !== "string" ||
    resolve(receipt.outputDirectory) !== receipt.outputDirectory ||
    !Number.isFinite(Date.parse(receipt.createdAt)) ||
    !Array.isArray(receipt.files)
  ) {
    fail("evidence-transaction", "the private evidence transaction identity is invalid");
  }
  const expectedRoles =
    receipt.kind === "command-ledger"
      ? ["command-ledger", "private-manifest"]
      : [
          "result-json",
          "result-markdown",
          "manual-observations",
          "private-manifest",
        ];
  if (!sameStrings(receipt.files.map((item) => item?.role), expectedRoles)) {
    fail("evidence-transaction", "the private evidence transaction role set is invalid");
  }
  const files = receipt.files.map((item) => {
    requireExactObjectKeys(
      item,
      ["role", "oldSha256", "newSha256", "sizeBytes", "bytesBase64"],
      "evidence-transaction",
      "a private evidence transaction member",
    );
    if (
      !(item.oldSha256 === null || /^[a-f0-9]{64}$/u.test(item.oldSha256 ?? "")) ||
      !/^[a-f0-9]{64}$/u.test(item.newSha256 ?? "") ||
      !Number.isSafeInteger(item.sizeBytes) ||
      item.sizeBytes < 0 ||
      item.sizeBytes > MAX_COMMAND_OUTPUT_BYTES ||
      typeof item.bytesBase64 !== "string"
    ) {
      fail("evidence-transaction", "a private evidence transaction member is invalid");
    }
    const bytes = Buffer.from(item.bytesBase64, "base64");
    if (
      bytes.toString("base64") !== item.bytesBase64 ||
      bytes.length !== item.sizeBytes ||
      sha256Buffer(bytes) !== item.newSha256
    ) {
      fail("evidence-transaction", "a private evidence transaction member changed");
    }
    return { ...item, bytes };
  });
  return { receipt, files, target };
}

function reconcileEvidenceTransactionStaging(privateDirectory) {
  const pattern = new RegExp(
    `^\\.${EVIDENCE_TRANSACTION_NAME.replaceAll(".", "\\.")}\\.${UUID_V4_FRAGMENT}\\.tmp$`,
    "u",
  );
  for (const name of readdirSync(privateDirectory).filter((entry) => pattern.test(entry))) {
    const target = join(privateDirectory, name);
    requireExactPrivateMode(target, "private evidence transaction staging", "file", 0o600);
    unlinkSync(target);
    syncEntry(privateDirectory);
  }
}

export function recoverEvidenceTransaction(
  privateDirectory,
  { afterRolePublished = () => {} } = {},
) {
  if (typeof afterRolePublished !== "function") {
    fail("evidence-transaction", "the evidence transaction recovery hook is invalid");
  }
  requireExactPrivateMode(privateDirectory, "private evidence directory", "directory", 0o700);
  reconcileEvidenceTransactionStaging(privateDirectory);
  const transactionPath = join(privateDirectory, EVIDENCE_TRANSACTION_NAME);
  if (!pathPresent(transactionPath)) return false;
  const transaction = validateEvidenceTransaction(privateDirectory);
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  const outputDirectory = resolve(transaction.receipt.outputDirectory);
  if (
    manifest.testId !== transaction.receipt.testId ||
    resolve(manifest.publicResult.directory) !== outputDirectory
  ) {
    fail("evidence-transaction", "the evidence transaction does not bind this private run");
  }
  requireExactPrivateMode(outputDirectory, "public result directory", "directory", 0o700);
  const states = transaction.files.map((item) => {
    const destination = evidenceTransactionDestination(
      privateDirectory,
      outputDirectory,
      item.role,
    );
    const currentSha256 = evidenceFileDigest(
      destination,
      `evidence transaction destination ${item.role}`,
    );
    if (currentSha256 !== item.oldSha256 && currentSha256 !== item.newSha256) {
      fail("evidence-transaction", "an evidence transaction destination has unexpected bytes");
    }
    return { ...item, destination, currentSha256 };
  });
  const manifestState = states.find((item) => item.role === "private-manifest");
  if (
    manifestState.currentSha256 === manifestState.newSha256 &&
    states.some(
      (item) => item.role !== "private-manifest" && item.currentSha256 !== item.newSha256,
    )
  ) {
    fail("evidence-transaction", "the evidence manifest advanced before its bound files");
  }
  for (const item of states.filter((entry) => entry.role !== "private-manifest")) {
    if (item.currentSha256 === item.newSha256) continue;
    if (item.role === "command-ledger") {
      atomicWritePrivate(item.destination, item.bytes.toString("utf8"));
    } else {
      atomicWriteOwnerFile(item.destination, item.bytes, "evidence-transaction");
    }
    if (sha256FileSync(item.destination) !== item.newSha256) {
      fail("evidence-transaction", "an evidence transaction file did not publish exactly");
    }
    afterRolePublished(item.role);
  }
  const currentManifestSha256 = sha256FileSync(manifestState.destination);
  if (currentManifestSha256 !== manifestState.newSha256) {
    atomicWritePrivate(manifestState.destination, manifestState.bytes.toString("utf8"));
    if (sha256FileSync(manifestState.destination) !== manifestState.newSha256) {
      fail("evidence-transaction", "the evidence transaction manifest did not publish exactly");
    }
    afterRolePublished("private-manifest");
  }
  unlinkSync(transaction.target);
  syncEntry(privateDirectory);
  return true;
}

function commitEvidenceTransaction(
  privateDirectory,
  outputDirectory,
  testId,
  kind,
  files,
  manifestBytes,
  testHooks = {},
) {
  const hooks = {
    afterJournalPublished: () => {},
    afterRolePublished: () => {},
    ...testHooks,
  };
  if (Object.values(hooks).some((hook) => typeof hook !== "function")) {
    fail("evidence-transaction", "the evidence transaction test hook contract is invalid");
  }
  recoverEvidenceTransaction(privateDirectory);
  const resolvedOutput = resolve(outputDirectory);
  requireExactPrivateMode(resolvedOutput, "public result directory", "directory", 0o700);
  const members = [
    ...files,
    { role: "private-manifest", bytes: Buffer.from(manifestBytes) },
  ].map(({ role, bytes }) => {
    const buffer = Buffer.from(bytes);
    const destination = evidenceTransactionDestination(
      privateDirectory,
      resolvedOutput,
      role,
    );
    return {
      role,
      oldSha256: evidenceFileDigest(destination, `evidence transaction source ${role}`),
      newSha256: sha256Buffer(buffer),
      sizeBytes: buffer.length,
      bytesBase64: buffer.toString("base64"),
    };
  });
  const receipt = {
    schema: EVIDENCE_TRANSACTION_SCHEMA,
    transactionId: randomUUID(),
    kind,
    testId,
    outputDirectory: resolvedOutput,
    createdAt: new Date().toISOString(),
    files: members,
  };
  atomicWritePrivate(
    join(privateDirectory, EVIDENCE_TRANSACTION_NAME),
    `${JSON.stringify(receipt, null, 2)}\n`,
  );
  hooks.afterJournalPublished();
  recoverEvidenceTransaction(privateDirectory, {
    afterRolePublished: hooks.afterRolePublished,
  });
}

function validatePrivateEvidenceManifest(privateDirectory, outputDirectory, testId) {
  recoverEvidenceTransaction(privateDirectory);
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  const expectedOutput = resolve(outputDirectory);
  if (
    manifest.testId !== testId ||
    resolve(manifest.publicResult.directory) !== expectedOutput ||
    !/^[a-f0-9]{64}$/u.test(manifest.commandLedger.sha256 ?? "")
  ) {
    fail("private-evidence", "the private evidence manifest does not match this acceptance run");
  }
  requireExactPrivateMode(expectedOutput, "public result directory", "directory", 0o700);
  const resultPath = join(expectedOutput, "result.json");
  requireExactPrivateMode(resultPath, "public result JSON", "file", 0o600);
  const result = parseJson(
    readFileSync(resultPath, "utf8"),
    "private-evidence",
    "the linked public result JSON is invalid",
  );
  const ledger = commandLedgerState(privateDirectory);
  if (
    result?.testId !== testId ||
    sha256FileSync(resultPath) !== manifest.publicResult.resultJsonSha256 ||
    ledger.sha256 !== manifest.commandLedger.sha256 ||
    ledger.entryCount !== manifest.commandLedger.entryCount
  ) {
    fail("private-evidence", "the linked public result or private command ledger changed");
  }
  if (manifest.recording.status === "pending") {
    if (
      manifest.recording.receiptRelativePath !== null ||
      manifest.recording.receiptSha256 !== null ||
      manifest.recording.recordingSha256 !== null ||
      manifest.recording.reviewStatus !== "pending"
    ) {
      fail("private-evidence", "the pending recording linkage is inconsistent");
    }
  } else {
    const receiptRelative = manifest.recording.receiptRelativePath;
    if (
      receiptRelative !== "record-and-replay-receipt.json" ||
      !/^[a-f0-9]{64}$/u.test(manifest.recording.receiptSha256 ?? "") ||
      !/^[a-f0-9]{64}$/u.test(manifest.recording.recordingSha256 ?? "") ||
      manifest.recording.reviewStatus !== "reviewed"
    ) {
      fail("private-evidence", "the verified recording linkage is incomplete");
    }
    const receiptPath = join(privateDirectory, receiptRelative);
    requireExactPrivateMode(receiptPath, "Record and Replay receipt", "file", 0o600);
    if (sha256FileSync(receiptPath) !== manifest.recording.receiptSha256) {
      fail("private-evidence", "the Record and Replay receipt changed");
    }
    const receipt = parseJson(
      readFileSync(receiptPath, "utf8"),
      "private-evidence",
      "the Record and Replay receipt is invalid",
    );
    requireExactObjectKeys(
      receipt,
      ["schema", "testId", "recordingRelativePath", "recordingSha256", "reviewStatus"],
      "private-evidence",
      "the Record and Replay receipt",
    );
    if (
      receipt.schema !== "opensocrates.record-and-replay-receipt/1.0.0" ||
      receipt.testId !== testId ||
      receipt.recordingSha256 !== manifest.recording.recordingSha256 ||
      receipt.reviewStatus !== "reviewed" ||
      typeof receipt.recordingRelativePath !== "string"
    ) {
      fail("private-evidence", "the Record and Replay receipt identity is invalid");
    }
    const recordingPath = join(privateDirectory, ...receipt.recordingRelativePath.split("/"));
    assertPathBelow(privateDirectory, recordingPath, "private Record and Replay capture", "file");
    requireExactPrivateMode(recordingPath, "private Record and Replay capture", "file", 0o600);
    if (sha256FileSync(recordingPath) !== receipt.recordingSha256) {
      fail("private-evidence", "the private Record and Replay capture changed");
    }
  }
  for (const [digest, archive, label] of [
    [manifest.publicResult.diagnosticZipSha256, `${expectedOutput}.diagnostic.zip`, "diagnostic public result ZIP"],
    [manifest.publicResult.publicZipSha256, `${expectedOutput}.zip`, "public result ZIP"],
  ]) {
    if (digest === null || !pathPresent(archive)) continue;
    requireExactPrivateMode(archive, label, "file", 0o600);
    if (sha256FileSync(archive) !== digest) {
      fail("private-evidence", `${label} changed after its durable linkage`);
    }
  }
  return manifest;
}

function bindRecordingReceipt(privateDirectory, recordingPath, testId) {
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  if (manifest.testId !== testId || manifest.recording.status !== "pending") {
    fail("private-evidence", "the recording receipt does not match a pending acceptance test");
  }
  const canonicalRecording = assertPathBelow(
    privateDirectory,
    resolve(recordingPath),
    "private Record and Replay capture",
    "file",
  );
  requireExactPrivateMode(
    canonicalRecording,
    "private Record and Replay capture",
    "file",
    0o600,
  );
  const recordingRelativePath = relative(privateDirectory, canonicalRecording).split(sep).join("/");
  if (new Set([PRIVATE_MANIFEST_NAME, COMMAND_LOG_NAME, CHECKPOINT_NAME]).has(recordingRelativePath)) {
    fail("private-evidence", "the recording receipt cannot bind a lifecycle control file");
  }
  const receiptPath = join(privateDirectory, "record-and-replay-receipt.json");
  if (pathPresent(receiptPath)) fail("private-evidence", "the recording receipt already exists");
  const recordingSha256 = sha256FileSync(canonicalRecording);
  const receipt = {
    schema: "opensocrates.record-and-replay-receipt/1.0.0",
    testId,
    recordingRelativePath,
    recordingSha256,
    reviewStatus: "reviewed",
  };
  atomicWritePrivate(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  manifest.recording = {
    status: "verified",
    testId,
    receiptRelativePath: "record-and-replay-receipt.json",
    receiptSha256: sha256FileSync(receiptPath),
    recordingSha256,
    reviewStatus: "reviewed",
  };
  manifest.updatedAt = new Date().toISOString();
  atomicWritePrivate(
    join(privateDirectory, PRIVATE_MANIFEST_NAME),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
  return receipt;
}

const ISOLATED_NPX_BIN_LINK_PATTERN = new RegExp(
  "^isolated-npx/runs/(?:call-[A-Za-z0-9]{6}|lifecycle-(?:purge-initial|purge-host-close-retry|install-initial|install-retry))/cache/_npx/[a-f0-9]{16}/node_modules/\\.bin/opensocrates$",
  "u",
);

function verifyExpectedCleanupSymlink(privateRoot, target, rootDevice, info) {
  const local = relative(privateRoot, target).split(sep).join("/");
  if (
    info.uid !== currentUid() ||
    info.dev !== rootDevice ||
    !ISOLATED_NPX_BIN_LINK_PATTERN.test(local) ||
    readlinkSync(target) !== "../opensocrates/installer/opensocrates.mjs"
  ) {
    fail("private-evidence", "the private cleanup tree contains an unsafe link");
  }
  const resolvedTarget = realpathSync(target);
  const resolvedLocal = relative(privateRoot, resolvedTarget);
  const resolvedInfo = lstatSync(resolvedTarget);
  if (
    resolvedLocal === "" ||
    resolvedLocal === ".." ||
    resolvedLocal.startsWith(`..${sep}`) ||
    !resolvedInfo.isFile() ||
    resolvedInfo.isSymbolicLink() ||
    resolvedInfo.uid !== currentUid() ||
    resolvedInfo.dev !== rootDevice ||
    resolvedInfo.nlink !== 1
  ) {
    fail("private-evidence", "the private cleanup npm link escapes its owned run root");
  }
}

function verifyOwnedCleanupTree(directory, privateRoot = directory, rootDevice = null) {
  const rootInfo = requireCanonicalOwnedEntry(directory, "private cleanup root", "directory");
  const expectedDevice = rootDevice ?? rootInfo.dev;
  if (rootDevice === null && (rootInfo.mode & 0o077) !== 0) {
    fail("private-evidence", "the private cleanup root is not owner-only");
  }
  if (rootInfo.dev !== expectedDevice) {
    fail("private-evidence", "the private cleanup tree crosses a filesystem boundary");
  }
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = join(directory, entry.name);
    const info = lstatSync(target);
    if (info.isSymbolicLink()) {
      verifyExpectedCleanupSymlink(privateRoot, target, expectedDevice, info);
      continue;
    }
    if (info.uid !== currentUid() || info.dev !== expectedDevice) {
      fail("private-evidence", "the private cleanup tree contains an unsafe entry");
    }
    if (entry.isDirectory()) {
      verifyOwnedCleanupTree(target, privateRoot, expectedDevice);
    } else if (!entry.isFile() || info.nlink !== 1) {
      fail("private-evidence", "the private cleanup tree contains a special or linked file");
    }
  }
}

function cleanupPrivateEvidence(
  privateDirectoryArgument,
  testId,
  publicZipSha256,
  {
    expectedParent = PRIVATE_PARENT,
    requiredPrefix = PRIVATE_DIRECTORY_PREFIX,
    publicBundlePath = null,
    allowMissingBundle = false,
    afterCleanupAuthorized = () => {},
  } = {},
) {
  if (
    typeof requiredPrefix !== "string" ||
    requiredPrefix.length === 0 ||
    !/^[a-f0-9]{64}$/u.test(publicZipSha256 ?? "") ||
    typeof allowMissingBundle !== "boolean" ||
    typeof afterCleanupAuthorized !== "function"
  ) {
    fail("private-evidence", "private cleanup requires an exact public ZIP digest and prefix");
  }
  const parent = realpathSync(resolve(expectedParent));
  requireCanonicalOwnedEntry(parent, "private cleanup parent", "directory");
  const privateDirectory = realpathSync(resolve(privateDirectoryArgument));
  if (
    dirname(privateDirectory) !== parent ||
    !basename(privateDirectory).startsWith(requiredPrefix) ||
    privateDirectory === parent
  ) {
    fail("private-evidence", "private cleanup is limited to one exact acceptance run directory");
  }
  if (pathPresent(join(privateDirectory, RUN_LOCK_NAME))) {
    fail("private-evidence", "private cleanup is forbidden while an acceptance run lock exists");
  }
  const manifest = readPrivateEvidenceManifest(privateDirectory);
  const storedDigests = new Set(
    [
      manifest.publicResult.publicZipSha256,
      manifest.publicResult.diagnosticZipSha256,
    ].filter((value) => value !== null),
  );
  if (manifest.testId !== testId || !storedDigests.has(publicZipSha256)) {
    fail("private-evidence", "private cleanup confirmation does not match a retained bundle");
  }
  if (manifest.retention.status === "cleanup_authorized") {
    verifyOwnedCleanupTree(privateDirectory);
    rmSync(privateDirectory, { recursive: true, force: false });
    syncEntry(parent);
    return { status: "cleaned_after_authorized_retry" };
  }
  const validated = validatePrivateEvidenceManifest(
    privateDirectory,
    manifest.publicResult.directory,
    testId,
  );
  if (
    !new Set(["diagnostic_bundle_ready", "public_bundle_ready"]).has(
      validated.retention.status,
    ) ||
    validated.retention.cleanupAuthorized !== false ||
    !storedDigests.has(publicZipSha256)
  ) {
    fail("private-evidence", "private cleanup confirmation does not match the retained public bundle");
  }
  let bundleToVerify = publicBundlePath === null
    ? publicZipSha256 === validated.publicResult.publicZipSha256
      ? `${validated.publicResult.directory}.zip`
      : `${validated.publicResult.directory}.diagnostic.zip`
    : resolve(publicBundlePath);
  if (pathPresent(bundleToVerify)) {
    requireExactPrivateMode(bundleToVerify, "confirmed public cleanup bundle", "file", 0o600);
    if (sha256FileSync(bundleToVerify) !== publicZipSha256) {
      fail("private-evidence", "the confirmed public cleanup bundle digest does not match");
    }
  } else if (!allowMissingBundle || publicBundlePath !== null) {
    fail(
      "private-evidence",
      "the retained bundle is missing; use the explicit no-bundle cleanup confirmation only after recording its digest",
    );
  }
  verifyOwnedCleanupTree(privateDirectory);
  validated.retention.status = "cleanup_authorized";
  validated.retention.cleanupAuthorized = true;
  validated.updatedAt = new Date().toISOString();
  atomicWritePrivate(
    join(privateDirectory, PRIVATE_MANIFEST_NAME),
    `${JSON.stringify(validated, null, 2)}\n`,
  );
  afterCleanupAuthorized();
  verifyOwnedCleanupTree(privateDirectory);
  rmSync(privateDirectory, { recursive: true, force: false });
  syncEntry(parent);
  return { status: "cleaned" };
}

function lifecycleProcessGroupAlive(processGroupId) {
  if (!Number.isSafeInteger(processGroupId) || processGroupId <= 1) {
    fail("lifecycle-recovery", "the lifecycle process-group identity is invalid");
  }
  try {
    process.kill(-processGroupId, 0);
    return true;
  } catch (error) {
    if (error?.code === "EPERM") return true;
    if (error?.code === "ESRCH") return false;
    fail("lifecycle-recovery", "the lifecycle process group cannot be checked safely");
  }
}

function safeLifecycleEnvironment(environment) {
  if (
    environment === null ||
    typeof environment !== "object" ||
    Array.isArray(environment) ||
    Object.getPrototypeOf(environment) !== Object.prototype
  ) {
    fail("lifecycle-intent", "the lifecycle environment is not a closed plain object");
  }
  const forbidden = /(?:TOKEN|SECRET|CREDENTIAL|PASSWORD|AUTH|COOKIE|NODE_OPTIONS|BASH_ENV)/iu;
  const entries = Object.entries(environment).sort(([left], [right]) => left.localeCompare(right));
  if (
    entries.length === 0 ||
    entries.some(
      ([key, value]) =>
        !/^[A-Za-z_][A-Za-z0-9_]*$/u.test(key) ||
        forbidden.test(key) ||
        typeof value !== "string" ||
        value.includes("\0"),
    )
  ) {
    fail("lifecycle-intent", "the lifecycle environment contains an unsupported value");
  }
  return Object.fromEntries(entries);
}

function lifecycleAttempt(operationKey) {
  if (operationKey === "purge-initial" || operationKey === "install-initial") return 1;
  if (operationKey === "purge-host-close-retry" || operationKey === "install-retry") return 2;
  fail("lifecycle-intent", "the lifecycle operation key is unsupported");
}

function lifecycleOperationRoot(privateDirectory, { create = false } = {}) {
  requireExactPrivateMode(privateDirectory, "private lifecycle root", "directory", 0o700);
  const root = join(privateDirectory, LIFECYCLE_OPERATIONS_NAME);
  if (!pathPresent(root)) {
    if (!create) return null;
    ensurePrivateDirectory(root);
  }
  requireExactPrivateMode(root, "private lifecycle operation directory", "directory", 0o700);
  return root;
}

function requireLifecycleJsonEntry(
  target,
  label,
  { inspectEntry = lstatSync, readDirectory = readdirSync, canonicalizeEntry = realpathSync } = {},
) {
  if (basename(target) !== "claimed.json") {
    const info = inspectEntry(target);
    if (info.nlink !== 1) {
      fail("lifecycle-recovery", `${label} is not a single-link owner-only receipt`);
    }
    return requireExactPrivateMode(target, label, "file", 0o600);
  }
  const parent = dirname(target);
  const inspectPresent = (candidate) => {
    try {
      return inspectEntry(candidate);
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      throw error;
    }
  };
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const info = inspectEntry(target);
    const stageEntries = readDirectory(parent)
      .filter((name) => CLAIM_PUBLISH_STAGE_PATTERN.test(name))
      .map((name) => {
        const candidate = join(parent, name);
        return { candidate, info: inspectPresent(candidate) };
      })
      .filter((entry) => entry.info !== null);
    const current = inspectEntry(target);
    if (current.dev !== info.dev || current.ino !== info.ino) {
      fail("lifecycle-recovery", `${label} changed identity during atomic publish inspection`);
    }
    if (current.nlink === 1) {
      const survivingStages = stageEntries.filter(
        (entry) => inspectPresent(entry.candidate) !== null,
      );
      if (survivingStages.length !== 0) {
        fail("lifecycle-recovery", `${label} has an unrelated atomic publish staging entry`);
      }
      return requireExactPrivateMode(target, label, "file", 0o600);
    }
    if (
      basename(target) !== "claimed.json" ||
      current.isSymbolicLink() ||
      !current.isFile() ||
      current.uid !== currentUid() ||
      current.nlink !== 2 ||
      (current.mode & 0o777) !== 0o600 ||
      canonicalizeEntry(target) !== resolve(target)
    ) {
      fail("lifecycle-recovery", `${label} is not an atomic owner-only receipt`);
    }
    const linkedStages = stageEntries.filter(
      (entry) => entry.info.dev === current.dev && entry.info.ino === current.ino,
    );
    if (stageEntries.length !== 1 || linkedStages.length !== 1) {
      if (stageEntries.length === 0 && attempt < 2) continue;
      fail("lifecycle-recovery", `${label} has an invalid atomic publish linkage`);
    }
    const [{ candidate, info: stagingInfo }] = linkedStages;
    try {
      if (
        stagingInfo.isSymbolicLink() ||
        !stagingInfo.isFile() ||
        stagingInfo.uid !== currentUid() ||
        stagingInfo.nlink !== 2 ||
        (stagingInfo.mode & 0o777) !== 0o600 ||
        canonicalizeEntry(candidate) !== resolve(candidate)
      ) {
        fail("lifecycle-recovery", `${label} has an unsafe atomic publish staging entry`);
      }
      return current;
    } catch (error) {
      if (error?.code !== "ENOENT" || attempt === 2) throw error;
    }
  }
  fail("lifecycle-recovery", `${label} did not converge after atomic publish inspection`);
}

function parseLifecycleJson(target, schema, keys, label) {
  requireLifecycleJsonEntry(target, label);
  const bytes = readFileSync(target);
  const value = parseJson(bytes.toString("utf8"), "lifecycle-recovery", `${label} is invalid JSON`);
  requireExactObjectKeys(value, keys, "lifecycle-recovery", label);
  if (value.schema !== schema) fail("lifecycle-recovery", `${label} has an unsupported schema`);
  return { value, bytes, sha256: sha256Buffer(bytes) };
}

function lifecycleOperationRecord(
  operationDirectory,
  { requiredDirectoryName = basename(operationDirectory) } = {},
) {
  requireExactPrivateMode(operationDirectory, "lifecycle operation", "directory", 0o700);
  const intentRecord = parseLifecycleJson(
    join(operationDirectory, "intent.json"),
    LIFECYCLE_INTENT_SCHEMA,
    [
      "schema",
      "operationId",
      "operationKey",
      "sequence",
      "attempt",
      "label",
      "executable",
      "executableSha256",
      "args",
      "argvSha256",
      "cwd",
      "env",
      "environmentSha256",
      "timeoutMs",
      "candidateIdentitySha256",
      "capsuleSha256",
      "previousOperationSha256",
      "preparedAt",
      "requestSha256",
    ],
    "lifecycle intent",
  );
  const intent = intentRecord.value;
  if (
    !/^[0-9a-f-]{36}$/u.test(intent.operationId ?? "") ||
    !/^[a-z0-9-]+$/u.test(intent.operationKey ?? "") ||
    !Number.isSafeInteger(intent.sequence) ||
    intent.sequence < 1 ||
    intent.attempt !== lifecycleAttempt(intent.operationKey) ||
    typeof intent.label !== "string" ||
    intent.label.length === 0 ||
    typeof intent.executable !== "string" ||
    realpathSync(intent.executable) !== intent.executable ||
    !statSync(intent.executable).isFile() ||
    !Array.isArray(intent.args) ||
    intent.args.some((item) => typeof item !== "string" || item.includes("\0")) ||
    intent.argvSha256 !== sha256Buffer(JSON.stringify(intent.args)) ||
    typeof intent.cwd !== "string" ||
    realpathSync(intent.cwd) !== intent.cwd ||
    !statSync(intent.cwd).isDirectory() ||
    intent.environmentSha256 !== sha256Buffer(JSON.stringify(safeLifecycleEnvironment(intent.env))) ||
    !Number.isSafeInteger(intent.timeoutMs) ||
    intent.timeoutMs < 1 ||
    intent.timeoutMs > 900_000 ||
    !/^[a-f0-9]{64}$/u.test(intent.candidateIdentitySha256 ?? "") ||
    !/^[a-f0-9]{64}$/u.test(intent.executableSha256 ?? "") ||
    !/^[a-f0-9]{64}$/u.test(intent.capsuleSha256 ?? "") ||
    sha256FileSync(intent.executable) !== intent.executableSha256 ||
    sha256FileSync(LIFECYCLE_CAPSULE) !== intent.capsuleSha256
  ) {
    fail("lifecycle-recovery", "the lifecycle intent identity changed or is unsupported");
  }
  const canonicalDirectoryName =
    `${String(intent.sequence).padStart(3, "0")}-${intent.operationKey}`;
  if (requiredDirectoryName !== canonicalDirectoryName) {
    fail("lifecycle-recovery", "the lifecycle operation sequence path is invalid");
  }
  const claimPath = join(operationDirectory, "claimed.json");
  const terminalPath = join(operationDirectory, "terminal.json");
  const blockedPath = join(operationDirectory, "blocked.json");
  let claimRecord = null;
  if (pathPresent(claimPath)) {
    claimRecord = parseLifecycleJson(
      claimPath,
      LIFECYCLE_CLAIM_SCHEMA,
      [
        "schema",
        "operationId",
        "operationKey",
        "sequence",
        "attempt",
        "state",
        "capsulePid",
        "processGroupId",
        "intentSha256",
        "stdoutFile",
        "stderrFile",
        "claimedAt",
      ],
      "lifecycle claim",
    );
    const claim = claimRecord.value;
    if (
      claim.operationId !== intent.operationId ||
      claim.operationKey !== intent.operationKey ||
      claim.sequence !== intent.sequence ||
      claim.attempt !== intent.attempt ||
      claim.state !== "claimed" ||
      !Number.isSafeInteger(claim.capsulePid) ||
      claim.capsulePid <= 1 ||
      claim.processGroupId !== claim.capsulePid ||
      claim.intentSha256 !== intentRecord.sha256 ||
      claim.stdoutFile !== "stdout.bin" ||
      claim.stderrFile !== "stderr.bin"
    ) {
      fail("lifecycle-recovery", "the lifecycle claim does not bind the exact intent");
    }
  }
  let terminalRecord = null;
  if (pathPresent(terminalPath)) {
    if (claimRecord === null) fail("lifecycle-recovery", "a terminal lifecycle has no durable claim");
    terminalRecord = parseLifecycleJson(
      terminalPath,
      LIFECYCLE_TERMINAL_SCHEMA,
      [
        "schema",
        "operationId",
        "operationKey",
        "sequence",
        "attempt",
        "state",
        "intentSha256",
        "claimSha256",
        "childPid",
        "completedAt",
        "durationMs",
        "exitStatus",
        "signal",
        "spawnError",
        "timedOut",
        "outputLimitExceeded",
        "processGroupQuiescent",
        "stdoutSha256",
        "stderrSha256",
        "stdoutSizeBytes",
        "stderrSizeBytes",
        "operationSha256",
      ],
      "lifecycle terminal receipt",
    );
    const terminal = terminalRecord.value;
    const terminalBase = { ...terminal };
    delete terminalBase.operationSha256;
    if (
      terminal.operationId !== intent.operationId ||
      terminal.operationKey !== intent.operationKey ||
      terminal.sequence !== intent.sequence ||
      terminal.attempt !== intent.attempt ||
      terminal.state !== "terminal" ||
      terminal.intentSha256 !== intentRecord.sha256 ||
      terminal.claimSha256 !== claimRecord.sha256 ||
      !Number.isSafeInteger(terminal.durationMs) ||
      terminal.durationMs < 0 ||
      !(terminal.exitStatus === null || Number.isSafeInteger(terminal.exitStatus)) ||
      typeof terminal.timedOut !== "boolean" ||
      typeof terminal.outputLimitExceeded !== "boolean" ||
      terminal.processGroupQuiescent !== true ||
      !/^[a-f0-9]{64}$/u.test(terminal.stdoutSha256 ?? "") ||
      !/^[a-f0-9]{64}$/u.test(terminal.stderrSha256 ?? "") ||
      terminal.operationSha256 !== sha256Buffer(JSON.stringify(terminalBase))
    ) {
      fail("lifecycle-recovery", "the lifecycle terminal receipt is invalid");
    }
    for (const [name, size, digest] of [
      ["stdout.bin", terminal.stdoutSizeBytes, terminal.stdoutSha256],
      ["stderr.bin", terminal.stderrSizeBytes, terminal.stderrSha256],
    ]) {
      const target = join(operationDirectory, name);
      requireExactPrivateMode(target, `lifecycle ${name}`, "file", 0o600);
      if (statSync(target).size !== size || sha256FileSync(target) !== digest) {
        fail("lifecycle-recovery", "a lifecycle stream changed after terminal receipt commit");
      }
    }
  }
  let blockedRecord = null;
  if (pathPresent(blockedPath)) {
    if (claimRecord === null || terminalRecord !== null) {
      fail("lifecycle-recovery", "the lifecycle blocked receipt has an impossible predecessor");
    }
    blockedRecord = parseLifecycleJson(
      blockedPath,
      LIFECYCLE_BLOCKED_SCHEMA,
      [
        "schema",
        "operationId",
        "operationKey",
        "sequence",
        "attempt",
        "state",
        "intentSha256",
        "claimSha256",
        "observedAt",
        "reason",
        "operationSha256",
      ],
      "lifecycle blocked receipt",
    );
    const blocked = blockedRecord.value;
    const blockedBase = { ...blocked };
    delete blockedBase.operationSha256;
    if (
      blocked.operationId !== intent.operationId ||
      blocked.operationKey !== intent.operationKey ||
      blocked.sequence !== intent.sequence ||
      blocked.attempt !== intent.attempt ||
      blocked.state !== "blocked_unverifiable" ||
      blocked.intentSha256 !== intentRecord.sha256 ||
      blocked.claimSha256 !== claimRecord.sha256 ||
      blocked.reason !== "claimed_process_group_gone_without_terminal_receipt" ||
      blocked.operationSha256 !== sha256Buffer(JSON.stringify(blockedBase))
    ) {
      fail("lifecycle-recovery", "the lifecycle blocked receipt is invalid");
    }
  }
  return {
    operationDirectory,
    intentRecord,
    claimRecord,
    terminalRecord,
    blockedRecord,
  };
}

function lifecycleOperationRecords(privateDirectory) {
  const root = lifecycleOperationRoot(privateDirectory);
  if (root === null) return [];
  const directories = readdirSync(root, { withFileTypes: true });
  if (directories.some((entry) => entry.isSymbolicLink() || !entry.isDirectory())) {
    fail("lifecycle-recovery", "the lifecycle operation journal contains an unsafe entry");
  }
  const records = directories
    .map((entry) => lifecycleOperationRecord(join(root, entry.name)))
    .sort((left, right) => left.intentRecord.value.sequence - right.intentRecord.value.sequence);
  let previousOperationSha256 = null;
  records.forEach((record, index) => {
    const intent = record.intentRecord.value;
    if (
      intent.sequence !== index + 1 ||
      intent.previousOperationSha256 !== previousOperationSha256
    ) {
      fail("lifecycle-recovery", "the lifecycle operation hash chain is invalid");
    }
    const terminalDigest = record.terminalRecord?.value.operationSha256 ?? null;
    const blockedDigest = record.blockedRecord?.value.operationSha256 ?? null;
    previousOperationSha256 = terminalDigest ?? blockedDigest;
    if (index < records.length - 1 && previousOperationSha256 === null) {
      fail("lifecycle-recovery", "a later lifecycle operation follows a nonterminal claim");
    }
  });
  return records;
}

export function reconcileMutationTelemetry(report, privateDirectory, checkpoint) {
  if (
    report?.mutation === null ||
    typeof report?.mutation !== "object" ||
    !Number.isSafeInteger(checkpoint?.recovery?.hostCloseRetriesUsed) ||
    checkpoint.recovery.hostCloseRetriesUsed < 0 ||
    checkpoint.recovery.hostCloseRetriesUsed > MAX_HOST_CLOSE_RETRIES ||
    !Number.isSafeInteger(checkpoint?.recovery?.reinstallRetriesUsed) ||
    checkpoint.recovery.reinstallRetriesUsed < 0 ||
    checkpoint.recovery.reinstallRetriesUsed > MAX_REINSTALL_RETRIES
  ) {
    fail("lifecycle-recovery", "mutation telemetry cannot be reconstructed from an invalid checkpoint");
  }
  const claimedKeys = lifecycleOperationRecords(privateDirectory)
    .filter((record) => record.claimRecord !== null)
    .map((record) => record.intentRecord.value.operationKey);
  if (new Set(claimedKeys).size !== claimedKeys.length) {
    fail("lifecycle-recovery", "the lifecycle journal contains a duplicate operation claim");
  }
  const purgeCommandAttempts = claimedKeys.filter((key) => key.startsWith("purge-")).length;
  const reinstallAttempts = claimedKeys.filter((key) => key.startsWith("install-")).length;
  const telemetry = {
    started: claimedKeys.length > 0,
    purgeCommandAttempts,
    trustResetAttempts: purgeCommandAttempts,
    reinstallAttempts,
    hostCloseRetriesUsed: checkpoint.recovery.hostCloseRetriesUsed,
    reinstallAttempted: reinstallAttempts > 0,
  };
  Object.assign(report.mutation, telemetry);
  return telemetry;
}

function writeLifecycleBlockedReceipt(record) {
  const intent = record.intentRecord.value;
  const blockedBase = {
    schema: LIFECYCLE_BLOCKED_SCHEMA,
    operationId: intent.operationId,
    operationKey: intent.operationKey,
    sequence: intent.sequence,
    attempt: intent.attempt,
    state: "blocked_unverifiable",
    intentSha256: record.intentRecord.sha256,
    claimSha256: record.claimRecord.sha256,
    observedAt: new Date().toISOString(),
    reason: "claimed_process_group_gone_without_terminal_receipt",
  };
  const blocked = {
    ...blockedBase,
    operationSha256: sha256Buffer(JSON.stringify(blockedBase)),
  };
  writeExclusivePrivateBytes(
    join(record.operationDirectory, "blocked.json"),
    Buffer.from(`${JSON.stringify(blocked, null, 2)}\n`),
    "lifecycle-recovery",
  );
  syncEntry(record.operationDirectory);
}

export function inspectLifecycleOperation(privateDirectoryArgument, operationKey) {
  const privateDirectory = resolve(privateDirectoryArgument);
  const record = lifecycleOperationRecords(privateDirectory).find(
    (item) => item.intentRecord.value.operationKey === operationKey,
  );
  if (!record) {
    return {
      state: "none",
      operationKey,
      attempt: lifecycleAttempt(operationKey),
      terminalReceiptPresent: false,
      streamsRetained: false,
    };
  }
  const intent = record.intentRecord.value;
  if (record.terminalRecord !== null) {
    return {
      state: "terminal",
      operationKey,
      attempt: intent.attempt,
      operationId: intent.operationId,
      processGroupId: record.claimRecord.value.processGroupId,
      terminalReceiptPresent: true,
      streamsRetained: true,
      operationSha256: record.terminalRecord.value.operationSha256,
      terminal: structuredClone(record.terminalRecord.value),
      operationDirectory: record.operationDirectory,
    };
  }
  if (record.blockedRecord !== null) {
    return {
      state: "blocked_unverifiable",
      operationKey,
      attempt: intent.attempt,
      operationId: intent.operationId,
      processGroupId: record.claimRecord.value.processGroupId,
      terminalReceiptPresent: false,
      streamsRetained:
        pathPresent(join(record.operationDirectory, "stdout.bin")) ||
        pathPresent(join(record.operationDirectory, "stderr.bin")),
      operationSha256: record.blockedRecord.value.operationSha256,
      operationDirectory: record.operationDirectory,
    };
  }
  if (record.claimRecord === null) {
    return {
      state: "prepared",
      operationKey,
      attempt: intent.attempt,
      operationId: intent.operationId,
      terminalReceiptPresent: false,
      streamsRetained: false,
      operationDirectory: record.operationDirectory,
    };
  }
  const processGroupId = record.claimRecord.value.processGroupId;
  if (lifecycleProcessGroupAlive(processGroupId)) {
    return {
      state: "claimed_active",
      operationKey,
      attempt: intent.attempt,
      operationId: intent.operationId,
      processGroupId,
      terminalReceiptPresent: false,
      streamsRetained:
        pathPresent(join(record.operationDirectory, "stdout.bin")) ||
        pathPresent(join(record.operationDirectory, "stderr.bin")),
      operationDirectory: record.operationDirectory,
    };
  }
  writeLifecycleBlockedReceipt(record);
  return inspectLifecycleOperation(privateDirectory, operationKey);
}

function lifecycleJournalResumeDisposition(privateDirectory) {
  const states = lifecycleOperationRecords(privateDirectory).map((record) =>
    inspectLifecycleOperation(
      privateDirectory,
      record.intentRecord.value.operationKey,
    ),
  );
  const active = states.find((state) => state.state === "claimed_active");
  if (active) return { status: "claimed_active", state: active, states };
  const blocked = states.find((state) => state.state === "blocked_unverifiable");
  if (blocked) return { status: "blocked_unverifiable", state: blocked, states };
  return { status: "clear", state: null, states };
}

function assertLifecycleJournalCanResume(privateDirectory) {
  const disposition = lifecycleJournalResumeDisposition(privateDirectory);
  if (disposition.status === "claimed_active") {
    fail(
      "lifecycle-orphan-active",
      "a previously claimed lifecycle process group is still active; resume and replay are forbidden",
    );
  }
  if (disposition.status === "blocked_unverifiable") {
    fail(
      "lifecycle-interrupted",
      "a claimed lifecycle has no terminal receipt; filesystem observation cannot produce PASS",
    );
  }
  return disposition.states;
}

function lifecycleRequestIdentity(request) {
  const executable = realpathSync(request.executable);
  const cwd = realpathSync(request.cwd);
  const env = safeLifecycleEnvironment(request.env);
  if (
    !statSync(executable).isFile() ||
    (statSync(executable).mode & 0o111) === 0 ||
    !statSync(cwd).isDirectory() ||
    !Array.isArray(request.args) ||
    request.args.some((item) => typeof item !== "string" || item.includes("\0")) ||
    typeof request.label !== "string" ||
    request.label.length === 0 ||
    !Number.isSafeInteger(request.timeout) ||
    request.timeout < 1 ||
    request.timeout > 900_000 ||
    !/^[a-f0-9]{64}$/u.test(request.candidateIdentitySha256 ?? "")
  ) {
    fail("lifecycle-intent", "the lifecycle operation request is unsupported");
  }
  const value = {
    operationKey: request.operationKey,
    attempt: lifecycleAttempt(request.operationKey),
    label: request.label,
    executable,
    executableSha256: sha256FileSync(executable),
    args: [...request.args],
    argvSha256: sha256Buffer(JSON.stringify(request.args)),
    cwd,
    env,
    environmentSha256: sha256Buffer(JSON.stringify(env)),
    timeoutMs: request.timeout,
    candidateIdentitySha256: request.candidateIdentitySha256,
    capsuleSha256: sha256FileSync(LIFECYCLE_CAPSULE),
  };
  return { value, requestSha256: sha256Buffer(JSON.stringify(value)) };
}

function lifecycleOperationStagingPath(privateDirectory, sequence, operationKey) {
  return join(
    privateDirectory,
    `.lifecycle-operation-${String(sequence).padStart(3, "0")}-${operationKey}.preparing`,
  );
}

function reconcileLifecycleOperationStaging({
  privateDirectory,
  root,
  operationDirectory,
  operationDirectoryName,
  staging,
  sequence,
  operationKey,
  requestSha256,
  previousOperationSha256,
  testHooks,
}) {
  if (!pathPresent(staging)) return null;
  requireExactPrivateMode(
    staging,
    "lifecycle operation staging directory",
    "directory",
    0o700,
  );
  const entries = readdirSync(staging);
  if (entries.length === 0) {
    rmSync(staging, { recursive: true, force: false });
    syncEntry(privateDirectory);
    return null;
  }
  if (!sameStrings(entries, ["intent.json"])) {
    fail(
      "lifecycle-recovery",
      "a partial or unknown lifecycle staging directory cannot be recovered",
    );
  }
  const record = lifecycleOperationRecord(staging, {
    requiredDirectoryName: operationDirectoryName,
  });
  const intent = record.intentRecord.value;
  if (
    record.claimRecord !== null ||
    record.terminalRecord !== null ||
    record.blockedRecord !== null ||
    intent.sequence !== sequence ||
    intent.operationKey !== operationKey ||
    intent.requestSha256 !== requestSha256 ||
    intent.previousOperationSha256 !== previousOperationSha256 ||
    pathPresent(operationDirectory)
  ) {
    fail(
      "lifecycle-recovery",
      "the staged lifecycle intent does not bind the exact pending operation",
    );
  }
  renameSync(staging, operationDirectory);
  syncEntry(root);
  syncEntry(privateDirectory);
  testHooks.afterOperationPublished?.(operationDirectory);
  return operationDirectory;
}

function prepareLifecycleOperation(request, testHooks = {}) {
  const privateDirectory = resolve(request.privateDirectory);
  const identity = lifecycleRequestIdentity(request);
  const records = lifecycleOperationRecords(privateDirectory);
  const existing = records.find(
    (record) => record.intentRecord.value.operationKey === request.operationKey,
  );
  if (existing) {
    if (existing.intentRecord.value.requestSha256 !== identity.requestSha256) {
      fail("lifecycle-recovery", "the existing lifecycle operation binds different exact inputs");
    }
    return existing.operationDirectory;
  }
  const previous = records.at(-1) ?? null;
  if (previous && previous.terminalRecord === null) {
    fail("lifecycle-recovery", "a new lifecycle operation cannot follow a nonterminal claim");
  }
  const root = lifecycleOperationRoot(privateDirectory, { create: true });
  const sequence = records.length + 1;
  const operationDirectoryName =
    `${String(sequence).padStart(3, "0")}-${request.operationKey}`;
  const operationDirectory = join(root, operationDirectoryName);
  const staging = lifecycleOperationStagingPath(
    privateDirectory,
    sequence,
    request.operationKey,
  );
  const previousOperationSha256 =
    previous?.terminalRecord?.value.operationSha256 ?? null;
  const recovered = reconcileLifecycleOperationStaging({
    privateDirectory,
    root,
    operationDirectory,
    operationDirectoryName,
    staging,
    sequence,
    operationKey: request.operationKey,
    requestSha256: identity.requestSha256,
    previousOperationSha256,
    testHooks,
  });
  if (recovered !== null) return recovered;
  mkdirSync(staging, { mode: 0o700 });
  chmodSync(staging, 0o700);
  syncEntry(privateDirectory);
  testHooks.afterStagingDirectoryCreated?.(staging);
  const intent = {
    schema: LIFECYCLE_INTENT_SCHEMA,
    operationId: randomUUID(),
    operationKey: request.operationKey,
    sequence,
    ...identity.value,
    previousOperationSha256,
    preparedAt: new Date().toISOString(),
    requestSha256: identity.requestSha256,
  };
  writeExclusivePrivateBytes(
    join(staging, "intent.json"),
    Buffer.from(`${JSON.stringify(intent, null, 2)}\n`),
    "lifecycle-intent",
  );
  syncEntry(staging);
  testHooks.afterIntentCommitted?.(staging);
  lifecycleOperationRecord(staging, {
    requiredDirectoryName: operationDirectoryName,
  });
  renameSync(staging, operationDirectory);
  syncEntry(root);
  syncEntry(privateDirectory);
  testHooks.afterOperationPublished?.(operationDirectory);
  return operationDirectory;
}

function lifecycleResultFromTerminal(state) {
  const terminal = state.terminal;
  const stdoutPath = join(state.operationDirectory, "stdout.bin");
  const stderrPath = join(state.operationDirectory, "stderr.bin");
  return {
    operationId: state.operationId,
    operationKey: state.operationKey,
    attempt: state.attempt,
    operationSha256: state.operationSha256,
    status: terminal.exitStatus,
    signal: terminal.signal,
    error:
      terminal.spawnError || terminal.timedOut || terminal.outputLimitExceeded
        ? new Error(
            terminal.outputLimitExceeded
              ? "lifecycle output limit exceeded"
              : terminal.timedOut
                ? "lifecycle command timed out"
                : terminal.spawnError,
          )
        : null,
    stdout: readFileSync(stdoutPath, "utf8").trim(),
    stderr: readFileSync(stderrPath, "utf8").trim(),
    stdoutSha256: terminal.stdoutSha256,
    stderrSha256: terminal.stderrSha256,
    durationMs: terminal.durationMs,
    recovered: true,
  };
}

export async function executeLifecycleOperation(request, { testHooks = {} } = {}) {
  const privateDirectory = resolve(request.privateDirectory);
  if (
    testHooks === null ||
    typeof testHooks !== "object" ||
    Array.isArray(testHooks) ||
    Object.values(testHooks).some((hook) => typeof hook !== "function")
  ) {
    fail("lifecycle-intent", "the lifecycle test hook contract is invalid");
  }
  const operationDirectory = prepareLifecycleOperation(request, testHooks);
  let state = inspectLifecycleOperation(privateDirectory, request.operationKey);
  if (state.state === "terminal") return lifecycleResultFromTerminal(state);
  if (state.state === "claimed_active") {
    fail("lifecycle-orphan-active", "the exact lifecycle process group is still active; replay is forbidden");
  }
  if (state.state === "blocked_unverifiable") {
    fail("lifecycle-interrupted", "a claimed lifecycle ended without a terminal receipt; acceptance is permanently blocked");
  }
  if (state.state !== "prepared") {
    fail("lifecycle-recovery", "the lifecycle operation cannot enter its claimed state");
  }
  const launchCapsule = () =>
    spawn(realpathSync(process.execPath), [LIFECYCLE_CAPSULE, operationDirectory], {
      cwd: ROOT,
      detached: true,
      stdio: "ignore",
      env: {
        HOME: request.env.HOME,
        PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
        TMPDIR: request.env.TMPDIR,
        LANG: "C",
        LC_ALL: "C",
      },
    });
  const capsule = testHooks.launchCapsule
    ? testHooks.launchCapsule({ operationDirectory, launchCapsule })
    : launchCapsule();
  if (
    capsule === null ||
    typeof capsule !== "object" ||
    typeof capsule.once !== "function" ||
    typeof capsule.unref !== "function"
  ) {
    fail("lifecycle-intent", "the lifecycle capsule launcher returned an invalid process handle");
  }
  let capsuleExited = false;
  capsule.once("exit", () => {
    capsuleExited = true;
  });
  capsule.once("error", () => {
    capsuleExited = true;
  });
  capsule.unref();
  const deadline = Date.now() + request.timeout + 15_000;
  while (Date.now() < deadline) {
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 20));
    state = inspectLifecycleOperation(privateDirectory, request.operationKey);
    if (state.state === "terminal") {
      const result = lifecycleResultFromTerminal(state);
      result.recovered = false;
      return result;
    }
    if (state.state === "blocked_unverifiable") {
      fail("lifecycle-interrupted", "a claimed lifecycle ended without a terminal receipt; acceptance is permanently blocked");
    }
    if (state.state === "prepared" && capsuleExited) {
      fail(
        "lifecycle-prepared",
        "the unclaimed lifecycle capsule exited before claim and may be relaunched only after precondition revalidation",
      );
    }
  }
  fail("lifecycle-orphan-active", "the lifecycle capsule did not reach a terminal receipt within its bound");
}

class CommandRecorder {
  constructor(privateDirectory, report, { evidenceTestHooks = {} } = {}) {
    this.privateDirectory = privateDirectory;
    this.report = report;
    this.evidenceTestHooks = evidenceTestHooks;
    recoverEvidenceTransaction(privateDirectory);
    this.commandDirectory = join(privateDirectory, "commands");
    ensurePrivateDirectory(this.commandDirectory);
    requireExactPrivateMode(this.commandDirectory, "private command directory", "directory", 0o700);
    this.logPath = join(privateDirectory, COMMAND_LOG_NAME);
    if (!pathPresent(this.logPath)) atomicWritePrivate(this.logPath, "");
    requireExactPrivateMode(this.logPath, "private command ledger", "file", 0o600);
    const entries = readFileSync(this.logPath, "utf8")
      .split(/\r?\n/u)
      .filter(Boolean)
      .map((line) => parseJson(line, "private-evidence", "the private command log is invalid"));
    const expectedOutputFiles = [];
    entries.forEach((entry, index) => {
      if (
        entry?.schema !== "opensocrates.acceptance-command/1.0.0" ||
        entry?.id !== index + 1 ||
        typeof entry?.rawStreamsPersisted !== "boolean" ||
        !/^[a-f0-9]{64}$/u.test(entry?.stdoutSha256 ?? "") ||
        !/^[a-f0-9]{64}$/u.test(entry?.stderrSha256 ?? "")
      ) {
        fail("private-evidence", "the private command log sequence is invalid");
      }
      for (const [field, expectedName, expectedHash] of [
        ["stdoutFile", `command-${String(entry.id).padStart(3, "0")}.stdout`, entry.stdoutSha256],
        ["stderrFile", `command-${String(entry.id).padStart(3, "0")}.stderr`, entry.stderrSha256],
      ]) {
        const name = entry[field];
        if (name === null) continue;
        if (!entry.rawStreamsPersisted || name !== expectedName) {
          fail("private-evidence", "the private command output manifest is invalid");
        }
        const target = join(this.commandDirectory, name);
        requireExactPrivateMode(target, `private command output ${name}`, "file", 0o600);
        if (sha256FileSync(target) !== expectedHash) {
          fail("private-evidence", "a private command output changed after it was recorded");
        }
        expectedOutputFiles.push(name);
      }
      if (!entry.rawStreamsPersisted && (entry.stdoutFile !== null || entry.stderrFile !== null)) {
        fail("private-evidence", "a suppressed command unexpectedly names a raw stream file");
      }
      if (entry.streamedOutputFile !== null && entry.streamedOutputFile !== undefined) {
        if (
          typeof entry.streamedOutputFile !== "string" ||
          entry.streamedOutputFile.startsWith("/") ||
          entry.streamedOutputFile.split("/").some((part) => part === "" || part === "." || part === "..")
        ) {
          fail("private-evidence", "the streamed command output path is unsafe");
        }
        const target = join(this.privateDirectory, ...entry.streamedOutputFile.split("/"));
        requireExactPrivateMode(target, "streamed private command output", "file", 0o600);
        if (
          statSync(target).size !== entry.streamedOutputSizeBytes ||
          sha256FileSync(target) !== entry.stdoutSha256
        ) {
          fail("private-evidence", "a streamed private command output changed after it was recorded");
        }
      }
      if (entry.lifecycleOperation !== null && entry.lifecycleOperation !== undefined) {
        requireExactObjectKeys(
          entry.lifecycleOperation,
          ["operationId", "operationKey", "attempt", "operationSha256"],
          "private-evidence",
          "the private lifecycle command linkage",
        );
        const lifecycleState = inspectLifecycleOperation(
          this.privateDirectory,
          entry.lifecycleOperation.operationKey,
        );
        if (
          lifecycleState.state !== "terminal" ||
          lifecycleState.operationId !== entry.lifecycleOperation.operationId ||
          lifecycleState.attempt !== entry.lifecycleOperation.attempt ||
          lifecycleState.operationSha256 !== entry.lifecycleOperation.operationSha256 ||
          entry.rawStreamsPersisted !== true ||
          entry.stdoutFile !== null ||
          entry.stderrFile !== null ||
          entry.stdoutSha256 !== lifecycleState.terminal.stdoutSha256 ||
          entry.stderrSha256 !== lifecycleState.terminal.stderrSha256
        ) {
          fail("private-evidence", "the private lifecycle command receipt is missing or changed");
        }
      }
    });
    if (!sameStrings(readdirSync(this.commandDirectory), expectedOutputFiles)) {
      fail("private-evidence", "the private command directory contains an untracked or missing stream");
    }
    report.commands = entries.map((entry) => ({
      id: entry.id,
      label: entry.label,
      exitStatus: entry.exitStatus,
      durationMs: entry.durationMs,
      stdoutSha256: entry.stdoutSha256,
      stderrSha256: entry.stderrSha256,
    }));
    this.entries = entries;
    this.sequence = entries.length;
  }

  persistEntry(entry) {
    const nextEntries = [...this.entries, entry];
    const nextLedger = nextEntries.map((item) => JSON.stringify(item)).join("\n") + "\n";
    if (pathPresent(join(this.privateDirectory, PRIVATE_MANIFEST_NAME))) {
      const updatedAt = new Date().toISOString();
      const manifest = refreshedPrivateEvidenceManifest(
        this.privateDirectory,
        null,
        null,
        { ledgerContents: nextLedger, updatedAt },
      );
      commitEvidenceTransaction(
        this.privateDirectory,
        manifest.publicResult.directory,
        manifest.testId,
        "command-ledger",
        [{ role: "command-ledger", bytes: Buffer.from(nextLedger) }],
        Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`),
        this.evidenceTestHooks,
      );
    } else {
      atomicWritePrivate(this.logPath, nextLedger);
    }
    requireExactPrivateMode(this.logPath, "private command ledger", "file", 0o600);
    this.entries = nextEntries;
  }

  run(
    label,
    executable,
    args,
    {
      cwd = ROOT,
      env = process.env,
      input = undefined,
      timeout = 120_000,
      allowFailure = false,
      persistRaw = true,
      projection = null,
      category = "command",
      failureMessage = `${label} did not complete successfully`,
    } = {},
  ) {
    if (typeof persistRaw !== "boolean") {
      fail("private-evidence", "persistRaw must be an explicit boolean");
    }
    if (projection !== null) {
      if (
        input !== undefined ||
        !new Set([
          "status-only",
          "claude-auth",
          "claude-marketplaces",
          "claude-plugins",
          "codex-marketplaces",
          "codex-plugins",
        ]).has(projection) ||
        !Array.isArray(args) ||
        args.some((item) => typeof item !== "string")
      ) {
        fail("private-evidence", "the requested child-side command projection is unsupported");
      }
      requireCanonicalOwnedEntry(PROJECTION_HELPER, "categorical projection helper", "file");
      return this.run(
        label,
        realpathSync(process.execPath),
        [PROJECTION_HELPER, projection, executable, ...args],
        {
          cwd,
          env,
          timeout,
          allowFailure,
          persistRaw: false,
          category,
          failureMessage,
        },
      );
    }
    const id = this.sequence + 1;
    this.sequence = id;
    const startedAt = new Date().toISOString();
    const started = Date.now();
    const completed = spawnSync(executable, args, {
      cwd,
      env,
      input,
      encoding: null,
      maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
      timeout,
    });
    const stdout = Buffer.isBuffer(completed.stdout) ? completed.stdout : Buffer.alloc(0);
    const stderr = Buffer.isBuffer(completed.stderr) ? completed.stderr : Buffer.alloc(0);
    const stdoutName = `command-${String(id).padStart(3, "0")}.stdout`;
    const stderrName = `command-${String(id).padStart(3, "0")}.stderr`;
    if (persistRaw) {
      writeExclusivePrivateBytes(join(this.commandDirectory, stdoutName), stdout, category);
      writeExclusivePrivateBytes(join(this.commandDirectory, stderrName), stderr, category);
    }
    const status = Number.isInteger(completed.status) ? completed.status : null;
    const publicEntry = {
      id,
      label,
      exitStatus: status,
      durationMs: Date.now() - started,
      stdoutSha256: sha256Buffer(stdout),
      stderrSha256: sha256Buffer(stderr),
    };
    this.report.commands.push(publicEntry);
    const privateEntry = {
      schema: "opensocrates.acceptance-command/1.0.0",
      id,
      label,
      executable,
      args,
      cwd,
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: publicEntry.durationMs,
      exitStatus: status,
      signal: completed.signal ?? null,
      rawStreamsPersisted: persistRaw,
      stdoutFile: persistRaw ? stdoutName : null,
      stderrFile: persistRaw ? stderrName : null,
      streamedOutputFile: null,
      streamedOutputSizeBytes: null,
      stdoutSha256: publicEntry.stdoutSha256,
      stderrSha256: publicEntry.stderrSha256,
      spawnError: completed.error ? completed.error.name : null,
    };
    this.persistEntry(privateEntry);
    if (!allowFailure && (completed.error || status !== 0)) {
      fail(category, failureMessage, id);
    }
    return {
      id,
      status,
      stdout: stdout.toString("utf8").trim(),
      stderr: stderr.toString("utf8").trim(),
      error: completed.error ?? null,
    };
  }

  async runLifecycle(
    label,
    executable,
    args,
    {
      cwd,
      env,
      timeout = 120_000,
      allowFailure = false,
      persistRaw = true,
      category = "lifecycle",
      failureMessage = `${label} did not complete successfully`,
      operationKey,
      candidateIdentitySha256,
    } = {},
  ) {
    if (
      persistRaw !== true ||
      typeof cwd !== "string" ||
      env === null ||
      typeof env !== "object" ||
      typeof operationKey !== "string" ||
      !/^[a-f0-9]{64}$/u.test(candidateIdentitySha256 ?? "")
    ) {
      fail("lifecycle-intent", "the durable lifecycle recorder contract is incomplete");
    }
    const completed = await executeLifecycleOperation({
      privateDirectory: this.privateDirectory,
      operationKey,
      label,
      executable,
      args,
      cwd,
      env,
      timeout,
      candidateIdentitySha256,
    });
    const alreadyImported = this.entries.find(
      (entry) => entry.lifecycleOperation?.operationId === completed.operationId,
    );
    if (alreadyImported) {
      if (!allowFailure && (completed.error || completed.status !== 0)) {
        fail(category, failureMessage, alreadyImported.id);
      }
      return {
        ...completed,
        id: alreadyImported.id,
        recovered: true,
      };
    }
    const id = this.sequence + 1;
    this.sequence = id;
    const publicEntry = {
      id,
      label,
      exitStatus: completed.status,
      durationMs: completed.durationMs,
      stdoutSha256: completed.stdoutSha256,
      stderrSha256: completed.stderrSha256,
    };
    this.report.commands.push(publicEntry);
    this.persistEntry({
      schema: "opensocrates.acceptance-command/1.0.0",
      id,
      label,
      executable,
      args,
      cwd,
      startedAt: new Date(Date.now() - completed.durationMs).toISOString(),
      completedAt: new Date().toISOString(),
      durationMs: completed.durationMs,
      exitStatus: completed.status,
      signal: completed.signal,
      rawStreamsPersisted: true,
      stdoutFile: null,
      stderrFile: null,
      streamedOutputFile: null,
      streamedOutputSizeBytes: null,
      stdoutSha256: completed.stdoutSha256,
      stderrSha256: completed.stderrSha256,
      spawnError: completed.error?.name ?? null,
      lifecycleOperation: {
        operationId: completed.operationId,
        operationKey: completed.operationKey,
        attempt: completed.attempt,
        operationSha256: completed.operationSha256,
      },
    });
    if (!allowFailure && (completed.error || completed.status !== 0)) {
      fail(category, failureMessage, id);
    }
    return { ...completed, id };
  }

  async runToFile(
    label,
    executable,
    args,
    target,
    {
      cwd = ROOT,
      env = process.env,
      timeout = 300_000,
      persistRaw = false,
      category = "command",
      failureMessage = `${label} did not complete successfully`,
    } = {},
  ) {
    if (typeof persistRaw !== "boolean") {
      fail("private-evidence", "persistRaw must be an explicit boolean");
    }
    const id = this.sequence + 1;
    this.sequence = id;
    const startedAt = new Date().toISOString();
    const started = Date.now();
    const parent = dirname(target);
    requireCanonicalOwnedEntry(parent, "streamed command output parent", "directory");
    requireOwnerOnly(parent, "the streamed command output parent");
    if (pathPresent(target)) fail(category, "the streamed command output target already exists");
    const descriptor = openSync(
      target,
      fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
      0o600,
    );
    let completed;
    try {
      completed = spawnSync(executable, args, {
        cwd,
        env,
        encoding: null,
        maxBuffer: MAX_COMMAND_OUTPUT_BYTES,
        timeout,
        stdio: ["ignore", descriptor, "pipe"],
      });
      fsyncSync(descriptor);
    } finally {
      closeSync(descriptor);
    }
    chmodSync(target, 0o600);
    syncEntry(parent);
    const stderr = Buffer.isBuffer(completed.stderr) ? completed.stderr : Buffer.alloc(0);
    const stderrName = `command-${String(id).padStart(3, "0")}.stderr`;
    if (persistRaw) {
      writeExclusivePrivateBytes(join(this.commandDirectory, stderrName), stderr, category);
    }
    const status = Number.isInteger(completed.status) ? completed.status : null;
    const outputSha256 = await sha256File(target);
    const outputSizeBytes = statSync(target).size;
    const publicEntry = {
      id,
      label,
      exitStatus: status,
      durationMs: Date.now() - started,
      stdoutSha256: outputSha256,
      stderrSha256: sha256Buffer(stderr),
    };
    this.report.commands.push(publicEntry);
    const privateEntry = {
      schema: "opensocrates.acceptance-command/1.0.0",
      id,
      label,
      executable,
      args,
      cwd,
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: publicEntry.durationMs,
      exitStatus: status,
      signal: completed.signal ?? null,
      rawStreamsPersisted: persistRaw,
      stdoutFile: null,
      streamedOutputFile: relative(this.privateDirectory, target),
      streamedOutputSizeBytes: outputSizeBytes,
      stderrFile: persistRaw ? stderrName : null,
      stdoutSha256: outputSha256,
      stderrSha256: publicEntry.stderrSha256,
      spawnError: completed.error ? completed.error.name : null,
    };
    this.persistEntry(privateEntry);
    if (completed.error || status !== 0) fail(category, failureMessage, id);
    return {
      id,
      status,
      outputSha256,
      outputSizeBytes,
      stderr: stderr.toString("utf8").trim(),
    };
  }
}

export async function performStep(report, id, label, action, replacements = []) {
  const started = Date.now();
  process.stdout.write(`- ${label} ... `);
  try {
    const details = (await action()) ?? {};
    report.steps.push({
      id,
      label,
      status: "passed",
      durationMs: Date.now() - started,
    });
    process.stdout.write("passed\n");
    return details;
  } catch (error) {
    const category = error instanceof AcceptanceError ? error.category : "harness";
    report.steps.push({
      id,
      label,
      status: "failed",
      durationMs: Date.now() - started,
      category,
      commandId: error instanceof AcceptanceError ? error.commandId : null,
    });
    process.stdout.write("failed\n");
    if (error instanceof AcceptanceError) throw error;
    throw new AcceptanceError(category, sanitizedMessage(error, replacements));
  }
}

function unknownFailureState() {
  return {
    classification: "unknown_unverified",
    actualStateRecorded: false,
    previousStateRestorationClaimed: false,
  };
}

async function inspectFailureSafely(operations, stage) {
  if (typeof operations.inspectFailure !== "function") return unknownFailureState();
  try {
    const observed = await operations.inspectFailure(stage);
    if (
      observed === null ||
      typeof observed !== "object" ||
      Array.isArray(observed) ||
      typeof observed.classification !== "string" ||
      typeof observed.actualStateRecorded !== "boolean" ||
      observed.previousStateRestorationClaimed === true
    ) {
      return unknownFailureState();
    }
    return {
      ...observed,
      actualStateRecorded: observed.actualStateRecorded,
      previousStateRestorationClaimed: false,
    };
  } catch {
    return unknownFailureState();
  }
}

export async function executeMutationPlan(
  operations,
  stages = ["purge", "clean-assertion", "reinstall", "post-install"],
) {
  const supportedPlans = [
    ["purge", "clean-assertion", "reinstall", "post-install"],
    ["clean-assertion", "reinstall", "post-install"],
    ["reinstall", "post-install"],
    ["post-install"],
  ];
  if (!supportedPlans.some((plan) => JSON.stringify(plan) === JSON.stringify(stages))) {
    fail("harness", "the lifecycle execution plan contains an unsupported stage");
  }
  let reinstallAttempted = false;
  for (const stage of stages) {
    try {
      if (stage === "purge") {
        const purge = await operations.purge();
        if (purge?.status === "awaiting-host-close") {
          return {
            status: "awaiting-host-close",
            phase: "purge",
            reinstallAttempted,
            residue: purge.residue ?? null,
          };
        }
        if (purge?.status !== "complete") {
          throw new AcceptanceError("purge", "the purge did not complete");
        }
      } else if (stage === "clean-assertion") {
        await operations.assertClean();
      } else if (stage === "reinstall") {
        reinstallAttempted = true;
        await operations.install();
      } else {
        const finalState = await operations.assertFinal();
        return {
          status: "complete",
          phase: "installed",
          reinstallAttempted,
          finalState,
        };
      }
    } catch (error) {
      return {
        status: "failed",
        phase: stage,
        error,
        reinstallAttempted,
        failureState: await inspectFailureSafely(operations, stage),
      };
    }
  }
  return {
    status: "failed",
    phase: stages.at(-1),
    error: new AcceptanceError("harness", "the lifecycle plan ended without final verification"),
    reinstallAttempted,
    failureState: await inspectFailureSafely(operations, stages.at(-1)),
  };
}

export async function executeMutationSequence(operations) {
  return executeMutationPlan(operations);
}

function currentUid() {
  if (typeof process.getuid !== "function") {
    fail("ownership", "file ownership cannot be verified on this platform");
  }
  return process.getuid();
}

function requireCanonicalOwnedEntry(target, label, expectedKind) {
  const info = lstatSync(target);
  if (info.isSymbolicLink() || info.uid !== currentUid()) {
    fail("ownership", `${label} is not an owner-controlled canonical entry`);
  }
  if (expectedKind === "directory" && !info.isDirectory()) {
    fail("ownership", `${label} is not a directory`);
  }
  if (expectedKind === "file" && (!info.isFile() || info.nlink !== 1)) {
    fail("ownership", `${label} is not a single-link regular file`);
  }
  let canonical;
  try {
    canonical = realpathSync(target);
  } catch {
    fail("ownership", `${label} could not be canonicalized`);
  }
  if (canonical !== resolve(target)) {
    fail("ownership", `${label} resolves through an unexpected path`);
  }
  return info;
}

function requireOwnerOnly(target, label) {
  const info = lstatSync(target);
  if ((info.mode & 0o077) !== 0) {
    fail("permissions", `${label} is accessible by group or other users`);
  }
  return (info.mode & 0o777).toString(8).padStart(3, "0");
}

function defaultTargets() {
  const allHosts = Object.fromEntries(
    SUPPORTED_HOSTS.map((host) => {
      const paths = purgePathsFor(host);
      const transient = transientPathsFor(host);
      if (transient.root !== paths.root || transient.parent !== paths.parent) {
        fail("ownership", `${host} purge and transaction ownership manifests disagree`);
      }
      return [host, { ...paths, transactionParent: transient.transient }];
    }),
  );
  const claude = allHosts.claude;
  const codex = allHosts.codex;
  const state = statePaths();
  const expectedHomes = {
    claude: resolve(join(homedir(), ".claude")),
    codex: resolve(join(homedir(), ".codex")),
  };
  if (claude.hostHome !== realpathOrLexical(expectedHomes.claude)) {
    fail("environment", "Claude does not resolve to its default home");
  }
  if (codex.hostHome !== realpathOrLexical(expectedHomes.codex)) {
    fail("environment", "Codex does not resolve to its default home");
  }
  return { allHosts, claude, codex, state };
}

function realpathOrLexical(target) {
  try {
    return realpathSync(target);
  } catch {
    return resolve(target);
  }
}

function resolveInstalledPluginRoot(host, managedRoot) {
  const marketplacePath = join(
    managedRoot,
    ...(host === "claude"
      ? [".claude-plugin", "marketplace.json"]
      : [".agents", "plugins", "marketplace.json"]),
  );
  requireCanonicalOwnedEntry(marketplacePath, `${host} marketplace metadata`, "file");
  const marketplace = parseJson(
    readFileSync(marketplacePath, "utf8"),
    "ownership",
    `${host} marketplace metadata is invalid JSON`,
  );
  const plugins = Array.isArray(marketplace?.plugins) ? marketplace.plugins : [];
  const matches = plugins.filter((entry) => entry?.name === "opensocrates");
  if (matches.length !== 1) {
    fail("ownership", `${host} marketplace does not declare one OpenSocrates plugin`);
  }
  const source = host === "claude" ? matches[0].source : matches[0].source?.path;
  if (typeof source !== "string" || !source.startsWith("./")) {
    fail("ownership", `${host} marketplace has an invalid local source`);
  }
  const pluginRoot = resolve(managedRoot, source);
  const local = relative(managedRoot, pluginRoot);
  if (local === "" || local === ".." || local.startsWith(`..${sep}`)) {
    fail("ownership", `${host} plugin source escapes its managed root`);
  }
  requireCanonicalOwnedEntry(pluginRoot, `${host} plugin payload`, "directory");
  return pluginRoot;
}

function inspectInUseMarker(versionRoot) {
  const marker = join(versionRoot, ".in_use");
  if (!pathPresent(marker)) return { present: false, live: false };
  requireCanonicalOwnedEntry(marker, "OpenSocrates cache in-use marker", "directory");
  const entries = readdirSync(marker, { withFileTypes: true });
  let live = false;
  for (const entry of entries) {
    if (entry.isSymbolicLink() || !entry.isFile() || !/^[1-9]\d*$/u.test(entry.name)) {
      fail("ownership", "OpenSocrates cache has an unrecognized in-use entry");
    }
    const info = requireCanonicalOwnedEntry(
      join(marker, entry.name),
      "OpenSocrates cache in-use process marker",
      "file",
    );
    if (info.size !== 0) {
      fail("ownership", "OpenSocrates cache has a nonempty in-use process marker");
    }
    const pid = Number(entry.name);
    if (!Number.isSafeInteger(pid)) {
      fail("ownership", "OpenSocrates cache has an invalid in-use process identifier");
    }
    try {
      process.kill(pid, 0);
      live = true;
    } catch (error) {
      if (error?.code === "EPERM") live = true;
      else if (error?.code !== "ESRCH") {
        fail("ownership", "OpenSocrates cache use could not be determined safely");
      }
    }
  }
  return { present: true, live };
}

function inspectOwnedCache(host, cacheRoot) {
  if (!pathPresent(cacheRoot)) {
    return { present: false, ownership: "absent", versionCount: 0, liveInUse: false };
  }
  requireCanonicalOwnedEntry(cacheRoot, `${host} OpenSocrates cache`, "directory");
  const entries = readdirSync(cacheRoot, { withFileTypes: true });
  let liveInUse = false;
  for (const entry of entries) {
    if (entry.isSymbolicLink() || !entry.isDirectory()) {
      fail("ownership", `${host} OpenSocrates cache contains an unrecognized entry`);
    }
    const versionRoot = join(cacheRoot, entry.name);
    requireCanonicalOwnedEntry(versionRoot, `${host} cached payload`, "directory");
    const releasePath = join(versionRoot, "release-manifest.json");
    const manifestPath = join(
      versionRoot,
      ...(host === "claude"
        ? [".claude-plugin", "plugin.json"]
        : [".codex-plugin", "plugin.json"]),
    );
    const checksumPath = join(versionRoot, "checksums.sha256");
    for (const [target, label] of [
      [releasePath, `${host} cached release manifest`],
      [manifestPath, `${host} cached plugin manifest`],
      [checksumPath, `${host} cached checksum inventory`],
    ]) {
      requireCanonicalOwnedEntry(target, label, "file");
    }
    const release = parseJson(
      readFileSync(releasePath, "utf8"),
      "ownership",
      `${host} cached release identity is invalid`,
    );
    const manifest = parseJson(
      readFileSync(manifestPath, "utf8"),
      "ownership",
      `${host} cached plugin identity is invalid`,
    );
    if (
      release?.schema !== "opensocrates.plugin-release-manifest/1.0.0" ||
      release?.host !== host ||
      release?.product_version !== entry.name ||
      manifest?.name !== "opensocrates" ||
      manifest?.version !== entry.name
    ) {
      fail("ownership", `${host} cached payload identity does not match its canonical target`);
    }
    liveInUse = inspectInUseMarker(versionRoot).live || liveInUse;
  }
  return {
    present: true,
    ownership: "verified",
    versionCount: entries.length,
    liveInUse,
  };
}

function verifyCacheMarketplaceShape(host, paths, category = "baseline") {
  if (paths.cacheMarketplaceRoot === null || paths.cacheRoot === null) return;
  const marketplacePresent = pathPresent(paths.cacheMarketplaceRoot);
  const cachePresent = pathPresent(paths.cacheRoot);
  if (!marketplacePresent) {
    if (cachePresent) {
      fail(category, `${host} cache root exists without its exact marketplace parent`);
    }
    return;
  }
  requireCanonicalOwnedEntry(
    paths.cacheMarketplaceRoot,
    `${host} cache marketplace`,
    "directory",
  );
  const entries = readdirSync(paths.cacheMarketplaceRoot, { withFileTypes: true });
  const expectedName = basename(paths.cacheRoot);
  if (
    entries.length !== (cachePresent ? 1 : 0) ||
    (cachePresent &&
      (entries[0].name !== expectedName ||
        entries[0].isSymbolicLink() ||
        !entries[0].isDirectory()))
  ) {
    fail(category, `${host} cache marketplace contains an unrecognized entry`);
  }
}

function inspectPluginData(target) {
  if (!pathPresent(target)) return { present: false, ownership: "absent", empty: true };
  requireCanonicalOwnedEntry(target, "Claude OpenSocrates plugin data", "directory");
  const entries = readdirSync(target);
  return {
    present: true,
    ownership: entries.length === 0 ? "verified_empty" : "unverified_nonempty",
    empty: entries.length === 0,
  };
}

function validateAutoUpdateReceipt(receipt) {
  const results = new Set(["blocked", "no-update", "updated", "failed"]);
  const hostResults = new Set(["blocked-major", "current", "updated", "failed"]);
  const errorCategories = new Set([
    "major-policy",
    "verification",
    "network",
    "preflight",
    "rollback",
    "locked",
    "activation",
    "internal",
  ]);
  if (
    receipt === null ||
    typeof receipt !== "object" ||
    Array.isArray(receipt) ||
    !sameStrings(Object.keys(receipt), [
      "schema",
      "version",
      "checkedAt",
      "hosts",
      "result",
      "errorCategory",
    ]) ||
    receipt.schema !== "opensocrates.auto-update-receipt/1.0.0" ||
    typeof receipt.version !== "string" ||
    !/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(receipt.version) ||
    typeof receipt.checkedAt !== "string" ||
    !Number.isFinite(Date.parse(receipt.checkedAt)) ||
    new Date(receipt.checkedAt).toISOString() !== receipt.checkedAt ||
    !Array.isArray(receipt.hosts) ||
    receipt.hosts.length === 0 ||
    receipt.hosts.some(
      (item) =>
        item === null ||
        typeof item !== "object" ||
        Array.isArray(item) ||
        !sameStrings(Object.keys(item), ["host", "result"]) ||
        !SUPPORTED_HOSTS.includes(item.host) ||
        !hostResults.has(item.result),
    ) ||
    new Set(receipt.hosts.map((item) => item.host)).size !== receipt.hosts.length ||
    !results.has(receipt.result) ||
    !(receipt.errorCategory === null || errorCategories.has(receipt.errorCategory))
  ) {
    fail("baseline", "the OpenSocrates auto-update receipt has an invalid schema");
  }
  const expectedHostResult = {
    blocked: "blocked-major",
    "no-update": "current",
    updated: "updated",
    failed: "failed",
  }[receipt.result];
  if (
    receipt.hosts.some((item) => item.result !== expectedHostResult) ||
    (receipt.result === "blocked" && receipt.errorCategory !== "major-policy") ||
    (new Set(["no-update", "updated"]).has(receipt.result) && receipt.errorCategory !== null) ||
    (receipt.result === "failed" && receipt.errorCategory === null)
  ) {
    fail("baseline", "the OpenSocrates auto-update receipt is internally inconsistent");
  }
  return receipt;
}

function inspectStateDirectory(targets, { requireInstalled = false } = {}) {
  const { state } = targets;
  if (!pathPresent(state.directory)) {
    if (requireInstalled) fail("baseline", "the installed OpenSocrates state directory is missing");
    return {
      present: false,
      ownership: "absent",
      desired: null,
      desiredStateSha256: "absent",
      launchAgentPresent: false,
    };
  }
  requireCanonicalOwnedEntry(state.directory, "OpenSocrates state directory", "directory");
  requireOwnerOnly(state.directory, "the OpenSocrates state directory");
  const allowed = new Set(["desired-state.json", "auto-update-receipt.json"]);
  const names = readdirSync(state.directory);
  const unknown = names.filter((name) => !allowed.has(name));
  if (unknown.length > 0) {
    fail("ownership", "the OpenSocrates state directory contains an unrecognized entry");
  }
  let desired = null;
  let desiredStateSha256 = "absent";
  if (pathPresent(state.desiredState)) {
    requireCanonicalOwnedEntry(state.desiredState, "OpenSocrates desired state", "file");
    requireOwnerOnly(state.desiredState, "the OpenSocrates desired-state file");
    const desiredBytes = readFileSync(state.desiredState);
    desired = parseJson(
      desiredBytes.toString("utf8"),
      "baseline",
      "the OpenSocrates desired-state file is invalid JSON",
    );
    desiredStateSha256 = sha256Buffer(desiredBytes);
  } else if (requireInstalled) {
    fail("baseline", "the installed OpenSocrates desired state is missing");
  }
  let receipt = null;
  if (pathPresent(state.receipt)) {
    requireCanonicalOwnedEntry(state.receipt, "OpenSocrates auto-update receipt", "file");
    requireOwnerOnly(state.receipt, "the OpenSocrates auto-update receipt");
    receipt = validateAutoUpdateReceipt(
      parseJson(
        readFileSync(state.receipt, "utf8"),
        "baseline",
        "the OpenSocrates auto-update receipt is invalid JSON",
      ),
    );
  }
  let launchAgentPresent = false;
  if (pathPresent(state.launchAgent)) {
    requireCanonicalOwnedEntry(state.launchAgent, "OpenSocrates LaunchAgent", "file");
    const contents = readFileSync(state.launchAgent, "utf8");
    if (!contents.includes("com.opensocrates.auto-update")) {
      fail("ownership", "the LaunchAgent does not have the OpenSocrates ownership identity");
    }
    launchAgentPresent = true;
  }
  return {
    present: true,
    ownership: "verified",
    desired,
    desiredStateSha256,
    receipt,
    launchAgentPresent,
  };
}

function inspectStateResidue(targets) {
  const directory = targets.state.directory;
  if (!pathPresent(directory)) {
    return {
      present: false,
      empty: true,
      desiredStatePresent: false,
      receiptPresent: false,
      lifecycleLockPresent: false,
      temporaryCount: 0,
      purgeTombstoneCount: 0,
      unknownLeafCount: 0,
    };
  }
  requireCanonicalOwnedEntry(directory, "OpenSocrates state directory", "directory");
  const result = {
    present: true,
    empty: false,
    desiredStatePresent: false,
    receiptPresent: false,
    lifecycleLockPresent: false,
    temporaryCount: 0,
    purgeTombstoneCount: 0,
    unknownLeafCount: 0,
  };
  const knownNames = new Map([
    ["desired-state.json", "desiredStatePresent"],
    ["auto-update-receipt.json", "receiptPresent"],
    ["lifecycle.lock", "lifecycleLockPresent"],
  ]);
  const names = readdirSync(directory);
  result.empty = names.length === 0;
  for (const name of names) {
    const target = join(directory, name);
    if (knownNames.has(name)) {
      requireCanonicalOwnedEntry(target, `OpenSocrates state leaf ${name}`, "file");
      result[knownNames.get(name)] = true;
    } else if (STATE_TEMP_PATTERN.test(name)) {
      requireCanonicalOwnedEntry(target, "OpenSocrates state temporary", "file");
      result.temporaryCount += 1;
    } else if (STATE_PURGE_TOMBSTONE_PATTERN.test(name)) {
      requireCanonicalOwnedEntry(target, "OpenSocrates purge-finalize tombstone", "file");
      result.purgeTombstoneCount += 1;
    } else {
      // Unknown leaves are never opened or repaired by this harness. Their
      // presence makes zero residue fail closed without treating another
      // shared location as OpenSocrates-owned.
      result.unknownLeafCount += 1;
    }
  }
  return result;
}

function inspectLaunchAgentJob(recorder) {
  const target = `gui/${currentUid()}/${AUTO_UPDATE_LABEL}`;
  const completed = recorder.run(
    "Inspect OpenSocrates launchd job state",
    "/bin/launchctl",
    ["print", target],
    {
      allowFailure: true,
      category: "launchd-state",
      failureMessage: "the OpenSocrates launchd job state could not be inspected",
      env: { ...process.env, LANG: "C", LC_ALL: "C" },
    },
  );
  if (completed.error) {
    fail("launchd-state", "the OpenSocrates launchd job state could not be inspected", completed.id);
  }
  if (completed.status === 0) return { loaded: true, observation: "loaded" };
  const detail = `${completed.stdout}\n${completed.stderr}`;
  if (!/(?:could not find service|service not found|could not find specified service)/iu.test(detail)) {
    fail("launchd-state", "the OpenSocrates launchd job absence could not be classified safely", completed.id);
  }
  return { loaded: false, observation: "unloaded" };
}

function inspectLaunchAgentTemporaryResidue(state) {
  const parent = state.launchAgentsDirectory ?? dirname(state.launchAgent);
  if (!pathPresent(parent)) return 0;
  requireCanonicalOwnedEntry(parent, "LaunchAgents directory", "directory");
  return readdirSync(parent).filter((name) => LAUNCH_AGENT_TEMP_PATTERN.test(name)).length;
}

function inspectTrustTransactionResidue(codexHome) {
  if (!pathPresent(codexHome)) return 0;
  requireCanonicalOwnedEntry(codexHome, "Codex configuration directory", "directory");
  return readdirSync(codexHome).filter((name) => TRUST_TRANSACTION_PATTERN.test(name)).length;
}

function inspectKnownTransactionResidue(host, paths) {
  if (!pathPresent(paths.transactionParent)) return 0;
  requireCanonicalOwnedEntry(paths.transactionParent, `${host} transaction parent`, "directory");
  return readdirSync(paths.transactionParent).filter((name) =>
    /^\.opensocrates\.(?:staging|backup|removed)-[A-Za-z0-9-]+$/u.test(name),
  ).length;
}

function assertNoKnownTransactionResidue(targets, category) {
  const residue = Object.fromEntries(
    SUPPORTED_HOSTS.map((host) => [
      host,
      inspectKnownTransactionResidue(host, targets.allHosts[host]),
    ]),
  );
  if (Object.values(residue).some((count) => count !== 0)) {
    fail(category, "an OpenSocrates lifecycle transaction residue exists");
  }
  if (inspectOpenCodeBridgeResidue(targets.allHosts.opencode) !== 0) {
    fail(category, "an OpenCode bridge transaction residue exists");
  }
  return residue;
}

function removedTrustSyntaxBinding(original, stripped) {
  const originalLines = original.toString("utf8").split(/(?<=\n)/u);
  const strippedLines = stripped.toString("utf8").split(/(?<=\n)/u);
  if (originalLines.length !== strippedLines.length) {
    fail("trust-state", "the exact OpenSocrates trust syntax could not be isolated safely");
  }
  const removed = [];
  let removedSyntaxByteCount = 0;
  for (let index = 0; index < originalLines.length; index += 1) {
    const before = originalLines[index];
    const after = strippedLines[index];
    if (before === after) continue;
    let prefix = 0;
    while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) {
      prefix += 1;
    }
    let suffix = 0;
    while (
      suffix < before.length - prefix &&
      suffix < after.length - prefix &&
      before[before.length - suffix - 1] === after[after.length - suffix - 1]
    ) {
      suffix += 1;
    }
    const retained = `${before.slice(0, prefix)}${before.slice(before.length - suffix)}`;
    if (retained !== after) {
      fail("trust-state", "the exact OpenSocrates trust syntax has an ambiguous byte boundary");
    }
    const bytes = Buffer.from(before.slice(prefix, before.length - suffix), "utf8");
    removedSyntaxByteCount += bytes.length;
    removed.push(bytes.toString("base64"));
  }
  return {
    removedSyntaxByteCount,
    removedSyntaxSha256: sha256Buffer(JSON.stringify(removed)),
  };
}

export function codexTrustBindingForContents(contents) {
  const original = Buffer.isBuffer(contents) ? contents : Buffer.from(contents);
  const result = stripCodexOpenSocratesTrustSections(original);
  const events = sorted(result.removedEvents ?? []);
  if (
    events.length > CODEX_TRUST_EVENTS.length ||
    !events.every((event) => CODEX_TRUST_EVENTS.includes(event))
  ) {
    fail("trust-state", "Codex returned an invalid OpenSocrates trust-section inventory");
  }
  const publicValue = {
    present: events.length > 0,
    exactSectionCount: events.length,
    events,
  };
  return {
    public: publicValue,
    binding: {
      ...publicValue,
      ...removedTrustSyntaxBinding(original, result.contents),
    },
  };
}

function inspectCodexTrustSectionsWithBinding() {
  const codexHome = join(homedir(), ".codex");
  const configPath = join(codexHome, "config.toml");
  if (!pathPresent(configPath)) {
    return codexTrustBindingForContents(Buffer.alloc(0));
  }
  requireCanonicalOwnedEntry(codexHome, "Codex configuration directory", "directory");
  const info = requireCanonicalOwnedEntry(configPath, "Codex configuration", "file");
  if (info.size > 16 * 1024 * 1024) {
    fail("trust-state", "the Codex configuration is too large for bounded trust inspection");
  }
  const original = readFileSync(configPath);
  return codexTrustBindingForContents(original);
}

function inspectCodexTrustSections() {
  return inspectCodexTrustSectionsWithBinding().public;
}

function assertNonTargetHostsAbsent(targets) {
  const state = {};
  for (const host of SUPPORTED_HOSTS.filter((candidate) => !HOSTS.includes(candidate))) {
    const paths = targets.allHosts[host];
    const rootPresent = pathPresent(paths.root);
    const bridgePresent = paths.bridge !== null && pathPresent(paths.bridge);
    const bridgeMarkerPresent = paths.bridgeMarker !== null && pathPresent(paths.bridgeMarker);
    if (rootPresent || bridgePresent || bridgeMarkerPresent) {
      fail("baseline", `${host} has an existing OpenSocrates target outside the requested reinstall set`);
    }
    state[host] = {
      managedRootPresent: false,
      bridgePresent: false,
      bridgeMarkerPresent: false,
    };
  }
  return state;
}

function exactResidueSnapshot(
  targets,
  registrations,
  launchAgentJob,
  trustSnapshot = null,
) {
  if (typeof launchAgentJob?.loaded !== "boolean") {
    fail("launchd-state", "zero-residue classification requires an observed launchd state");
  }
  const hosts = {};
  for (const host of SUPPORTED_HOSTS) {
    const paths = targets.allHosts[host];
    let cache = { present: false, ownership: "not-applicable", versionCount: 0, liveInUse: false };
    if (paths.cacheRoot !== null) cache = inspectOwnedCache(host, paths.cacheRoot);
    hosts[host] = {
      registrationPresent:
        HOSTS.includes(host)
          ? registrations === null
            ? null
            : registrations[host].marketplaceCount > 0 || registrations[host].pluginCount > 0
          : false,
      unsupportedLegacyRegistrationPresent:
        HOSTS.includes(host)
          ? registrations === null
            ? null
            : registrations[host].unsupportedLegacyConflictCount > 0
          : false,
      managedRootPresent: pathPresent(paths.root),
      cachePresent: cache.present,
      cacheMarketplacePresent:
        paths.cacheMarketplaceRoot !== null && pathPresent(paths.cacheMarketplaceRoot),
      liveInUse: cache.liveInUse,
      pluginDataPresent: paths.pluginData.some(pathPresent),
      transactionResidueCount: inspectKnownTransactionResidue(host, paths),
      bridgePresent: paths.bridge !== null ? pathPresent(paths.bridge) : false,
      bridgeMarkerPresent: paths.bridgeMarker !== null ? pathPresent(paths.bridgeMarker) : false,
    };
  }
  const trust = trustSnapshot ?? inspectCodexTrustSections();
  const stateResidue = inspectStateResidue(targets);
  const launchAgentPlistPresent = pathPresent(targets.state.launchAgent);
  const launchAgentTemporaryCount = inspectLaunchAgentTemporaryResidue(targets.state);
  const trustTransactionResidueCount = inspectTrustTransactionResidue(
    targets.codex.hostHome,
  );
  const openCodeBridgeResidueCount = inspectOpenCodeBridgeResidue(targets.allHosts.opencode);
  return {
    hosts,
    stateResidue,
    launchAgentPlistPresent,
    launchAgentTemporaryCount,
    launchAgentJobLoaded: launchAgentJob.loaded,
    codexTrustSectionCount: trust.exactSectionCount,
    trustTransactionResidueCount,
    openCodeBridgeResidueCount,
  };
}

function residueHasExactSchema(snapshot, { allowUnknownTargetRegistrations = false } = {}) {
  const topLevelFields = [
    "hosts",
    "stateResidue",
    "launchAgentPlistPresent",
    "launchAgentTemporaryCount",
    "launchAgentJobLoaded",
    "codexTrustSectionCount",
    "trustTransactionResidueCount",
    "openCodeBridgeResidueCount",
  ];
  const hostKeys =
    snapshot !== null && typeof snapshot === "object" && !Array.isArray(snapshot)
      ? Object.keys(snapshot.hosts ?? {})
      : [];
  const hostFields = [
    "registrationPresent",
    "unsupportedLegacyRegistrationPresent",
    "managedRootPresent",
    "cachePresent",
    "cacheMarketplacePresent",
    "liveInUse",
    "pluginDataPresent",
    "transactionResidueCount",
    "bridgePresent",
    "bridgeMarkerPresent",
  ];
  const stateFields = [
    "present",
    "empty",
    "desiredStatePresent",
    "receiptPresent",
    "lifecycleLockPresent",
    "temporaryCount",
    "purgeTombstoneCount",
    "unknownLeafCount",
  ];
  const exactObject = (value, fields) =>
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    sameStrings(Object.keys(value), fields);
  if (
    !exactObject(snapshot, topLevelFields) ||
    !sameStrings(hostKeys, SUPPORTED_HOSTS) ||
    !SUPPORTED_HOSTS.every((host) => {
      const value = snapshot.hosts[host];
      return (
        exactObject(value, hostFields) &&
        hostFields.every((field) => {
          if (field === "transactionResidueCount") {
            return Number.isSafeInteger(value[field]) && value[field] >= 0;
          }
          if (
            allowUnknownTargetRegistrations &&
            HOSTS.includes(host) &&
            new Set(["registrationPresent", "unsupportedLegacyRegistrationPresent"]).has(field)
          ) {
            return value[field] === null || typeof value[field] === "boolean";
          }
          return typeof value[field] === "boolean";
        }) &&
        Number.isSafeInteger(value.transactionResidueCount) &&
        value.transactionResidueCount >= 0
      );
    }) ||
    !exactObject(snapshot.stateResidue, stateFields) ||
    ![
      "present",
      "empty",
      "desiredStatePresent",
      "receiptPresent",
      "lifecycleLockPresent",
    ].every((field) => typeof snapshot.stateResidue[field] === "boolean") ||
    !["temporaryCount", "purgeTombstoneCount", "unknownLeafCount"].every(
      (field) => Number.isSafeInteger(snapshot.stateResidue[field]) && snapshot.stateResidue[field] >= 0,
    ) ||
    !["launchAgentPlistPresent", "launchAgentJobLoaded"].every(
      (field) => typeof snapshot[field] === "boolean",
    ) ||
    ![
      "launchAgentTemporaryCount",
      "codexTrustSectionCount",
      "trustTransactionResidueCount",
      "openCodeBridgeResidueCount",
    ].every(
      (field) => Number.isSafeInteger(snapshot[field]) && snapshot[field] >= 0,
    )
  ) {
    return false;
  }
  return true;
}

function filesystemResidueIsEmpty(snapshot) {
  if (!residueHasExactSchema(snapshot, { allowUnknownTargetRegistrations: true })) {
    return false;
  }
  return (
    SUPPORTED_HOSTS.map((host) => snapshot.hosts[host]).every(
      (item) =>
        !item.managedRootPresent &&
        !item.cachePresent &&
        !item.cacheMarketplacePresent &&
        !item.liveInUse &&
        !item.pluginDataPresent &&
        item.transactionResidueCount === 0 &&
        !item.bridgePresent &&
        !item.bridgeMarkerPresent,
    ) &&
    !snapshot.stateResidue.present &&
    snapshot.stateResidue.empty &&
    !snapshot.stateResidue.desiredStatePresent &&
    !snapshot.stateResidue.receiptPresent &&
    !snapshot.stateResidue.lifecycleLockPresent &&
    snapshot.stateResidue.temporaryCount === 0 &&
    snapshot.stateResidue.purgeTombstoneCount === 0 &&
    snapshot.stateResidue.unknownLeafCount === 0 &&
    !snapshot.launchAgentPlistPresent &&
    snapshot.launchAgentTemporaryCount === 0 &&
    snapshot.launchAgentJobLoaded === false &&
    snapshot.codexTrustSectionCount === 0 &&
    snapshot.trustTransactionResidueCount === 0 &&
    snapshot.openCodeBridgeResidueCount === 0
  );
}

function residueIsEmpty(snapshot) {
  return (
    residueHasExactSchema(snapshot) &&
    filesystemResidueIsEmpty(snapshot) &&
    SUPPORTED_HOSTS.every(
      (host) =>
        snapshot.hosts[host].registrationPresent === false &&
        snapshot.hosts[host].unsupportedLegacyRegistrationPresent === false,
    )
  );
}

function validateDeactivatedDesiredState(desired) {
  requireExactObjectKeys(
    desired,
    [
      "schema",
      "channel",
      "installedHosts",
      "activeVersion",
      "updatePolicy",
      "autoUpdate",
      "availableVersion",
      "lastCheckAt",
      "lastSuccessfulUpdateAt",
    ],
    "purge",
    "the deferred OpenSocrates desired state",
  );
  requireExactObjectKeys(
    desired.updatePolicy,
    ["intervalHours", "allowMajor"],
    "purge",
    "the deferred OpenSocrates update policy",
  );
  requireExactObjectKeys(
    desired.autoUpdate,
    ["enabled", "hosts", "nextCheckAt"],
    "purge",
    "the deferred OpenSocrates auto-update state",
  );
  const nullableTimestamp = (value) => value === null || publicIsoTimestamp(value);
  if (
    desired.schema !== DESIRED_STATE_SCHEMA ||
    !new Set(["stable", "next"]).has(desired.channel) ||
    !Array.isArray(desired.installedHosts) ||
    desired.installedHosts.length !== 0 ||
    desired.activeVersion !== null ||
    !Number.isSafeInteger(desired.updatePolicy.intervalHours) ||
    desired.updatePolicy.intervalHours < 1 ||
    desired.updatePolicy.intervalHours > 24 * 7 ||
    typeof desired.updatePolicy.allowMajor !== "boolean" ||
    desired.autoUpdate.enabled !== false ||
    !Array.isArray(desired.autoUpdate.hosts) ||
    desired.autoUpdate.hosts.length !== 0 ||
    desired.autoUpdate.nextCheckAt !== null ||
    !(desired.availableVersion === null || publicSemver(desired.availableVersion)) ||
    !nullableTimestamp(desired.lastCheckAt) ||
    !nullableTimestamp(desired.lastSuccessfulUpdateAt)
  ) {
    fail("purge", "the deferred OpenSocrates desired state is not exactly deactivated");
  }
  return desired;
}

export function inspectDeactivatedDesiredState(targets) {
  const state = inspectStateDirectory(targets);
  if (!state.present || state.desired === null) {
    fail("purge", "the deferred OpenSocrates desired state is missing");
  }
  return structuredClone(validateDeactivatedDesiredState(state.desired));
}

export function assertOnlyRetryableHostCloseResidue(snapshot, liveHosts, desiredState) {
  if (
    !residueHasExactSchema(snapshot) ||
    !Array.isArray(liveHosts) ||
    liveHosts.length === 0 ||
    new Set(liveHosts).size !== liveHosts.length ||
    liveHosts.some((host) => !HOSTS.includes(host))
  ) {
    fail("purge", "the deferred host-close residue identity is incomplete");
  }
  validateDeactivatedDesiredState(desiredState);
  const liveSet = new Set(liveHosts);
  const hostsAreExact = SUPPORTED_HOSTS.every((host) => {
    const item = snapshot.hosts[host];
    const expectedLive = liveSet.has(host);
    return (
      item.registrationPresent === false &&
      item.unsupportedLegacyRegistrationPresent === false &&
      item.managedRootPresent === false &&
      item.cachePresent === expectedLive &&
      item.cacheMarketplacePresent === expectedLive &&
      item.liveInUse === expectedLive &&
      item.pluginDataPresent === false &&
      item.transactionResidueCount === 0 &&
      item.bridgePresent === false &&
      item.bridgeMarkerPresent === false
    );
  });
  const stateIsExact =
    snapshot.stateResidue.present === true &&
    snapshot.stateResidue.empty === false &&
    snapshot.stateResidue.desiredStatePresent === true &&
    snapshot.stateResidue.receiptPresent === false &&
    snapshot.stateResidue.lifecycleLockPresent === false &&
    snapshot.stateResidue.temporaryCount === 0 &&
    snapshot.stateResidue.purgeTombstoneCount === 0 &&
    snapshot.stateResidue.unknownLeafCount === 0;
  if (
    !hostsAreExact ||
    !stateIsExact ||
    snapshot.launchAgentPlistPresent ||
    snapshot.launchAgentTemporaryCount !== 0 ||
    snapshot.launchAgentJobLoaded ||
    snapshot.codexTrustSectionCount !== 0 ||
    snapshot.trustTransactionResidueCount !== 0 ||
    snapshot.openCodeBridgeResidueCount !== 0
  ) {
    fail(
      "purge",
      "live cache is not the only retryable purge residue; automatic host-close retry is forbidden",
    );
  }
  return true;
}

function publicResidueSummary(snapshot) {
  return {
    hosts: Object.fromEntries(
      Object.entries(snapshot.hosts).map(([host, item]) => [
        host,
        {
          registrationPresent: item.registrationPresent,
          unsupportedLegacyRegistrationPresent: item.unsupportedLegacyRegistrationPresent,
          managedRootPresent: item.managedRootPresent,
          cachePresent: item.cachePresent,
          cacheMarketplacePresent: item.cacheMarketplacePresent,
          liveInUse: item.liveInUse,
          pluginDataPresent: item.pluginDataPresent,
          transactionResidueCount: item.transactionResidueCount,
          bridgePresent: item.bridgePresent,
          bridgeMarkerPresent: item.bridgeMarkerPresent,
        },
      ]),
    ),
    stateResidue: snapshot.stateResidue,
    launchAgentPlistPresent: snapshot.launchAgentPlistPresent,
    launchAgentTemporaryCount: snapshot.launchAgentTemporaryCount,
    launchAgentJobLoaded: snapshot.launchAgentJobLoaded,
    codexTrustSectionCount: snapshot.codexTrustSectionCount,
    trustTransactionResidueCount: snapshot.trustTransactionResidueCount,
    openCodeBridgeResidueCount: snapshot.openCodeBridgeResidueCount,
    empty: residueIsEmpty(snapshot),
  };
}

export function assertHostCloseRetrySnapshot(
  previous,
  current,
  confirmedHosts,
  previousBindings,
  currentBindings,
) {
  const bindingFields = [
    "sourceCommit",
    "packageSha256",
    "artifactDigest",
    "desiredStateSha256",
  ];
  const exactBindings = (value) =>
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    sameStrings(Object.keys(value), bindingFields) &&
    bindingFields.every((field) => typeof value[field] === "string" && value[field].length > 0);
  if (
    !exactBindings(previousBindings) ||
    !exactBindings(currentBindings) ||
    JSON.stringify(previousBindings) !== JSON.stringify(currentBindings)
  ) {
    fail("recovery", "the exact candidate or desired-state binding changed before the host-close retry");
  }
  if (
    !Array.isArray(confirmedHosts) ||
    confirmedHosts.length === 0 ||
    new Set(confirmedHosts).size !== confirmedHosts.length ||
    confirmedHosts.some((host) => !SUPPORTED_HOSTS.includes(host))
  ) {
    fail("host-close-confirmation", "the host-close confirmation set is invalid");
  }
  const expectedHostFields = [
    "registrationPresent",
    "unsupportedLegacyRegistrationPresent",
    "managedRootPresent",
    "cachePresent",
    "cacheMarketplacePresent",
    "liveInUse",
    "pluginDataPresent",
    "transactionResidueCount",
    "bridgePresent",
    "bridgeMarkerPresent",
  ];
  for (const value of [previous, current]) {
    if (
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      !sameStrings(Object.keys(value.hosts ?? {}), SUPPORTED_HOSTS) ||
      !SUPPORTED_HOSTS.every((host) => {
        const item = value.hosts[host];
        return item !== null &&
          typeof item === "object" &&
          !Array.isArray(item) &&
          sameStrings(Object.keys(item), expectedHostFields);
      })
    ) {
      fail("recovery", "the checkpointed host-close residue snapshot is incomplete");
    }
  }
  const normalizedCurrent = structuredClone(current);
  for (const host of confirmedHosts) {
    if (previous.hosts[host].liveInUse !== true || current.hosts[host].liveInUse !== false) {
      fail("host-close-confirmation", "a confirmed host did not show exactly one live-marker resolution");
    }
    normalizedCurrent.hosts[host].liveInUse = true;
  }
  if (JSON.stringify(previous) !== JSON.stringify(normalizedCurrent)) {
    fail("recovery", "machine state drifted outside the confirmed live-marker resolution");
  }
  return true;
}

export function requireHostCloseRetryAdmission(checkpoint, { resolved = false } = {}) {
  const admission = checkpoint?.recovery?.hostCloseRetryAdmission;
  if (
    admission === null ||
    typeof admission !== "object" ||
    Array.isArray(admission) ||
    !sameStrings(Object.keys(admission), [
      "initialSnapshot",
      "confirmedHosts",
      "bindings",
      "deactivatedDesiredState",
      "resolvedSnapshot",
    ]) ||
    !residueHasExactSchema(admission.initialSnapshot) ||
    !Array.isArray(admission.confirmedHosts) ||
    admission.confirmedHosts.length === 0 ||
    new Set(admission.confirmedHosts).size !== admission.confirmedHosts.length ||
    admission.confirmedHosts.some((host) => !HOSTS.includes(host)) ||
    (admission.resolvedSnapshot !== null &&
      !residueHasExactSchema(admission.resolvedSnapshot)) ||
    (resolved && admission.resolvedSnapshot === null)
  ) {
    fail("recovery", "the durable host-close retry admission is incomplete");
  }
  assertOnlyRetryableHostCloseResidue(
    admission.initialSnapshot,
    admission.confirmedHosts,
    admission.deactivatedDesiredState,
  );
  if (admission.resolvedSnapshot !== null) {
    assertHostCloseRetrySnapshot(
      admission.initialSnapshot,
      admission.resolvedSnapshot,
      admission.confirmedHosts,
      admission.bindings,
      admission.bindings,
    );
  }
  return admission;
}

function reinstallRetryAdmissionFor(checkpoint, candidate) {
  return {
    operationKey: "install-retry",
    attempt: lifecycleAttempt("install-retry"),
    sourceCommit: checkpoint.sourceCommit,
    packageSha256: candidate.packageSha256,
    artifactDigest: checkpoint.ci.artifact.digest,
  };
}

export function requireReinstallRetryAdmission(checkpoint, candidate = null) {
  const admission = checkpoint?.recovery?.reinstallRetryAdmission;
  if (
    admission === null ||
    typeof admission !== "object" ||
    Array.isArray(admission) ||
    !sameStrings(Object.keys(admission), [
      "operationKey",
      "attempt",
      "sourceCommit",
      "packageSha256",
      "artifactDigest",
    ]) ||
    admission.operationKey !== "install-retry" ||
    admission.attempt !== lifecycleAttempt("install-retry") ||
    !/^[a-f0-9]{40}$/u.test(admission.sourceCommit ?? "") ||
    !/^[a-f0-9]{64}$/u.test(admission.packageSha256 ?? "") ||
    !/^sha256:[a-f0-9]{64}$/u.test(admission.artifactDigest ?? "") ||
    admission.sourceCommit !== checkpoint?.sourceCommit ||
    admission.packageSha256 !== checkpoint?.packageSha256 ||
    admission.artifactDigest !== checkpoint?.ci?.artifact?.digest ||
    checkpoint?.recovery?.reinstallRetriesUsed !== 1 ||
    (candidate !== null && admission.packageSha256 !== candidate?.packageSha256)
  ) {
    fail("recovery", "the durable reinstall retry admission is incomplete or changed");
  }
  return admission;
}

export function classifyPurgeFailureSnapshot(registrations, snapshot) {
  if (registrations === null) {
    return {
      classification: "unknown_unverified",
      actualStateRecorded: false,
      registrationInspection: "failed",
      previousStateRestorationClaimed: false,
    };
  }
  const explicitAbsence = HOSTS.every((host) => {
    const item = registrations?.[host];
    return item?.marketplaceCount === 0 &&
      item?.pluginCount === 0 &&
      item?.unsupportedLegacyConflictCount === 0 &&
      item?.rootMatchesExpected === true;
  });
  const residue = publicResidueSummary(snapshot);
  const exactInstalledTopology = HOSTS.every((host) => {
    const item = registrations?.[host];
    return item?.marketplaceCount === 1 &&
      item?.pluginCount === 1 &&
      item?.version === PRODUCT_VERSION &&
      item?.unsupportedLegacyConflictCount === 0 &&
      item?.rootMatchesExpected === true &&
      snapshot.hosts[host].managedRootPresent;
  }) && snapshot.stateResidue.present;
  return {
    classification:
      explicitAbsence && residue.empty
        ? "purged_after_failure"
        : exactInstalledTopology
          ? "installed_topology_after_purge_failure_unverified"
          : "partial_or_unverified",
    actualStateRecorded: true,
    registrationInspection: "passed",
    residue,
    previousStateRestorationClaimed: false,
  };
}

function commandJson(recorder, label, executable, args, options, category, message) {
  const completed = recorder.run(label, executable, args, {
    ...options,
    category,
    failureMessage: message,
  });
  return parseJson(completed.stdout, category, message);
}

function registrationRoot(entry, host) {
  if (entry === null) return null;
  const values = host === "claude"
    ? [entry.path, entry.installLocation].filter((value) => value !== undefined && value !== null)
    : [entry.root];
  if (
    values.length === 0 ||
    values.some((value) => typeof value !== "string" || value.trim().length === 0)
  ) {
    fail("host-state", `${host} OpenSocrates marketplace did not report a usable root`);
  }
  const roots = values.map((value) => realpathOrLexical(resolve(value)));
  if (new Set(roots).size !== 1) {
    fail("host-state", `${host} OpenSocrates marketplace reported conflicting roots`);
  }
  return roots[0];
}

function registrationRootMatches(entry, host, targets) {
  if (entry === null) return true;
  if (!targets?.[host]?.root) {
    fail("host-state", `${host} registration root cannot be bound without an expected managed root`);
  }
  const expectedTarget = resolve(targets[host].root);
  if (pathPresent(expectedTarget)) {
    requireCanonicalOwnedEntry(expectedTarget, `${host} expected managed registration root`, "directory");
  }
  const expected = realpathOrLexical(expectedTarget);
  if (registrationRoot(entry, host) !== expected) {
    fail("host-state", `${host} OpenSocrates registration points outside its canonical managed root`);
  }
  return true;
}

export function hostRegistrationSnapshot(recorder, targets = null) {
  const claudeMarkets = commandJson(
    recorder,
    "List Claude plugin marketplaces",
    "claude",
    ["plugin", "marketplace", "list", "--json"],
    { projection: "claude-marketplaces", persistRaw: false },
    "host-state",
    "Claude Code could not list plugin marketplaces",
  );
  const claudePlugins = commandJson(
    recorder,
    "List Claude installed plugins",
    "claude",
    ["plugin", "list", "--json"],
    { projection: "claude-plugins", persistRaw: false },
    "host-state",
    "Claude Code could not list installed plugins",
  );
  const codexMarkets = commandJson(
    recorder,
    "List Codex plugin marketplaces",
    "codex",
    ["plugin", "marketplace", "list", "--json"],
    { projection: "codex-marketplaces", persistRaw: false },
    "host-state",
    "Codex could not list plugin marketplaces",
  );
  const codexPlugins = commandJson(
    recorder,
    "List Codex OpenSocrates plugin state",
    "codex",
    ["plugin", "list", "--marketplace", "opensocrates", "--available", "--json"],
    { projection: "codex-plugins", persistRaw: false },
    "host-state",
    "Codex could not inspect the OpenSocrates plugin",
  );
  if (
    !Array.isArray(claudeMarkets) ||
    !Array.isArray(claudePlugins) ||
    !Array.isArray(codexMarkets?.marketplaces) ||
    !Array.isArray(codexPlugins?.installed)
  ) {
    fail("host-state", "a host returned an unexpected plugin inventory schema");
  }
  const claudeMarketMatches = claudeMarkets.filter((entry) => entry?.name === "opensocrates");
  const claudePluginMatches = claudePlugins.filter(
    (entry) => entry?.id === "opensocrates@opensocrates",
  );
  const claudeLegacyMarketplaceCount = claudeMarkets.filter(
    (entry) =>
      typeof entry?.name === "string" &&
      entry.name !== "opensocrates" &&
      entry.name.toLowerCase() === "opensocrates",
  ).length;
  const claudeLegacyPluginCount = claudePlugins.filter(
    (entry) =>
      typeof entry?.id === "string" &&
      entry.id !== "opensocrates@opensocrates" &&
      entry.id.toLowerCase() === "opensocrates@opensocrates",
  ).length;
  const codexMarketMatches = codexMarkets.marketplaces.filter(
    (entry) => entry?.name === "opensocrates",
  );
  const codexPluginMatches = codexPlugins.installed.filter(
    (entry) => entry?.pluginId === "opensocrates@opensocrates",
  );
  const claudeRootMatchesExpected =
    claudeMarketMatches.length <= 1
      ? registrationRootMatches(claudeMarketMatches[0] ?? null, "claude", targets)
      : false;
  const codexRootMatchesExpected =
    codexMarketMatches.length <= 1
      ? registrationRootMatches(codexMarketMatches[0] ?? null, "codex", targets)
      : false;
  return {
    claude: {
      marketplaceCount: claudeMarketMatches.length,
      pluginCount: claudePluginMatches.length,
      version: claudePluginMatches.length === 1 ? claudePluginMatches[0].version ?? null : null,
      unsupportedLegacyConflictCount: claudeLegacyMarketplaceCount + claudeLegacyPluginCount,
      rootMatchesExpected: claudeRootMatchesExpected,
    },
    codex: {
      marketplaceCount: codexMarketMatches.length,
      pluginCount: codexPluginMatches.length,
      version: codexPluginMatches.length === 1 ? codexPluginMatches[0].version ?? null : null,
      unsupportedLegacyConflictCount: 0,
      rootMatchesExpected: codexRootMatchesExpected,
    },
  };
}

function assertRegistrationState(snapshot, expected) {
  for (const host of HOSTS) {
    const item = snapshot[host];
    if (item.unsupportedLegacyConflictCount !== 0) {
      fail(
        expected === "installed-baseline" ? "baseline" : "residue",
        `${host} has an unsupported pre-1.0 OpenSocrates registration requiring manual review`,
      );
    }
    if (expected === "absent") {
      if (item.marketplaceCount !== 0 || item.pluginCount !== 0 || item.rootMatchesExpected !== true) {
        fail("residue", `${host} still has an OpenSocrates registration`);
      }
      continue;
    }
    if (
      item.marketplaceCount !== 1 ||
      item.pluginCount !== 1 ||
      item.version !== PRODUCT_VERSION ||
      item.rootMatchesExpected !== true
    ) {
      fail(
        expected === "installed-baseline" ? "baseline" : "post-install",
        `${host} is not installed exactly once at the expected version`,
      );
    }
  }
}

function codexHookInventory(recorder) {
  const completed = recorder.run(
    "Inspect Codex OpenSocrates hook trust categorically",
    process.execPath,
    ["--input-type=module", "-e", CODEX_HOOK_PROBE_SOURCE],
    {
      category: "codex-hooks",
      failureMessage: "Codex hook inventory could not be obtained safely",
      timeout: 30_000,
      persistRaw: false,
    },
  );
  const value = parseJson(
    completed.stdout,
    "codex-hooks",
    "Codex hook inventory returned invalid categorical evidence",
  );
  if (
    value?.schema !== "opensocrates.codex-hook-inventory/1.0.0" ||
    value.errorCount !== 0 ||
    value.warningCount !== 0 ||
    !Array.isArray(value.hooks)
  ) {
    fail("codex-hooks", "Codex hook inventory reported an error, warning, or invalid schema");
  }
  const hooks = value.hooks;
  if (
    hooks.some((hook) => {
      try {
        requireExactObjectKeys(
          hook,
          ["eventName", "namespace", "timeoutSec", "trustStatus"],
          "codex-hooks",
          "a Codex hook inventory item",
        );
      } catch {
        return true;
      }
      return (
        hook.namespace !== "opensocrates@opensocrates" ||
        typeof hook.eventName !== "string" ||
        !(hook.timeoutSec === null || Number.isFinite(hook.timeoutSec)) ||
        typeof hook.trustStatus !== "string"
      );
    })
  ) {
    fail("codex-hooks", "Codex returned an invalid OpenSocrates hook identity");
  }
  const events = hooks.map((hook) => hook?.eventName);
  if (hooks.length !== CODEX_TRUST_EVENTS.length || !sameStrings(events, EXPECTED_CODEX_EVENTS)) {
    fail("codex-hooks", "Codex did not report the exact seven OpenSocrates hooks");
  }
  const sessionStart = hooks.find((hook) => hook.eventName === "sessionStart");
  if (sessionStart?.timeoutSec !== 2) {
    fail("codex-hooks", "Codex SessionStart does not retain the two-second host budget");
  }
  const trustStatuses = sorted([...new Set(hooks.map((hook) => hook.trustStatus))]);
  if (
    trustStatuses.some(
      (status) => !new Set(["managed", "modified", "trusted", "untrusted"]).has(status),
    )
  ) {
    fail("codex-hooks", "Codex returned an unknown hook trust state");
  }
  return {
    hookCount: hooks.length,
    events: sorted(events),
    namespace: "opensocrates@opensocrates",
    trustStatuses,
    sessionStartTimeoutSeconds: sessionStart.timeoutSec,
  };
}

export function assertExactUntrustedHooks(inventory) {
  if (!sameStrings(inventory.trustStatuses, ["untrusted"])) {
    fail("first-approval", "the reinstalled Codex hooks are not all new and untrusted");
  }
}

async function exactOwnedTreeBinding(
  directory,
  label,
  { allowAbsent = false, ignoreCacheInUseMarkers = false } = {},
) {
  if (!pathPresent(directory)) {
    if (!allowAbsent) fail("baseline", `${label} is missing`);
    return {
      present: false,
      entryCount: 0,
      fileCount: 0,
      aggregateSha256: sha256Buffer(JSON.stringify([])),
    };
  }
  requireCanonicalOwnedEntry(directory, label, "directory");
  const entries = [];
  const visit = (current, prefix = "") => {
    const children = readdirSync(current, { withFileTypes: true })
      .sort((left, right) => left.name.localeCompare(right.name));
    for (const child of children) {
      const target = join(current, child.name);
      const relativeName = prefix === "" ? child.name : `${prefix}/${child.name}`;
      if (
        ignoreCacheInUseMarkers &&
        child.name === ".in_use" &&
        prefix !== "" &&
        !prefix.includes("/")
      ) {
        if (inspectInUseMarker(current).live) {
          fail("baseline", `${label} became live while binding its stable payload`);
        }
        continue;
      }
      if (child.isDirectory()) {
        const info = requireCanonicalOwnedEntry(target, `${label} directory`, "directory");
        entries.push({
          path: `${relativeName}/`,
          type: "directory",
          mode: info.mode & 0o777,
        });
        visit(target, relativeName);
      } else if (child.isFile()) {
        const info = requireCanonicalOwnedEntry(target, `${label} file`, "file");
        entries.push({
          path: relativeName,
          type: "file",
          mode: info.mode & 0o777,
          size: info.size,
          target,
        });
      } else {
        fail("baseline", `${label} contains a link or special entry`);
      }
    }
  };
  visit(directory);
  const bound = [];
  for (const entry of entries) {
    if (entry.type === "directory") {
      bound.push(entry);
    } else {
      const { target, ...publicEntry } = entry;
      bound.push({ ...publicEntry, sha256: await sha256File(target) });
    }
  }
  return {
    present: true,
    entryCount: bound.length,
    fileCount: bound.filter((entry) => entry.type === "file").length,
    aggregateSha256: sha256Buffer(JSON.stringify(bound)),
  };
}

function assertBaselineExactBindings(value) {
  requireExactObjectKeys(
    value,
    ["schema", "managedRoots", "caches", "desiredStateSha256", "codexTrust"],
    "baseline",
    "the exact baseline binding",
  );
  if (
    value.schema !== "opensocrates.reinstall-cycle-baseline-binding/1.0.0" ||
    !sameStrings(Object.keys(value.managedRoots ?? {}), HOSTS) ||
    !sameStrings(Object.keys(value.caches ?? {}), HOSTS) ||
    !/^[a-f0-9]{64}$/u.test(value.desiredStateSha256 ?? "")
  ) {
    fail("baseline", "the exact baseline binding is incomplete");
  }
  const validateTree = (tree, { cache }) => {
    requireExactObjectKeys(
      tree,
      cache
        ? ["present", "entryCount", "fileCount", "aggregateSha256"]
        : ["entryCount", "fileCount", "aggregateSha256"],
      "baseline",
      "the exact baseline tree binding",
    );
    if (
      (cache && typeof tree.present !== "boolean") ||
      !Number.isSafeInteger(tree.entryCount) ||
      tree.entryCount < 0 ||
      !Number.isSafeInteger(tree.fileCount) ||
      tree.fileCount < 0 ||
      tree.fileCount > tree.entryCount ||
      !/^[a-f0-9]{64}$/u.test(tree.aggregateSha256 ?? "") ||
      (cache && !tree.present && (tree.entryCount !== 0 || tree.fileCount !== 0))
    ) {
      fail("baseline", "the exact baseline tree binding is invalid");
    }
  };
  for (const host of HOSTS) {
    validateTree(value.managedRoots[host], { cache: false });
    validateTree(value.caches[host], { cache: true });
  }
  requireExactObjectKeys(
    value.codexTrust,
    [
      "present",
      "exactSectionCount",
      "events",
      "removedSyntaxByteCount",
      "removedSyntaxSha256",
    ],
    "baseline",
    "the exact Codex trust binding",
  );
  if (
    typeof value.codexTrust.present !== "boolean" ||
    !Number.isSafeInteger(value.codexTrust.exactSectionCount) ||
    value.codexTrust.exactSectionCount < 0 ||
    value.codexTrust.exactSectionCount > CODEX_TRUST_EVENTS.length ||
    value.codexTrust.present !== (value.codexTrust.exactSectionCount > 0) ||
    !Array.isArray(value.codexTrust.events) ||
    value.codexTrust.events.length !== value.codexTrust.exactSectionCount ||
    new Set(value.codexTrust.events).size !== value.codexTrust.events.length ||
    value.codexTrust.events.some((event) => !CODEX_TRUST_EVENTS.includes(event)) ||
    !Number.isSafeInteger(value.codexTrust.removedSyntaxByteCount) ||
    value.codexTrust.removedSyntaxByteCount < 0 ||
    !/^[a-f0-9]{64}$/u.test(value.codexTrust.removedSyntaxSha256 ?? "")
  ) {
    fail("baseline", "the exact Codex trust binding is invalid");
  }
  return value;
}

async function baselineInventory(recorder, targets) {
  const registrations = hostRegistrationSnapshot(recorder, targets);
  assertRegistrationState(registrations, "installed-baseline");
  const state = inspectStateDirectory(targets, { requireInstalled: true });
  const desired = state.desired;
  if (
    desired?.schema !== DESIRED_STATE_SCHEMA ||
    desired?.activeVersion !== PRODUCT_VERSION ||
    !sameStrings(desired?.installedHosts ?? [], HOSTS) ||
    desired?.autoUpdate?.enabled !== false ||
    !sameStrings(desired?.autoUpdate?.hosts ?? [], []) ||
    state.launchAgentPresent
  ) {
    fail(
      "baseline",
      "the starting state is not the expected installed Claude/Codex state with updates disabled",
    );
  }
  inspectManagedLayout();
  const pluginRoots = {
    claude: resolveInstalledPluginRoot("claude", targets.claude.root),
    codex: resolveInstalledPluginRoot("codex", targets.codex.root),
  };
  const managedPayloadIntegrity = {};
  const cachePayloadIntegrity = {};
  for (const host of HOSTS) {
    await verifyManagedRootExact(host, targets[host].root, pluginRoots[host]);
    managedPayloadIntegrity[host] = "verified";
    verifyCacheMarketplaceShape(host, targets[host]);
    await verifyCachePayloadsForBaseline(host, targets[host].cacheRoot);
    cachePayloadIntegrity[host] = "verified";
  }
  const caches = {
    claude: inspectOwnedCache("claude", targets.claude.cacheRoot),
    codex: inspectOwnedCache("codex", targets.codex.cacheRoot),
  };
  const pluginData = targets.claude.pluginData.map(inspectPluginData);
  if (pluginData.some((item) => !item.empty)) {
    fail("ownership", "Claude OpenSocrates plugin data is nonempty and cannot be proven safe to purge");
  }
  const nonTargetHosts = assertNonTargetHostsAbsent(targets);
  const trustInspection = inspectCodexTrustSectionsWithBinding();
  const trust = trustInspection.public;
  const trustTransactionResidueCount = inspectTrustTransactionResidue(
    targets.codex.hostHome,
  );
  if (trustTransactionResidueCount !== 0) {
    fail("baseline", "a Codex OpenSocrates trust-reset transaction residue already exists");
  }
  const launchAgentTemporaryCount = inspectLaunchAgentTemporaryResidue(targets.state);
  if (launchAgentTemporaryCount !== 0) {
    fail("baseline", "an OpenSocrates LaunchAgent temporary residue already exists");
  }
  const launchAgentJob = inspectLaunchAgentJob(recorder);
  if (launchAgentJob.loaded) {
    fail("baseline", "the starting OpenSocrates launchd job is loaded despite updates being disabled");
  }
  const openCodeBridgeResidueCount = inspectOpenCodeBridgeResidue(targets.allHosts.opencode);
  if (openCodeBridgeResidueCount !== 0) {
    fail("baseline", "an OpenCode bridge transaction residue already exists");
  }
  const transactionResidue = assertNoKnownTransactionResidue(targets, "baseline");
  const hooks = codexHookInventory(recorder);
  const exactBindings = {
    schema: "opensocrates.reinstall-cycle-baseline-binding/1.0.0",
    managedRoots: Object.fromEntries(
      await Promise.all(
        HOSTS.map(async (host) => {
          const binding = await exactOwnedTreeBinding(
            targets[host].root,
            `${host} managed baseline root`,
          );
          const { present: _present, ...managedBinding } = binding;
          return [host, managedBinding];
        }),
      ),
    ),
    caches: Object.fromEntries(
      await Promise.all(
        HOSTS.map(async (host) => [
          host,
          await exactOwnedTreeBinding(
            targets[host].cacheRoot,
            `${host} cache baseline root`,
            { allowAbsent: true, ignoreCacheInUseMarkers: true },
          ),
        ]),
      ),
    ),
    desiredStateSha256: state.desiredStateSha256,
    codexTrust: trustInspection.binding,
  };
  assertBaselineExactBindings(exactBindings);
  return {
    public: {
      registrations,
      managedRootsPresent: { claude: true, codex: true },
      caches,
      managedPayloadIntegrity,
      cachePayloadIntegrity,
      pluginData,
      statePresent: state.present,
      launchAgentPresent: state.launchAgentPresent,
      launchAgentTemporaryCount,
      launchAgentJobLoaded: launchAgentJob.loaded,
      codexTrust: trust,
      trustTransactionResidueCount,
      codexHooks: hooks,
      nonTargetHosts,
      transactionResidue,
      openCodeBridgeResidueCount,
      ownership: "verified",
    },
    pluginRoots,
    exactBindings,
  };
}

function safeInventoryPath(value) {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    !value.startsWith("/") &&
    !value.includes("\\") &&
    value.split("/").every((part) => part !== "" && part !== "." && part !== "..")
  );
}

async function verifyInstalledPayload(host, pluginRoot, payloadReceiptPath) {
  const releasePath = join(pluginRoot, "release-manifest.json");
  const manifestPath = join(
    pluginRoot,
    ...(host === "claude"
      ? [".claude-plugin", "plugin.json"]
      : [".codex-plugin", "plugin.json"]),
  );
  for (const [target, label] of [
    [releasePath, `${host} installed release manifest`],
    [manifestPath, `${host} installed plugin manifest`],
  ]) {
    requireCanonicalOwnedEntry(target, label, "file");
  }
  const release = parseJson(
    readFileSync(releasePath, "utf8"),
    "post-install",
    `${host} installed release manifest is invalid`,
  );
  const manifest = parseJson(
    readFileSync(manifestPath, "utf8"),
    "post-install",
    `${host} installed plugin manifest is invalid`,
  );
  if (
    release?.schema !== "opensocrates.plugin-release-manifest/1.0.0" ||
    release?.host !== host ||
    release?.product_version !== PRODUCT_VERSION ||
    manifest?.name !== "opensocrates" ||
    manifest?.version !== PRODUCT_VERSION
  ) {
    fail("post-install", `${host} installed identity does not match ${PRODUCT_VERSION}`);
  }
  requireCanonicalOwnedEntry(payloadReceiptPath, `${host} private payload receipt`, "file");
  requireOwnerOnly(payloadReceiptPath, `the ${host} private payload receipt`);
  const receipt = parseJson(
    readFileSync(payloadReceiptPath, "utf8"),
    "post-install",
    `${host} private payload receipt is invalid`,
  );
  const verified = await verifyChecksumInventory(
    pluginRoot,
    "post-install",
    `${host} installed payload`,
  );
  const runtimePath = join(pluginRoot, ...String(receipt?.runtimeRelative ?? "").split("/"));
  if (!safeInventoryPath(receipt?.runtimeRelative)) {
    fail("post-install", `${host} private payload receipt has an unsafe runtime identity`);
  }
  requireCanonicalOwnedEntry(runtimePath, `${host} installed runtime receipt target`, "file");
  const runtimeSha256 = await sha256File(runtimePath);
  if (
    receipt?.schema !== "opensocrates.reinstall-payload-receipt/1.0.0" ||
    receipt?.host !== host ||
    receipt?.productVersion !== PRODUCT_VERSION ||
    receipt?.fileCount !== verified.declared.size ||
    receipt?.checksumInventorySha256 !== verified.checksumInventorySha256 ||
    receipt?.releaseManifestSha256 !== (await sha256File(releasePath)) ||
    receipt?.runtimeSha256 !== runtimeSha256 ||
    JSON.stringify(receipt?.files) !==
      JSON.stringify(
        Object.fromEntries([...verified.declared].sort(([left], [right]) => left.localeCompare(right))),
      )
  ) {
    fail("post-install", `${host} installed bytes do not match the downloaded exact-SHA CI payload`);
  }
  return {
    version: PRODUCT_VERSION,
    declaredFileCount: verified.declared.size,
    checksumInventorySha256: verified.checksumInventorySha256,
    releaseManifestSha256: receipt.releaseManifestSha256,
    runtimeSha256,
    ciPayloadByteIdentity: "matched",
  };
}

function verifyInstalledRuntime(recorder, host, pluginRoot) {
  const runtime = join(
    pluginRoot,
    "runtime",
    "darwin-arm64",
    "opensocrates-runtime",
    "opensocrates-runtime",
  );
  const info = requireCanonicalOwnedEntry(runtime, `${host} installed runtime`, "file");
  if ((info.mode & 0o111) === 0) {
    fail("post-install", `${host} installed runtime is not executable`);
  }
  const architecture = inspectMachOArchitecture(recorder, `${host} installed runtime`, runtime);
  const value = commandJson(
    recorder,
    `Read ${host} installed runtime identity`,
    runtime,
    ["version", "--json"],
    {},
    "post-install",
    `${host} installed runtime could not report its identity`,
  );
  if (value?.product !== "opensocrates" || value?.product_version !== PRODUCT_VERSION) {
    fail("post-install", `${host} installed runtime reported the wrong version`);
  }
  return {
    product: value.product,
    productVersion: value.product_version,
    contentRevision: value.content_revision,
    architectures: architecture.architectures,
    executable: true,
  };
}

function verifyPackagedStatus(recorder, candidate) {
  const completed = runPackedNpx(
    recorder,
    "Run exact packed npx all-host status",
    candidate,
    [
      "--yes",
      `--package=${candidate.packageArchive}`,
      "opensocrates",
      "status",
      "--host",
      "all",
    ],
    {
      category: "post-install",
      failureMessage: "the exact packed all-host status check failed",
      invocationMode: "account-home-lifecycle",
      timeout: 180_000,
    },
  );
  const expected = [
    `Desired version: ${PRODUCT_VERSION}`,
    `claude: installed ${PRODUCT_VERSION} (in sync)`,
    `codex: installed ${PRODUCT_VERSION} (in sync)`,
    "Overall: no detected drift",
  ];
  if (expected.some((line) => !completed.stdout.includes(line))) {
    fail("post-install", "the exact packed status output did not report both hosts in sync");
  }
  return { desiredVersion: PRODUCT_VERSION, hostsInSync: [...HOSTS], drift: false };
}

function measureInstalledSessionStart(
  recorder,
  privateDirectory,
  codexPluginRoot,
  expectedReleaseManifestSha256,
  pythonBinary,
) {
  const reportPath = join(privateDirectory, "codex-session-start-timing.json");
  writeFileSync(reportPath, "", { flag: "wx", mode: 0o600 });
  requireCanonicalOwnedEntry(reportPath, "private SessionStart timing report", "file");
  requireOwnerOnly(reportPath, "the private SessionStart timing report");
  const monotonicStartMs = performance.now();
  recorder.run(
    "Measure installed Codex SessionStart budget",
    pythonBinary,
    [
      "tools/measure_codex_hook_timing.py",
      "--package",
      codexPluginRoot,
      "--runs",
      "20",
      "--report",
      reportPath,
    ],
    {
      category: "session-start-budget",
      failureMessage: "the installed Codex SessionStart timing gate failed",
      timeout: 300_000,
      env: {
        HOME: privateDirectory,
        PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
        TMPDIR: tmpdir(),
        LANG: "C",
        LC_ALL: "C",
        PYTHONPATH: "",
        PYTHONNOUSERSITE: "1",
      },
    },
  );
  const monotonicEndMs = performance.now();
  requireCanonicalOwnedEntry(reportPath, "private SessionStart timing report", "file");
  requireOwnerOnly(reportPath, "the private SessionStart timing report");
  const value = parseJson(
    readFileSync(reportPath, "utf8"),
    "session-start-budget",
    "the installed SessionStart timing report is invalid",
  );
  if (
    value?.target !== "darwin-arm64" ||
    value?.sample_count !== 20 ||
    value?.configured_timeout_ms !== 2000 ||
    value?.pass !== true ||
    value?.process_model !== SESSION_START_PROCESS_MODEL ||
    value?.artifact_identity !== `sha256:${expectedReleaseManifestSha256}` ||
    typeof value?.latency_ms?.first !== "number" ||
    typeof value?.latency_ms?.p95 !== "number" ||
    typeof value?.latency_ms?.max !== "number" ||
    value.latency_ms.first >= 2000 ||
    value.latency_ms.max >= 2000 ||
    value.latency_ms.p95 > 1000
  ) {
    fail("session-start-budget", "the installed SessionStart timing result did not meet the two-second contract");
  }
  return {
    observationStatus: "pass",
    target: value.target,
    sampleCount: value.sample_count,
    configuredTimeoutMs: value.configured_timeout_ms,
    hardTimeoutMilliseconds: 2000,
    clock: "performance.now_monotonic",
    monotonicStartMilliseconds: Number(monotonicStartMs.toFixed(3)),
    monotonicEndMilliseconds: Number(monotonicEndMs.toFixed(3)),
    coldProcessPerSample: true,
    hardTimeoutEnforced: true,
    processModel: value.process_model,
    firstMs: value.latency_ms.first,
    p95Ms: value.latency_ms.p95,
    maxMs: value.latency_ms.max,
    pass: true,
    artifactIdentity: value.artifact_identity,
  };
}

function walkFiles(directory, output = []) {
  requireCanonicalOwnedEntry(directory, "artifact directory", "directory");
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = join(directory, entry.name);
    if (entry.isSymbolicLink()) {
      fail("ci-artifact", "the CI artifact contains a symbolic link");
    }
    if (entry.isDirectory()) {
      requireCanonicalOwnedEntry(target, "artifact directory", "directory");
      walkFiles(target, output);
    } else if (entry.isFile()) {
      requireCanonicalOwnedEntry(target, "artifact file", "file");
      output.push(target);
    } else {
      fail("ci-artifact", "the CI artifact contains a special filesystem entry");
    }
  }
  return output;
}

function findSingleFile(directory, expectedName, category) {
  const matches = walkFiles(directory).filter((target) => basename(target) === expectedName);
  if (matches.length !== 1) {
    fail(category, `expected exactly one ${expectedName} in the CI artifact`);
  }
  return matches[0];
}

function exactString(value, category, message) {
  if (typeof value !== "string" || value.length === 0) fail(category, message);
  return value;
}

function versionAtLeast(value, minimum) {
  const match = String(value).match(/(\d+)\.(\d+)\.(\d+)/u);
  if (!match) return false;
  const current = match.slice(1).map(Number);
  for (let index = 0; index < minimum.length; index += 1) {
    if (current[index] > minimum[index]) return true;
    if (current[index] < minimum[index]) return false;
  }
  return true;
}

export function canonicalHostVersion(value, host) {
  const normalized = typeof value === "string" ? value.trim() : "";
  const prefix = host === "claude"
    ? "(?:claude(?: code)?)"
    : host === "codex"
      ? "(?:codex(?:-cli)?)"
      : null;
  const suffix = host === "claude" ? "Claude Code" : "Codex CLI";
  if (prefix === null || normalized.length === 0 || normalized.length > 120) {
    fail("host-prerequisite", "the host version output has an unsupported identity");
  }
  const match = normalized.match(
    new RegExp(
      `^(?:${prefix}\\s+)?v?(\\d+\\.\\d+\\.\\d+(?:[-+][0-9A-Za-z.-]+)?)(?:\\s+\\(${suffix}\\))?$`,
      "iu",
    ),
  );
  if (match === null) {
    fail("host-prerequisite", `${host} returned a noncanonical version string`);
  }
  return match[1];
}

function resolveExecutable(name) {
  if (name.includes(sep)) {
    const candidate = realpathSync(name);
    accessSync(candidate, fsConstants.X_OK);
    return candidate;
  }
  for (const directory of String(process.env.PATH ?? "").split(":")) {
    if (!directory) continue;
    const candidate = join(directory, name);
    try {
      accessSync(candidate, fsConstants.X_OK);
      const canonical = realpathSync(candidate);
      const info = statSync(canonical);
      if (info.isFile() && (info.mode & 0o111) !== 0) return canonical;
    } catch {
      // Continue through the fixed PATH entries without invoking a shell.
    }
  }
  fail("environment", `${name} could not be resolved to an executable`);
}

function requireSafeIdentity() {
  if (typeof process.getuid !== "function" || typeof process.geteuid !== "function") {
    fail("environment", "POSIX user identity is required");
  }
  const uid = process.getuid();
  const effectiveUid = process.geteuid();
  if (uid === 0 || effectiveUid === 0) {
    fail("environment", "root execution is prohibited for lifecycle acceptance");
  }
  if (uid !== effectiveUid || process.env.SUDO_UID || process.env.SUDO_GID || process.env.SUDO_USER) {
    fail("environment", "sudo or changed effective-user execution is prohibited");
  }
  const accountHome = resolve(userInfo().homedir);
  const environmentHome = resolve(process.env.HOME ?? "");
  const runtimeHome = resolve(homedir());
  if (environmentHome !== accountHome || runtimeHome !== accountHome) {
    fail("environment", "HOME does not match the effective account home");
  }
  const homeInfo = requireCanonicalOwnedEntry(accountHome, "effective account home", "directory");
  if (homeInfo.uid !== uid) fail("environment", "the effective account does not own its home directory");
  return { uidMatchesEffectiveUid: true, homeOwnedByEffectiveUid: true, sudo: false };
}

function verifyEnvironment(recorder, report) {
  const identity = requireSafeIdentity();
  if (process.platform !== "darwin" || process.arch !== "arm64") {
    fail("environment", "this acceptance test requires Apple-silicon macOS");
  }
  if (Number(process.versions.node.split(".")[0]) < 20) {
    fail("environment", "Node.js 20 or later is required");
  }
  const overrides = [
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "OPENSOCRATES_STATE_DIR",
    "OPENSOCRATES_LAUNCH_AGENTS_DIR",
    "CLAUDE_BIN",
    "CODEX_BIN",
    "ANTIGRAVITY_CONFIG_DIR",
    "CURSOR_CONFIG_DIR",
    "GROK_HOME",
    "OPENCODE_CONFIG_DIR",
  ].filter((name) => process.env[name]);
  if (overrides.length > 0) {
    fail("environment", `unset path overrides before testing: ${overrides.join(", ")}`);
  }
  recorder.run(
    "Read macOS product version",
    "/usr/bin/sw_vers",
    ["-productVersion"],
    { category: "environment", failureMessage: "macOS version could not be determined" },
  );
  const hardwareArchitecture = recorder.run(
    "Read Darwin hardware architecture",
    "/usr/bin/uname",
    ["-m"],
    { category: "environment", failureMessage: "hardware architecture could not be determined" },
  ).stdout;
  const arm64Capability = recorder.run(
    "Confirm native arm64 hardware capability",
    "/usr/sbin/sysctl",
    ["-n", "hw.optional.arm64"],
    { category: "environment", failureMessage: "native arm64 capability could not be determined" },
  ).stdout;
  if (!new Set(["arm64", "aarch64"]).has(hardwareArchitecture) || arm64Capability !== "1") {
    fail("environment", "the Mac is not reporting native Apple-silicon hardware");
  }
  report.environment.platform = "darwin";
  report.environment.hardwareArchitecture = "arm64";
  report.environment.processArchitecture = process.arch;
  report.environment.identity = identity;
  return {
    platform: report.environment.platform,
    hardwareArchitecture: "arm64",
    processArchitecture: process.arch,
  };
}

function prepareIsolatedNpx(privateDirectory) {
  const executionRoot = join(privateDirectory, "isolated-npx");
  const runsRoot = join(executionRoot, "runs");
  for (const target of [executionRoot, runsRoot]) ensurePrivateDirectory(target);
  if (readdirSync(runsRoot).length !== 0) {
    fail("npx-isolation", "the isolated npm run root must start empty");
  }
  requireSafeIdentity();
  const account = userInfo();
  const accountHome = validateLifecycleAccountHome(account.homedir);
  const accountUser = validateLifecycleAccountUser(account.username);
  return {
    root: executionRoot,
    runsRoot,
    accountHome,
    accountUser,
    npxBinary: resolveExecutable("npx"),
    npmBinary: resolveExecutable("npm"),
    nodeBinary: realpathSync(process.execPath),
    pythonBinary: resolveExecutable("python3.12"),
    claudeBinary: resolveExecutable("claude"),
    codexBinary: resolveExecutable("codex"),
  };
}

function assertPathBelow(parent, target, label, expectedKind) {
  const canonicalParent = realpathSync(parent);
  const canonicalTarget = realpathSync(target);
  const local = relative(canonicalParent, canonicalTarget);
  if (local === "" || local === ".." || local.startsWith(`..${sep}`)) {
    fail("ownership", `${label} is outside the private candidate root`);
  }
  requireCanonicalOwnedEntry(canonicalTarget, label, expectedKind);
  return canonicalTarget;
}

export function validateLifecycleAccountHome(
  candidateHome,
  { expectedHome = userInfo().homedir, expectedUid = currentUid() } = {},
) {
  if (
    typeof candidateHome !== "string" ||
    typeof expectedHome !== "string" ||
    !Number.isSafeInteger(expectedUid) ||
    expectedUid < 0
  ) {
    fail("npx-isolation", "the lifecycle account HOME identity is invalid");
  }
  try {
    const candidateLexical = resolve(candidateHome);
    const expectedLexical = resolve(expectedHome);
    const candidateInfo = lstatSync(candidateLexical);
    const expectedInfo = lstatSync(expectedLexical);
    if (
      candidateInfo.isSymbolicLink() ||
      expectedInfo.isSymbolicLink() ||
      !candidateInfo.isDirectory() ||
      !expectedInfo.isDirectory() ||
      candidateInfo.uid !== expectedUid ||
      expectedInfo.uid !== expectedUid ||
      realpathSync(candidateLexical) !== candidateLexical ||
      realpathSync(expectedLexical) !== expectedLexical ||
      candidateLexical !== expectedLexical
    ) {
      fail("npx-isolation", "the lifecycle account HOME is not the canonical current-user directory");
    }
    return candidateLexical;
  } catch (error) {
    if (error instanceof AcceptanceError) throw error;
    fail("npx-isolation", "the lifecycle account HOME could not be verified safely");
  }
}

export function validateLifecycleAccountUser(
  candidateUser,
  { expectedUser = userInfo().username } = {},
) {
  if (
    typeof candidateUser !== "string" ||
    typeof expectedUser !== "string" ||
    !/^[A-Za-z0-9._-]{1,255}$/u.test(candidateUser) ||
    !/^[A-Za-z0-9._-]{1,255}$/u.test(expectedUser) ||
    candidateUser !== expectedUser
  ) {
    fail("npx-isolation", "the lifecycle account username is not the current POSIX user");
  }
  return candidateUser;
}

function lifecycleAccountHome(execution) {
  requireSafeIdentity();
  return validateLifecycleAccountHome(execution.accountHome);
}

const NPM_USER_CONFIG =
  "audit=false\nfund=false\nupdate-notifier=false\nignore-scripts=true\n";

function npmRunEnvironment(execution, paths, userConfig, invocationMode) {
  const nodeDirectory = dirname(execution.nodeBinary);
  const fixedPath = [
    nodeDirectory,
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
  ].filter((item, index, values) => values.indexOf(item) === index);
  return {
    HOME:
      invocationMode === "account-home-lifecycle"
        ? lifecycleAccountHome(execution)
        : paths.home,
    USER: validateLifecycleAccountUser(execution.accountUser),
    PATH: fixedPath.join(":"),
    TMPDIR: paths.tmp,
    LANG: "C",
    LC_ALL: "C",
    TZ: "UTC",
    NODE_PATH: "",
    CLAUDE_BIN: execution.claudeBinary,
    CODEX_BIN: execution.codexBinary,
    npm_config_cache: paths.cache,
    npm_config_prefix: paths.prefix,
    npm_config_userconfig: userConfig,
    npm_config_globalconfig: "/dev/null",
    npm_config_dry_run: "false",
    npm_config_json: "false",
    npm_config_audit: "false",
    npm_config_fund: "false",
    npm_config_update_notifier: "false",
    npm_config_ignore_scripts: "true",
  };
}

function durableLifecycleNpmRun(execution, operationKey) {
  lifecycleAttempt(operationKey);
  requireExactPrivateMode(execution.runsRoot, "isolated npm run root", "directory", 0o700);
  const runRoot = join(execution.runsRoot, `lifecycle-${operationKey}`);
  if (!pathPresent(runRoot)) {
    mkdirSync(runRoot, { mode: 0o700 });
    chmodSync(runRoot, 0o700);
    syncEntry(execution.runsRoot);
  }
  requireExactPrivateMode(runRoot, "durable lifecycle npm run", "directory", 0o700);
  const paths = {};
  for (const name of ["cwd", "cache", "prefix", "home", "tmp"]) {
    const target = join(runRoot, name);
    if (!pathPresent(target)) {
      mkdirSync(target, { mode: 0o700 });
      chmodSync(target, 0o700);
      syncEntry(runRoot);
    }
    requireExactPrivateMode(target, `durable lifecycle npm ${name}`, "directory", 0o700);
    paths[name] = realpathSync(target);
  }
  const userConfig = join(runRoot, "user.npmrc");
  if (!pathPresent(userConfig)) writeExclusivePrivateBytes(userConfig, NPM_USER_CONFIG, "npx-isolation");
  requireExactPrivateMode(userConfig, "durable lifecycle npm user config", "file", 0o600);
  if (readFileSync(userConfig, "utf8") !== NPM_USER_CONFIG) {
    fail("npx-isolation", "the durable lifecycle npm user config changed");
  }
  if (!sameStrings(readdirSync(runRoot), [...Object.keys(paths), "user.npmrc"])) {
    fail("npx-isolation", "the durable lifecycle npm sandbox has an unexpected entry");
  }
  return {
    ...paths,
    runRoot: realpathSync(runRoot),
    userConfig: realpathSync(userConfig),
    env: npmRunEnvironment(execution, paths, userConfig, "account-home-lifecycle"),
  };
}

function freshNpmRun(
  execution,
  invocationMode = "isolated-preflight",
  lifecycleOperationKey = null,
) {
  if (!NPM_INVOCATION_MODES.has(invocationMode)) {
    fail("npx-isolation", "packed npm execution requested an unsupported invocation mode");
  }
  if (lifecycleOperationKey !== null) {
    if (invocationMode !== "account-home-lifecycle") {
      fail("npx-isolation", "a durable lifecycle sandbox requires the account HOME mode");
    }
    return durableLifecycleNpmRun(execution, lifecycleOperationKey);
  }
  requireCanonicalOwnedEntry(execution.runsRoot, "isolated npm run root", "directory");
  requireOwnerOnly(execution.runsRoot, "the isolated npm run root");
  const runRoot = realpathSync(mkdtempSync(join(execution.runsRoot, "call-")));
  chmodSync(runRoot, 0o700);
  const paths = Object.fromEntries(
    ["cwd", "cache", "prefix", "home", "tmp"].map((name) => {
      const target = join(runRoot, name);
      ensurePrivateDirectory(target);
      return [name, target];
    }),
  );
  const userConfig = join(runRoot, "user.npmrc");
  writePrivate(userConfig, NPM_USER_CONFIG);
  return {
    ...paths,
    runRoot,
    userConfig,
    env: npmRunEnvironment(execution, paths, userConfig, invocationMode),
  };
}

function npxRunOptions(
  candidate,
  overrides = {},
  invocationMode = "isolated-preflight",
  lifecycleOperationKey = null,
) {
  if (Object.hasOwn(overrides, "cwd") || Object.hasOwn(overrides, "env")) {
    fail("npx-isolation", "packed npm execution cannot override its isolated cwd or environment");
  }
  const run = freshNpmRun(candidate.execution, invocationMode, lifecycleOperationKey);
  return {
    ...overrides,
    cwd: run.cwd,
    env: run.env,
  };
}

function packedInvocationVerb(args) {
  const commandIndex = args.indexOf("opensocrates");
  return commandIndex >= 0 ? args[commandIndex + 1] ?? null : null;
}

export function statusCommandArguments(candidate) {
  return [
    "--yes",
    `--package=${candidate.packageArchive}`,
    "opensocrates",
    "status",
    "--host",
    "all",
  ];
}

export function packedNpxInvocation(candidate, args, overrides = {}) {
  if (!Array.isArray(args) || args.some((item) => typeof item !== "string")) {
    fail("npx-isolation", "packed npx arguments must be a fixed string array");
  }
  const {
    invocationMode = "isolated-preflight",
    lifecycleOperationKey = null,
    ...runOverrides
  } = overrides;
  if (!NPM_INVOCATION_MODES.has(invocationMode)) {
    fail("npx-isolation", "packed npx execution requested an unsupported invocation mode");
  }
  const verb = packedInvocationVerb(args);
  const expectedLifecycleArguments =
    verb === "remove"
      ? purgeCommandArguments(candidate)
      : verb === "install"
        ? installCommandArguments(candidate)
        : verb === "status"
          ? statusCommandArguments(candidate)
          : null;
  const lifecycleVerb = expectedLifecycleArguments !== null;
  const mutatingLifecycleVerb = verb === "remove" || verb === "install";
  const exactLifecycleCommand =
    lifecycleVerb &&
    JSON.stringify(expectedLifecycleArguments) === JSON.stringify(args);
  if (
    (invocationMode === "account-home-lifecycle" && !exactLifecycleCommand) ||
    (invocationMode === "isolated-preflight" && lifecycleVerb)
  ) {
    fail("npx-isolation", "packed lifecycle argv and HOME mode do not match the closed contract");
  }
  if (
    (mutatingLifecycleVerb && lifecycleOperationKey === null) ||
    (!mutatingLifecycleVerb && lifecycleOperationKey !== null) ||
    (verb === "remove" && !new Set(["purge-initial", "purge-host-close-retry"]).has(lifecycleOperationKey)) ||
    (verb === "install" && !new Set(["install-initial", "install-retry"]).has(lifecycleOperationKey))
  ) {
    fail("lifecycle-intent", "the packed mutation does not bind its exact lifecycle operation key");
  }
  return {
    executable: candidate.execution.npxBinary,
    args: [...args],
    options: npxRunOptions(
      candidate,
      runOverrides,
      invocationMode,
      lifecycleOperationKey,
    ),
  };
}

function lifecycleCandidateIdentity(candidate) {
  const value = {
    sourceCommit: candidate.sourceCommit,
    packageSha256: candidate.packageSha256,
    rawArtifactSha256: candidate.rawArtifactSha256,
    buildSourceReceiptSha256: candidate.buildSourceReceiptSha256,
    accountUser: candidate.execution?.accountUser,
    execution: {
      nodeBinarySha256: candidate.execution?.nodeBinarySha256,
      npmBinarySha256: candidate.execution?.npmBinarySha256,
      npxBinarySha256: candidate.execution?.npxBinarySha256,
      pythonBinarySha256: candidate.execution?.pythonBinarySha256,
      claudeBinarySha256: candidate.execution?.claudeBinarySha256,
      codexBinarySha256: candidate.execution?.codexBinarySha256,
    },
    assets: Object.fromEntries(
      HOSTS.map((host) => [
        host,
        {
          sha256: candidate.assets?.[host]?.sha256,
          checksumSha256: candidate.assets?.[host]?.checksumSha256,
          payloadReceiptSha256: candidate.assets?.[host]?.payloadReceiptSha256,
          releaseManifestSha256: candidate.assets?.[host]?.releaseManifestSha256,
        },
      ]),
    ),
  };
  if (
    !/^[a-f0-9]{40}$/u.test(value.sourceCommit ?? "") ||
    validateLifecycleAccountUser(value.accountUser) !== value.accountUser ||
    [
      value.packageSha256,
      value.rawArtifactSha256,
      value.buildSourceReceiptSha256,
      ...Object.values(value.execution),
      ...HOSTS.flatMap((host) => Object.values(value.assets[host])),
    ].some((item) => !/^[a-f0-9]{64}$/u.test(item ?? ""))
  ) {
    fail("artifact-integrity", "the durable lifecycle candidate identity is incomplete");
  }
  return sha256Buffer(JSON.stringify(value));
}

export function runPackedNpx(recorder, label, candidate, args, overrides = {}) {
  const { lifecycleOperationKey = null, ...invocationOverrides } = overrides;
  const verb = packedInvocationVerb(args);
  const invocation = packedNpxInvocation(candidate, args, {
    ...invocationOverrides,
    lifecycleOperationKey:
      verb === "remove" || verb === "install" ? lifecycleOperationKey : null,
  });
  if (verb === "remove" || verb === "install") {
    if (lifecycleOperationKey === null || typeof recorder.runLifecycle !== "function") {
      fail("lifecycle-intent", "a destructive packed npx call lacks its durable operation capsule");
    }
    return recorder.runLifecycle(
      label,
      invocation.executable,
      invocation.args,
      {
        ...invocation.options,
        operationKey: lifecycleOperationKey,
        candidateIdentitySha256: lifecycleCandidateIdentity(candidate),
      },
    );
  }
  if (lifecycleOperationKey !== null) {
    fail("lifecycle-intent", "a nonmutating packed npx call cannot claim a lifecycle operation key");
  }
  return recorder.run(
    label,
    invocation.executable,
    invocation.args,
    invocation.options,
  );
}

async function pinExecutionIdentity(recorder, execution) {
  execution.npxBinarySha256 = await sha256File(execution.npxBinary);
  execution.npmBinarySha256 = await sha256File(execution.npmBinary);
  execution.nodeBinarySha256 = await sha256File(execution.nodeBinary);
  execution.pythonBinarySha256 = await sha256File(execution.pythonBinary);
  execution.claudeBinarySha256 = await sha256File(execution.claudeBinary);
  execution.codexBinarySha256 = await sha256File(execution.codexBinary);
  const candidate = { execution };
  execution.npxVersion = recorder.run(
    "Read pinned npx version",
    execution.npxBinary,
    ["--version"],
    npxRunOptions(candidate, {
      category: "npx-isolation",
      failureMessage: "the pinned npx version could not be read",
    }),
  ).stdout;
  execution.npmVersion = recorder.run(
    "Read pinned npm version",
    execution.npmBinary,
    ["--version"],
    npxRunOptions(candidate, {
      category: "npx-isolation",
      failureMessage: "the pinned npm version could not be read",
    }),
  ).stdout;
  if (
    !/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(execution.npxVersion) ||
    !/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(execution.npmVersion)
  ) {
    fail("npx-isolation", "npm or npx returned an unsupported version identity");
  }
  execution.nodeVersion = process.version;
  execution.pythonVersion = recorder.run(
    "Read pinned Python version",
    execution.pythonBinary,
    ["-c", "import platform; print(platform.python_version())"],
    {
      category: "python-toolchain",
      failureMessage: "the pinned Python version could not be read",
      persistRaw: false,
      env: {
        HOME: execution.accountHome,
        PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
        LANG: "C",
        LC_ALL: "C",
        PYTHONPATH: "",
        PYTHONNOUSERSITE: "1",
      },
    },
  ).stdout;
  if (!/^3\.12\.\d+$/u.test(execution.pythonVersion)) {
    fail("python-toolchain", "the acceptance timing gate requires Python 3.12");
  }
  return execution;
}

async function verifyExecutionIdentity(recorder, candidate) {
  const execution = candidate.execution;
  if (
    (await sha256File(execution.npxBinary)) !== execution.npxBinarySha256 ||
    (await sha256File(execution.npmBinary)) !== execution.npmBinarySha256 ||
    (await sha256File(execution.nodeBinary)) !== execution.nodeBinarySha256 ||
    (await sha256File(execution.pythonBinary)) !== execution.pythonBinarySha256 ||
    (await sha256File(execution.claudeBinary)) !== execution.claudeBinarySha256 ||
    (await sha256File(execution.codexBinary)) !== execution.codexBinarySha256 ||
    realpathSync(process.execPath) !== execution.nodeBinary
  ) {
    fail("npx-isolation", "a pinned Node, Python, npm, npx, or host executable changed after candidate preparation");
  }
  validateLifecycleAccountUser(execution.accountUser);
  const npxVersion = recorder.run(
    "Reconfirm pinned npx version",
    execution.npxBinary,
    ["--version"],
    npxRunOptions(candidate, {
      category: "npx-isolation",
      failureMessage: "the pinned npx version could not be reconfirmed",
    }),
  ).stdout;
  const npmVersion = recorder.run(
    "Reconfirm pinned npm version",
    execution.npmBinary,
    ["--version"],
    npxRunOptions(candidate, {
      category: "npx-isolation",
      failureMessage: "the pinned npm version could not be reconfirmed",
    }),
  ).stdout;
  if (
    npxVersion !== execution.npxVersion ||
    npmVersion !== execution.npmVersion ||
    process.version !== execution.nodeVersion ||
    !/^3\.12\.\d+$/u.test(execution.pythonVersion ?? "")
  ) {
    fail("npx-isolation", "the npm, npx, Node, or Python execution identity changed before lifecycle use");
  }
  verifyLifecycleHostAuthentication(recorder, execution);
}

function verifyGitHubAuthentication(recorder) {
  recorder.run("Verify GitHub authentication", "gh", ["auth", "status"], {
    category: "github-auth",
    failureMessage: "GitHub CLI is not authenticated",
    projection: "status-only",
    persistRaw: false,
  });
}

function verifySource(recorder, report) {
  verifyGitHubAuthentication(recorder);
  const topLevel = recorder.run("Resolve Git checkout root", "git", ["rev-parse", "--show-toplevel"], {
    category: "source",
    failureMessage: "the script must run from a Git checkout",
  }).stdout;
  if (resolve(topLevel) !== ROOT) {
    fail("source", "the script location and Git checkout root do not match");
  }
  const worktree = recorder.run(
    "Verify clean candidate worktree",
    "git",
    ["status", "--porcelain", "--untracked-files=all"],
    { category: "source", failureMessage: "the Git worktree state could not be checked" },
  ).stdout;
  if (worktree !== "") {
    fail("source", "the Git worktree must be clean before acceptance testing");
  }
  const commit = recorder.run("Resolve candidate commit", "git", ["rev-parse", "HEAD"], {
    category: "source",
    failureMessage: "the source commit could not be determined",
  }).stdout;
  if (!/^[a-f0-9]{40}$/u.test(commit)) fail("source", "the source commit is invalid");
  const tree = recorder.run("Resolve candidate source tree", "git", ["rev-parse", "HEAD^{tree}"], {
    category: "source",
    failureMessage: "the source tree could not be determined",
  }).stdout;
  if (!/^[a-f0-9]{40}$/u.test(tree)) fail("source", "the source tree is invalid");
  const branch = recorder.run(
    "Resolve pull-request branch",
    "git",
    ["symbolic-ref", "--quiet", "--short", "HEAD"],
    { category: "source", failureMessage: "check out the pull-request branch" },
  ).stdout;
  const repository = commandJson(
    recorder,
    "Verify canonical GitHub repository",
    "gh",
    ["repo", "view", REPOSITORY, "--json", "nameWithOwner"],
    {},
    "source",
    "the GitHub repository could not be determined",
  );
  if (repository?.nameWithOwner !== REPOSITORY) {
    fail("source", `the checkout must belong to ${REPOSITORY}`);
  }
  const pullRequest = commandJson(
    recorder,
    "Resolve current branch pull request",
    "gh",
    ["pr", "view", branch, "--repo", REPOSITORY, "--json", "number,headRefOid,state,url"],
    {},
    "source",
    "the current branch's pull request could not be inspected",
  );
  const pullRequestNumber = Number(pullRequest?.number);
  if (!Number.isSafeInteger(pullRequestNumber) || pullRequestNumber <= 0) {
    fail("source", "GitHub returned an invalid pull-request number");
  }
  if (pullRequest?.headRefOid !== commit) {
    fail("source", "the checkout is not at the current pull-request head");
  }
  if (pullRequest?.state !== "OPEN") {
    fail("source", `pull request #${pullRequestNumber} is not open`);
  }
  report.source.commit = commit;
  report.source.tree = tree;
  report.source.pullRequest = pullRequestNumber;
  report.source.pullRequestUrl = exactString(
    pullRequest.url,
    "source",
    "the pull-request URL is missing",
  );
  return { commit, tree };
}

function verifyHosts(recorder, report) {
  const claudeVersionOutput = recorder.run("Read Claude Code version", "claude", ["--version"], {
    category: "host-prerequisite",
    failureMessage: "Claude Code is unavailable",
    persistRaw: false,
  }).stdout;
  const claudeVersion = canonicalHostVersion(claudeVersionOutput, "claude");
  if (!versionAtLeast(claudeVersion, [2, 1, 205])) {
    fail("host-prerequisite", "Claude Code 2.1.205 or later is required");
  }
  const claudeAuthentication = commandJson(
    recorder,
    "Verify Claude authentication",
    "claude",
    ["auth", "status", "--json"],
    { projection: "claude-auth", persistRaw: false },
    "host-auth",
    "Claude Code authentication could not be inspected",
  );
  if (claudeAuthentication?.loggedIn !== true) {
    fail("host-auth", "Claude Code is not authenticated");
  }
  const codexVersionOutput = recorder.run("Read Codex CLI version", "codex", ["--version"], {
    category: "host-prerequisite",
    failureMessage: "Codex CLI is unavailable",
    persistRaw: false,
  }).stdout;
  const codexVersion = canonicalHostVersion(codexVersionOutput, "codex");
  recorder.run("Verify Codex authentication", "codex", ["login", "status"], {
    category: "host-auth",
    failureMessage: "Codex CLI is not authenticated",
    projection: "status-only",
    persistRaw: false,
  });
  report.environment.claudeVersion = claudeVersion;
  report.environment.codexVersion = codexVersion;
  return {
    claudeVersion: report.environment.claudeVersion,
    codexVersion: report.environment.codexVersion,
  };
}

function verifyLifecycleHostAuthentication(recorder, execution) {
  const run = freshNpmRun(execution, "isolated-preflight", null);
  const environment = {
    ...run.env,
    HOME: lifecycleAccountHome(execution),
  };
  const claudeAuthentication = commandJson(
    recorder,
    "Verify pinned Claude authentication in lifecycle environment",
    execution.claudeBinary,
    ["auth", "status", "--json"],
    { env: environment, projection: "claude-auth", persistRaw: false },
    "host-auth",
    "the pinned Claude CLI authentication could not be inspected in the lifecycle environment",
  );
  if (claudeAuthentication?.loggedIn !== true) {
    fail("host-auth", "the pinned Claude CLI is not authenticated in the lifecycle environment");
  }
  recorder.run(
    "Verify pinned Codex authentication in lifecycle environment",
    execution.codexBinary,
    ["login", "status"],
    {
      env: environment,
      category: "host-auth",
      failureMessage: "the pinned Codex CLI is not authenticated in the lifecycle environment",
      projection: "status-only",
      persistRaw: false,
    },
  );
  return { claude: true, codex: true };
}

function requireEmptyDirectory(target, label) {
  requireCanonicalOwnedEntry(target, label, "directory");
  if (readdirSync(target).length !== 0) fail("ownership", `${label} must be empty`);
}

function assertSafeArchiveEntry(entry, label, { requiredPrefix = null } = {}) {
  const normalized = entry.endsWith("/") ? entry.slice(0, -1) : entry;
  if (
    normalized.length === 0 ||
    normalized.startsWith("/") ||
    normalized.includes("\\") ||
    normalized.split("/").some((part) => part === "" || part === "." || part === "..") ||
    normalized.split("/").some((part) => part === "__MACOSX" || part === ".DS_Store" || part.startsWith("._")) ||
    (requiredPrefix !== null && normalized !== requiredPrefix && !normalized.startsWith(`${requiredPrefix}/`))
  ) {
    fail("artifact-integrity", `${label} contains an unsafe or unexpected entry`);
  }
}

function readDescriptorExactly(descriptor, length, position, category, label) {
  const buffer = Buffer.alloc(length);
  let offset = 0;
  while (offset < length) {
    const count = readSync(descriptor, buffer, offset, length - offset, position + offset);
    if (count === 0) fail(category, `${label} ended before its declared metadata boundary`);
    offset += count;
  }
  return buffer;
}

const ZIP_CRC32_TABLE = (() => {
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

function zipCrc32(bytes) {
  let value = 0xffffffff;
  for (const byte of bytes) value = ZIP_CRC32_TABLE[(value ^ byte) & 0xff] ^ (value >>> 8);
  return (value ^ 0xffffffff) >>> 0;
}

function inflateVerifiedZipPayload(compressed, entry, category, label) {
  let output;
  if (entry.method === 0) {
    if (entry.compressedSize !== entry.uncompressedSize) {
      fail(category, `${label} ZIP stored entry has inconsistent sizes`);
    }
    output = compressed;
  } else {
    try {
      const inflated = inflateRawSync(compressed, {
        info: true,
        maxOutputLength: entry.uncompressedSize + 1,
      });
      if (inflated.engine.bytesWritten !== compressed.length) {
        fail(category, `${label} ZIP deflate stream has trailing or unconsumed input`);
      }
      output = inflated.buffer;
    } catch (error) {
      if (error instanceof AcceptanceError) throw error;
      fail(category, `${label} ZIP deflate stream exceeds or violates its declared bound`);
    }
  }
  if (output.length !== entry.uncompressedSize || zipCrc32(output) !== entry.crc32) {
    fail(category, `${label} ZIP payload does not match its declared size and CRC`);
  }
  return output;
}

function assertZipPathTrie(entries, category, label) {
  const root = { type: "directory", children: new Map() };
  for (const entry of entries) {
    const segments = entry.name.replace(/\/$/u, "").split("/");
    let node = root;
    for (let index = 0; index < segments.length; index += 1) {
      if (node.type === "file") {
        fail(category, `${label} ZIP has a file ancestor path conflict`);
      }
      const segment = segments[index];
      const folded = segment.normalize("NFC").toLowerCase();
      let child = node.children.get(folded);
      if (child === undefined) {
        child = { original: segment, type: null, children: new Map() };
        node.children.set(folded, child);
      } else if (child.original !== segment) {
        fail(category, `${label} ZIP has a per-segment case or NFC collision`);
      }
      node = child;
      if (index === segments.length - 1) {
        const type = entry.directory ? "directory" : "file";
        if (node.type !== null || (type === "file" && node.children.size > 0)) {
          fail(category, `${label} ZIP has a duplicate, alias, or ancestor type conflict`);
        }
        node.type = type;
      }
    }
  }
}

function inspectZipCentralDirectory(
  archive,
  { label, category, profile = "strict-package" },
) {
  if (!ZIP_PROFILES.has(profile)) {
    fail(category, `${label} ZIP verification profile is unsupported`);
  }
  const githubArtifactContainer = profile === "github-artifact-container";
  requireCanonicalOwnedEntry(archive, `${label} ZIP`, "file");
  const size = statSync(archive).size;
  if (!Number.isSafeInteger(size) || size < 22 || size > MAX_ARTIFACT_BYTES) {
    fail(category, `${label} ZIP has an invalid container size`);
  }
  const descriptor = openSync(archive, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW);
  try {
    const tailLength = Math.min(size, 65_557);
    const tail = readDescriptorExactly(
      descriptor,
      tailLength,
      size - tailLength,
      category,
      label,
    );
    let endOffset = -1;
    for (let index = tail.length - 22; index >= 0; index -= 1) {
      if (
        tail.readUInt32LE(index) === 0x06054b50 &&
        index + 22 + tail.readUInt16LE(index + 20) === tail.length
      ) {
        endOffset = index;
        break;
      }
    }
    if (endOffset < 0) fail(category, `${label} ZIP has no exact end-of-directory record`);
    const disk = tail.readUInt16LE(endOffset + 4);
    const centralDisk = tail.readUInt16LE(endOffset + 6);
    const diskEntries = tail.readUInt16LE(endOffset + 8);
    const entryCount = tail.readUInt16LE(endOffset + 10);
    const centralSize = tail.readUInt32LE(endOffset + 12);
    const centralOffset = tail.readUInt32LE(endOffset + 16);
    const absoluteEndOffset = size - tailLength + endOffset;
    if (
      disk !== 0 ||
      centralDisk !== 0 ||
      diskEntries !== entryCount ||
      entryCount === 0 ||
      entryCount > MAX_ARCHIVE_ENTRIES ||
      centralSize === 0 ||
      centralSize > MAX_ZIP_CENTRAL_DIRECTORY_BYTES ||
      centralOffset + centralSize !== absoluteEndOffset
    ) {
      fail(category, `${label} ZIP has unsupported multi-disk, ZIP64, or bounded-size metadata`);
    }
    const central = readDescriptorExactly(
      descriptor,
      centralSize,
      centralOffset,
      category,
      label,
    );
    const entries = [];
    let cursor = 0;
    let totalUncompressed = 0;
    for (let index = 0; index < entryCount; index += 1) {
      if (cursor + 46 > central.length || central.readUInt32LE(cursor) !== 0x02014b50) {
        fail(category, `${label} ZIP central directory is truncated or ambiguous`);
      }
      const madeBy = central.readUInt16LE(cursor + 4);
      const requiredVersion = central.readUInt16LE(cursor + 6);
      const flags = central.readUInt16LE(cursor + 8);
      const method = central.readUInt16LE(cursor + 10);
      const crc32 = central.readUInt32LE(cursor + 16);
      const compressedSize = central.readUInt32LE(cursor + 20);
      const uncompressedSize = central.readUInt32LE(cursor + 24);
      const nameLength = central.readUInt16LE(cursor + 28);
      const extraLength = central.readUInt16LE(cursor + 30);
      const commentLength = central.readUInt16LE(cursor + 32);
      const entryDisk = central.readUInt16LE(cursor + 34);
      const internalAttributes = central.readUInt16LE(cursor + 36);
      const externalAttributes = central.readUInt32LE(cursor + 38);
      const localOffset = central.readUInt32LE(cursor + 42);
      const next = cursor + 46 + nameLength + extraLength + commentLength;
      const externalLowAttributes = externalAttributes & 0xffff;
      const centralProfileMatches = githubArtifactContainer
        ? madeBy === 0x032d &&
          flags === 0x0008 &&
          method === 8 &&
          externalLowAttributes === 0x20
        : madeBy === 0x0314 &&
          flags === 0x0800 &&
          new Set([0, 8]).has(method) &&
          externalLowAttributes === 0;
      if (
        next > central.length ||
        nameLength === 0 ||
        !centralProfileMatches ||
        requiredVersion !== 20 ||
        extraLength !== 0 ||
        commentLength !== 0 ||
        entryDisk !== 0 ||
        internalAttributes !== 0 ||
        uncompressedSize > MAX_ZIP_ENTRY_BYTES ||
        totalUncompressed + uncompressedSize > MAX_ZIP_UNCOMPRESSED_BYTES ||
        (uncompressedSize > 0 && compressedSize === 0) ||
        (compressedSize > 0 && uncompressedSize / compressedSize > MAX_ZIP_COMPRESSION_RATIO)
      ) {
        fail(category, `${label} ZIP entry exceeds the closed flags, metadata, type, size, or ratio contract`);
      }
      const nameBytes = Buffer.from(
        central.subarray(cursor + 46, cursor + 46 + nameLength),
      );
      const name = nameBytes.toString("utf8");
      if (
        name.includes("\uFFFD") ||
        name.includes("\0") ||
        !Buffer.from(name, "utf8").equals(nameBytes) ||
        (githubArtifactContainer &&
          ![...nameBytes].every((byte) => byte >= 0x20 && byte <= 0x7e))
      ) {
        fail(category, `${label} ZIP contains an invalid or noncanonical UTF-8 member name`);
      }
      assertSafeArchiveEntry(name, label);
      const mode = externalAttributes >>> 16;
      const fileType = mode & 0o170000;
      const directory = name.endsWith("/");
      if (
        !new Set([0o100000, 0o040000]).has(fileType) ||
        (fileType === 0o040000) !== directory ||
        (githubArtifactContainer &&
          (directory || !new Set([0o100600, 0o100644, 0o100755]).has(mode))) ||
        (directory && (compressedSize !== 0 || uncompressedSize !== 0 || crc32 !== 0))
      ) {
        fail(category, `${label} ZIP contains a link, special entry, or inconsistent Unix type`);
      }
      totalUncompressed += uncompressedSize;
      entries.push({
        name,
        nameBytes,
        flags,
        method,
        crc32,
        compressedSize,
        uncompressedSize,
        localOffset,
        mode,
        directory,
      });
      cursor = next;
    }
    if (cursor !== central.length) {
      fail(category, `${label} ZIP central directory contains trailing ambiguous metadata`);
    }
    assertZipPathTrie(entries, category, label);
    const physicalEntries = [...entries].sort((left, right) => left.localOffset - right.localOffset);
    let expectedLocalOffset = 0;
    let totalActual = 0;
    for (let index = 0; index < physicalEntries.length; index += 1) {
      const entry = physicalEntries[index];
      if (entry.localOffset !== expectedLocalOffset || entry.localOffset + 30 > centralOffset) {
        fail(category, `${label} ZIP local member ranges contain a gap, overlap, or alias`);
      }
      const header = readDescriptorExactly(
        descriptor,
        30,
        entry.localOffset,
        category,
        label,
      );
      if (header.readUInt32LE(0) !== 0x04034b50) {
        fail(category, `${label} ZIP local member header is invalid`);
      }
      const localNameLength = header.readUInt16LE(26);
      const localExtraLength = header.readUInt16LE(28);
      const dataOffset = entry.localOffset + 30 + localNameLength + localExtraLength;
      const localProfileMatches = githubArtifactContainer
        ? header.readUInt32LE(14) === 0 &&
          header.readUInt32LE(18) === 0 &&
          header.readUInt32LE(22) === 0
        : header.readUInt32LE(14) === entry.crc32 &&
          header.readUInt32LE(18) === entry.compressedSize &&
          header.readUInt32LE(22) === entry.uncompressedSize;
      const descriptorLength = githubArtifactContainer ? 16 : 0;
      if (
        header.readUInt16LE(4) !== 20 ||
        header.readUInt16LE(6) !== entry.flags ||
        header.readUInt16LE(8) !== entry.method ||
        !localProfileMatches ||
        localNameLength !== entry.nameBytes.length ||
        localExtraLength !== 0 ||
        dataOffset + entry.compressedSize + descriptorLength > centralOffset
      ) {
        fail(category, `${label} ZIP local and central metadata do not agree exactly`);
      }
      const localNameBytes = readDescriptorExactly(
        descriptor,
        localNameLength,
        entry.localOffset + 30,
        category,
        label,
      );
      if (!localNameBytes.equals(entry.nameBytes)) {
        fail(category, `${label} ZIP local and central raw member names do not agree`);
      }
      if (githubArtifactContainer) {
        const descriptorBytes = readDescriptorExactly(
          descriptor,
          16,
          dataOffset + entry.compressedSize,
          category,
          label,
        );
        if (
          descriptorBytes.readUInt32LE(0) !== 0x08074b50 ||
          descriptorBytes.readUInt32LE(4) !== entry.crc32 ||
          descriptorBytes.readUInt32LE(8) !== entry.compressedSize ||
          descriptorBytes.readUInt32LE(12) !== entry.uncompressedSize
        ) {
          fail(category, `${label} ZIP signed data descriptor does not match central metadata`);
        }
      }
      const compressed = readDescriptorExactly(
        descriptor,
        entry.compressedSize,
        dataOffset,
        category,
        label,
      );
      const output = inflateVerifiedZipPayload(compressed, entry, category, label);
      totalActual += output.length;
      if (totalActual > MAX_ZIP_UNCOMPRESSED_BYTES) {
        fail(category, `${label} ZIP actual output exceeds the cumulative bound`);
      }
      entry.dataOffset = dataOffset;
      entry.payloadSha256 = sha256Buffer(output);
      expectedLocalOffset = dataOffset + entry.compressedSize + descriptorLength;
      const nextOffset =
        index + 1 < physicalEntries.length
          ? physicalEntries[index + 1].localOffset
          : centralOffset;
      if (expectedLocalOffset !== nextOffset) {
        fail(category, `${label} ZIP data region contains trailing or ambiguous bytes`);
      }
    }
    return {
      entryCount,
      totalUncompressedBytes: totalActual,
      entries,
    };
  } finally {
    closeSync(descriptor);
  }
}

function ensureVerifiedExtractionDirectory(root, relativeDirectory) {
  let current = root;
  for (const segment of relativeDirectory.split("/").filter(Boolean)) {
    current = join(current, segment);
    if (!pathPresent(current)) mkdirSync(current, { mode: 0o700 });
    requireExactPrivateMode(current, "verified ZIP extraction directory", "directory", 0o700);
  }
  return current;
}

function extractedZipTree(directory) {
  const entries = [];
  const visit = (current, prefix = "") => {
    for (const item of readdirSync(current, { withFileTypes: true })) {
      const relativeName = prefix === "" ? item.name : `${prefix}/${item.name}`;
      const target = join(current, item.name);
      if (item.isDirectory()) {
        requireExactPrivateMode(target, "verified ZIP output directory", "directory", 0o700);
        entries.push(`${relativeName}/`);
        visit(target, relativeName);
      } else if (item.isFile()) {
        requireExactPrivateMode(target, "verified ZIP output file", "file", 0o600);
        entries.push(relativeName);
      } else {
        fail("artifact-integrity", "the verified ZIP output contains a special entry");
      }
    }
  };
  visit(directory);
  return sorted(entries);
}

function extractVerifiedZip(
  recorder,
  archive,
  directory,
  { label, category, profile = "strict-package" },
) {
  void recorder;
  requireEmptyDirectory(directory, `${label} extraction directory`);
  const inspected = inspectZipCentralDirectory(archive, { label, category, profile });
  const descriptor = openSync(archive, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW);
  try {
    for (const entry of inspected.entries) {
      const normalizedName = entry.name.replace(/\/$/u, "");
      if (entry.directory) {
        ensureVerifiedExtractionDirectory(directory, normalizedName);
        continue;
      }
      const parentRelative = normalizedName.includes("/")
        ? normalizedName.slice(0, normalizedName.lastIndexOf("/"))
        : "";
      const parent = ensureVerifiedExtractionDirectory(directory, parentRelative);
      const compressed = readDescriptorExactly(
        descriptor,
        entry.compressedSize,
        entry.dataOffset,
        category,
        label,
      );
      const output = inflateVerifiedZipPayload(compressed, entry, category, label);
      if (sha256Buffer(output) !== entry.payloadSha256) {
        fail(category, `${label} ZIP payload changed between verification and extraction`);
      }
      writeExclusivePrivateBytes(join(parent, basename(normalizedName)), output, category);
    }
  } finally {
    closeSync(descriptor);
  }
  const expectedTree = new Set();
  for (const entry of inspected.entries) {
    const normalizedName = entry.name.replace(/\/$/u, "");
    const segments = normalizedName.split("/");
    for (let index = 1; index < segments.length; index += 1) {
      expectedTree.add(`${segments.slice(0, index).join("/")}/`);
    }
    expectedTree.add(entry.directory ? `${normalizedName}/` : normalizedName);
    if (!entry.directory) {
      const target = join(directory, ...segments);
      if (
        statSync(target).size !== entry.uncompressedSize ||
        sha256FileSync(target) !== entry.payloadSha256
      ) {
        fail(category, `${label} ZIP extracted payload does not match its verified plan`);
      }
    }
  }
  if (!sameStrings(extractedZipTree(directory), [...expectedTree])) {
    fail(category, `${label} ZIP extracted tree differs from its verified plan`);
  }
  syncEntry(directory);
  return {
    entryCount: inspected.entryCount,
    totalUncompressedBytes: inspected.totalUncompressedBytes,
  };
}

function hardenPrivateTree(directory) {
  requireCanonicalOwnedEntry(directory, "private extracted directory", "directory");
  chmodSync(directory, 0o700);
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = join(directory, entry.name);
    const info = lstatSync(target);
    if (info.isSymbolicLink() || info.uid !== currentUid()) {
      fail("private-evidence", "an extracted private entry is not owner-controlled");
    }
    if (entry.isDirectory()) {
      hardenPrivateTree(target);
    } else if (entry.isFile() && info.nlink === 1) {
      chmodSync(target, 0o600);
    } else {
      fail("private-evidence", "an extracted private entry is special or multiply linked");
    }
  }
}

function tarString(buffer, start, length, category, label) {
  const field = buffer.subarray(start, start + length);
  const zero = field.indexOf(0);
  const value = field.subarray(0, zero < 0 ? field.length : zero).toString("utf8");
  if (value.includes("\uFFFD")) fail(category, `${label} tar contains invalid UTF-8 metadata`);
  return value;
}

function tarOctal(buffer, start, length, category, label) {
  const value = tarString(buffer, start, length, category, label).trim();
  if (!/^[0-7]+$/u.test(value)) fail(category, `${label} tar contains an invalid numeric field`);
  const number = Number.parseInt(value, 8);
  if (!Number.isSafeInteger(number) || number < 0) {
    fail(category, `${label} tar contains an unsafe numeric field`);
  }
  return number;
}

function inspectTarGzip(archive, { label, category, requiredPrefix }) {
  requireCanonicalOwnedEntry(archive, `${label} tarball`, "file");
  const compressedSize = statSync(archive).size;
  if (compressedSize <= 0 || compressedSize > MAX_NPM_TARBALL_BYTES) {
    fail(category, `${label} tarball has an invalid compressed size`);
  }
  let tar;
  try {
    tar = gunzipSync(readFileSync(archive), {
      maxOutputLength: MAX_NPM_TAR_UNCOMPRESSED_BYTES,
    });
  } catch {
    fail(category, `${label} tarball could not be decompressed within its size limit`);
  }
  if (
    tar.length === 0 ||
    tar.length > MAX_NPM_TAR_UNCOMPRESSED_BYTES ||
    tar.length / compressedSize > MAX_ZIP_COMPRESSION_RATIO
  ) {
    fail(category, `${label} tarball exceeds its uncompressed size or ratio limit`);
  }
  const names = new Set();
  const foldedNames = new Set();
  let offset = 0;
  let entryCount = 0;
  let totalFileBytes = 0;
  let terminated = false;
  while (offset + 512 <= tar.length) {
    const header = tar.subarray(offset, offset + 512);
    if (header.every((byte) => byte === 0)) {
      if (!tar.subarray(offset).every((byte) => byte === 0)) {
        fail(category, `${label} tarball contains data after its end marker`);
      }
      terminated = true;
      break;
    }
    const expectedChecksum = tarOctal(header, 148, 8, category, label);
    const checksumHeader = Buffer.from(header);
    checksumHeader.fill(0x20, 148, 156);
    const actualChecksum = checksumHeader.reduce((sum, byte) => sum + byte, 0);
    if (expectedChecksum !== actualChecksum) {
      fail(category, `${label} tarball header checksum is invalid`);
    }
    const name = tarString(header, 0, 100, category, label);
    const prefix = tarString(header, 345, 155, category, label);
    const fullName = prefix.length > 0 ? `${prefix}/${name}` : name;
    const type = String.fromCharCode(header[156] || 0x30);
    const size = tarOctal(header, 124, 12, category, label);
    if (!new Set(["0", "5"]).has(type) || size > MAX_NPM_TAR_UNCOMPRESSED_BYTES) {
      fail(category, `${label} tarball contains a link, special entry, or oversized member`);
    }
    if (type === "5" && size !== 0) {
      fail(category, `${label} tarball directory has a nonzero body`);
    }
    assertSafeArchiveEntry(fullName, label, { requiredPrefix });
    const folded = fullName.normalize("NFC").toLowerCase();
    if (names.has(fullName) || foldedNames.has(folded)) {
      fail(category, `${label} tarball contains a duplicate or case-colliding member`);
    }
    names.add(fullName);
    foldedNames.add(folded);
    const bodyStart = offset + 512;
    const paddedSize = Math.ceil(size / 512) * 512;
    if (bodyStart + paddedSize > tar.length) {
      fail(category, `${label} tarball member exceeds the container boundary`);
    }
    totalFileBytes += size;
    if (totalFileBytes > MAX_NPM_TAR_UNCOMPRESSED_BYTES) {
      fail(category, `${label} tarball exceeds the aggregate file-size limit`);
    }
    entryCount += 1;
    if (entryCount > MAX_ARCHIVE_ENTRIES) {
      fail(category, `${label} tarball exceeds the entry-count limit`);
    }
    offset = bodyStart + paddedSize;
  }
  if (!terminated || entryCount === 0) {
    fail(category, `${label} tarball has no exact end marker or regular member`);
  }
  return { entryCount, totalFileBytes };
}

function extractVerifiedTarGzip(
  recorder,
  archive,
  directory,
  { label, category, requiredPrefix },
) {
  requireEmptyDirectory(directory, `${label} extraction directory`);
  const inspected = inspectTarGzip(archive, { label, category, requiredPrefix });
  recorder.run(
    `Extract ${label} into a fresh private directory`,
    "/usr/bin/tar",
    ["-xzf", archive, "-C", directory],
    { category, failureMessage: `${label} tarball could not be extracted safely` },
  );
  hardenPrivateTree(directory);
  walkFiles(directory);
  return inspected;
}

function readChecksumInventory(pluginRoot, category, label) {
  const checksumPath = join(pluginRoot, "checksums.sha256");
  requireCanonicalOwnedEntry(checksumPath, `${label} checksum inventory`, "file");
  const declared = new Map();
  for (const line of readFileSync(checksumPath, "utf8").split(/\r?\n/u).filter(Boolean)) {
    const match = line.match(/^([a-fA-F0-9]{64})\s+[*]?(.+)$/u);
    const item = match?.[2]?.trim();
    if (!match || !safeInventoryPath(item) || item === "checksums.sha256" || declared.has(item)) {
      fail(category, `${label} checksum inventory is unsafe or ambiguous`);
    }
    declared.set(item, match[1].toLowerCase());
  }
  if (declared.size === 0) fail(category, `${label} checksum inventory is empty`);
  return { checksumPath, declared };
}

export async function verifyChecksumInventory(
  pluginRoot,
  category,
  label,
  { allowedExtra = () => false } = {},
) {
  const { checksumPath, declared } = readChecksumInventory(pluginRoot, category, label);
  const actual = walkFiles(pluginRoot)
    .map((target) => relative(pluginRoot, target).split(sep).join("/"))
    .filter((item) => item !== "checksums.sha256" && !allowedExtra(item));
  if (!sameStrings(actual, [...declared.keys()])) {
    fail(category, `${label} payload differs from its checksum inventory`);
  }
  for (const [item, expected] of declared) {
    if ((await sha256File(join(pluginRoot, ...item.split("/")))) !== expected) {
      fail(category, `${label} payload failed checksum verification`);
    }
  }
  return {
    checksumPath,
    declared,
    checksumInventorySha256: await sha256File(checksumPath),
  };
}

function deepJsonEqual(left, right) {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) &&
      Array.isArray(right) &&
      left.length === right.length &&
      left.every((item, index) => deepJsonEqual(item, right[index]));
  }
  if (
    left === null ||
    right === null ||
    typeof left !== "object" ||
    typeof right !== "object"
  ) {
    return false;
  }
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return leftKeys.length === rightKeys.length &&
    leftKeys.every(
      (key, index) => key === rightKeys[index] && deepJsonEqual(left[key], right[key]),
    );
}

function expectedManagedMarketplace(host) {
  if (host === "claude") {
    return {
      name: "opensocrates",
      owner: { name: "Parker Hwang" },
      metadata: {
        description: "OpenSocrates reasoning support for Claude Code and Cowork",
        version: PRODUCT_VERSION,
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
  }
  return {
    name: "opensocrates",
    interface: { displayName: "OpenSocrates" },
    plugins: [
      {
        name: "opensocrates",
        source: { source: "local", path: "./build/generated/plugins/codex" },
        policy: { installation: "AVAILABLE", authentication: "ON_INSTALL" },
        category: "Productivity",
      },
    ],
  };
}

function validatePayloadIdentity(host, pluginRoot, expectedVersion, category, label) {
  const releasePath = join(pluginRoot, "release-manifest.json");
  const manifestPath = join(
    pluginRoot,
    ...(host === "claude"
      ? [".claude-plugin", "plugin.json"]
      : [".codex-plugin", "plugin.json"]),
  );
  requireCanonicalOwnedEntry(releasePath, `${label} release manifest`, "file");
  requireCanonicalOwnedEntry(manifestPath, `${label} plugin manifest`, "file");
  const release = parseJson(
    readFileSync(releasePath, "utf8"),
    category,
    `${label} release manifest is invalid`,
  );
  const manifest = parseJson(
    readFileSync(manifestPath, "utf8"),
    category,
    `${label} plugin manifest is invalid`,
  );
  if (
    release?.schema !== "opensocrates.plugin-release-manifest/1.0.0" ||
    release?.host !== host ||
    release?.product_version !== expectedVersion ||
    !Number.isSafeInteger(release?.content_revision) ||
    release.content_revision < 1 ||
    manifest?.name !== "opensocrates" ||
    manifest?.version !== expectedVersion
  ) {
    fail(category, `${label} identity does not match its canonical host and version`);
  }
}

async function verifyManagedRootExact(
  host,
  managedRoot,
  pluginRoot,
  { category = "baseline" } = {},
) {
  requireCanonicalOwnedEntry(managedRoot, `${host} managed root`, "directory");
  const markerPath = join(managedRoot, ".opensocrates-managed.json");
  requireCanonicalOwnedEntry(markerPath, `${host} ownership marker`, "file");
  const marker = parseJson(
    readFileSync(markerPath, "utf8"),
    category,
    `${host} ownership marker is invalid`,
  );
  if (!markerMatches(marker, host)) {
    fail(category, `${host} ownership marker does not match the exact installer contract`);
  }
  validatePayloadIdentity(host, pluginRoot, PRODUCT_VERSION, category, `${host} installed payload`);
  const verified = await verifyChecksumInventory(
    pluginRoot,
    category,
    `${host} installed payload`,
  );
  const marketplaceRelative = host === "claude"
    ? ".claude-plugin/marketplace.json"
    : ".agents/plugins/marketplace.json";
  const marketplacePath = join(managedRoot, ...marketplaceRelative.split("/"));
  requireCanonicalOwnedEntry(marketplacePath, `${host} managed marketplace`, "file");
  const marketplace = parseJson(
    readFileSync(marketplacePath, "utf8"),
    category,
    `${host} managed marketplace is invalid`,
  );
  if (!deepJsonEqual(marketplace, expectedManagedMarketplace(host))) {
    fail(category, `${host} managed marketplace differs from the exact installer contract`);
  }
  const pluginRelative = relative(managedRoot, pluginRoot).split(sep).join("/");
  const allowed = new Set([
    ".opensocrates-managed.json",
    marketplaceRelative,
    `${pluginRelative}/checksums.sha256`,
    ...[...verified.declared.keys()].map((item) => `${pluginRelative}/${item}`),
  ]);
  const actual = walkFiles(managedRoot).map((target) =>
    relative(managedRoot, target).split(sep).join("/"));
  if (!sameStrings(actual, [...allowed])) {
    fail(category, `${host} managed root contains an undeclared or missing file`);
  }
}

async function verifyCachePayloadsForBaseline(host, cacheRoot) {
  if (cacheRoot === null || !pathPresent(cacheRoot)) return;
  requireCanonicalOwnedEntry(cacheRoot, `${host} OpenSocrates cache`, "directory");
  for (const entry of readdirSync(cacheRoot, { withFileTypes: true })) {
    if (entry.isSymbolicLink() || !entry.isDirectory()) {
      fail("baseline", `${host} OpenSocrates cache contains an unrecognized entry`);
    }
    const versionRoot = join(cacheRoot, entry.name);
    requireCanonicalOwnedEntry(versionRoot, `${host} cached payload`, "directory");
    validatePayloadIdentity(host, versionRoot, entry.name, "baseline", `${host} cached payload`);
    await verifyChecksumInventory(versionRoot, "baseline", `${host} cached payload`, {
      allowedExtra: (item) => item === ".orphaned_at" || item.startsWith(".in_use/"),
    });
  }
}

function inspectMachOArchitecture(recorder, label, executable) {
  const completed = recorder.run(
    `Inspect ${label} Mach-O architecture`,
    "/usr/bin/lipo",
    ["-archs", executable],
    { category: "architecture", failureMessage: `${label} is not a valid native arm64 Mach-O` },
  );
  const architectures = completed.stdout.split(/\s+/u).filter(Boolean);
  if (!sameStrings(architectures, ["arm64"])) {
    fail("architecture", `${label} is not an arm64-only native runtime`, completed.id);
  }
  return { architectures };
}

function validateNpmPackMetadata(item) {
  if (
    item?.name !== "opensocrates" ||
    item?.version !== PRODUCT_VERSION ||
    item?.entryCount !== NPM_PACKAGE_FILES.length ||
    !Array.isArray(item?.files) ||
    !sameStrings(item.files.map((entry) => entry?.path), NPM_PACKAGE_FILES) ||
    item.files.some(
      (entry) =>
        !Number.isSafeInteger(entry?.size) ||
        entry.size < 0 ||
        entry.mode !== (entry.path === "installer/opensocrates.mjs" ? 0o755 : 0o644),
    ) ||
    !Array.isArray(item?.bundled) ||
    item.bundled.length !== 0
  ) {
    fail("npm-package", "npm pack metadata does not match the exact eight-file package contract");
  }
}

function validateNpmPackageManifest(manifest) {
  if (
    manifest === null ||
    typeof manifest !== "object" ||
    Array.isArray(manifest) ||
    manifest?.name !== "opensocrates" ||
    manifest?.version !== PRODUCT_VERSION ||
    JSON.stringify(manifest?.bin) !==
      JSON.stringify({ opensocrates: "installer/opensocrates.mjs" }) ||
    !sameStrings(manifest?.files ?? [], NPM_PACKAGE_FILES_FIELD) ||
    JSON.stringify(manifest?.scripts) !== JSON.stringify(NPM_PACKAGE_SCRIPTS) ||
    JSON.stringify(manifest?.engines) !== JSON.stringify({ node: ">=20" })
  ) {
    fail("npm-package", "the npm manifest differs from the closed publishing contract");
  }
  return manifest;
}

function packSourceNpmCandidate(recorder, execution, sourceRoot, packageDirectory) {
  requireCanonicalOwnedEntry(sourceRoot, "npm source root", "directory");
  requireCanonicalOwnedEntry(packageDirectory, "npm package destination", "directory");
  const sourceManifestPath = join(sourceRoot, "package.json");
  requireCanonicalOwnedEntry(sourceManifestPath, "source npm package manifest", "file");
  const sourceManifest = parseJson(
    readFileSync(sourceManifestPath, "utf8"),
    "npm-package",
    "the source npm package manifest is invalid",
  );
  validateNpmPackageManifest(sourceManifest);
  return commandJson(
    recorder,
    "Pack exact candidate npm tarball",
    execution.npmBinary,
    [
      "pack",
      sourceRoot,
      "--silent",
      "--json",
      "--ignore-scripts",
      "--pack-destination",
      packageDirectory,
    ],
    npxRunOptions({ execution }, { timeout: 180_000 }),
    "npm-package",
    "the candidate could not be packed as an npm package",
  );
}

async function inspectPackedNpmCandidate(
  recorder,
  packageArchive,
  packageDirectory,
  packMetadata,
) {
  validateNpmPackMetadata(packMetadata);
  const extraction = join(packageDirectory, "extracted");
  ensurePrivateDirectory(extraction);
  extractVerifiedTarGzip(recorder, packageArchive, extraction, {
    label: "packed npm tarball",
    category: "npm-package",
    requiredPrefix: "package",
  });
  const packageRoot = join(extraction, "package");
  requireCanonicalOwnedEntry(packageRoot, "packed npm package root", "directory");
  const extractedFiles = walkFiles(packageRoot);
  const extractedRelative = extractedFiles.map((target) =>
    relative(packageRoot, target).split(sep).join("/"),
  );
  if (!sameStrings(extractedRelative, NPM_PACKAGE_FILES)) {
    fail("npm-package", "the packed npm archive contains an extra or missing regular file");
  }
  const sourceFileHashes = {};
  for (const item of NPM_PACKAGE_FILES) {
    const packedPath = join(packageRoot, ...item.split("/"));
    const sourcePath = join(ROOT, ...item.split("/"));
    requireCanonicalOwnedEntry(packedPath, `packed npm file ${item}`, "file");
    requireCanonicalOwnedEntry(sourcePath, `source npm file ${item}`, "file");
    const packedHash = await sha256File(packedPath);
    const sourceHash = await sha256File(sourcePath);
    if (packedHash !== sourceHash) {
      fail("npm-package", `the packed npm file ${item} differs from the exact source commit`);
    }
    sourceFileHashes[item] = sourceHash;
  }
  const packageManifestPath = join(packageRoot, "package.json");
  const installerPath = join(packageRoot, "installer", "opensocrates.mjs");
  requireCanonicalOwnedEntry(packageManifestPath, "packed npm package manifest", "file");
  requireCanonicalOwnedEntry(installerPath, "packed npm executable", "file");
  const manifest = parseJson(
    readFileSync(packageManifestPath, "utf8"),
    "npm-package",
    "the packed npm package manifest is invalid",
  );
  validateNpmPackageManifest(manifest);
  const packedInstallerSha256 = await sha256File(installerPath);
  if (packedInstallerSha256 !== (await sha256File(join(ROOT, "installer", "opensocrates.mjs")))) {
    fail("npm-package", "the packed npm executable differs from the clean source commit");
  }
  return {
    manifestSha256: await sha256File(packageManifestPath),
    installerSha256: packedInstallerSha256,
    bin: "opensocrates=installer/opensocrates.mjs",
    entryCount: NPM_PACKAGE_FILES.length,
    files: [...NPM_PACKAGE_FILES],
    sourceFileHashes,
    bundledCount: 0,
  };
}

async function extractHostPayloadReceipt(recorder, privateDirectory, host, asset) {
  const extractionRoot = join(privateDirectory, "candidate", "payloads", host);
  ensurePrivateDirectory(dirname(extractionRoot));
  ensurePrivateDirectory(extractionRoot);
  extractVerifiedZip(recorder, asset.archivePath, extractionRoot, {
    label: `${host} exact CI archive`,
    category: "artifact-integrity",
  });
  const releasePath = findSingleFile(
    extractionRoot,
    "release-manifest.json",
    "artifact-integrity",
  );
  const pluginRoot = dirname(releasePath);
  requireCanonicalOwnedEntry(pluginRoot, `${host} extracted plugin root`, "directory");
  const outsideFiles = walkFiles(extractionRoot).filter((target) => {
    const local = relative(pluginRoot, target);
    return local === ".." || local.startsWith(`..${sep}`);
  });
  if (outsideFiles.length > 0) {
    fail("artifact-integrity", `${host} CI archive contains files outside its plugin root`);
  }
  const release = parseJson(
    readFileSync(releasePath, "utf8"),
    "artifact-integrity",
    `${host} extracted release manifest is invalid`,
  );
  if (
    release?.schema !== "opensocrates.plugin-release-manifest/1.0.0" ||
    release?.host !== host ||
    release?.product_version !== PRODUCT_VERSION ||
    !sameStrings(release?.release_targets ?? [], ["darwin-arm64"]) ||
    !sameStrings(release?.runtime_targets ?? [], ["darwin-arm64"])
  ) {
    fail("artifact-integrity", `${host} extracted payload has the wrong identity or target`);
  }
  const verified = await verifyChecksumInventory(
    pluginRoot,
    "artifact-integrity",
    `${host} extracted CI payload`,
  );
  const runtimeRelative = "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime";
  const runtimePath = join(pluginRoot, ...runtimeRelative.split("/"));
  requireCanonicalOwnedEntry(runtimePath, `${host} extracted native runtime`, "file");
  const architecture = inspectMachOArchitecture(recorder, `${host} candidate runtime`, runtimePath);
  const allPayloadFiles = walkFiles(pluginRoot);
  if (
    asset.aggregatePackageFileCount !== allPayloadFiles.length ||
    asset.aggregatePackageChecksumFile !== `${host}/checksums.sha256`
  ) {
    fail(
      "artifact-integrity",
      `${host} aggregate package count or checksum-file identity does not match the extracted payload`,
    );
  }
  const runtimeSha256 = await sha256File(runtimePath);
  const receipt = {
    schema: "opensocrates.reinstall-payload-receipt/1.0.0",
    host,
    productVersion: PRODUCT_VERSION,
    archiveSha256: asset.sha256,
    releaseManifestSha256: await sha256File(releasePath),
    checksumInventorySha256: verified.checksumInventorySha256,
    fileCount: verified.declared.size,
    files: Object.fromEntries([...verified.declared].sort(([left], [right]) => left.localeCompare(right))),
    runtimeRelative,
    runtimeSha256,
    architectures: architecture.architectures,
    aggregatePackageFileCount: asset.aggregatePackageFileCount,
    aggregatePackageChecksumFile: asset.aggregatePackageChecksumFile,
  };
  const receiptPath = join(privateDirectory, "candidate", `${host}-payload-receipt.json`);
  writePrivate(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  return {
    payloadReceiptPath: receiptPath,
    payloadReceiptSha256: await sha256File(receiptPath),
    payloadFileCount: receipt.fileCount,
    checksumInventorySha256: receipt.checksumInventorySha256,
    releaseManifestSha256: receipt.releaseManifestSha256,
    runtimeSha256: receipt.runtimeSha256,
    runtimeArchitecture: "arm64",
  };
}

function validateCiRunMetadata(metadata, runId, sourceCommit) {
  if (
    metadata?.id !== runId ||
    metadata?.head_sha !== sourceCommit ||
    metadata?.status !== "completed" ||
    metadata?.conclusion !== "success" ||
    metadata?.path !== ".github/workflows/ci.yml" ||
    metadata?.repository?.full_name !== REPOSITORY ||
    !Number.isSafeInteger(metadata?.run_attempt) ||
    metadata.run_attempt < 1 ||
    !Number.isSafeInteger(metadata?.workflow_id)
  ) {
    fail("ci-not-ready", "the CI run metadata does not pin the exact repository, workflow, and commit");
  }
}

function nativeArtifactName(runId, runAttempt) {
  if (
    !Number.isSafeInteger(runId) ||
    runId <= 0 ||
    !Number.isSafeInteger(runAttempt) ||
    runAttempt <= 0
  ) {
    fail("ci-artifact", "the Native package artifact run identity is invalid");
  }
  return `package-darwin-arm64-${runId}-${runAttempt}`;
}

function validateArtifactMetadata(metadata, { artifactName, runId, runAttempt, sourceCommit }) {
  const digest = String(metadata?.digest ?? "");
  const expectedArtifactName = nativeArtifactName(runId, runAttempt);
  if (
    !Number.isSafeInteger(metadata?.id) ||
    metadata.id <= 0 ||
    artifactName !== expectedArtifactName ||
    metadata?.name !== expectedArtifactName ||
    metadata?.expired !== false ||
    !/^sha256:[a-f0-9]{64}$/u.test(digest) ||
    !Number.isSafeInteger(metadata?.size_in_bytes) ||
    metadata.size_in_bytes <= 0 ||
    metadata.size_in_bytes > MAX_ARTIFACT_BYTES ||
    metadata?.workflow_run?.id !== runId ||
    metadata?.workflow_run?.head_sha !== sourceCommit
  ) {
    fail(
      "ci-artifact",
      "the exact Native package artifact does not pin its immutable ID, digest, size, workflow run, and full head SHA",
    );
  }
  return {
    id: metadata.id,
    name: metadata.name,
    digest,
    sizeBytes: metadata.size_in_bytes,
    workflowRunId: metadata.workflow_run.id,
    workflowRunHeadSha: metadata.workflow_run.head_sha,
  };
}

function validateBuildSourceReceipt(receipt, { sourceCommit, sourceTree }) {
  if (
    receipt === null ||
    typeof receipt !== "object" ||
    Array.isArray(receipt) ||
    Object.getPrototypeOf(receipt) !== Object.prototype ||
    !sameStrings(Object.keys(receipt), ["schema", "repository", "commit", "tree"]) ||
    receipt.schema !== "opensocrates.package-source-provenance/1.0.0" ||
    receipt.repository !== REPOSITORY ||
    !/^[a-f0-9]{40}$/u.test(receipt.commit ?? "") ||
    !/^[a-f0-9]{40}$/u.test(receipt.tree ?? "") ||
    receipt.commit !== sourceCommit ||
    receipt.tree !== sourceTree
  ) {
    fail("ci-artifact", "the package build source receipt does not match the exact local commit and tree");
  }
  return { headSha: receipt.commit, treeSha: receipt.tree };
}

function artifactDownloadTimeoutMs(sizeBytes) {
  if (
    !Number.isSafeInteger(sizeBytes) ||
    sizeBytes <= 0 ||
    sizeBytes > MAX_ARTIFACT_BYTES
  ) {
    fail("ci-artifact", "the immutable artifact download size is outside its bounded contract");
  }
  return Math.min(
    MAX_ARTIFACT_DOWNLOAD_TIMEOUT_MS,
    ARTIFACT_DOWNLOAD_OVERHEAD_MS +
      Math.ceil((sizeBytes * 1_000) / ARTIFACT_DOWNLOAD_MIN_BYTES_PER_SECOND),
  );
}

async function downloadImmutableArtifact(
  recorder,
  ghBinary,
  artifactId,
  target,
  sizeBytes,
) {
  return recorder.runToFile(
    "Download immutable Native package artifact by exact artifact ID",
    ghBinary,
    ["api", `repos/${REPOSITORY}/actions/artifacts/${artifactId}/zip`],
    target,
    {
      category: "ci-artifact",
      failureMessage: "the immutable Native package artifact ZIP could not be downloaded",
      timeout: artifactDownloadTimeoutMs(sizeBytes),
    },
  );
}

async function prepareCandidate(recorder, report, privateDirectory) {
  const execution = await pinExecutionIdentity(
    recorder,
    prepareIsolatedNpx(privateDirectory),
  );
  verifyLifecycleHostAuthentication(recorder, execution);
  const ghBinary = resolveExecutable("gh");
  const runs = commandJson(
    recorder,
    "List CI runs for the exact candidate commit",
    "gh",
    [
      "run",
      "list",
      "--repo",
      REPOSITORY,
      "--workflow",
      "ci.yml",
      "--commit",
      report.source.commit,
      "--limit",
      "20",
      "--json",
      "databaseId,headSha,conclusion,event,createdAt,url",
    ],
    {},
    "ci-not-ready",
    "GitHub Actions runs could not be listed",
  );
  if (!Array.isArray(runs)) {
    fail("ci-not-ready", "GitHub returned an unexpected workflow-run schema");
  }
  const run = runs.find(
    (candidate) =>
      candidate?.headSha === report.source.commit && candidate?.conclusion === "success",
  );
  if (!run) fail("ci-not-ready", "no successful CI run exists yet for this exact commit");
  const runId = Number(run.databaseId);
  if (!Number.isSafeInteger(runId) || runId <= 0) {
    fail("ci-not-ready", "the successful CI run has an invalid identifier");
  }
  const runMetadata = commandJson(
    recorder,
    "Pin exact successful CI run metadata",
    "gh",
    ["api", `repos/${REPOSITORY}/actions/runs/${runId}`],
    {},
    "ci-not-ready",
    "the exact CI run metadata could not be read",
  );
  validateCiRunMetadata(runMetadata, runId, report.source.commit);
  const artifactName = nativeArtifactName(runId, runMetadata.run_attempt);
  const artifactPage = commandJson(
    recorder,
    "Pin exact Native CI artifact metadata",
    "gh",
    ["api", `repos/${REPOSITORY}/actions/runs/${runId}/artifacts?per_page=100`],
    {},
    "ci-artifact",
    "the exact CI artifact metadata could not be read",
  );
  const artifactMatches = Array.isArray(artifactPage?.artifacts)
    ? artifactPage.artifacts.filter((artifact) => artifact?.name === artifactName)
    : [];
  if (artifactMatches.length !== 1) {
    fail("ci-artifact", "the successful CI run does not contain one exact Native package artifact");
  }
  const artifactMetadata = artifactMatches[0];
  const pinnedArtifact = validateArtifactMetadata(artifactMetadata, {
    artifactName,
    runId,
    runAttempt: runMetadata.run_attempt,
    sourceCommit: report.source.commit,
  });
  const candidateDirectory = join(privateDirectory, "candidate");
  const artifactDirectory = join(candidateDirectory, "artifact");
  const packageDirectory = join(candidateDirectory, "npm");
  ensurePrivateDirectory(candidateDirectory);
  ensurePrivateDirectory(artifactDirectory);
  ensurePrivateDirectory(packageDirectory);
  requireEmptyDirectory(artifactDirectory, "Native artifact extraction directory");
  const rawArtifactPath = join(
    candidateDirectory,
    `native-artifact-${pinnedArtifact.id}.zip`,
  );
  const downloaded = await downloadImmutableArtifact(
    recorder,
    ghBinary,
    pinnedArtifact.id,
    rawArtifactPath,
    pinnedArtifact.sizeBytes,
  );
  if (
    downloaded.outputSizeBytes !== pinnedArtifact.sizeBytes ||
    `sha256:${downloaded.outputSha256}` !== pinnedArtifact.digest
  ) {
    fail("ci-artifact", "the raw artifact ZIP bytes do not match the immutable GitHub digest and size");
  }
  extractVerifiedZip(recorder, rawArtifactPath, artifactDirectory, {
    label: "immutable artifact container",
    category: "ci-artifact",
    profile: "github-artifact-container",
  });
  const postArtifactMetadata = commandJson(
    recorder,
    "Reconfirm immutable Native artifact metadata after download",
    ghBinary,
    ["api", `repos/${REPOSITORY}/actions/artifacts/${pinnedArtifact.id}`],
    {},
    "ci-artifact",
    "the immutable Native artifact metadata could not be reconfirmed",
  );
  const postPinnedArtifact = validateArtifactMetadata(postArtifactMetadata, {
    artifactName,
    runId,
    runAttempt: runMetadata.run_attempt,
    sourceCommit: report.source.commit,
  });
  const postRunMetadata = commandJson(
    recorder,
    "Reconfirm exact CI run attempt after artifact download",
    ghBinary,
    ["api", `repos/${REPOSITORY}/actions/runs/${runId}`],
    {},
    "ci-not-ready",
    "the exact CI run attempt could not be reconfirmed",
  );
  validateCiRunMetadata(postRunMetadata, runId, report.source.commit);
  if (
    JSON.stringify(postPinnedArtifact) !== JSON.stringify(pinnedArtifact) ||
    postRunMetadata.run_attempt !== runMetadata.run_attempt ||
    postRunMetadata.workflow_id !== runMetadata.workflow_id
  ) {
    fail("ci-artifact", "the artifact or workflow-run attempt changed across the download boundary");
  }
  const buildSourceReceiptPath = findSingleFile(
    artifactDirectory,
    "package-source-provenance.json",
    "ci-artifact",
  );
  const buildSourceReceipt = parseJson(
    readFileSync(buildSourceReceiptPath, "utf8"),
    "ci-artifact",
    "the package build source receipt is invalid JSON",
  );
  const verifiedBuildSource = validateBuildSourceReceipt(buildSourceReceipt, {
    sourceCommit: report.source.commit,
    sourceTree: report.source.tree,
  });
  const buildSourceReceiptSha256 = await sha256File(buildSourceReceiptPath);
  report.source.ciRunId = runId;
  report.source.ciRunUrl = exactString(run.url, "ci-artifact", "the CI run URL is missing");
  report.source.ci = {
    repository: REPOSITORY,
    workflowPath: ".github/workflows/ci.yml",
    workflowId: runMetadata.workflow_id,
    runId,
    runAttempt: runMetadata.run_attempt,
    conclusion: "success",
    headSha: report.source.commit,
    buildSource: {
      ...verifiedBuildSource,
      receiptSha256: buildSourceReceiptSha256,
    },
    artifact: {
      id: artifactMetadata.id,
      name: artifactName,
      digest: pinnedArtifact.digest,
      sizeBytes: pinnedArtifact.sizeBytes,
      rawContainerSha256: downloaded.outputSha256,
      workflowRunId: pinnedArtifact.workflowRunId,
      workflowRunHeadSha: pinnedArtifact.workflowRunHeadSha,
      target: "darwin-arm64",
    },
  };
  const manifestName = `opensocrates-${PRODUCT_VERSION}-release-manifest.json`;
  const manifestPath = findSingleFile(artifactDirectory, manifestName, "artifact-integrity");
  const manifest = parseJson(
    readFileSync(manifestPath, "utf8"),
    "artifact-integrity",
    "the combined release manifest is invalid JSON",
  );
  if (
    manifest?.schema !== "opensocrates.release-manifest/1.0.0" ||
    manifest?.product_version !== PRODUCT_VERSION
  ) {
    fail("artifact-integrity", "the combined release manifest has the wrong schema or version");
  }
  const assets = {};
  for (const host of HOSTS) {
    const expectedName = `opensocrates-${PRODUCT_VERSION}-${host}-plugin.zip`;
    const hostManifest = manifest.hosts?.[host];
    if (
      hostManifest?.archive !== expectedName ||
      hostManifest?.package_tree !== host ||
      !Number.isSafeInteger(hostManifest?.package_file_count) ||
      hostManifest.package_file_count <= 0 ||
      hostManifest?.package_checksum_file !== `${host}/checksums.sha256`
    ) {
      fail("artifact-integrity", `${host} has an unexpected archive name in the manifest`);
    }
    if (!sameStrings(hostManifest?.release_targets ?? [], ["darwin-arm64"])) {
      fail("artifact-integrity", `${host} has the wrong native release target`);
    }
    const expectedHash = String(hostManifest.archive_sha256 ?? "").replace(/^sha256:/u, "");
    if (!/^[a-f0-9]{64}$/u.test(expectedHash)) {
      fail("artifact-integrity", `${host} has an invalid archive hash in the manifest`);
    }
    const archivePath = findSingleFile(artifactDirectory, expectedName, "artifact-integrity");
    const actualHash = await sha256File(archivePath);
    if (actualHash !== expectedHash) {
      fail("artifact-integrity", `${host} archive does not match the CI release manifest`);
    }
    const checksumPath = join(candidateDirectory, `${expectedName}.sha256`);
    writePrivate(checksumPath, `${expectedHash}  ${expectedName}\n`);
    assets[host] = {
      archivePath,
      checksumPath,
      checksumSha256: await sha256File(checksumPath),
      checksumProvenance: "locally_derived_from_verified_manifest",
      sha256: expectedHash,
      name: expectedName,
      aggregatePackageFileCount: hostManifest.package_file_count,
      aggregatePackageChecksumFile: hostManifest.package_checksum_file,
    };
  }
  const cleanBeforePack = recorder.run(
    "Reconfirm clean source immediately before npm pack",
    "git",
    ["status", "--porcelain", "--untracked-files=all"],
    { category: "source", failureMessage: "the source changed before npm pack" },
  );
  if (cleanBeforePack.stdout !== "") fail("source", "the source changed before npm pack");
  const metadata = packSourceNpmCandidate(
    recorder,
    execution,
    ROOT,
    packageDirectory,
  );
  const item = Array.isArray(metadata) ? metadata[0] : null;
  validateNpmPackMetadata(item);
  const packageArchive = join(
    packageDirectory,
    basename(exactString(item.filename, "npm-package", "npm pack returned no archive filename")),
  );
  requireCanonicalOwnedEntry(packageArchive, "candidate npm tarball", "file");
  assertPathBelow(candidateDirectory, packageArchive, "candidate npm tarball", "file");
  const packageSha256 = await sha256File(packageArchive);
  const npmIdentity = await inspectPackedNpmCandidate(
    recorder,
    packageArchive,
    packageDirectory,
    item,
  );
  report.source.npmPackage = {
    name: item.name,
    version: item.version,
    sha256: packageSha256,
    manifestSha256: npmIdentity.manifestSha256,
    installerSha256: npmIdentity.installerSha256,
    bin: npmIdentity.bin,
    entryCount: npmIdentity.entryCount,
    files: npmIdentity.files,
    sourceFileHashes: npmIdentity.sourceFileHashes,
    bundledCount: npmIdentity.bundledCount,
    execution: {
      nodeVersion: execution.nodeVersion,
      npmVersion: execution.npmVersion,
      npxVersion: execution.npxVersion,
      pythonVersion: execution.pythonVersion,
      npmBinarySha256: execution.npmBinarySha256,
      npxBinarySha256: execution.npxBinarySha256,
      nodeBinarySha256: execution.nodeBinarySha256,
      pythonBinarySha256: execution.pythonBinarySha256,
    },
  };
  const candidateForNpx = { packageArchive, execution };
  runPackedNpx(
    recorder,
    "Invoke packed candidate through real npx entrypoint",
    candidateForNpx,
    ["--yes", `--package=${packageArchive}`, "opensocrates", "help"],
    {
      category: "npm-package",
      failureMessage: "the packed OpenSocrates command could not start through npx",
      timeout: 180_000,
    },
  );
  runPackedNpx(
    recorder,
    "Verify exact candidate host archives through packed npx",
    candidateForNpx,
    [
      "--yes",
      `--package=${packageArchive}`,
      "opensocrates",
      "verify",
      "--host",
      "all",
      "--asset-claude",
      assets.claude.archivePath,
      "--checksum-claude",
      assets.claude.checksumPath,
      "--asset-codex",
      assets.codex.archivePath,
      "--checksum-codex",
      assets.codex.checksumPath,
    ],
    {
      category: "artifact-integrity",
      failureMessage: "the packed installer rejected an exact candidate host archive",
      timeout: 300_000,
    },
  );
  for (const host of HOSTS) {
    Object.assign(
      assets[host],
      await extractHostPayloadReceipt(recorder, privateDirectory, host, assets[host]),
    );
  }
  commitPublicAssetIdentities(report, assets);
  const candidate = {
    sourceCommit: report.source.commit,
    packageArchive,
    packageSha256,
    assets,
    execution,
    runId,
    manifestSha256: await sha256File(manifestPath),
    rawArtifactPath,
    rawArtifactSha256: downloaded.outputSha256,
    rawArtifactSizeBytes: downloaded.outputSizeBytes,
    buildSourceReceiptPath,
    buildSourceReceiptSha256,
    sourceTree: report.source.tree,
  };
  validateCandidatePaths(privateDirectory, candidate);
  return candidate;
}

function candidateCheckpoint(reportDirectory, report, candidate, exactBaselineBindings) {
  assertBaselineExactBindings(exactBaselineBindings);
  return {
    schema: CHECKPOINT_SCHEMA,
    testId: report.testId,
    phase: "ready-to-purge",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    reportDirectory,
    baseline: {
      kind: report.baseline.kind,
      initialState: report.baseline.initialState,
      initialInstalledHosts: [...report.baseline.installedHosts],
      perHostInstallState: Object.fromEntries(
        HOSTS.map((host) => [
          host,
          {
            installed: true,
            version: report.baseline.inventory.registrations[host].version,
          },
        ]),
      ),
      initialTopology: report.baseline.inventory.registrations,
      initialInventory: structuredClone(report.baseline.inventory),
      initialInventorySha256: sha256Buffer(JSON.stringify(report.baseline.inventory)),
      exactBindings: structuredClone(exactBaselineBindings),
      exactBindingsSha256: sha256Buffer(JSON.stringify(exactBaselineBindings)),
    },
    intendedFinalHosts: [...HOSTS],
    intendedFinalState: "installed",
    sourceCommit: report.source.commit,
    sourceTree: report.source.tree,
    ciRunId: report.source.ciRunId,
    packageArchive: candidate.packageArchive,
    packageSha256: candidate.packageSha256,
    manifestSha256: candidate.manifestSha256,
    rawArtifactPath: candidate.rawArtifactPath,
    rawArtifactSha256: candidate.rawArtifactSha256,
    rawArtifactSizeBytes: candidate.rawArtifactSizeBytes,
    buildSourceReceiptPath: candidate.buildSourceReceiptPath,
    buildSourceReceiptSha256: candidate.buildSourceReceiptSha256,
    ci: report.source.ci,
    npmIdentity: report.source.npmPackage,
    execution: candidate.execution,
    recovery: {
      hostCloseRetriesUsed: 0,
      reinstallRetriesUsed: 0,
      hostCloseRetryAdmission: null,
      reinstallRetryAdmission: null,
    },
    lastObservedState: {
      classification: "installed_baseline",
      installedHosts: [...HOSTS],
    },
    assets: Object.fromEntries(
      HOSTS.map((host) => [
        host,
        {
          archivePath: candidate.assets[host].archivePath,
          checksumPath: candidate.assets[host].checksumPath,
          checksumSha256: candidate.assets[host].checksumSha256,
          checksumProvenance: candidate.assets[host].checksumProvenance,
          sha256: candidate.assets[host].sha256,
          name: candidate.assets[host].name,
          aggregatePackageFileCount: candidate.assets[host].aggregatePackageFileCount,
          aggregatePackageChecksumFile: candidate.assets[host].aggregatePackageChecksumFile,
          payloadReceiptPath: candidate.assets[host].payloadReceiptPath,
          payloadReceiptSha256: candidate.assets[host].payloadReceiptSha256,
          payloadFileCount: candidate.assets[host].payloadFileCount,
          checksumInventorySha256: candidate.assets[host].checksumInventorySha256,
          releaseManifestSha256: candidate.assets[host].releaseManifestSha256,
          runtimeSha256: candidate.assets[host].runtimeSha256,
          runtimeArchitecture: candidate.assets[host].runtimeArchitecture,
        },
      ]),
    ),
  };
}

function writeCheckpoint(privateDirectory, checkpoint) {
  checkpoint.updatedAt = new Date().toISOString();
  atomicWritePrivate(
    join(privateDirectory, CHECKPOINT_NAME),
    `${JSON.stringify(checkpoint, null, 2)}\n`,
  );
}

function transitionCheckpoint(privateDirectory, checkpoint, phase, lastObservedState = null) {
  if (!CHECKPOINT_PHASES.has(phase)) fail("checkpoint", "an unsupported lifecycle phase was requested");
  checkpoint.phase = phase;
  if (lastObservedState !== null) checkpoint.lastObservedState = lastObservedState;
  writeCheckpoint(privateDirectory, checkpoint);
}

export function makeFinalVerificationSnapshot(report, finalState) {
  const value = {
    finalState,
    assertions: structuredClone(report.assertions),
    commands: structuredClone(report.commands),
    mutation: {
      purgeCommandAttempts: report.mutation.purgeCommandAttempts,
      trustResetAttempts: report.mutation.trustResetAttempts,
      reinstallAttempts: report.mutation.reinstallAttempts,
      hostCloseRetriesUsed: report.mutation.hostCloseRetriesUsed,
      reinstallAttempted: report.mutation.reinstallAttempted,
    },
    completedAt: report.completedAt ?? new Date().toISOString(),
  };
  return {
    value,
    sha256: sha256Buffer(JSON.stringify(value)),
  };
}

export function restoreFinalVerificationSnapshot(report, checkpoint) {
  const receipt = checkpoint.lastObservedState?.finalVerification;
  if (
    checkpoint.lastObservedState?.classification !== "candidate_installed_verified" ||
    receipt === null ||
    typeof receipt !== "object" ||
    Array.isArray(receipt) ||
    receipt.sha256 !== sha256Buffer(JSON.stringify(receipt.value)) ||
    receipt.value?.finalState?.status !== "installed" ||
    !sameStrings(receipt.value?.finalState?.installedHosts ?? [], HOSTS) ||
    !Array.isArray(receipt.value?.commands) ||
    receipt.value?.assertions === null ||
    typeof receipt.value.assertions !== "object"
  ) {
    fail("checkpoint", "the finalize-only checkpoint receipt is incomplete or changed");
  }
  report.assertions = structuredClone(receipt.value.assertions);
  report.commands = structuredClone(receipt.value.commands);
  Object.assign(report.mutation, receipt.value.mutation);
  return {
    status: "complete",
    phase: "installed",
    reinstallAttempted: receipt.value.mutation.reinstallAttempted,
    finalState: structuredClone(receipt.value.finalState),
    completedAt: receipt.value.completedAt,
  };
}

function readMachineLeaseCheckpoint(privateDirectory) {
  requireExactPrivateMode(
    privateDirectory,
    "private acceptance directory",
    "directory",
    0o700,
  );
  const checkpointPath = join(privateDirectory, CHECKPOINT_NAME);
  requireExactPrivateMode(checkpointPath, "acceptance checkpoint", "file", 0o600);
  const checkpoint = parseJson(
    readFileSync(checkpointPath, "utf8"),
    "checkpoint",
    "the private acceptance checkpoint is invalid",
  );
  checkpointLeaseIdentity(checkpoint);
  return checkpoint;
}

async function validateCheckpoint(privateDirectory) {
  recoverEvidenceTransaction(privateDirectory);
  requireCanonicalOwnedEntry(privateDirectory, "private acceptance directory", "directory");
  requireOwnerOnly(privateDirectory, "the private acceptance directory");
  const checkpointPath = join(privateDirectory, CHECKPOINT_NAME);
  requireCanonicalOwnedEntry(checkpointPath, "acceptance checkpoint", "file");
  requireOwnerOnly(checkpointPath, "the acceptance checkpoint");
  const checkpoint = parseJson(
    readFileSync(checkpointPath, "utf8"),
    "checkpoint",
    "the private acceptance checkpoint is invalid",
  );
  if (
    checkpoint?.schema !== CHECKPOINT_SCHEMA ||
    !UUID_V4_PATTERN.test(checkpoint?.testId ?? "") ||
    !CHECKPOINT_PHASES.has(checkpoint?.phase) ||
    !/^[a-f0-9]{40}$/u.test(checkpoint?.sourceCommit ?? "") ||
    !/^[a-f0-9]{40}$/u.test(checkpoint?.sourceTree ?? "") ||
    !Number.isSafeInteger(checkpoint?.ciRunId) ||
    checkpoint?.baseline?.kind !== BASELINE ||
    checkpoint?.baseline?.initialState !== "installed" ||
    !sameStrings(checkpoint?.baseline?.initialInstalledHosts ?? [], HOSTS) ||
    checkpoint?.baseline?.initialInventorySha256 !==
      sha256Buffer(JSON.stringify(checkpoint?.baseline?.initialInventory)) ||
    checkpoint?.baseline?.exactBindingsSha256 !==
      sha256Buffer(JSON.stringify(checkpoint?.baseline?.exactBindings)) ||
    checkpoint?.ci?.headSha !== checkpoint?.sourceCommit ||
    checkpoint?.ci?.runId !== checkpoint?.ciRunId ||
    checkpoint?.ci?.artifact?.name !==
      nativeArtifactName(checkpoint?.ciRunId, checkpoint?.ci?.runAttempt) ||
    checkpoint?.ci?.buildSource?.headSha !== checkpoint?.sourceCommit ||
    checkpoint?.ci?.buildSource?.treeSha !== checkpoint?.sourceTree ||
    checkpoint?.ci?.buildSource?.receiptSha256 !== checkpoint?.buildSourceReceiptSha256 ||
    !sameStrings(checkpoint?.intendedFinalHosts ?? [], HOSTS) ||
    checkpoint?.intendedFinalState !== "installed" ||
    !Number.isSafeInteger(checkpoint?.recovery?.hostCloseRetriesUsed) ||
    checkpoint.recovery.hostCloseRetriesUsed < 0 ||
    checkpoint.recovery.hostCloseRetriesUsed > MAX_HOST_CLOSE_RETRIES ||
    !Number.isSafeInteger(checkpoint?.recovery?.reinstallRetriesUsed) ||
    checkpoint.recovery.reinstallRetriesUsed < 0 ||
    checkpoint.recovery.reinstallRetriesUsed > MAX_REINSTALL_RETRIES
  ) {
    fail("checkpoint", "the private acceptance checkpoint has an unsupported state");
  }
  assertBaselineExactBindings(checkpoint.baseline.exactBindings);
  if (!Object.hasOwn(checkpoint.recovery, "hostCloseRetryAdmission")) {
    fail("checkpoint", "the private acceptance checkpoint is missing retry admission state");
  }
  if (!Object.hasOwn(checkpoint.recovery, "reinstallRetryAdmission")) {
    fail("checkpoint", "the private acceptance checkpoint is missing reinstall retry admission state");
  }
  if (checkpoint.recovery.hostCloseRetryAdmission !== null) {
    const admission = requireHostCloseRetryAdmission(checkpoint, {
      resolved: checkpoint.phase === "purge-retry-in-progress",
    });
    if (
      checkpoint.phase === "awaiting-host-close" &&
      admission.resolvedSnapshot !== null
    ) {
      fail("checkpoint", "an awaiting host-close checkpoint already consumed its retry admission");
    }
  }
  if (checkpoint.recovery.reinstallRetryAdmission !== null) {
    requireReinstallRetryAdmission(checkpoint);
  } else if (
    checkpoint.phase === "reinstall-retry-in-progress" ||
    checkpoint.recovery.reinstallRetriesUsed !== 0
  ) {
    fail("checkpoint", "the consumed reinstall retry is missing its durable admission");
  }
  const head = spawnSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" });
  if (head.error || head.status !== 0 || head.stdout.trim() !== checkpoint.sourceCommit) {
    fail("checkpoint", "the checkout no longer matches the exact checkpoint commit");
  }
  const tree = spawnSync("git", ["rev-parse", "HEAD^{tree}"], { cwd: ROOT, encoding: "utf8" });
  if (tree.error || tree.status !== 0 || tree.stdout.trim() !== checkpoint.sourceTree) {
    fail("checkpoint", "the checkout no longer matches the exact checkpoint source tree");
  }
  const status = spawnSync("git", ["status", "--porcelain", "--untracked-files=all"], {
    cwd: ROOT,
    encoding: "utf8",
  });
  if (status.error || status.status !== 0 || status.stdout.trim() !== "") {
    fail("checkpoint", "the checkout must remain clean before resuming");
  }
  validateCandidatePaths(privateDirectory, candidateFromCheckpoint(checkpoint));
  if ((await sha256File(checkpoint.packageArchive)) !== checkpoint.packageSha256) {
    fail("checkpoint", "the packed npm candidate changed after the first purge attempt");
  }
  if (
    (await sha256File(checkpoint.rawArtifactPath)) !== checkpoint.rawArtifactSha256 ||
    statSync(checkpoint.rawArtifactPath).size !== checkpoint.rawArtifactSizeBytes ||
    `sha256:${checkpoint.rawArtifactSha256}` !== checkpoint.ci.artifact.digest
  ) {
    fail("checkpoint", "the immutable raw CI artifact changed after candidate preparation");
  }
  const resumedBuildSourceReceipt = parseJson(
    readFileSync(checkpoint.buildSourceReceiptPath, "utf8"),
    "checkpoint",
    "the package build source receipt is invalid",
  );
  validateBuildSourceReceipt(resumedBuildSourceReceipt, {
    sourceCommit: checkpoint.sourceCommit,
    sourceTree: checkpoint.sourceTree,
  });
  if (
    (await sha256File(checkpoint.buildSourceReceiptPath)) !== checkpoint.buildSourceReceiptSha256
  ) {
    fail("checkpoint", "the package build source receipt changed after candidate preparation");
  }
  for (const host of HOSTS) {
    if (
      !checkpoint.assets?.[host] ||
      (await sha256File(checkpoint.assets[host].archivePath)) !== checkpoint.assets[host].sha256 ||
      (await sha256File(checkpoint.assets[host].checksumPath)) !==
        checkpoint.assets[host].checksumSha256 ||
      (await sha256File(checkpoint.assets[host].payloadReceiptPath)) !==
        checkpoint.assets[host].payloadReceiptSha256
    ) {
      fail("checkpoint", `${host} candidate archive changed after the first purge attempt`);
    }
    requireCanonicalOwnedEntry(
      checkpoint.assets[host].checksumPath,
      `${host} candidate checksum`,
      "file",
    );
  }
  const reportDirectory = resolve(checkpoint.reportDirectory);
  const report = validateExistingPublicReports(reportDirectory);
  if (
    report?.schema !== RESULT_SCHEMA ||
    report?.testId !== checkpoint.testId ||
    report?.source?.commit !== checkpoint.sourceCommit ||
    report?.source?.tree !== checkpoint.sourceTree ||
    report?.baseline?.kind !== BASELINE
  ) {
    fail("checkpoint", "the public result and private checkpoint do not match");
  }
  if (
    report?.baseline?.initialState !== checkpoint.baseline.initialState ||
    !sameStrings(report?.baseline?.installedHosts ?? [], checkpoint.baseline.initialInstalledHosts) ||
    report?.source?.ci?.runId !== checkpoint.ci.runId ||
    report?.source?.ci?.runAttempt !== checkpoint.ci.runAttempt ||
    report?.source?.ci?.artifact?.id !== checkpoint.ci.artifact.id ||
    report?.source?.ci?.artifact?.digest !== checkpoint.ci.artifact.digest ||
    report?.source?.ci?.buildSource?.headSha !== checkpoint.sourceCommit ||
    report?.source?.ci?.buildSource?.treeSha !== checkpoint.sourceTree ||
    report?.source?.ci?.buildSource?.receiptSha256 !== checkpoint.buildSourceReceiptSha256 ||
    report?.source?.npmPackage?.sha256 !== checkpoint.packageSha256
  ) {
    fail("checkpoint", "the immutable baseline or provenance receipt changed");
  }
  if (
    JSON.stringify(report?.baseline?.inventory) !==
      JSON.stringify(checkpoint.baseline.initialInventory)
  ) {
    fail("checkpoint", "the exact categorical baseline inventory changed");
  }
  validatePrivateEvidenceManifest(privateDirectory, reportDirectory, report.testId);
  return { checkpoint, report, reportDirectory };
}

export function candidateFromCheckpoint(checkpoint) {
  return {
    sourceCommit: checkpoint.sourceCommit,
    packageArchive: checkpoint.packageArchive,
    packageSha256: checkpoint.packageSha256,
    manifestSha256: checkpoint.manifestSha256,
    rawArtifactPath: checkpoint.rawArtifactPath,
    rawArtifactSha256: checkpoint.rawArtifactSha256,
    rawArtifactSizeBytes: checkpoint.rawArtifactSizeBytes,
    buildSourceReceiptPath: checkpoint.buildSourceReceiptPath,
    buildSourceReceiptSha256: checkpoint.buildSourceReceiptSha256,
    sourceTree: checkpoint.sourceTree,
    runId: checkpoint.ciRunId,
    assets: checkpoint.assets,
    execution: checkpoint.execution,
  };
}

function validateCandidatePaths(privateDirectory, candidate) {
  requireCanonicalOwnedEntry(privateDirectory, "private acceptance directory", "directory");
  for (const [target, label, kind] of [
    [candidate.packageArchive, "candidate npm tarball", "file"],
    [candidate.rawArtifactPath, "immutable raw CI artifact", "file"],
    [candidate.buildSourceReceiptPath, "package build source receipt", "file"],
    [candidate.execution.root, "isolated npx root", "directory"],
    [candidate.execution.runsRoot, "isolated npm run root", "directory"],
  ]) {
    assertPathBelow(privateDirectory, target, label, kind);
  }
  for (const host of HOSTS) {
    for (const [target, label] of [
      [candidate.assets[host].archivePath, `${host} candidate archive`],
      [candidate.assets[host].checksumPath, `${host} candidate checksum`],
      [candidate.assets[host].payloadReceiptPath, `${host} payload receipt`],
    ]) {
      assertPathBelow(privateDirectory, target, label, "file");
    }
  }
  const npxBinary = realpathSync(candidate.execution.npxBinary);
  const npmBinary = realpathSync(candidate.execution.npmBinary);
  const nodeBinary = realpathSync(candidate.execution.nodeBinary);
  const pythonBinary = realpathSync(candidate.execution.pythonBinary);
  const claudeBinary = realpathSync(candidate.execution.claudeBinary);
  const codexBinary = realpathSync(candidate.execution.codexBinary);
  const accountHome = lifecycleAccountHome(candidate.execution);
  const accountUser = validateLifecycleAccountUser(candidate.execution.accountUser);
  accessSync(npxBinary, fsConstants.X_OK);
  accessSync(npmBinary, fsConstants.X_OK);
  accessSync(nodeBinary, fsConstants.X_OK);
  accessSync(pythonBinary, fsConstants.X_OK);
  accessSync(claudeBinary, fsConstants.X_OK);
  accessSync(codexBinary, fsConstants.X_OK);
  if (
    npxBinary !== candidate.execution.npxBinary ||
    npmBinary !== candidate.execution.npmBinary ||
    nodeBinary !== candidate.execution.nodeBinary ||
    pythonBinary !== candidate.execution.pythonBinary ||
    claudeBinary !== candidate.execution.claudeBinary ||
    codexBinary !== candidate.execution.codexBinary ||
    accountHome !== candidate.execution.accountHome ||
    accountUser !== candidate.execution.accountUser ||
    !statSync(npxBinary).isFile() ||
    !statSync(npmBinary).isFile() ||
    !statSync(nodeBinary).isFile() ||
    !statSync(pythonBinary).isFile() ||
    !statSync(claudeBinary).isFile() ||
    !statSync(codexBinary).isFile()
  ) {
    fail("npx-isolation", "a pinned Node, Python, npm, npx, or host executable changed or is unsafe");
  }
}

function verifyResumeSource(recorder, report) {
  const head = recorder.run("Reconfirm checkpoint source commit", "git", ["rev-parse", "HEAD"], {
    category: "checkpoint",
    failureMessage: "the checkpoint source commit could not be reconfirmed",
  }).stdout;
  const status = recorder.run(
    "Reconfirm clean checkpoint worktree",
    "git",
    ["status", "--porcelain", "--untracked-files=all"],
    { category: "checkpoint", failureMessage: "the checkpoint worktree could not be reconfirmed" },
  ).stdout;
  const tree = recorder.run(
    "Reconfirm checkpoint source tree",
    "git",
    ["rev-parse", "HEAD^{tree}"],
    { category: "checkpoint", failureMessage: "the checkpoint source tree could not be reconfirmed" },
  ).stdout;
  const pullRequest = commandJson(
    recorder,
    "Reconfirm pull-request head commit",
    "gh",
    [
      "pr",
      "view",
      String(report.source.pullRequest),
      "--repo",
      REPOSITORY,
      "--json",
      "headRefOid,state",
    ],
    {},
    "checkpoint",
    "the pull-request head could not be reconfirmed",
  );
  if (
    head !== report.source.commit ||
    status !== "" ||
    tree !== report.source.tree ||
    pullRequest?.headRefOid !== report.source.commit ||
    pullRequest?.state !== "OPEN"
  ) {
    fail("checkpoint", "the source checkout or pull-request head changed after the artifact gate");
  }
}

function inspectOpenCodeBridgeResidue(paths) {
  if (paths.bridgeParent === null || !pathPresent(paths.bridgeParent)) return 0;
  requireCanonicalOwnedEntry(paths.bridgeParent, "OpenCode plugin directory", "directory");
  return readdirSync(paths.bridgeParent).filter(
    (name) =>
      /^\.opensocrates\.js\.(?:staging|backup|removed)-[A-Za-z0-9-]+$/u.test(name) ||
      /^\.opensocrates-managed\.json\.(?:staging|backup|removed)-[A-Za-z0-9-]+$/u.test(name),
  ).length;
}

export function purgeCommandArguments(candidate) {
  return [
    "--yes",
    `--package=${candidate.packageArchive}`,
    "opensocrates",
    "remove",
    "--host",
    "all",
    "--purge",
    "--reset-trust",
  ];
}

export function installCommandArguments(candidate) {
  return [
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
  ];
}

async function verifyCandidateUnchanged(recorder, candidate) {
  validateCandidatePaths(dirname(candidate.execution.root), candidate);
  await verifyExecutionIdentity(recorder, candidate);
  if ((await sha256File(candidate.packageArchive)) !== candidate.packageSha256) {
    fail("artifact-integrity", "the exact packed npm candidate changed before lifecycle mutation");
  }
  if (
    (await sha256File(candidate.rawArtifactPath)) !== candidate.rawArtifactSha256 ||
    statSync(candidate.rawArtifactPath).size !== candidate.rawArtifactSizeBytes
  ) {
    fail("artifact-integrity", "the immutable raw CI artifact changed before lifecycle mutation");
  }
  const buildSourceReceipt = parseJson(
    readFileSync(candidate.buildSourceReceiptPath, "utf8"),
    "artifact-integrity",
    "the package build source receipt became invalid",
  );
  validateBuildSourceReceipt(buildSourceReceipt, {
    sourceCommit: candidate.sourceCommit,
    sourceTree: candidate.sourceTree,
  });
  if ((await sha256File(candidate.buildSourceReceiptPath)) !== candidate.buildSourceReceiptSha256) {
    fail("artifact-integrity", "the package build source receipt changed before lifecycle mutation");
  }
  for (const host of HOSTS) {
    if (
      (await sha256File(candidate.assets[host].archivePath)) !== candidate.assets[host].sha256 ||
      (await sha256File(candidate.assets[host].checksumPath)) !==
        candidate.assets[host].checksumSha256 ||
      (await sha256File(candidate.assets[host].payloadReceiptPath)) !==
        candidate.assets[host].payloadReceiptSha256
    ) {
      fail("artifact-integrity", `${host} exact-SHA CI input changed before lifecycle mutation`);
    }
  }
}

async function inspectRecoveryState(
  recorder,
  targets,
  candidate,
  { trustSnapshot = null } = {},
) {
  const launchAgentJob = inspectLaunchAgentJob(recorder);
  const snapshot = exactResidueSnapshot(targets, null, launchAgentJob, trustSnapshot);
  const residue = publicResidueSummary(snapshot);
  const installedHosts = HOSTS.filter((host) => snapshot.hosts[host].managedRootPresent);
  if (installedHosts.length === 0 && filesystemResidueIsEmpty(snapshot)) {
    const registrations = hostRegistrationSnapshot(recorder, targets);
    const observed = exactResidueSnapshot(
      targets,
      registrations,
      launchAgentJob,
      trustSnapshot,
    );
    const observedResidue = publicResidueSummary(observed);
    return {
      classification: observedResidue.empty ? "purged_after_failure" : "partial_or_unverified",
      installedHosts: [],
      missingHosts: [...HOSTS],
      registrationInspection: "passed_without_installed_payload",
      residue: observedResidue,
      actualStateRecorded: true,
      previousStateRestorationClaimed: false,
    };
  }
  if (installedHosts.length > 0) {
    try {
      const state = inspectStateDirectory(targets, { requireInstalled: true });
      const desired = state.desired;
      const missingHosts = HOSTS.filter((host) => !installedHosts.includes(host));
      const installedPayloads = {};
      for (const host of installedHosts) {
        const pluginRoot = resolveInstalledPluginRoot(host, targets[host].root);
        await verifyManagedRootExact(host, targets[host].root, pluginRoot, {
          category: "recovery",
        });
        installedPayloads[host] = await verifyInstalledPayload(
          host,
          pluginRoot,
          candidate.assets[host].payloadReceiptPath,
        );
      }
      const missingHostsClean = missingHosts.every((host) => {
        const item = snapshot.hosts[host];
        return (
          !item.managedRootPresent &&
          !item.cachePresent &&
          !item.cacheMarketplacePresent &&
          !item.pluginDataPresent &&
          item.transactionResidueCount === 0 &&
          !item.bridgePresent &&
          !item.bridgeMarkerPresent
        );
      });
      const nonTargetHostsClean = SUPPORTED_HOSTS.filter((host) => !HOSTS.includes(host)).every(
        (host) => {
          const item = snapshot.hosts[host];
          return (
            !item.managedRootPresent &&
            !item.cachePresent &&
            !item.cacheMarketplacePresent &&
            !item.pluginDataPresent &&
            item.transactionResidueCount === 0 &&
            !item.bridgePresent &&
            !item.bridgeMarkerPresent
          );
        },
      );
      if (
        desired?.schema !== DESIRED_STATE_SCHEMA ||
        desired?.activeVersion !== PRODUCT_VERSION ||
        !sameStrings(desired?.installedHosts ?? [], installedHosts) ||
        desired?.autoUpdate?.enabled !== false ||
        !sameStrings(desired?.autoUpdate?.hosts ?? [], []) ||
        state.launchAgentPresent ||
        launchAgentJob.loaded ||
        !missingHostsClean ||
        !nonTargetHostsClean ||
        !SUPPORTED_HOSTS.every(
          (host) => snapshot.hosts[host].transactionResidueCount === 0,
        ) ||
        snapshot.launchAgentTemporaryCount !== 0 ||
        snapshot.codexTrustSectionCount !== 0 ||
        snapshot.trustTransactionResidueCount !== 0 ||
        snapshot.openCodeBridgeResidueCount !== 0 ||
        snapshot.stateResidue.lifecycleLockPresent ||
        snapshot.stateResidue.temporaryCount !== 0 ||
        snapshot.stateResidue.purgeTombstoneCount !== 0 ||
        snapshot.stateResidue.unknownLeafCount !== 0
      ) {
        fail("recovery", "the installed filesystem topology is not an exact candidate subset");
      }
      return {
        classification:
          installedHosts.length === HOSTS.length
            ? "candidate_installed_unverified"
            : "candidate_partial_installed",
        installedHosts: sorted(installedHosts),
        missingHosts: sorted(missingHosts),
        registrationInspection: "deferred_to_preserve_first_review",
        candidatePayloads: installedPayloads,
        residue,
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      };
    } catch {
      return {
        classification: "partial_or_unverified",
        installedHosts: sorted(installedHosts),
        missingHosts: HOSTS.filter((host) => !installedHosts.includes(host)),
        registrationInspection: "deferred_to_preserve_first_review",
        residue,
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      };
    }
  }
  return {
    classification: "partial_or_unverified",
    installedHosts: [],
    missingHosts: [...HOSTS],
    registrationInspection: "not_safe_to_attempt",
    residue,
    actualStateRecorded: true,
    previousStateRestorationClaimed: false,
  };
}

async function inspectFailureState(recorder, targets, candidate, stage) {
  if (stage === "reinstall" || stage === "post-install" || stage === "recovery") {
    return inspectRecoveryState(recorder, targets, candidate);
  }
  let registrations = null;
  let registrationInspection = "passed";
  try {
    registrations = hostRegistrationSnapshot(recorder, targets);
  } catch {
    registrationInspection = "failed";
  }
  try {
    const snapshot = exactResidueSnapshot(
      targets,
      registrations,
      inspectLaunchAgentJob(recorder),
    );
    return classifyPurgeFailureSnapshot(registrations, snapshot);
  } catch {
    return {
      classification: "unknown_unverified",
      actualStateRecorded: false,
      registrationInspection,
      previousStateRestorationClaimed: false,
    };
  }
}

function nextActionForFailure(phase, state) {
  if (phase === "finalizing") {
    return "do_not_replay_first_review_review_private_evidence_and_restore_an_exact_baseline_before_a_new_run";
  }
  if (phase === "purge" || phase === "clean-assertion") {
    return "review_private_command_and_exact_residue_without_automatic_repair";
  }
  if (state?.classification === "purged_after_failure") {
    return "resume_the_existing_checkpoint_with_the_same_exact_inputs";
  }
  if (state?.classification === "candidate_partial_installed") {
    return "observe_and_review_the_atomic_all_host_install_failure_without_automatic_repair";
  }
  if (state?.classification === "candidate_installed_unverified") {
    return "resume_post_install_checks_without_another_lifecycle_mutation";
  }
  return "review_the_actual_partial_state_without_claiming_restoration_or_automatic_repair";
}

export function finalizationFailureState(checkpoint) {
  const state = checkpoint?.lastObservedState;
  if (
    checkpoint?.phase !== "finalizing" ||
    state?.classification !== "one_shot_final_verification_interrupted" ||
    !UUID_V4_PATTERN.test(state.finalizationId ?? "") ||
    !UUID_V4_PATTERN.test(state.testId ?? "") ||
    !/^[a-f0-9]{40}$/u.test(state.sourceCommit ?? "") ||
    !sameStrings(state.installedHosts ?? [], HOSTS) ||
    state.firstReviewReplayForbidden !== true ||
    state.actualStateRecorded !== false ||
    state.previousStateRestorationClaimed !== false
  ) {
    fail("finalizing", "the private one-shot interruption state is incomplete");
  }
  return {
    classification: state.classification,
    installedHosts: [...HOSTS],
    actualStateRecorded: false,
    previousStateRestorationClaimed: false,
  };
}

export function selectFailureState(checkpoint, inspectedState) {
  const specific = new Set([
    "partial_purge_after_bounded_retry",
    "installer_defect_residue_after_purge",
    "non_retryable_residue_with_live_cache",
  ]);
  if (
    checkpoint?.phase === "purge-failed" &&
    specific.has(checkpoint?.lastObservedState?.classification)
  ) {
    return {
      ...checkpoint.lastObservedState,
      actualStateRecorded: true,
      previousStateRestorationClaimed: false,
    };
  }
  return inspectedState ?? unknownFailureState();
}

async function currentRetryBindings(targets, candidate, checkpoint) {
  let desiredStateSha256 = "absent";
  if (pathPresent(targets.state.desiredState)) {
    requireCanonicalOwnedEntry(
      targets.state.desiredState,
      "OpenSocrates desired state retry binding",
      "file",
    );
    requireOwnerOnly(targets.state.desiredState, "the OpenSocrates desired state retry binding");
    desiredStateSha256 = await sha256File(targets.state.desiredState);
  }
  return {
    sourceCommit: checkpoint.sourceCommit,
    packageSha256: candidate.packageSha256,
    artifactDigest: checkpoint.ci.artifact.digest,
    desiredStateSha256,
  };
}

async function purgeExactCandidate(
  recorder,
  report,
  targets,
  candidate,
  privateDirectory,
  checkpoint,
  { hostCloseRetry = false } = {},
) {
  await verifyCandidateUnchanged(recorder, candidate);
  const operationKey = hostCloseRetry
    ? "purge-host-close-retry"
    : "purge-initial";
  const existingOperation = inspectLifecycleOperation(privateDirectory, operationKey);
  if (hostCloseRetry) {
    const retryAlreadyWrittenAhead = checkpoint.phase === "purge-retry-in-progress";
    if (
      checkpoint.recovery.hostCloseRetriesUsed >= MAX_HOST_CLOSE_RETRIES &&
      !retryAlreadyWrittenAhead
    ) {
      fail("purge", "the bounded host-close purge retry was already consumed");
    }
    if (existingOperation.state !== "terminal") {
      const admission = requireHostCloseRetryAdmission(checkpoint, {
        resolved: retryAlreadyWrittenAhead,
      });
      const registrations = hostRegistrationSnapshot(recorder, targets);
      const currentSnapshot = exactResidueSnapshot(
        targets,
        registrations,
        inspectLaunchAgentJob(recorder),
      );
      const currentDesiredState = inspectDeactivatedDesiredState(targets);
      const currentBindings = await currentRetryBindings(targets, candidate, checkpoint);
      assertHostCloseRetrySnapshot(
        admission.initialSnapshot,
        currentSnapshot,
        admission.confirmedHosts,
        admission.bindings,
        currentBindings,
      );
      if (
        JSON.stringify(currentDesiredState) !==
        JSON.stringify(admission.deactivatedDesiredState)
      ) {
        fail("recovery", "the deferred desired state changed before the host-close retry");
      }
      if (
        retryAlreadyWrittenAhead &&
        JSON.stringify(currentSnapshot) !== JSON.stringify(admission.resolvedSnapshot)
      ) {
        fail("recovery", "machine state changed after the durable host-close retry admission");
      }
      if (!retryAlreadyWrittenAhead) {
        checkpoint.recovery.hostCloseRetriesUsed += 1;
        admission.resolvedSnapshot = structuredClone(currentSnapshot);
      }
      report.mutation.hostCloseRetriesUsed = checkpoint.recovery.hostCloseRetriesUsed;
      transitionCheckpoint(privateDirectory, checkpoint, "purge-retry-in-progress", {
        classification: "confirmed_live_marker_resolved_retry_in_progress",
        confirmedHostCloseCandidates: [...admission.confirmedHosts],
        residue: publicResidueSummary(currentSnapshot),
        retryBindings: currentBindings,
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      });
    }
  } else {
    transitionCheckpoint(privateDirectory, checkpoint, "purging", {
      classification: "combined_purge_write_ahead",
      previousStateRestorationClaimed: false,
    });
  }
  report.mutation.started = true;
  report.mutation.phase = "purge";
  report.mutation.purgeCommandAttempts += 1;
  report.mutation.trustResetAttempts += 1;
  const removed = await runPackedNpx(
    recorder,
    "Purge all hosts and reset exact Codex trust through exact packed npx",
    candidate,
    purgeCommandArguments(candidate),
    {
      allowFailure: true,
      invocationMode: "account-home-lifecycle",
      lifecycleOperationKey: operationKey,
      timeout: 300_000,
    },
  );
  if (removed.error || removed.status !== 0) {
    let snapshot = null;
    try {
      const registrations = hostRegistrationSnapshot(recorder, targets);
      snapshot = exactResidueSnapshot(
        targets,
        registrations,
        inspectLaunchAgentJob(recorder),
      );
    } catch {
      fail("purge", "the exact packed all-host purge failed with residue that is unsafe to classify", removed.id);
    }
    const liveHosts = Object.entries(snapshot.hosts)
      .filter(([, item]) => item.liveInUse)
      .map(([host]) => host);
    const raw = `${removed.stdout}\n${removed.stderr}`;
    if (liveHosts.length > 0 && raw.includes("host-in-use")) {
      let deactivatedDesiredState = null;
      try {
        deactivatedDesiredState = inspectDeactivatedDesiredState(targets);
        assertOnlyRetryableHostCloseResidue(
          snapshot,
          liveHosts,
          deactivatedDesiredState,
        );
      } catch {
        transitionCheckpoint(privateDirectory, checkpoint, "purge-failed", {
          classification: "non_retryable_residue_with_live_cache",
          residue: publicResidueSummary(snapshot),
          actualStateRecorded: true,
          previousStateRestorationClaimed: false,
        });
        fail(
          "purge",
          "the purge left defects beyond the exact live cache; host-close retry is forbidden",
          removed.id,
        );
      }
      if (checkpoint.recovery.hostCloseRetriesUsed >= MAX_HOST_CLOSE_RETRIES) {
        transitionCheckpoint(privateDirectory, checkpoint, "purge-failed", {
          classification: "partial_purge_after_bounded_retry",
          residue: publicResidueSummary(snapshot),
          actualStateRecorded: true,
          previousStateRestorationClaimed: false,
        });
        fail("purge", "the single bounded host-close retry still left an active cache", removed.id);
      }
      report.assertions.deferredInUse = {
        detected: true,
        hosts: sorted(liveHosts),
        reinstallBlocked: true,
      };
      const retryBindings = await currentRetryBindings(targets, candidate, checkpoint);
      checkpoint.recovery.hostCloseRetryAdmission = {
        initialSnapshot: structuredClone(snapshot),
        confirmedHosts: sorted(liveHosts),
        bindings: structuredClone(retryBindings),
        deactivatedDesiredState,
        resolvedSnapshot: null,
      };
      transitionCheckpoint(privateDirectory, checkpoint, "awaiting-host-close", {
        classification: "partial_purge_host_in_use",
        confirmedHostCloseCandidates: sorted(liveHosts),
        residue: publicResidueSummary(snapshot),
        retryBindings,
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      });
      return {
        status: "awaiting-host-close",
        residue: publicResidueSummary(snapshot),
      };
    }
    transitionCheckpoint(privateDirectory, checkpoint, "purge-failed", {
      classification: "partial_or_unverified",
      residue: publicResidueSummary(snapshot),
      previousStateRestorationClaimed: false,
    });
    fail("purge", "the exact packed all-host purge failed; reinstall remains blocked", removed.id);
  }

  transitionCheckpoint(privateDirectory, checkpoint, "purge-complete-unverified", {
    classification: "purge_commands_completed_zero_residue_unverified",
    previousStateRestorationClaimed: false,
  });
  return { status: "complete" };
}

function assertZeroResidue(recorder, report, targets, privateDirectory, checkpoint) {
  const registrations = hostRegistrationSnapshot(recorder, targets);
  assertRegistrationState(registrations, "absent");
  const snapshot = exactResidueSnapshot(
    targets,
    registrations,
    inspectLaunchAgentJob(recorder),
  );
  const summary = publicResidueSummary(snapshot);
  report.assertions.zeroResidue = summary;
  if (!summary.empty) {
    transitionCheckpoint(privateDirectory, checkpoint, "purge-failed", {
      classification: "installer_defect_residue_after_purge",
      residue: summary,
      previousStateRestorationClaimed: false,
    });
    fail("residue", "OpenSocrates exact-target residue remains; reinstall is blocked");
  }
  transitionCheckpoint(privateDirectory, checkpoint, "purged", {
    classification: "purged_zero_residue",
    installedHosts: [],
    previousStateRestorationClaimed: false,
  });
  return summary;
}

async function installExactCandidate(
  recorder,
  report,
  candidate,
  privateDirectory,
  checkpoint,
) {
  await verifyCandidateUnchanged(recorder, candidate);
  report.mutation.phase = "reinstall";
  report.mutation.reinstallAttempted = true;
  report.mutation.reinstallAttempts += 1;
  transitionCheckpoint(privateDirectory, checkpoint, "reinstalling", {
    classification: "purged_before_atomic_all_host_reinstall",
    installedHosts: [],
    previousStateRestorationClaimed: false,
  });
  await runPackedNpx(
    recorder,
    "Reinstall Claude and Codex atomically through exact packed npx",
    candidate,
    installCommandArguments(candidate),
    {
      category: "reinstall",
      failureMessage: "the exact packed all-host reinstall failed",
      invocationMode: "account-home-lifecycle",
      lifecycleOperationKey:
        checkpoint.recovery.reinstallRetriesUsed > 0
          ? "install-retry"
          : "install-initial",
      timeout: 600_000,
    },
  );
  transitionCheckpoint(privateDirectory, checkpoint, "post-install-checks", {
    classification: "atomic_all_host_install_succeeded_post_checks_pending",
    installedHosts: [...HOSTS],
    previousStateRestorationClaimed: false,
  });
}

export async function assertFinalInstalled(
  recorder,
  report,
  targets,
  candidate,
  privateDirectory,
) {
  // This is deliberately the first Codex process after the installer-owned
  // registration commands. It observes the new/untrusted review state before
  // any status, runtime, or task launch can consume the first-review event.
  const hooks = codexHookInventory(recorder);
  assertExactUntrustedHooks(hooks);
  const registrations = hostRegistrationSnapshot(recorder, targets);
  assertRegistrationState(registrations, "installed-final");
  const state = inspectStateDirectory(targets, { requireInstalled: true });
  const launchAgentJob = inspectLaunchAgentJob(recorder);
  const launchAgentTemporaryCount = inspectLaunchAgentTemporaryResidue(targets.state);
  const trust = inspectCodexTrustSections();
  const trustTransactionResidueCount = inspectTrustTransactionResidue(
    targets.codex.hostHome,
  );
  if (
    state.desired?.schema !== DESIRED_STATE_SCHEMA ||
    state.desired?.activeVersion !== PRODUCT_VERSION ||
    !sameStrings(state.desired?.installedHosts ?? [], HOSTS) ||
    state.desired?.autoUpdate?.enabled !== false ||
    !sameStrings(state.desired?.autoUpdate?.hosts ?? [], []) ||
    state.launchAgentPresent ||
    launchAgentTemporaryCount !== 0 ||
    launchAgentJob.loaded ||
    trust.exactSectionCount !== 0 ||
    trustTransactionResidueCount !== 0
  ) {
    fail("post-install", "the final desired state is not the exact installed two-host state with updates disabled");
  }
  const layout = inspectManagedLayout({
    claude: targets.claude.root,
    codex: targets.codex.root,
  });
  const nonTargetHosts = assertNonTargetHostsAbsent(targets);
  const pluginRoots = {
    claude: resolveInstalledPluginRoot("claude", targets.claude.root),
    codex: resolveInstalledPluginRoot("codex", targets.codex.root),
  };
  const payloads = {};
  const runtimes = {};
  for (const host of HOSTS) {
    await verifyManagedRootExact(host, targets[host].root, pluginRoots[host], {
      category: "post-install",
    });
    payloads[host] = await verifyInstalledPayload(
      host,
      pluginRoots[host],
      candidate.assets[host].payloadReceiptPath,
    );
    runtimes[host] = verifyInstalledRuntime(recorder, host, pluginRoots[host]);
  }
  assertNoKnownTransactionResidue(targets, "post-install");
  const status = verifyPackagedStatus(recorder, candidate);
  const timing = measureInstalledSessionStart(
    recorder,
    privateDirectory,
    pluginRoots.codex,
    candidate.assets.codex.releaseManifestSha256,
    candidate.execution.pythonBinary,
  );
  const desiredState = {
    schema: state.desired.schema,
    activeVersion: state.desired.activeVersion,
    installedHosts: sorted(state.desired.installedHosts),
    autoUpdateEnabled: state.desired.autoUpdate.enabled,
    launchAgentPresent: state.launchAgentPresent,
    launchAgentJobLoaded: launchAgentJob.loaded,
  };
  report.assertions.finalRegistration = { status: "pass", hosts: registrations };
  report.assertions.finalStatus = { status: "pass", ...status };
  report.assertions.finalVersion = {
    status: "pass",
    desiredVersion: PRODUCT_VERSION,
    runtimes,
  };
  report.assertions.finalChecksum = { status: "pass", payloads };
  report.assertions.finalManagedLayout = { status: "pass", ...layout };
  report.assertions.finalArchitecture = {
    status: "pass",
    hardware: "arm64",
    process: process.arch,
    installed: Object.fromEntries(
      HOSTS.map((host) => [host, runtimes[host].architectures]),
    ),
  };
  report.assertions.finalPermissions = {
    status: "pass",
    stateDirectoryMode: requireOwnerOnly(targets.state.directory, "the final state directory"),
    desiredStateMode: requireOwnerOnly(targets.state.desiredState, "the final desired-state file"),
    managedRootsOwnedByEffectiveUser: HOSTS.every(
      (host) => lstatSync(targets[host].root).uid === currentUid(),
    ),
    runtimesExecutable: HOSTS.every((host) => runtimes[host].executable),
  };
  report.assertions.finalDesiredState = { status: "pass", ...desiredState };
  report.assertions.codexFirstApproval = {
    status: "pass",
    exactHookCount: hooks.hookCount,
    events: hooks.events,
    namespace: hooks.namespace,
    trustStatuses: hooks.trustStatuses,
    sessionStartTimeoutSeconds: hooks.sessionStartTimeoutSeconds,
    observedBeforeOtherPostInstallCodexLaunch: true,
    manualApprovalRequired: true,
  };
  report.assertions.sessionStartBudget = timing;
  report.assertions.finalTopology = {
    status: "pass",
    sourceCommit: report.source.commit,
    installedHosts: [...HOSTS],
    version: PRODUCT_VERSION,
    admittedTopology: "claude_and_codex_only; other_supported_hosts_absent",
    nonTargetHosts,
    previousCacheDataTrustContentRestorationClaimed: false,
  };
  return {
    status: "installed",
    version: PRODUCT_VERSION,
    installedHosts: [...HOSTS],
  };
}

export function recoveryPlanForPhase(
  checkpoint,
  observedState = null,
  { hostAppsClosedConfirmed = false } = {},
) {
  const phase = checkpoint.phase;
  if (phase === "ready-to-purge") {
    return {
      stages: ["purge", "clean-assertion", "reinstall", "post-install"],
      hostCloseRetry: false,
      hostsToInstall: [...HOSTS],
      requireOriginalBaseline: true,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "purging") {
    if (observedState?.classification === "installed_baseline_unchanged") {
      return {
        stages: ["purge", "clean-assertion", "reinstall", "post-install"],
        hostCloseRetry: false,
        hostsToInstall: [...HOSTS],
        requireOriginalBaseline: true,
        consumeReinstallRetry: false,
      };
    }
    if (observedState?.classification === "purged_after_failure") {
      return {
        stages: ["clean-assertion", "reinstall", "post-install"],
        hostCloseRetry: false,
        hostsToInstall: [...HOSTS],
        requireOriginalBaseline: false,
        consumeReinstallRetry: false,
      };
    }
    fail("recovery", "an interrupted initial purge is not safe for automatic continuation");
  }
  if (phase === "purge-retry-in-progress") {
    if (observedState?.classification !== "purged_after_failure") {
      fail("recovery", "an interrupted bounded purge retry is observation-only unless already purged");
    }
    return {
      stages: ["clean-assertion", "reinstall", "post-install"],
      hostCloseRetry: false,
      hostsToInstall: [...HOSTS],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "awaiting-host-close") {
    if (!hostAppsClosedConfirmed) {
      fail("host-close-confirmation", "resume requires explicit confirmation that the listed host apps were closed");
    }
    if (checkpoint.recovery.hostCloseRetriesUsed >= MAX_HOST_CLOSE_RETRIES) {
      fail("purge", "the single bounded host-close retry was already consumed");
    }
    return {
      stages: ["purge", "clean-assertion", "reinstall", "post-install"],
      hostCloseRetry: true,
      hostsToInstall: [...HOSTS],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "purge-complete-unverified") {
    return {
      stages: ["clean-assertion", "reinstall", "post-install"],
      hostCloseRetry: false,
      hostsToInstall: [...HOSTS],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "purged") {
    return {
      stages: ["clean-assertion", "reinstall", "post-install"],
      hostCloseRetry: false,
      hostsToInstall: [...HOSTS],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "reinstalling" || phase === "reinstall-failed") {
    if (observedState?.classification === "candidate_installed_unverified") {
      return {
        stages: ["post-install"],
        hostCloseRetry: false,
        hostsToInstall: [],
        requireOriginalBaseline: false,
        consumeReinstallRetry: false,
      };
    }
    if (observedState?.classification === "purged_after_failure") {
      if (checkpoint.recovery.reinstallRetriesUsed >= MAX_REINSTALL_RETRIES) {
        fail("recovery", "the single bounded exact-candidate reinstall retry was already consumed");
      }
      return {
        stages: ["clean-assertion", "reinstall", "post-install"],
        hostCloseRetry: false,
        hostsToInstall: [...HOSTS],
        requireOriginalBaseline: false,
        consumeReinstallRetry: true,
      };
    }
    fail("recovery", "the partial reinstall state is unsafe for automatic repair");
  }
  if (phase === "reinstall-retry-in-progress") {
    requireReinstallRetryAdmission(checkpoint);
    return {
      stages: ["clean-assertion", "reinstall", "post-install"],
      hostCloseRetry: false,
      hostsToInstall: [...HOSTS],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "post-install-failed") {
    fail("recovery", "a failed one-shot post-install review cannot be replayed automatically");
  }
  if (phase === "post-install-checks") {
    if (observedState?.classification !== "candidate_installed_unverified") {
      fail("recovery", "post-install checks can resume only from an exact installed candidate topology");
    }
    return {
      stages: ["post-install"],
      hostCloseRetry: false,
      hostsToInstall: [],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  if (phase === "purge-failed") {
    fail("recovery", "a non-deferred purge failure is observation-only and requires installer defect review");
  }
  if (phase === "finalizing") {
    fail("recovery", "interrupted first-review verification cannot be replayed automatically");
  }
  if (phase === "final-verified") {
    if (observedState?.classification !== "candidate_installed_verified") {
      fail("recovery", "the finalize-only checkpoint is missing its exact verified snapshot");
    }
    return {
      stages: [],
      finalizeOnly: true,
      hostCloseRetry: false,
      hostsToInstall: [],
      requireOriginalBaseline: false,
      consumeReinstallRetry: false,
    };
  }
  fail("checkpoint", "the completed installed checkpoint cannot be resumed");
}

async function assertOriginalBaselineUnchanged(
  recorder,
  targets,
  checkpoint,
  inventoryReader = baselineInventory,
) {
  const currentInventory = await inventoryReader(recorder, targets);
  const current = currentInventory.public;
  assertBaselineExactBindings(checkpoint.baseline.exactBindings);
  assertBaselineExactBindings(currentInventory.exactBindings);
  if (
    JSON.stringify(current) !== JSON.stringify(checkpoint.baseline.initialInventory) ||
    sha256Buffer(JSON.stringify(current)) !== checkpoint.baseline.initialInventorySha256 ||
    checkpoint.baseline.exactBindingsSha256 !==
      sha256Buffer(JSON.stringify(checkpoint.baseline.exactBindings)) ||
    JSON.stringify(currentInventory.exactBindings) !==
      JSON.stringify(checkpoint.baseline.exactBindings) ||
    sha256Buffer(JSON.stringify(currentInventory.exactBindings)) !==
      checkpoint.baseline.exactBindingsSha256
  ) {
    fail("baseline", "the exact admitted baseline bytes changed before the first purge command");
  }
  return current;
}

export function beginFinalizationClaim(
  privateDirectory,
  checkpoint,
  { testId, sourceCommit } = {},
) {
  if (
    !UUID_V4_PATTERN.test(testId ?? "") ||
    !/^[a-f0-9]{40}$/u.test(sourceCommit ?? "") ||
    sourceCommit !== checkpoint.sourceCommit ||
    checkpoint.phase !== "post-install-checks"
  ) {
    fail("finalizing", "the one-shot finalization claim is invalid");
  }
  const finalizationId = randomUUID();
  transitionCheckpoint(privateDirectory, checkpoint, "finalizing", {
    classification: "candidate_installed_final_verification_in_progress",
    finalizationId,
    testId,
    sourceCommit,
    installedHosts: [...HOSTS],
    firstReviewReplayForbidden: true,
    actualStateRecorded: false,
    previousStateRestorationClaimed: false,
  });
  return finalizationId;
}

export async function runFinalVerificationOnce(
  privateDirectory,
  checkpoint,
  verifier,
  { testId, sourceCommit, finalizationId } = {},
) {
  if (
    typeof verifier !== "function" ||
    !UUID_V4_PATTERN.test(testId ?? "") ||
    !/^[a-f0-9]{40}$/u.test(sourceCommit ?? "") ||
    !UUID_V4_PATTERN.test(finalizationId ?? "") ||
    sourceCommit !== checkpoint.sourceCommit ||
    checkpoint.phase !== "finalizing" ||
    checkpoint.lastObservedState?.classification !==
      "candidate_installed_final_verification_in_progress" ||
    checkpoint.lastObservedState?.finalizationId !== finalizationId ||
    checkpoint.lastObservedState?.testId !== testId ||
    checkpoint.lastObservedState?.sourceCommit !== sourceCommit
  ) {
    fail("finalizing", "the one-shot final verifier is not bound to its durable claim");
  }
  try {
    return await verifier();
  } catch (error) {
    transitionCheckpoint(privateDirectory, checkpoint, "finalizing", {
      classification: "one_shot_final_verification_interrupted",
      finalizationId,
      testId,
      sourceCommit,
      installedHosts: [...HOSTS],
      firstReviewReplayForbidden: true,
      actualStateRecorded: false,
      previousStateRestorationClaimed: false,
    });
    throw error;
  }
}

export async function runMutation(
  recorder,
  report,
  targets,
  candidate,
  privateDirectory,
  checkpoint,
  {
    hostAppsClosedConfirmed = false,
    lifecycleStep = null,
    runtime: runtimeOverrides = null,
    testHooks = {},
  } = {},
) {
  if (checkpoint.phase === "final-verified") {
    return restoreFinalVerificationSnapshot(report, checkpoint);
  }
  if (checkpoint.phase === "finalizing") {
    fail("recovery", "interrupted first-review verification cannot be replayed automatically");
  }
  requireExactObjectKeys(
    testHooks,
    Object.keys(testHooks).length === 0 ? [] : ["afterReinstallRetryWriteAhead"],
    "harness",
    "the mutation test hooks",
  );
  if (
    Object.hasOwn(testHooks, "afterReinstallRetryWriteAhead") &&
    typeof testHooks.afterReinstallRetryWriteAhead !== "function"
  ) {
    fail("harness", "the mutation retry write-ahead hook is invalid");
  }
  const runtime = {
    verifyCandidateUnchanged,
    baselineInventory,
    inspectRecoveryState,
    assertFinalInstalled,
    inspectFailureState,
    purgeCandidate: purgeExactCandidate,
    assertClean: assertZeroResidue,
    installCandidate: installExactCandidate,
    sealPublicResult: createSealedPublicResult,
    commitFinalVerified: (directory, value, lastObservedState) =>
      transitionCheckpoint(directory, value, "final-verified", lastObservedState),
    ...(runtimeOverrides ?? {}),
  };
  requireExactObjectKeys(
    runtime,
    [
      "verifyCandidateUnchanged",
      "baselineInventory",
      "inspectRecoveryState",
      "assertFinalInstalled",
      "inspectFailureState",
      "purgeCandidate",
      "assertClean",
      "installCandidate",
      "sealPublicResult",
      "commitFinalVerified",
    ],
    "harness",
    "the mutation runtime seam",
  );
  if (Object.values(runtime).some((operation) => typeof operation !== "function")) {
    fail("harness", "the mutation runtime seam is incomplete");
  }
  reconcileMutationTelemetry(report, privateDirectory, checkpoint);
  await runtime.verifyCandidateUnchanged(recorder, candidate);
  if (
    checkpoint.phase === "reinstall-failed" &&
    checkpoint.lastObservedState?.classification ===
      "atomic_all_host_install_terminal_failed"
  ) {
    fail(
      "reinstall",
      "the atomic all-host install has a durable non-success terminal and is observation-only",
    );
  }
  const recoveryPhases = new Set([
    "purging",
    "purge-retry-in-progress",
    "reinstalling",
    "reinstall-retry-in-progress",
    "reinstall-failed",
    "post-install-checks",
    "post-install-failed",
  ]);
  const interruptedOperationKey =
    checkpoint.phase === "purging"
      ? "purge-initial"
      : checkpoint.phase === "purge-retry-in-progress"
        ? "purge-host-close-retry"
        : checkpoint.phase === "reinstalling"
          ? checkpoint.recovery.reinstallRetriesUsed > 0
            ? "install-retry"
            : "install-initial"
          : checkpoint.phase === "reinstall-retry-in-progress"
            ? "install-retry"
          : null;
  const interruptedOperationState =
    interruptedOperationKey === null
      ? null
      : inspectLifecycleOperation(privateDirectory, interruptedOperationKey);
  if (
    interruptedOperationState?.state === "claimed_active" ||
    interruptedOperationState?.state === "blocked_unverifiable"
  ) {
    fail(
      "lifecycle-recovery",
      "an interrupted claimed lifecycle cannot be replayed or inferred from filesystem state",
    );
  }
  if (checkpoint.phase === "reinstall-retry-in-progress") {
    requireReinstallRetryAdmission(checkpoint, candidate);
  }
  if (
    interruptedOperationKey?.startsWith("install-") &&
    interruptedOperationState?.state === "terminal"
  ) {
    const terminal = interruptedOperationState.terminal;
    const terminalSucceeded =
      terminal.exitStatus === 0 &&
      terminal.signal === null &&
      terminal.spawnError === null &&
      terminal.timedOut === false &&
      terminal.outputLimitExceeded === false &&
      terminal.processGroupQuiescent === true;
    if (!terminalSucceeded) {
      const actual = await runtime.inspectRecoveryState(recorder, targets, candidate);
      if (typeof actual?.actualStateRecorded !== "boolean") {
        fail("recovery", "the recovery inspector omitted its actual-state evidence flag");
      }
      transitionCheckpoint(privateDirectory, checkpoint, "reinstall-failed", {
        classification: "atomic_all_host_install_terminal_failed",
        operationKey: interruptedOperationKey,
        operationSha256: interruptedOperationState.operationSha256,
        exitStatus: terminal.exitStatus,
        observedClassification: actual.classification,
        installedHosts: structuredClone(actual.installedHosts ?? []),
        actualStateRecorded: actual.actualStateRecorded,
        previousStateRestorationClaimed: false,
      });
      fail(
        "reinstall",
        "the atomic all-host install terminal is non-success and cannot be promoted by topology observation",
      );
    }
  }
  let observedState = checkpoint.lastObservedState;
  if (interruptedOperationKey !== null) {
    observedState = {
      classification: `durable_${interruptedOperationState.state}`,
      operationKey: interruptedOperationKey,
      terminalReceiptPresent: interruptedOperationState.terminalReceiptPresent,
      actualStateRecorded: false,
      previousStateRestorationClaimed: false,
    };
  } else if (checkpoint.phase === "purging") {
    try {
      const current = (await runtime.baselineInventory(recorder, targets)).public;
      observedState =
        JSON.stringify(current) === JSON.stringify(checkpoint.baseline.initialInventory)
          ? {
              classification: "installed_baseline_unchanged",
              actualStateRecorded: true,
              previousStateRestorationClaimed: false,
            }
          : await runtime.inspectFailureState(recorder, targets, candidate, "purge");
    } catch {
      observedState = await runtime.inspectFailureState(recorder, targets, candidate, "purge");
    }
  } else if (checkpoint.phase === "purge-retry-in-progress") {
    observedState = await runtime.inspectFailureState(recorder, targets, candidate, "purge");
  } else if (recoveryPhases.has(checkpoint.phase)) {
    observedState = await runtime.inspectRecoveryState(recorder, targets, candidate);
  }
  if (recoveryPhases.has(checkpoint.phase)) {
    transitionCheckpoint(privateDirectory, checkpoint, checkpoint.phase, observedState);
  }
  const plan =
    checkpoint.phase === "purging"
      ? {
          stages: ["purge", "clean-assertion", "reinstall", "post-install"],
          hostCloseRetry: false,
          hostsToInstall: [...HOSTS],
          requireOriginalBaseline: new Set(["none", "prepared"]).has(
            interruptedOperationState.state,
          ),
          consumeReinstallRetry: false,
        }
      : checkpoint.phase === "purge-retry-in-progress"
        ? {
            stages: ["purge", "clean-assertion", "reinstall", "post-install"],
            hostCloseRetry: true,
            hostsToInstall: [...HOSTS],
            requireOriginalBaseline: false,
            consumeReinstallRetry: false,
          }
        : checkpoint.phase === "reinstalling"
          ? {
              stages: new Set(["none", "prepared"]).has(
                interruptedOperationState.state,
              )
                ? ["clean-assertion", "reinstall", "post-install"]
                : ["reinstall", "post-install"],
              hostCloseRetry: false,
              hostsToInstall: [...HOSTS],
              requireOriginalBaseline: false,
              consumeReinstallRetry: false,
            }
          : checkpoint.phase === "reinstall-retry-in-progress"
            ? {
                stages: new Set(["none", "prepared"]).has(
                  interruptedOperationState.state,
                )
                  ? ["clean-assertion", "reinstall", "post-install"]
                  : ["reinstall", "post-install"],
                hostCloseRetry: false,
                hostsToInstall: [...HOSTS],
                requireOriginalBaseline: false,
                consumeReinstallRetry: false,
              }
          : recoveryPlanForPhase(checkpoint, observedState, { hostAppsClosedConfirmed });
  if (plan.finalizeOnly) {
    return restoreFinalVerificationSnapshot(report, checkpoint);
  }
  if (plan.requireOriginalBaseline) {
    await assertOriginalBaselineUnchanged(
      recorder,
      targets,
      checkpoint,
      runtime.baselineInventory,
    );
  }
  if (plan.consumeReinstallRetry) {
    checkpoint.recovery.reinstallRetriesUsed += 1;
    checkpoint.recovery.reinstallRetryAdmission = reinstallRetryAdmissionFor(
      checkpoint,
      candidate,
    );
    transitionCheckpoint(privateDirectory, checkpoint, "reinstall-retry-in-progress", {
      classification: "atomic_all_host_reinstall_retry_write_ahead",
      operationKey: "install-retry",
      retryNumber: checkpoint.recovery.reinstallRetriesUsed,
      actualStateRecorded: true,
      previousStateRestorationClaimed: false,
    });
    testHooks.afterReinstallRetryWriteAhead?.();
  }
  const outcome = await executeMutationPlan(
    {
      purge: () =>
        runtime.purgeCandidate(recorder, report, targets, candidate, privateDirectory, checkpoint, {
          hostCloseRetry: plan.hostCloseRetry,
        }),
      assertClean: () =>
        runtime.assertClean(recorder, report, targets, privateDirectory, checkpoint),
      install: () =>
        runtime.installCandidate(
          recorder,
          report,
          candidate,
          privateDirectory,
          checkpoint,
        ),
      assertFinal: async () => {
        const finalizationId = beginFinalizationClaim(
          privateDirectory,
          checkpoint,
          {
            testId: report.testId,
            sourceCommit: report.source.commit,
          },
        );
        const finalState = await runFinalVerificationOnce(
          privateDirectory,
          checkpoint,
          () =>
            runtime.assertFinalInstalled(
              recorder,
              report,
              targets,
              candidate,
              privateDirectory,
            ),
          {
            testId: report.testId,
            sourceCommit: report.source.commit,
            finalizationId,
          },
        );
        return finalState;
      },
      inspectFailure: (stage) =>
        runtime.inspectFailureState(recorder, targets, candidate, stage),
    },
    plan.stages,
  );
  reconcileMutationTelemetry(report, privateDirectory, checkpoint);
  outcome.reinstallAttempted = report.mutation.reinstallAttempted;
  if (outcome.status === "complete") {
    if (
      lifecycleStep === null ||
      typeof lifecycleStep !== "object" ||
      Array.isArray(lifecycleStep) ||
      typeof lifecycleStep.id !== "string" ||
      typeof lifecycleStep.label !== "string" ||
      !Number.isFinite(lifecycleStep.started)
    ) {
      fail("finalizing", "the completed lifecycle step cannot be sealed without its exact context");
    }
    outcome.completedAt = new Date().toISOString();
    const prospectiveReport = structuredClone(report);
    prospectiveReport.steps.push({
      id: lifecycleStep.id,
      label: lifecycleStep.label,
      status: "passed",
      durationMs: Math.max(0, Date.now() - lifecycleStep.started),
      category: null,
      commandId: null,
    });
    applyMutationOutcome(prospectiveReport, outcome);
    reconcileMutationTelemetry(prospectiveReport, privateDirectory, checkpoint);
    const finalVerification = makeFinalVerificationSnapshot(
      prospectiveReport,
      outcome.finalState,
    );
    const finalizationId = checkpoint.lastObservedState?.finalizationId;
    if (
      checkpoint.phase !== "finalizing" ||
      checkpoint.lastObservedState?.classification !==
        "candidate_installed_final_verification_in_progress" ||
      !UUID_V4_PATTERN.test(finalizationId ?? "") ||
      checkpoint.lastObservedState?.testId !== prospectiveReport.testId ||
      checkpoint.lastObservedState?.sourceCommit !== prospectiveReport.source.commit
    ) {
      fail("finalizing", "the completed verifier is not bound to its durable finalization claim");
    }
    const priorPhase = checkpoint.phase;
    const priorObservedState = structuredClone(checkpoint.lastObservedState);
    let sealed;
    try {
      sealed = runtime.sealPublicResult(
        privateDirectory,
        prospectiveReport,
        finalVerification,
        { finalizationId },
      );
      if (
        JSON.stringify(sealed.report) !== JSON.stringify(prospectiveReport) ||
        sealed.receipt.finalVerificationSha256 !== finalVerification.sha256 ||
        sealed.receipt.finalizationId !== finalizationId ||
        sealed.receipt.testId !== prospectiveReport.testId ||
        sealed.receipt.sourceCommit !== prospectiveReport.source.commit
      ) {
        fail("finalizing", "the sealed public result differs from the prospective passed report");
      }
      runtime.commitFinalVerified(privateDirectory, checkpoint, {
        classification: "candidate_installed_verified",
        finalizationId,
        testId: prospectiveReport.testId,
        installedHosts: [...HOSTS],
        sourceCommit: prospectiveReport.source.commit,
        finalVerification,
        sealedPublicResult: {
          receiptSha256: sealed.receiptSha256,
          sealSha256: sealed.receipt.sealSha256,
          resultJsonSha256: sealed.receipt.files["result.json"].sha256,
        },
        actualStateRecorded: true,
        previousStateRestorationClaimed: false,
      });
    } catch (error) {
      checkpoint.phase = priorPhase;
      checkpoint.lastObservedState = priorObservedState;
      throw error;
    }
    for (const key of Object.keys(report)) delete report[key];
    Object.assign(report, structuredClone(sealed.report));
    outcome.reportSealed = true;
  } else if (outcome.status === "failed") {
    if (checkpoint.phase === "finalizing") {
      outcome.phase = "finalizing";
      outcome.failureState = finalizationFailureState(checkpoint);
      return outcome;
    }
    outcome.failureState = selectFailureState(checkpoint, outcome.failureState);
    const failurePhase =
      outcome.phase === "reinstall"
        ? "reinstall-failed"
        : outcome.phase === "post-install"
          ? "post-install-failed"
          : "purge-failed";
    transitionCheckpoint(
      privateDirectory,
      checkpoint,
      failurePhase,
      outcome.failureState ?? {
        classification: "unsafe_to_classify",
        previousStateRestorationClaimed: false,
      },
    );
  }
  return outcome;
}

export function applyMutationOutcome(report, outcome) {
  report.mutation.reinstallAttempted =
    report.mutation.reinstallAttempted || outcome.reinstallAttempted;
  if (outcome.status === "complete") {
    report.mutation.phase = "installed";
    report.mutation.lifecycleOutcome = "reinstall_verified";
    report.mutation.finalState = "installed";
    report.mutation.nextAction = "complete_record_and_replay_manual_observations";
    report.automatedResult = "passed";
    report.manualResult = "pending";
    report.overallResult = "pending";
    report.completedAt = outcome.completedAt ?? new Date().toISOString();
    return;
  }
  if (outcome.status === "awaiting-host-close") {
    report.mutation.phase = "awaiting-host-close";
    report.mutation.lifecycleOutcome = "partial_purge_awaiting_one_confirmed_retry";
    report.mutation.finalState = "partial_purge";
    report.mutation.nextAction = "close_listed_host_apps_then_resume_the_same_exact_purge";
    report.assertions.deferredResidue = outcome.residue;
    report.automatedResult = "paused";
    report.manualResult = "not-run";
    report.overallResult = "pending";
    return;
  }
  report.mutation.phase = outcome.phase;
  const actualStateRecorded = outcome.failureState?.actualStateRecorded === true;
  report.mutation.lifecycleOutcome = actualStateRecorded
    ? "failed_with_actual_state_recorded"
    : "failed_with_state_unclassified";
  report.mutation.finalState = actualStateRecorded
    ? outcome.failureState.classification
    : "unknown_unverified";
  report.mutation.nextAction = nextActionForFailure(outcome.phase, outcome.failureState);
  report.assertions.failureState = outcome.failureState ?? null;
  report.automatedResult = "failed";
  report.manualResult = "not-run";
  report.overallResult = "failed";
  report.completedAt = new Date().toISOString();
  report.failure = {
    category: outcome.error instanceof AcceptanceError ? outcome.error.category : "harness",
    message: sanitizedMessage(outcome.error),
    commandId: outcome.error instanceof AcceptanceError ? outcome.error.commandId : null,
  };
}

function createEvidenceDirectories() {
  const outputDirectory = realpathSync(
    mkdtempSync(join(tmpdir(), RESULT_DIRECTORY_PREFIX)),
  );
  chmodSync(outputDirectory, 0o700);
  ensurePrivateDirectory(PRIVATE_PARENT);
  requireCanonicalOwnedEntry(PRIVATE_PARENT, "private acceptance parent", "directory");
  requireOwnerOnly(PRIVATE_PARENT, "the private acceptance parent");
  const privateDirectory = realpathSync(
    mkdtempSync(join(PRIVATE_PARENT, PRIVATE_DIRECTORY_PREFIX)),
  );
  chmodSync(privateDirectory, 0o700);
  return { outputDirectory, privateDirectory };
}

export function persistRun(
  report,
  outputDirectory,
  privateDirectory,
  { preserveManual = false, evidenceTestHooks = {} } = {},
) {
  recoverEvidenceTransaction(privateDirectory);
  const files = publicReportBytesForWrite(outputDirectory, report, {
    preserveManual,
    privateValues: [privateDirectory, outputDirectory],
  });
  const updatedAt = new Date().toISOString();
  const manifest = refreshedPrivateEvidenceManifest(
    privateDirectory,
    outputDirectory,
    report,
    { updatedAt, resultOverride: true },
  );
  commitEvidenceTransaction(
    privateDirectory,
    outputDirectory,
    report.testId,
    "public-report",
    [
      { role: "result-json", bytes: files["result.json"] },
      { role: "result-markdown", bytes: files["result.md"] },
      { role: "manual-observations", bytes: files["manual-observations.md"] },
    ],
    Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`),
    evidenceTestHooks,
  );
}

export function persistBlockedLifecycleJournalOutcome(
  privateDirectory,
  checkpoint,
  report,
  outputDirectory,
) {
  const disposition = lifecycleJournalResumeDisposition(privateDirectory);
  if (disposition.status === "claimed_active") {
    fail(
      "lifecycle-orphan-active",
      "a previously claimed lifecycle process group is still active; resume and replay are forbidden",
    );
  }
  if (disposition.status === "clear") return null;
  const state = disposition.state;
  if (
    state.state !== "blocked_unverifiable" ||
    !new Set([
      "purge-initial",
      "purge-host-close-retry",
      "install-initial",
      "install-retry",
    ]).has(state.operationKey) ||
    !new Set([1, 2]).has(state.attempt) ||
    !/^[a-f0-9]{64}$/u.test(state.operationSha256 ?? "")
  ) {
    fail("lifecycle-recovery", "the blocked lifecycle receipt identity is incomplete");
  }
  transitionCheckpoint(privateDirectory, checkpoint, "blocked-unverifiable", {
    classification: "blocked_unverifiable",
    operationKey: state.operationKey,
    attempt: state.attempt,
    operationSha256: state.operationSha256,
    terminalReceiptPresent: false,
    actualStateRecorded: false,
    previousStateRestorationClaimed: false,
  });
  report.mutation.started = true;
  report.mutation.phase = state.operationKey.startsWith("install-") ? "reinstall" : "purge";
  if (state.operationKey.startsWith("install-")) {
    report.mutation.reinstallAttempted = true;
    report.mutation.reinstallAttempts = Math.max(
      report.mutation.reinstallAttempts,
      state.attempt,
    );
  } else {
    report.mutation.purgeCommandAttempts = Math.max(
      report.mutation.purgeCommandAttempts,
      state.attempt,
    );
    report.mutation.trustResetAttempts = Math.max(
      report.mutation.trustResetAttempts,
      state.attempt,
    );
    if (state.operationKey === "purge-host-close-retry") {
      report.mutation.hostCloseRetriesUsed = Math.max(
        report.mutation.hostCloseRetriesUsed,
        1,
      );
    }
  }
  report.mutation.lifecycleOutcome = "blocked_unverifiable";
  report.mutation.finalState = "unknown_unverified";
  report.mutation.nextAction =
    "manual_observation_only_no_replay_or_acceptance_claim";
  report.mutation.originalCacheDataTrustRestorationClaimed = false;
  report.assertions.lifecycleRecovery = {
    classification: "blocked_unverifiable",
    operationKey: state.operationKey,
    attempt: state.attempt,
    receiptSha256: state.operationSha256,
  };
  report.automatedResult = "failed";
  report.manualResult = "not-run";
  report.overallResult = "failed";
  report.completedAt = new Date().toISOString();
  report.failure = {
    category: "lifecycle-interrupted",
    message:
      "A claimed lifecycle has no verified terminal receipt; replay and acceptance PASS are blocked.",
    commandId: null,
  };
  persistRun(report, outputDirectory, privateDirectory);
  return { status: "blocked_unverifiable", state: structuredClone(state) };
}

export function persistRunAndFinalizeCheckpoint(
  report,
  outputDirectory,
  privateDirectory,
  checkpoint,
  { afterPublicPersist = () => {} } = {},
) {
  let persistedReport = report;
  let sealed = null;
  if (report.automatedResult === "passed" && checkpoint?.phase === "final-verified") {
    sealed = validateSealedPublicResult(privateDirectory, report.testId);
    const binding = checkpoint.lastObservedState?.sealedPublicResult;
    if (
      checkpoint.lastObservedState?.finalizationId !== sealed.receipt.finalizationId ||
      checkpoint.lastObservedState?.testId !== sealed.receipt.testId ||
      checkpoint.lastObservedState?.sourceCommit !== sealed.receipt.sourceCommit ||
      binding?.receiptSha256 !== sealed.receiptSha256 ||
      binding?.sealSha256 !== sealed.receipt.sealSha256 ||
      binding?.resultJsonSha256 !== sealed.receipt.files["result.json"].sha256 ||
      checkpoint.lastObservedState?.finalVerification?.sha256 !==
        sealed.receipt.finalVerificationSha256
    ) {
      fail("finalizing", "the final-verified checkpoint is not bound to the sealed public result");
    }
    persistedReport = sealed.report;
    persistRun(persistedReport, outputDirectory, privateDirectory);
  } else {
    persistRun(report, outputDirectory, privateDirectory);
  }
  afterPublicPersist();
  if (report.automatedResult === "passed" && checkpoint?.phase === "final-verified") {
    transitionCheckpoint(privateDirectory, checkpoint, "installed", {
      classification: "candidate_installed_verified",
      finalizationId: sealed.receipt.finalizationId,
      testId: sealed.receipt.testId,
      installedHosts: [...HOSTS],
      sourceCommit: persistedReport.source.commit,
      finalVerificationSha256:
        checkpoint.lastObservedState?.finalVerification?.sha256 ?? null,
      sealedPublicResult: {
        receiptSha256: sealed.receiptSha256,
        sealSha256: sealed.receipt.sealSha256,
        resultJsonSha256: sealed.receipt.files["result.json"].sha256,
      },
      publicResultPersistedBeforeCompletion: true,
      actualStateRecorded: true,
      previousStateRestorationClaimed: false,
    });
  }
}

function reportRunLocations(outputDirectory, privateDirectory, report) {
  console.log(`Public sanitized result directory: ${outputDirectory}`);
  console.log(`Private evidence directory: ${privateDirectory}`);
  if (report.automatedResult === "paused") {
    console.log("Close only the host apps named in the categorical deferred result, then resume:");
    console.log(
      `  node tools/reinstall_cycle_acceptance.mjs --resume ${JSON.stringify(privateDirectory)} ` +
        "--confirm-host-apps-closed",
    );
  } else if (report.automatedResult === "passed") {
    console.log("Automated checks passed; complete the Record & Replay manual observations next.");
    console.log(`Manual checklist: ${join(outputDirectory, "manual-observations.md")}`);
    console.log("Bind the reviewed private recording before marking its checklist field PASS:");
    console.log(
      `  node tools/reinstall_cycle_acceptance.mjs --bind-recording ` +
        `${JSON.stringify(privateDirectory)} RECORDING_FILE ${JSON.stringify(report.testId)}`,
    );
    console.log(
      "After every categorical field is PASS, FAIL, NOT_OBSERVED, or BLOCKED, create the public ZIP:",
    );
    console.log(
      `  node tools/reinstall_cycle_acceptance.mjs --pack ${JSON.stringify(outputDirectory)} ` +
        `--private-evidence ${JSON.stringify(privateDirectory)}`,
    );
  }
}

async function performLifecycleStep(report, id, label, action) {
  const started = Date.now();
  process.stdout.write(`- ${label} ... `);
  const outcome = await action({ id, label, started });
  const status =
    outcome.status === "complete"
      ? "passed"
      : outcome.status === "awaiting-host-close"
        ? "paused"
        : "failed";
  if (outcome.reportSealed !== true) {
    report.steps.push({
      id,
      label,
      status,
      durationMs: Date.now() - started,
      category:
        outcome.error instanceof AcceptanceError ? outcome.error.category : null,
      commandId:
        outcome.error instanceof AcceptanceError ? outcome.error.commandId : null,
    });
  }
  process.stdout.write(`${status}\n`);
  return outcome;
}

async function runInitialAcceptance() {
  const { outputDirectory, privateDirectory } = createEvidenceDirectories();
  const report = makeReport();
  initializePrivateEvidenceManifest(privateDirectory, outputDirectory, report);
  const recorder = new CommandRecorder(privateDirectory, report);
  const targets = defaultTargets();
  const lock = new SingleRunLock(privateDirectory);
  const machineLease = new MachineAcceptanceLease(
    PRIVATE_PARENT,
    privateDirectory,
    report.testId,
  );
  let checkpoint = null;
  let exactBaselineBindings = null;
  let machineLeaseOwned = false;
  let publicStatePersisted = false;
  lock.acquire();
  try {
    try {
      machineLease.acquire();
      machineLeaseOwned = true;
      await performStep(report, "environment", "Verify the real Mac and host prerequisites", () => {
        const environment = verifyEnvironment(recorder, report);
        verifyHosts(recorder, report);
        return environment;
      });
      await performStep(report, "source", "Pin the open pull-request source commit", () =>
        verifySource(recorder, report),
      );
      await performStep(
        report,
        "baseline",
        "Inventory the installed purged-same-machine baseline without private content",
        async () => {
          const inventory = await baselineInventory(recorder, targets);
          report.baseline.initialState = "installed";
          report.baseline.installedHosts = [...HOSTS];
          report.baseline.inventory = inventory.public;
          exactBaselineBindings = structuredClone(inventory.exactBindings);
          return { baseline: BASELINE, initialState: "installed" };
        },
      );
      const candidate = await performStep(
        report,
        "artifact-gate",
        "Prepare exact-commit npm and successful Native CI inputs",
        () => prepareCandidate(recorder, report, privateDirectory),
      );
      checkpoint = candidateCheckpoint(
        outputDirectory,
        report,
        candidate,
        exactBaselineBindings,
      );
      persistRun(report, outputDirectory, privateDirectory);
      writeCheckpoint(privateDirectory, checkpoint);
      machineLease.bindCheckpoint(checkpoint);
      verifyResumeSource(recorder, report);
      const outcome = await performLifecycleStep(
        report,
        "lifecycle",
        "Run purge, zero-residue assertion, and exact reinstall",
        (lifecycleStep) =>
          runMutation(
            recorder,
            report,
            targets,
            candidate,
            privateDirectory,
            checkpoint,
            { lifecycleStep },
          ),
      );
      if (outcome.reportSealed !== true) applyMutationOutcome(report, outcome);
    } catch (error) {
      if (report.automatedResult === "running") {
        report.automatedResult = "failed";
        report.manualResult = "not-run";
        report.overallResult = "failed";
        report.completedAt = new Date().toISOString();
        const actualStateRecorded =
          report.mutation.started &&
          checkpoint?.lastObservedState?.actualStateRecorded === true;
        report.mutation.lifecycleOutcome = report.mutation.started
          ? actualStateRecorded
            ? "failed_with_actual_state_recorded"
            : "failed_with_state_unclassified"
          : "preflight_failed_without_mutation";
        report.mutation.finalState = report.mutation.started
          ? actualStateRecorded
            ? checkpoint.lastObservedState.classification
            : "unknown_unverified"
          : report.baseline.initialState === "installed"
            ? "installed_unchanged"
            : "not_checked";
        report.mutation.nextAction = report.mutation.started
          ? "review_the_existing_checkpoint_actual_state_without_claiming_restoration"
          : "resolve_preflight_without_lifecycle_mutation";
        report.failure = {
          category: error instanceof AcceptanceError ? error.category : "harness",
          message: sanitizedMessage(error, [
            [privateDirectory, "$PRIVATE_EVIDENCE"],
            [outputDirectory, "$PUBLIC_RESULT"],
          ]),
          commandId: error instanceof AcceptanceError ? error.commandId : null,
        };
      }
    }
    persistRunAndFinalizeCheckpoint(
      report,
      outputDirectory,
      privateDirectory,
      checkpoint,
    );
    publicStatePersisted = true;
  } finally {
    if (machineLeaseOwned) {
      if (publicStatePersisted) {
        if (report.automatedResult === "passed" && checkpoint?.phase === "installed") {
          machineLease.releaseCompleted(checkpoint);
        } else if (report.automatedResult === "paused") {
          machineLease.markPaused();
        } else if (report.automatedResult === "failed" && report.mutation.started === false) {
          machineLease.releaseCompleted(checkpoint);
        }
      } else if (report.mutation.started === false) {
        try {
          machineLease.releaseAbortedPreflight();
        } catch (error) {
          console.error(`Machine lease recovery error: ${sanitizedMessage(error)}`);
        }
      }
    }
    lock.release();
  }
  if (new Set(["failed", "paused"]).has(report.automatedResult)) {
    try {
      createDiagnosticBundle(privateDirectory, outputDirectory);
    } catch (error) {
      console.error(`Result ZIP error: ${sanitizedMessage(error)}`);
    }
  }
  reportRunLocations(outputDirectory, privateDirectory, report);
  if (report.automatedResult === "failed") process.exitCode = 1;
  return { report, outputDirectory, privateDirectory };
}

export function executePhaseAwareResumePreflight(
  phase,
  { verifyEnvironment: environmentCheck, verifyHosts: hostCheck, verifySource: sourceCheck },
) {
  for (const operation of [environmentCheck, hostCheck, sourceCheck]) {
    if (typeof operation !== "function") {
      fail("recovery", "the phase-aware resume preflight is incomplete");
    }
  }
  if (phase === "finalizing") {
    fail("recovery", "the one-shot final review was entered and cannot be replayed");
  }
  if (phase === "final-verified") return "finalize-only";
  environmentCheck();
  const sourceOnlyPhases = new Set([
    "reinstalling",
    "reinstall-retry-in-progress",
    "reinstall-failed",
    "post-install-checks",
    "post-install-failed",
  ]);
  if (!sourceOnlyPhases.has(phase)) hostCheck();
  sourceCheck();
  return sourceOnlyPhases.has(phase) ? "source-only" : "full";
}

function finalizeSealedCheckpointResume(
  privateDirectory,
  { hostAppsClosedConfirmed = false } = {},
) {
  recoverEvidenceTransaction(privateDirectory);
  requireExactPrivateMode(
    privateDirectory,
    "private acceptance directory",
    "directory",
    0o700,
  );
  const checkpointPath = join(privateDirectory, CHECKPOINT_NAME);
  requireExactPrivateMode(checkpointPath, "acceptance checkpoint", "file", 0o600);
  const checkpoint = parseJson(
    readFileSync(checkpointPath, "utf8"),
    "checkpoint",
    "the private acceptance checkpoint is invalid",
  );
  if (!new Set(["finalizing", "final-verified"]).has(checkpoint?.phase)) {
    return null;
  }
  if (hostAppsClosedConfirmed) {
    fail(
      "usage",
      "--confirm-host-apps-closed is not valid for a sealed finalize-only checkpoint",
    );
  }
  if (
    checkpoint.schema !== CHECKPOINT_SCHEMA ||
    !UUID_V4_PATTERN.test(checkpoint.testId ?? "") ||
    !/^[a-f0-9]{40}$/u.test(checkpoint.sourceCommit ?? "") ||
    typeof checkpoint.reportDirectory !== "string"
  ) {
    fail("checkpoint", "the finalize-only checkpoint identity is incomplete");
  }
  if (!pathPresent(sealedPublicDirectory(privateDirectory))) {
    fail(
      "recovery",
      "the one-shot final review was entered without a complete sealed result and cannot be replayed",
    );
  }
  const sealed = validateSealedPublicResult(privateDirectory);
  const reportDirectory = resolve(checkpoint.reportDirectory);
  requireExactPrivateMode(
    reportDirectory,
    "public acceptance result directory",
    "directory",
    0o700,
  );
  const existingReport = validateExistingPublicReports(reportDirectory);
  if (
    existingReport.testId !== checkpoint.testId ||
    existingReport.source.commit !== checkpoint.sourceCommit ||
    sealed.receipt.testId !== checkpoint.testId ||
    sealed.receipt.sourceCommit !== checkpoint.sourceCommit ||
    sealed.report.source.commit !== checkpoint.sourceCommit
  ) {
    fail("finalizing", "the sealed result does not bind the checkpoint source commit");
  }
  validatePrivateEvidenceManifest(
    privateDirectory,
    reportDirectory,
    sealed.report.testId,
  );
  const sealedBinding = {
    receiptSha256: sealed.receiptSha256,
    sealSha256: sealed.receipt.sealSha256,
    resultJsonSha256: sealed.receipt.files["result.json"].sha256,
  };
  const observed = checkpoint.lastObservedState;
  const identityMatches =
    UUID_V4_PATTERN.test(observed?.finalizationId ?? "") &&
    observed.finalizationId === sealed.receipt.finalizationId &&
    observed.testId === sealed.receipt.testId &&
    observed.sourceCommit === sealed.receipt.sourceCommit &&
    checkpoint.sourceCommit === sealed.receipt.sourceCommit;
  if (checkpoint.phase === "finalizing") {
    if (
      observed?.classification !==
        "candidate_installed_final_verification_in_progress" ||
      !identityMatches
    ) {
      fail(
        "recovery",
        "the interrupted finalization is not bound to one complete matching sealed result",
      );
    }
    transitionCheckpoint(privateDirectory, checkpoint, "final-verified", {
      classification: "candidate_installed_verified",
      finalizationId: sealed.receipt.finalizationId,
      testId: sealed.receipt.testId,
      installedHosts: [...HOSTS],
      sourceCommit: sealed.receipt.sourceCommit,
      finalVerification: structuredClone(sealed.receipt.finalVerification),
      sealedPublicResult: sealedBinding,
      actualStateRecorded: true,
      previousStateRestorationClaimed: false,
    });
  } else {
    const binding = observed?.sealedPublicResult;
    if (
      observed?.classification !== "candidate_installed_verified" ||
      !identityMatches ||
      observed?.finalVerification?.sha256 !==
        sealed.receipt.finalVerificationSha256 ||
      binding?.receiptSha256 !== sealedBinding.receiptSha256 ||
      binding?.sealSha256 !== sealedBinding.sealSha256 ||
      binding?.resultJsonSha256 !== sealedBinding.resultJsonSha256
    ) {
      fail("finalizing", "the finalize-only checkpoint changed after result sealing");
    }
  }
  persistRun(sealed.report, reportDirectory, privateDirectory);
  transitionCheckpoint(privateDirectory, checkpoint, "installed", {
    classification: "candidate_installed_verified",
    finalizationId: sealed.receipt.finalizationId,
    testId: sealed.receipt.testId,
    installedHosts: [...HOSTS],
    sourceCommit: sealed.report.source.commit,
    finalVerificationSha256: sealed.receipt.finalVerificationSha256,
    sealedPublicResult: sealedBinding,
    publicResultPersistedBeforeCompletion: true,
    actualStateRecorded: true,
    previousStateRestorationClaimed: false,
  });
  return {
    checkpoint,
    report: sealed.report,
    reportDirectory,
  };
}

async function resumeAcceptance(
  privateDirectoryArgument,
  { hostAppsClosedConfirmed = false } = {},
) {
  if (!privateDirectoryArgument) fail("usage", "--resume requires a private evidence directory");
  const privateDirectory = resolve(privateDirectoryArgument);
  const lock = new SingleRunLock(privateDirectory);
  lock.acquire();
  let checkpoint;
  let report;
  let reportDirectory;
  let machineLease = null;
  let machineLeaseOwned = false;
  let publicStatePersisted = false;
  try {
    const leaseCheckpoint = readMachineLeaseCheckpoint(privateDirectory);
    machineLease = new MachineAcceptanceLease(
      PRIVATE_PARENT,
      privateDirectory,
      leaseCheckpoint.testId,
    );
    machineLease.acquire(leaseCheckpoint);
    machineLeaseOwned = true;
    const finalized = finalizeSealedCheckpointResume(privateDirectory, {
      hostAppsClosedConfirmed,
    });
    if (finalized !== null) {
      checkpoint = finalized.checkpoint;
      report = finalized.report;
      reportDirectory = finalized.reportDirectory;
      publicStatePersisted = true;
      reportRunLocations(
        finalized.reportDirectory,
        privateDirectory,
        finalized.report,
      );
      return {
        report: finalized.report,
        outputDirectory: finalized.reportDirectory,
        privateDirectory,
      };
    }
    ({ checkpoint, report, reportDirectory } = await validateCheckpoint(privateDirectory));
    const blockedJournal = persistBlockedLifecycleJournalOutcome(
      privateDirectory,
      checkpoint,
      report,
      reportDirectory,
    );
    if (blockedJournal !== null) {
      publicStatePersisted = true;
      process.exitCode = 1;
      reportRunLocations(reportDirectory, privateDirectory, report);
      return {
        report,
        outputDirectory: reportDirectory,
        privateDirectory,
      };
    }
    assertLifecycleJournalCanResume(privateDirectory);
    if (hostAppsClosedConfirmed && checkpoint.phase !== "awaiting-host-close") {
      fail("usage", "--confirm-host-apps-closed is valid only for an awaiting-host-close checkpoint");
    }
    const recorder = new CommandRecorder(privateDirectory, report);
    const targets = defaultTargets();
    report.automatedResult = "running";
    report.manualResult = "pending";
    report.overallResult = "pending";
    report.completedAt = null;
    report.failure = null;
    try {
      executePhaseAwareResumePreflight(checkpoint.phase, {
        verifyEnvironment: () => verifyEnvironment(recorder, report),
        verifyHosts: () => verifyHosts(recorder, report),
        verifySource: () => verifyResumeSource(recorder, report),
      });
      const candidate = candidateFromCheckpoint(checkpoint);
      const outcome = await performLifecycleStep(
        report,
        "lifecycle-resume",
        "Resume the existing exact-input lifecycle checkpoint",
        (lifecycleStep) =>
          runMutation(
            recorder,
            report,
            targets,
            candidate,
            privateDirectory,
            checkpoint,
            { hostAppsClosedConfirmed, lifecycleStep },
          ),
      );
      if (outcome.reportSealed !== true) applyMutationOutcome(report, outcome);
    } catch (error) {
      report.automatedResult = "failed";
      report.manualResult = "not-run";
      report.overallResult = "failed";
      report.completedAt = new Date().toISOString();
      const actualStateRecorded = checkpoint.lastObservedState?.actualStateRecorded === true;
      report.mutation.lifecycleOutcome = actualStateRecorded
        ? "failed_with_actual_state_recorded"
        : "failed_with_state_unclassified";
      report.mutation.finalState = actualStateRecorded
        ? checkpoint.lastObservedState.classification
        : "unknown_unverified";
      report.mutation.nextAction =
        "review_the_existing_checkpoint_actual_state_without_claiming_restoration";
      report.failure = {
        category: error instanceof AcceptanceError ? error.category : "harness",
        message: sanitizedMessage(error, [
          [privateDirectory, "$PRIVATE_EVIDENCE"],
          [reportDirectory, "$PUBLIC_RESULT"],
        ]),
        commandId: error instanceof AcceptanceError ? error.commandId : null,
      };
    }
    persistRunAndFinalizeCheckpoint(
      report,
      reportDirectory,
      privateDirectory,
      checkpoint,
    );
    publicStatePersisted = true;
  } finally {
    if (machineLeaseOwned && publicStatePersisted) {
      if (report?.automatedResult === "passed" && checkpoint?.phase === "installed") {
        machineLease.releaseCompleted(checkpoint);
      } else if (report?.automatedResult === "paused") {
        machineLease.markPaused();
      }
    }
    lock.release();
  }
  if (new Set(["failed", "paused"]).has(report.automatedResult)) {
    try {
      createDiagnosticBundle(privateDirectory, reportDirectory);
    } catch (error) {
      console.error(`Result ZIP error: ${sanitizedMessage(error)}`);
    }
    process.exitCode = 1;
  }
  reportRunLocations(reportDirectory, privateDirectory, report);
  return { report, outputDirectory: reportDirectory, privateDirectory };
}

function printHelp() {
  console.log(`Usage:
  node tools/reinstall_cycle_acceptance.mjs
  node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY
  node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY --confirm-host-apps-closed
  node tools/reinstall_cycle_acceptance.mjs --bind-recording PRIVATE_EVIDENCE_DIRECTORY RECORDING_FILE TEST_ID
  node tools/reinstall_cycle_acceptance.mjs --pack RESULT_DIRECTORY --private-evidence PRIVATE_EVIDENCE_DIRECTORY
  node tools/reinstall_cycle_acceptance.mjs --cleanup-private PRIVATE_EVIDENCE_DIRECTORY --test-id TEST_ID --public-zip-sha256 BUNDLE_SHA256 [--public-bundle BUNDLE_FILE | --allow-missing-public-bundle]

The first command gates an exact pull-request commit and successful matching
Native CI artifact, inventories the installed state, then uses only the packed
npx entrypoint for purge and reinstall. A deferred host-use marker is resumed
with the second command; the third is the explicit single retry after closing
only the named host apps. The fourth binds the reviewed private Record & Replay
capture. After every field is PASS, FAIL, NOT_OBSERVED, or BLOCKED, the fifth
creates the sanitized final ZIP. The sixth removes one exact private evidence
directory only after its diagnostic or final bundle digest is confirmed. Use
--public-bundle when the exact bundle was moved, or the explicit missing-bundle
flag only after retaining its recorded digest.`);
}

export {
  AcceptanceError,
  artifactDownloadTimeoutMs,
  bindRecordingReceipt,
  cleanupPrivateEvidence,
  CommandRecorder,
  assertNoKnownTransactionResidue,
  assertRegistrationState,
  assertSafeArchiveEntry,
  downloadImmutableArtifact,
  extractVerifiedTarGzip,
  extractVerifiedZip,
  exactResidueSnapshot,
  exactOwnedTreeBinding,
  filesystemResidueIsEmpty,
  inspectRecoveryState,
  inspectLaunchAgentTemporaryResidue,
  inspectKnownTransactionResidue,
  inspectStateDirectory,
  inspectStateResidue,
  inspectTrustTransactionResidue,
  codexHookInventory,
  commitPublicAssetIdentities,
  createSealedPublicResult,
  initializePrivateEvidenceManifest,
  makeReport,
  manualTemplate,
  measureInstalledSessionStart,
  packExisting,
  packSourceNpmCandidate,
  publicResidueSummary,
  requireLifecycleJsonEntry,
  publishSealedPublicResult,
  refreshPrivateEvidenceManifest,
  residueIsEmpty,
  validateArtifactMetadata,
  validateBuildSourceReceipt,
  validateNpmPackMetadata,
  validatePrivateEvidenceManifest,
  validatePublicAssertions,
  validatePublicText,
  validatePublicRuntimeIdentity,
  verifyGitHubAuthentication,
  verifyLifecycleHostAuthentication,
  verifyCacheMarketplaceShape,
  verifyManagedRootExact,
  verifyHosts,
  writeReports,
  zipReports,
};

export async function main(args = process.argv.slice(2)) {
  try {
    if (args.length === 0) {
      await runInitialAcceptance();
    } else if (args[0] === "--resume" && args.length === 2) {
      await resumeAcceptance(args[1]);
    } else if (
      args[0] === "--resume" &&
      args.length === 3 &&
      args[2] === "--confirm-host-apps-closed"
    ) {
      await resumeAcceptance(args[1], { hostAppsClosedConfirmed: true });
    } else if (args[0] === "--bind-recording" && args.length === 4) {
      bindRecordingReceipt(args[1], args[2], args[3]);
    } else if (
      args[0] === "--pack" &&
      args.length === 4 &&
      args[2] === "--private-evidence"
    ) {
      packExisting(args[1], args[3]);
    } else if (
      args[0] === "--cleanup-private" &&
      new Set([6, 7, 8]).has(args.length) &&
      args[2] === "--test-id" &&
      args[4] === "--public-zip-sha256" &&
      (args.length === 6 ||
        (args.length === 7 && args[6] === "--allow-missing-public-bundle") ||
        (args.length === 8 && args[6] === "--public-bundle"))
    ) {
      cleanupPrivateEvidence(args[1], args[3], args[5], {
        publicBundlePath: args.length === 8 ? args[7] : null,
        allowMissingBundle: args.length === 7,
      });
    } else if ((args[0] === "--help" || args[0] === "-h") && args.length === 1) {
      printHelp();
    } else {
      fail("usage", "use --help to see the supported reinstall acceptance commands");
    }
  } catch (error) {
    console.error(`Reinstall-cycle acceptance error: ${sanitizedMessage(error)}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  await main();
}
