#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import {
  chmodSync,
  closeSync,
  constants as fsConstants,
  existsSync,
  fsyncSync,
  mkdirSync,
  openSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const REPOSITORY = "ParkerHwang/OpenSocrates";
const SCHEMA = "opensocrates.package-source-provenance/1.0.0";

function fail(message) {
  throw new Error(message);
}

function git(args, cwd) {
  const completed = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (completed.error || completed.status !== 0) fail("git provenance inspection failed");
  return completed.stdout.trim();
}

function syncEntry(target) {
  const descriptor = openSync(target, "r");
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

function writeAtomicExclusive(target, contents) {
  if (existsSync(target)) fail("provenance output already exists");
  const parent = dirname(target);
  mkdirSync(parent, { recursive: true, mode: 0o700 });
  const temporary = resolve(parent, `.${basename(target)}.${process.pid}.tmp`);
  let descriptor = null;
  try {
    descriptor = openSync(
      temporary,
      fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
      0o600,
    );
    writeFileSync(descriptor, contents, { encoding: "utf8" });
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = null;
    chmodSync(temporary, 0o600);
    renameSync(temporary, target);
    syncEntry(parent);
  } finally {
    if (descriptor !== null) closeSync(descriptor);
    if (existsSync(temporary)) unlinkSync(temporary);
  }
}

export function writePackageProvenance({ cwd, output, expectedCommit, repository }) {
  const root = resolve(cwd);
  const target = resolve(output);
  const local = relative(root, target);
  if (local === "" || local === ".." || local.startsWith(`..${sep}`)) {
    fail("provenance output must remain inside the source checkout");
  }
  if (!/^[a-f0-9]{40}$/u.test(expectedCommit ?? "")) {
    fail("the expected source commit is missing or invalid");
  }
  if (repository !== REPOSITORY) fail("the package repository identity is invalid");
  const commit = git(["rev-parse", "HEAD"], root);
  const tree = git(["rev-parse", "HEAD^{tree}"], root);
  const trackedStatus = git(["status", "--porcelain", "--untracked-files=no"], root);
  if (commit !== expectedCommit || !/^[a-f0-9]{40}$/u.test(tree) || trackedStatus !== "") {
    fail("the package checkout does not match the exact clean expected source commit");
  }
  const receipt = { schema: SCHEMA, repository, commit, tree };
  writeAtomicExclusive(target, `${JSON.stringify(receipt, null, 2)}\n`);
  return receipt;
}

function main(args = process.argv.slice(2)) {
  if (!(args.length === 0 || (args.length === 2 && args[0] === "--output"))) {
    fail("usage: write_package_provenance.mjs --output RELATIVE_PATH");
  }
  writePackageProvenance({
    cwd: process.cwd(),
    output: args.length === 0
      ? "build/evidence/package-source-provenance.json"
      : args[1],
    expectedCommit: process.env.OPENSOCRATES_EXPECTED_SOURCE_SHA,
    repository: process.env.GITHUB_REPOSITORY ?? REPOSITORY,
  });
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  try {
    main();
  } catch (error) {
    console.error(`package provenance error: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
