#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  chmodSync,
  closeSync,
  constants as fsConstants,
  createReadStream,
  fsyncSync,
  linkSync,
  lstatSync,
  openSync,
  readFileSync,
  realpathSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const INTENT_SCHEMA = "opensocrates.lifecycle-operation-intent/1.0.0";
const CLAIM_SCHEMA = "opensocrates.lifecycle-operation-claim/1.0.0";
const TERMINAL_SCHEMA = "opensocrates.lifecycle-operation-terminal/1.0.0";
const MAX_STREAM_BYTES = 16 * 1024 * 1024;

function sha256Bytes(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256File(target) {
  const hash = createHash("sha256");
  return new Promise((resolvePromise, rejectPromise) => {
    const stream = createReadStream(target);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.once("error", rejectPromise);
    stream.once("end", () => resolvePromise(hash.digest("hex")));
  });
}

function exactKeys(value, keys) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    JSON.stringify(Object.keys(value).sort()) === JSON.stringify([...keys].sort())
  );
}

function requirePrivateEntry(target, kind, mode) {
  const info = lstatSync(target);
  if (
    info.isSymbolicLink() ||
    info.uid !== process.getuid() ||
    (kind === "directory" && !info.isDirectory()) ||
    (kind === "file" && (!info.isFile() || info.nlink !== 1)) ||
    (info.mode & 0o777) !== mode ||
    realpathSync(target) !== resolve(target)
  ) {
    throw new Error("unsafe lifecycle operation capsule path");
  }
  return info;
}

