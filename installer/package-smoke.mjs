#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { unlinkSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const environment = {
  ...process.env,
  npm_config_dry_run: "false",
  npm_config_json: "true",
};

const packed = spawnSync(npm, ["pack", "--silent", "--json"], {
  cwd: root,
  encoding: "utf8",
  env: environment,
});
if (packed.status !== 0) {
  process.stderr.write(packed.stderr);
  process.exit(packed.status ?? 1);
}

let archive;
try {
  const metadata = JSON.parse(packed.stdout);
  archive = resolve(root, metadata[0].filename);
  const executed = spawnSync(
    npx,
    ["--yes", `--package=${archive}`, "opensocrates", "help"],
    {
      cwd: root,
      stdio: "inherit",
      env: { ...process.env, npm_config_dry_run: "false", npm_config_json: "false" },
    },
  );
  if (executed.status !== 0) {
    process.exit(executed.status ?? 1);
  }
} finally {
  if (archive) {
    unlinkSync(archive);
  }
}
