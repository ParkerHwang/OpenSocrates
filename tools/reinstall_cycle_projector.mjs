#!/usr/bin/env node

import { spawnSync } from "node:child_process";

const MAX_OUTPUT_BYTES = 16 * 1024 * 1024;

function fail() {
  process.stderr.write("OpenSocrates categorical projection failed\n");
  process.exit(1);
}

function relevant(value, key, expected) {
  return typeof value?.[key] === "string" && value[key].toLowerCase() === expected;
}

function optionalString(value, key) {
  return typeof value?.[key] === "string" ? value[key] : null;
}

function project(kind, value) {
  if (kind === "status-only") return { status: "ok" };
  if (kind === "claude-auth" && typeof value?.loggedIn === "boolean") {
    return { loggedIn: value.loggedIn };
  }
  if (kind === "claude-marketplaces" && Array.isArray(value)) {
    return value
      .filter((entry) => relevant(entry, "name", "opensocrates"))
      .map((entry) => ({
        name: entry.name,
        source: optionalString(entry, "source"),
        path: optionalString(entry, "path"),
        installLocation: optionalString(entry, "installLocation"),
      }));
  }
  if (kind === "claude-plugins" && Array.isArray(value)) {
    return value
      .filter((entry) => relevant(entry, "id", "opensocrates@opensocrates"))
      .map((entry) => ({ id: entry.id, version: optionalString(entry, "version") }));
  }
  if (kind === "codex-marketplaces" && Array.isArray(value?.marketplaces)) {
    return {
      marketplaces: value.marketplaces
        .filter((entry) => relevant(entry, "name", "opensocrates"))
        .map((entry) => ({ name: entry.name, root: optionalString(entry, "root") })),
    };
  }
  if (kind === "codex-plugins" && Array.isArray(value?.installed)) {
    return {
      installed: value.installed
        .filter((entry) => relevant(entry, "pluginId", "opensocrates@opensocrates"))
        .map((entry) => ({
          pluginId: entry.pluginId,
          version: optionalString(entry, "version"),
        })),
    };
  }
  fail();
}

const [kind, executable, ...args] = process.argv.slice(2);
if (
  !new Set([
    "status-only",
    "claude-auth",
    "claude-marketplaces",
    "claude-plugins",
    "codex-marketplaces",
    "codex-plugins",
  ]).has(kind) ||
  typeof executable !== "string" ||
  executable.length === 0 ||
  args.some((item) => typeof item !== "string")
) {
  fail();
}

const completed = spawnSync(executable, args, {
  cwd: process.cwd(),
  env: process.env,
  encoding: "utf8",
  maxBuffer: MAX_OUTPUT_BYTES,
  stdio: ["ignore", "pipe", "pipe"],
});
if (completed.error || completed.status !== 0) fail();
let value = null;
if (kind !== "status-only") {
  try {
    value = JSON.parse(completed.stdout);
  } catch {
    fail();
  }
}
process.stdout.write(`${JSON.stringify(project(kind, value))}\n`);