function syncEntry(target) {
  const descriptor = openSync(target, "r");
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
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

export function publishExclusiveJson(
  target,
  value,
  { singleWinner = false, afterPublish = () => {} } = {},
) {
  if (typeof afterPublish !== "function") {
    throw new Error("invalid lifecycle receipt publish hook");
  }
  const parent = dirname(target);
  requirePrivateEntry(parent, "directory", 0o700);
  const staging = resolve(
    parent,
    `.${basename(target)}.${process.pid}.${randomUUID()}.tmp`,
  );
  const descriptor = openSync(
    staging,
    fsConstants.O_CREAT |
      fsConstants.O_EXCL |
      fsConstants.O_WRONLY |
      fsConstants.O_NOFOLLOW,
    0o600,
  );
  try {
    writeFileSync(descriptor, `${JSON.stringify(value, null, 2)}\n`);
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
  chmodSync(staging, 0o600);
  requirePrivateEntry(staging, "file", 0o600);
  try {
    if (singleWinner) {
      linkSync(staging, target);
    } else {
      if (pathPresent(target)) throw new Error("lifecycle receipt already exists");
      renameSync(staging, target);
    }
    syncEntry(parent);
    afterPublish({ target, staging, singleWinner });
    if (singleWinner) {
      unlinkSync(staging);
      syncEntry(parent);
    }
  } finally {
    if (pathPresent(staging)) {
      const info = lstatSync(staging);
      if (!info.isSymbolicLink() && info.isFile() && info.uid === process.getuid()) {
        unlinkSync(staging);
        syncEntry(parent);
      }
    }
  }
  requirePrivateEntry(target, "file", 0o600);
}

function openExclusiveStream(target) {
  return openSync(
    target,
    fsConstants.O_CREAT |
      fsConstants.O_EXCL |
      fsConstants.O_WRONLY |
      fsConstants.O_NOFOLLOW,
    0o600,
  );
}

function safeEnvironment(value) {
  if (!exactKeys(value, Object.keys(value))) return false;
  const forbidden = /(?:TOKEN|SECRET|CREDENTIAL|PASSWORD|AUTH|COOKIE|NODE_OPTIONS|BASH_ENV)/iu;
  return Object.entries(value).every(
    ([key, item]) =>
      /^[A-Za-z_][A-Za-z0-9_]*$/u.test(key) &&
      !forbidden.test(key) &&
      typeof item === "string" &&
      !item.includes("\0"),
  );
}

function lifecycleGroupMembers() {
  const inspected = spawnSync("/bin/ps", ["-axo", "pid=,pgid="], {
    encoding: "utf8",
    env: { PATH: "/usr/bin:/bin", LANG: "C", LC_ALL: "C" },
    maxBuffer: 4 * 1024 * 1024,
  });
  if (inspected.error || inspected.status !== 0 || typeof inspected.stdout !== "string") {
    return null;
  }
  const inspectionPid = Number.isSafeInteger(inspected.pid) ? inspected.pid : null;
  const members = [];
  for (const line of inspected.stdout.split(/\r?\n/u)) {
    const match = line.match(/^\s*(\d+)\s+(\d+)\s*$/u);
    if (!match) continue;
    const pid = Number(match[1]);
    const processGroupId = Number(match[2]);
    if (
      processGroupId === process.pid &&
      pid !== process.pid &&
      pid !== inspectionPid
    ) {
      members.push(pid);
    }
  }
  return members;
}

function terminateLifecycleDescendants() {
  const members = lifecycleGroupMembers();
  if (members === null) return false;
  for (const pid of members) {
    try {
      process.kill(pid, "SIGKILL");
    } catch (error) {
      if (error?.code !== "ESRCH") return false;
    }
  }
  return true;
}

async function waitForLifecycleGroupQuiescence(timeoutMs = 2_000) {
  const deadline = Date.now() + timeoutMs;
  let consecutiveEmptyChecks = 0;
  while (Date.now() < deadline) {
    const members = lifecycleGroupMembers();
    if (members === null) return false;
    if (members.length === 0) {
      consecutiveEmptyChecks += 1;
      if (consecutiveEmptyChecks >= 2) return true;
    } else {
      consecutiveEmptyChecks = 0;
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 50));
  }
  return false;
}

async function main() {
  if (process.argv.length !== 3 || typeof process.getuid !== "function") process.exit(90);
  const operationDirectory = resolve(process.argv[2]);
  requirePrivateEntry(operationDirectory, "directory", 0o700);
  const intentPath = resolve(operationDirectory, "intent.json");
  requirePrivateEntry(intentPath, "file", 0o600);
  const intentBytes = readFileSync(intentPath);
  const intent = JSON.parse(intentBytes.toString("utf8"));
  const intentKeys = [
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
  ];
  if (
    !exactKeys(intent, intentKeys) ||
    intent.schema !== INTENT_SCHEMA ||
    !/^[0-9a-f-]{36}$/u.test(intent.operationId) ||
    !/^[a-z0-9-]+$/u.test(intent.operationKey) ||
    !Number.isSafeInteger(intent.sequence) ||
    intent.sequence < 1 ||
    !Number.isSafeInteger(intent.attempt) ||
    intent.attempt < 1 ||
    typeof intent.label !== "string" ||
    intent.label.length === 0 ||
    typeof intent.executable !== "string" ||
    !intent.executable.startsWith("/") ||
    realpathSync(intent.executable) !== intent.executable ||
    !statSync(intent.executable).isFile() ||
    !Array.isArray(intent.args) ||
    intent.args.some((item) => typeof item !== "string" || item.includes("\0")) ||
    realpathSync(intent.cwd) !== intent.cwd ||
    !statSync(intent.cwd).isDirectory() ||
    !safeEnvironment(intent.env) ||
    !Number.isSafeInteger(intent.timeoutMs) ||
    intent.timeoutMs < 1 ||
    intent.timeoutMs > 900_000 ||
    !/^[a-f0-9]{64}$/u.test(intent.candidateIdentitySha256) ||
    !/^[a-f0-9]{64}$/u.test(intent.capsuleSha256) ||
    intent.argvSha256 !== sha256Bytes(JSON.stringify(intent.args)) ||
    intent.environmentSha256 !== sha256Bytes(JSON.stringify(intent.env)) ||
    intent.executableSha256 !== (await sha256File(intent.executable)) ||
    intent.capsuleSha256 !== (await sha256File(fileURLToPath(import.meta.url)))
  ) {
    process.exit(91);
  }

  const intentSha256 = sha256Bytes(intentBytes);
  const claimPath = resolve(operationDirectory, "claimed.json");
  const stdoutPath = resolve(operationDirectory, "stdout.bin");
  const stderrPath = resolve(operationDirectory, "stderr.bin");
  const claim = {
    schema: CLAIM_SCHEMA,
    operationId: intent.operationId,
    operationKey: intent.operationKey,
    sequence: intent.sequence,
    attempt: intent.attempt,
    state: "claimed",
    capsulePid: process.pid,
    processGroupId: process.pid,
    intentSha256,
    stdoutFile: basename(stdoutPath),
    stderrFile: basename(stderrPath),
    claimedAt: new Date().toISOString(),
  };
  publishExclusiveJson(claimPath, claim, { singleWinner: true });
  const stdoutDescriptor = openExclusiveStream(stdoutPath);
  const stderrDescriptor = openExclusiveStream(stderrPath);
  const stdoutHash = createHash("sha256");
  const stderrHash = createHash("sha256");
  let stdoutBytes = 0;
  let stderrBytes = 0;
  let outputLimitExceeded = false;
  let timedOut = false;
  let spawnError = null;
  let childPid = null;
  let exitStatus = null;
  let signal = null;
  const started = Date.now();
  const child = spawn(intent.executable, intent.args, {
    cwd: intent.cwd,
    env: intent.env,
    detached: false,
    stdio: ["ignore", "pipe", "pipe"],
  });
  childPid = child.pid ?? null;
  const consume = (chunk, descriptor, hash, streamName) => {
    const next = streamName === "stdout" ? stdoutBytes + chunk.length : stderrBytes + chunk.length;
    if (next > MAX_STREAM_BYTES) {
      outputLimitExceeded = true;
      if (!terminateLifecycleDescendants()) child.kill("SIGKILL");
      return;
    }
    writeSync(descriptor, chunk);
    hash.update(chunk);
    if (streamName === "stdout") stdoutBytes = next;
    else stderrBytes = next;
  };
  child.stdout.on("data", (chunk) => consume(chunk, stdoutDescriptor, stdoutHash, "stdout"));
  child.stderr.on("data", (chunk) => consume(chunk, stderrDescriptor, stderrHash, "stderr"));
  child.once("error", (error) => {
    spawnError = error?.name ?? "Error";
  });
  const timeout = setTimeout(() => {
    timedOut = true;
    if (!terminateLifecycleDescendants()) child.kill("SIGKILL");
  }, intent.timeoutMs);
  await new Promise((resolvePromise) => {
    child.once("close", (code, childSignal) => {
      exitStatus = Number.isInteger(code) ? code : null;
      signal = childSignal ?? null;
      resolvePromise();
    });
  });
  clearTimeout(timeout);
  fsyncSync(stdoutDescriptor);
  fsyncSync(stderrDescriptor);
  closeSync(stdoutDescriptor);
  closeSync(stderrDescriptor);
  chmodSync(stdoutPath, 0o600);
  chmodSync(stderrPath, 0o600);
  syncEntry(operationDirectory);
  if (!(await waitForLifecycleGroupQuiescence())) {
    return;
  }
  const terminalBase = {
    schema: TERMINAL_SCHEMA,
    operationId: intent.operationId,
    operationKey: intent.operationKey,
    sequence: intent.sequence,
    attempt: intent.attempt,
    state: "terminal",
    intentSha256,
    claimSha256: await sha256File(claimPath),
    childPid,
    completedAt: new Date().toISOString(),
    durationMs: Date.now() - started,
    exitStatus,
    signal,
    spawnError,
    timedOut,
    outputLimitExceeded,
    processGroupQuiescent: true,
    stdoutSha256: stdoutHash.digest("hex"),
    stderrSha256: stderrHash.digest("hex"),
    stdoutSizeBytes: stdoutBytes,
    stderrSizeBytes: stderrBytes,
  };
  const terminal = {
    ...terminalBase,
    operationSha256: sha256Bytes(JSON.stringify(terminalBase)),
  };
  publishExclusiveJson(resolve(operationDirectory, "terminal.json"), terminal);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    await main();
  } catch {
    process.exitCode = 92;
  }
}
