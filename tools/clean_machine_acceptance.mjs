#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  chmodSync,
  createReadStream,
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPOSITORY = "ParkerHwang/OpenSocrates";
const RESULT_SCHEMA = "opensocrates.clean-machine-acceptance/1.0.0";
const DESIRED_STATE_SCHEMA = "opensocrates.desired-state/1.0.0";
const VERSION = readFileSync(join(ROOT, "VERSION"), "utf8").trim();
const HOSTS = Object.freeze(["claude", "codex"]);
const RESULT_FILES = Object.freeze([
  "result.json",
  "result.md",
  "manual-observations.md",
]);
const MANUAL_FIELDS = Object.freeze([
  "Claude single public entry",
  "Claude controller status",
  "Codex plugin recognition",
  "Host runtime loading",
]);

class AcceptanceError extends Error {
  constructor(category, message, exitCode = null) {
    super(message);
    this.name = "AcceptanceError";
    this.category = category;
    this.exitCode = exitCode;
  }
}

function fail(category, message, exitCode = null) {
  throw new AcceptanceError(category, message, exitCode);
}

function command(
  executable,
  args,
  {
    cwd = ROOT,
    env = process.env,
    category = "command",
    failureMessage = `${executable} did not complete successfully`,
  } = {},
) {
  const result = spawnSync(executable, args, {
    cwd,
    env,
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error) {
    fail(category, failureMessage);
  }
  if (result.status !== 0) {
    fail(category, failureMessage, result.status ?? null);
  }
  return result.stdout.trim();
}

function parseJson(text, category, message) {
  try {
    return JSON.parse(text);
  } catch {
    fail(category, message);
  }
}

function sanitizedMessage(error, scratch = null) {
  const replacements = [
    [homedir(), "$HOME"],
    [ROOT, "$CHECKOUT"],
    ...(scratch ? [[scratch, "$TMP"]] : []),
  ];
  let value = error instanceof Error ? error.message : String(error);
  for (const [target, replacement] of replacements) {
    if (target) value = value.split(target).join(replacement);
  }
  return value
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/giu, "[redacted-email]")
    .replace(/\b(?:gh[opusr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/gu, "[redacted-token]")
    .replace(/[\r\n]+/gu, " ")
    .slice(0, 500);
}

function exactString(value, category, message) {
  if (typeof value !== "string" || value.length === 0) {
    fail(category, message);
  }
  return value;
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

async function sha256File(target) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(target)) hash.update(chunk);
  return hash.digest("hex");
}

function walkFiles(directory, output = []) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = join(directory, entry.name);
    if (entry.isDirectory()) {
      walkFiles(target, output);
    } else if (entry.isFile()) {
      output.push(target);
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

function sorted(values) {
  return [...values].sort();
}

function sameStrings(left, right) {
  return JSON.stringify(sorted(left)) === JSON.stringify(sorted(right));
}

function requireOwnerOnly(target, category, label) {
  const mode = statSync(target).mode & 0o777;
  if ((mode & 0o077) !== 0) {
    fail(category, `${label} is accessible by group or other users`);
  }
  return mode.toString(8).padStart(3, "0");
}

function managedRoot(host) {
  return join(homedir(), host === "claude" ? ".claude" : ".codex", "managed-marketplaces", "opensocrates");
}

function installedPluginRoot(host, root) {
  const marketplacePath = join(
    root,
    ...(host === "claude"
      ? [".claude-plugin", "marketplace.json"]
      : [".agents", "plugins", "marketplace.json"]),
  );
  if (!pathPresent(marketplacePath)) {
    fail("post-install", `${host} managed marketplace metadata is missing`);
  }
  const marketplace = parseJson(
    readFileSync(marketplacePath, "utf8"),
    "post-install",
    `${host} managed marketplace metadata is invalid JSON`,
  );
  const plugins = Array.isArray(marketplace?.plugins) ? marketplace.plugins : [];
  const matches = plugins.filter((entry) => entry?.name === "opensocrates");
  if (matches.length !== 1) {
    fail("post-install", `${host} managed marketplace does not declare one OpenSocrates plugin`);
  }
  const source = host === "claude" ? matches[0].source : matches[0].source?.path;
  if (typeof source !== "string" || !source.startsWith("./")) {
    fail("post-install", `${host} managed marketplace has an invalid local plugin source`);
  }
  const pluginRoot = resolve(root, source);
  const local = relative(root, pluginRoot);
  if (local === "" || local === ".." || local.startsWith(`..${sep}`)) {
    fail("post-install", `${host} managed marketplace plugin source escapes its owned root`);
  }
  const info = pathPresent(pluginRoot) ? lstatSync(pluginRoot) : null;
  if (!info?.isDirectory() || info.isSymbolicLink()) {
    fail("post-install", `${host} managed marketplace plugin root is missing or unsafe`);
  }
  return pluginRoot;
}

function inspectManagedLayout(
  roots = { claude: managedRoot("claude"), codex: managedRoot("codex") },
) {
  const claudePlugin = installedPluginRoot("claude", roots.claude);
  const codexPlugin = installedPluginRoot("codex", roots.codex);
  const claudeSkillsPath = join(claudePlugin, "skills");
  if (!pathPresent(claudeSkillsPath)) {
    fail("post-install", "Claude's installed plugin has no skills directory");
  }
  const claudeSkills = readdirSync(claudeSkillsPath);
  if (!sameStrings(claudeSkills, ["opensocrates"])) {
    fail("post-install", "Claude exposes more than the single OpenSocrates controller skill");
  }
  if (
    pathPresent(join(claudePlugin, "commands")) ||
    !pathPresent(join(claudeSkillsPath, "opensocrates", "SKILL.md"))
  ) {
    fail("post-install", "Claude's public controller layout is not canonical");
  }
  if (!pathPresent(join(codexPlugin, "skills", "opensocrates", "SKILL.md"))) {
    fail("post-install", "Codex's OpenSocrates controller skill is missing");
  }
  for (const host of HOSTS) {
    const markerPath = join(roots[host], ".opensocrates-managed.json");
    if (!pathPresent(markerPath)) {
      fail("post-install", `${host} ownership marker is missing`);
    }
    const marker = parseJson(
      readFileSync(markerPath, "utf8"),
      "post-install",
      `${host} has an invalid ownership marker`,
    );
    if (marker?.marketplaceName !== "opensocrates" || marker?.pluginName !== "opensocrates") {
      fail("post-install", `${host} has the wrong ownership marker`);
    }
  }
  return {
    claudePublicSkills: claudeSkills,
    claudeCommandsPresent: false,
    codexControllerPresent: true,
  };
}

function marketplaceEntries(host) {
  if (host === "claude") {
    const payload = parseJson(
      command("claude", ["plugin", "marketplace", "list", "--json"], {
        category: "host-state",
        failureMessage: "Claude Code could not list plugin marketplaces",
      }),
      "host-state",
      "Claude Code returned invalid marketplace JSON",
    );
    if (!Array.isArray(payload)) {
      fail("host-state", "Claude Code returned an unexpected marketplace schema");
    }
    return payload;
  }
  const payload = parseJson(
    command("codex", ["plugin", "marketplace", "list", "--json"], {
      category: "host-state",
      failureMessage: "Codex could not list plugin marketplaces",
    }),
    "host-state",
    "Codex returned invalid marketplace JSON",
  );
  if (!Array.isArray(payload?.marketplaces)) {
    fail("host-state", "Codex returned an unexpected marketplace schema");
  }
  return payload.marketplaces;
}

function pluginEntries(host) {
  if (host === "claude") {
    const payload = parseJson(
      command("claude", ["plugin", "list", "--json"], {
        category: "host-state",
        failureMessage: "Claude Code could not list installed plugins",
      }),
      "host-state",
      "Claude Code returned invalid plugin JSON",
    );
    if (!Array.isArray(payload)) {
      fail("host-state", "Claude Code returned an unexpected plugin schema");
    }
    return payload;
  }
  const payload = parseJson(
    command(
      "codex",
      ["plugin", "list", "--marketplace", "opensocrates", "--available", "--json"],
      {
        category: "host-state",
        failureMessage: "Codex could not inspect the OpenSocrates plugin",
      },
    ),
    "host-state",
    "Codex returned invalid plugin JSON",
  );
  if (!Array.isArray(payload?.installed) || !Array.isArray(payload?.available)) {
    fail("host-state", "Codex returned an unexpected plugin schema");
  }
  return payload.installed;
}

function writePrivate(target, contents) {
  writeFileSync(target, contents, { encoding: "utf8", mode: 0o600 });
  chmodSync(target, 0o600);
}

function manualTemplate(report) {
  const automated = report.automatedResult.toUpperCase();
  const defaultCheck = report.automatedResult === "passed" ? "PENDING" : "NOT_RUN";
  return `# OpenSocrates clean-machine manual observations

Automated result: ${automated}
${MANUAL_FIELDS.map((label) => `${label}: ${defaultCheck}`).join("\n")}

Change every \`PENDING\` value to \`PASS\` or \`FAIL\` after completing the matching check.

- Claude single public entry: start a new Claude Code task and confirm that the
  skill/command UI shows one OpenSocrates entry, \`/opensocrates\`.
- Claude controller status: run \`/opensocrates status\` in that task and confirm
  that the controller responds.
- Codex plugin recognition: start a new Codex task, explicitly ask it to use
  OpenSocrates for a planning question, and confirm that it recognizes the plugin.
- Host runtime loading: confirm that neither host reports an installation,
  permission, or runtime-loading error.

Do not add free-form text, prompts, transcripts, account names, credentials, or
local paths. The pack command rejects a modified template.
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
  return `# OpenSocrates clean-machine acceptance result

- Overall: **${report.overallResult}**
- Automated: **${report.automatedResult}**
- Manual: **${report.manualResult}**
- Product version: \`${report.source.version}\`
- Pull request: ${report.source.pullRequestUrl ?? "not recorded"}
- Source commit: \`${report.source.commit ?? "not recorded"}\`
- CI run: ${report.source.ciRunUrl ?? "not recorded"}
- Platform: \`${report.environment.platform ?? "not recorded"}\`
${failure}
| Check | Result | Duration | Failure category |
| --- | --- | ---: | --- |
${rows || "| No checks completed | failed | 0 ms | harness |"}

This report intentionally excludes prompts, transcripts, authentication identity,
credentials, absolute home/workspace paths, and raw command output.
`;
}

function writeReports(outputDirectory, report, { preserveManual = false } = {}) {
  writePrivate(join(outputDirectory, "result.json"), `${JSON.stringify(report, null, 2)}\n`);
  writePrivate(join(outputDirectory, "result.md"), markdownReport(report));
  const manual = join(outputDirectory, "manual-observations.md");
  if (!preserveManual || !existsSync(manual)) {
    writePrivate(manual, manualTemplate(report));
  }
}

function zipReports(outputDirectory) {
  for (const name of RESULT_FILES) {
    if (!existsSync(join(outputDirectory, name))) {
      fail("result-bundle", `the result directory is missing ${name}`);
    }
  }
  const archive = `${outputDirectory}.zip`;
  if (existsSync(archive)) rmSync(archive);
  command("/usr/bin/zip", ["-q", "-j", archive, ...RESULT_FILES.map((name) => join(outputDirectory, name))], {
    cwd: outputDirectory,
    category: "result-bundle",
    failureMessage: "the privacy-safe result ZIP could not be created",
  });
  chmodSync(archive, 0o600);
  return archive;
}

function resultDirectory() {
  const timestamp = new Date().toISOString().replace(/[-:.]/gu, "").replace("Z", "Z");
  return join(homedir(), `opensocrates-clean-machine-result-${timestamp}-${randomUUID().slice(0, 8)}`);
}

async function performStep(report, id, label, action, scratch) {
  const started = Date.now();
  process.stdout.write(`- ${label} ... `);
  try {
    const details = (await action()) ?? {};
    report.steps.push({
      id,
      label,
      status: "passed",
      durationMs: Date.now() - started,
      ...details,
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
      exitCode: error instanceof AcceptanceError ? error.exitCode : null,
    });
    process.stdout.write("failed\n");
    if (error instanceof AcceptanceError) throw error;
    throw new AcceptanceError(category, sanitizedMessage(error, scratch));
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
      version: VERSION,
      commit: null,
      ciRunId: null,
      ciRunUrl: null,
      npmPackage: null,
      assets: {},
    },
    environment: {
      platform: null,
      nodeVersion: process.version,
      claudeVersion: null,
      codexVersion: null,
    },
    baseline: {
      defaultPaths: true,
      priorManagedInstallation: "not-checked",
    },
    steps: [],
    assertions: {},
    automatedResult: "running",
    manualResult: "pending",
    overallResult: "pending",
    failure: null,
    privacy: {
      rawCommandOutputIncluded: false,
      promptsIncluded: false,
      transcriptsIncluded: false,
      authenticationIdentityIncluded: false,
      credentialsIncluded: false,
      absoluteLocalPathsIncluded: false,
    },
  };
}

async function runAcceptance() {
  const outputDirectory = resultDirectory();
  mkdirSync(outputDirectory, { recursive: false, mode: 0o700 });
  chmodSync(outputDirectory, 0o700);
  const scratch = mkdtempSync(join(tmpdir(), "opensocrates-clean-machine-"));
  const report = makeReport();
  let archive = null;
  let succeeded = false;
  let assets = null;
  let packageArchive = null;

  console.log(`OpenSocrates ${VERSION} clean-machine acceptance`);
  console.log("Raw host and authentication output will not be written to the result bundle.\n");

  try {
    await performStep(
      report,
      "environment",
      "Verify a default Apple-silicon macOS environment",
      () => {
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
        ].filter((name) => process.env[name]);
        if (overrides.length > 0) {
          fail("environment", `unset path overrides before testing: ${overrides.join(", ")}`);
        }
        const osVersion = command("/usr/bin/sw_vers", ["-productVersion"], {
          category: "environment",
          failureMessage: "macOS version could not be determined",
        });
        report.environment.platform = `macOS ${osVersion} arm64`;
        return { platform: report.environment.platform };
      },
      scratch,
    );

    await performStep(
      report,
      "source",
      "Pin the checkout to the current pull-request commit",
      () => {
        command("gh", ["auth", "status"], {
          category: "github-auth",
          failureMessage: "GitHub CLI is not authenticated",
        });
        const topLevel = command("git", ["rev-parse", "--show-toplevel"], {
          category: "source",
          failureMessage: "the script must run from a Git checkout",
        });
        if (resolve(topLevel) !== ROOT) {
          fail("source", "the script location and Git checkout root do not match");
        }
        const worktree = command("git", ["status", "--porcelain", "--untracked-files=all"], {
          category: "source",
          failureMessage: "the Git worktree state could not be checked",
        });
        if (worktree !== "") {
          fail("source", "the Git worktree must be clean before acceptance testing");
        }
        const commit = command("git", ["rev-parse", "HEAD"], {
          category: "source",
          failureMessage: "the source commit could not be determined",
        });
        const branch = command("git", ["symbolic-ref", "--quiet", "--short", "HEAD"], {
          category: "source",
          failureMessage: "check out the pull-request branch instead of a detached commit",
        });
        const repository = parseJson(
          command("gh", ["repo", "view", REPOSITORY, "--json", "nameWithOwner"], {
            category: "source",
            failureMessage: "the GitHub repository could not be determined",
          }),
          "source",
          "GitHub returned invalid repository metadata",
        );
        if (repository?.nameWithOwner !== REPOSITORY) {
          fail("source", `the checkout must belong to ${REPOSITORY}`);
        }
        const pullRequest = parseJson(
          command(
            "gh",
            [
              "pr",
              "view",
              branch,
              "--repo",
              REPOSITORY,
              "--json",
              "number,headRefOid,state,url",
            ],
            {
              category: "source",
              failureMessage: "the current branch's pull request could not be inspected",
            },
          ),
          "source",
          "GitHub returned invalid pull-request metadata",
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
        report.source.pullRequest = pullRequestNumber;
        report.source.pullRequestUrl = exactString(
          pullRequest.url,
          "source",
          "the pull-request URL is missing",
        );
        return { commit };
      },
      scratch,
    );

    await performStep(
      report,
      "hosts",
      "Verify Claude Code and Codex are current and authenticated",
      () => {
        const claudeVersion = command("claude", ["--version"], {
          category: "host-prerequisite",
          failureMessage: "Claude Code is unavailable",
        });
        if (!versionAtLeast(claudeVersion, [2, 1, 205])) {
          fail("host-prerequisite", "Claude Code 2.1.205 or later is required");
        }
        command("claude", ["auth", "status"], {
          category: "host-auth",
          failureMessage: "Claude Code is not authenticated",
        });
        const codexVersion = command("codex", ["--version"], {
          category: "host-prerequisite",
          failureMessage: "Codex CLI is unavailable",
        });
        command("codex", ["login", "status"], {
          category: "host-auth",
          failureMessage: "Codex CLI is not authenticated",
        });
        report.environment.claudeVersion = claudeVersion.slice(0, 120);
        report.environment.codexVersion = codexVersion.slice(0, 120);
        return {
          claudeVersion: report.environment.claudeVersion,
          codexVersion: report.environment.codexVersion,
        };
      },
      scratch,
    );

    await performStep(
      report,
      "baseline",
      "Prove there is no prior managed OpenSocrates installation",
      () => {
        const stateDirectory = join(homedir(), ".opensocrates");
        const launchAgent = join(
          homedir(),
          "Library",
          "LaunchAgents",
          "com.opensocrates.auto-update.plist",
        );
        const occupiedPaths = [stateDirectory, launchAgent, ...HOSTS.map(managedRoot)].filter(pathPresent);
        if (occupiedPaths.length > 0) {
          fail("dirty-baseline", "a previous managed OpenSocrates installation or updater exists");
        }
        const claudeMarkets = marketplaceEntries("claude");
        const claudePlugins = pluginEntries("claude");
        const codexMarkets = marketplaceEntries("codex");
        const registered = [
          ...claudeMarkets
            .filter((entry) => entry?.name?.toLowerCase?.() === "opensocrates")
            .map(() => "claude-marketplace"),
          ...claudePlugins
            .filter((entry) => entry?.id?.toLowerCase?.() === "opensocrates@opensocrates")
            .map(() => "claude-plugin"),
          ...codexMarkets
            .filter((entry) => entry?.name?.toLowerCase?.() === "opensocrates")
            .map(() => "codex-marketplace"),
        ];
        if (registered.length > 0) {
          fail("dirty-baseline", "a previous OpenSocrates host registration exists");
        }
        report.baseline.priorManagedInstallation = "absent";
        return { priorManagedInstallation: "absent" };
      },
      scratch,
    );

    await performStep(
      report,
      "ci-artifact",
      "Download the successful CI package built from this exact commit",
      () => {
        const runs = parseJson(
          command(
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
            {
              category: "ci-not-ready",
              failureMessage: "GitHub Actions runs could not be listed",
            },
          ),
          "ci-not-ready",
          "GitHub returned invalid workflow-run metadata",
        );
        if (!Array.isArray(runs)) {
          fail("ci-not-ready", "GitHub returned an unexpected workflow-run schema");
        }
        const run = runs.find(
          (candidate) =>
            candidate?.headSha === report.source.commit && candidate?.conclusion === "success",
        );
        if (!run) {
          fail("ci-not-ready", "no successful CI run exists yet for this exact commit");
        }
        const runId = Number(run.databaseId);
        if (!Number.isSafeInteger(runId) || runId <= 0) {
          fail("ci-not-ready", "the successful CI run has an invalid identifier");
        }
        const artifactDirectory = join(scratch, "artifact");
        mkdirSync(artifactDirectory, { recursive: true, mode: 0o700 });
        command(
          "gh",
          [
            "run",
            "download",
            String(runId),
            "--repo",
            REPOSITORY,
            "--name",
            `package-darwin-arm64-${runId}`,
            "--dir",
            artifactDirectory,
          ],
          {
            category: "ci-artifact",
            failureMessage: "the native macOS CI artifact could not be downloaded",
          },
        );
        report.source.ciRunId = runId;
        report.source.ciRunUrl = exactString(
          run.url,
          "ci-artifact",
          "the CI run URL is missing",
        );
        assets = { directory: artifactDirectory, hosts: {} };
        return { ciRunId: runId, event: run.event ?? "unknown" };
      },
      scratch,
    );

    await performStep(
      report,
      "artifact-integrity",
      "Verify both host archives against the combined release manifest",
      async () => {
        const manifestName = `opensocrates-${VERSION}-release-manifest.json`;
        const manifestPath = findSingleFile(
          assets.directory,
          manifestName,
          "artifact-integrity",
        );
        const manifest = parseJson(
          readFileSync(manifestPath, "utf8"),
          "artifact-integrity",
          "the combined release manifest is invalid JSON",
        );
        if (
          manifest?.schema !== "opensocrates.release-manifest/1.0.0" ||
          manifest?.product_version !== VERSION
        ) {
          fail("artifact-integrity", "the combined release manifest has the wrong schema or version");
        }
        for (const host of HOSTS) {
          const expectedName = `opensocrates-${VERSION}-${host}-plugin.zip`;
          const hostManifest = manifest.hosts?.[host];
          if (hostManifest?.archive !== expectedName) {
            fail("artifact-integrity", `${host} has an unexpected archive name in the manifest`);
          }
          const expectedHash = String(hostManifest.archive_sha256 ?? "").replace(/^sha256:/u, "");
          if (!/^[a-f0-9]{64}$/u.test(expectedHash)) {
            fail("artifact-integrity", `${host} has an invalid archive hash in the manifest`);
          }
          const archivePath = findSingleFile(
            assets.directory,
            expectedName,
            "artifact-integrity",
          );
          const actualHash = await sha256File(archivePath);
          if (actualHash !== expectedHash) {
            fail("artifact-integrity", `${host} archive does not match the CI release manifest`);
          }
          const checksumPath = join(scratch, `${expectedName}.sha256`);
          writePrivate(checksumPath, `${expectedHash}  ${expectedName}\n`);
          assets.hosts[host] = { archivePath, checksumPath, sha256: expectedHash };
          report.source.assets[host] = { name: expectedName, sha256: expectedHash };
        }
        return { verifiedHosts: [...HOSTS] };
      },
      scratch,
    );

    await performStep(
      report,
      "npm-package",
      "Pack and invoke the pull request's real npm installer",
      async () => {
        const packageDirectory = join(scratch, "npm");
        mkdirSync(packageDirectory, { recursive: true, mode: 0o700 });
        const metadata = parseJson(
          command(
            "npm",
            ["pack", "--silent", "--json", "--pack-destination", packageDirectory],
            {
              env: {
                ...process.env,
                npm_config_dry_run: "false",
                npm_config_json: "true",
              },
              category: "npm-package",
              failureMessage: "the pull request could not be packed as an npm package",
            },
          ),
          "npm-package",
          "npm returned invalid pack metadata",
        );
        const item = Array.isArray(metadata) ? metadata[0] : null;
        if (item?.name !== "opensocrates" || item?.version !== VERSION) {
          fail("npm-package", "npm packed the wrong package name or version");
        }
        packageArchive = join(packageDirectory, basename(exactString(
          item.filename,
          "npm-package",
          "npm pack did not return an archive filename",
        )));
        if (!existsSync(packageArchive)) {
          fail("npm-package", "the npm package archive was not created");
        }
        report.source.npmPackage = {
          name: item.name,
          version: item.version,
          sha256: await sha256File(packageArchive),
        };
        command("npx", ["--yes", `--package=${packageArchive}`, "opensocrates", "help"], {
          env: {
            ...process.env,
            npm_config_dry_run: "false",
            npm_config_json: "false",
          },
          category: "npm-package",
          failureMessage: "the packed OpenSocrates command could not start through npx",
        });
        return { packageName: item.name, packageVersion: item.version };
      },
      scratch,
    );

    await performStep(
      report,
      "install",
      "Install Claude and Codex together through one transaction",
      () => {
        command(
          "npx",
          [
            "--yes",
            `--package=${packageArchive}`,
            "opensocrates",
            "install",
            "--host",
            "all",
            // Host-qualified candidate assets define the exact transaction
            // set, so this remains a two-host atomic install even when other
            // supported host CLIs are present on the acceptance machine.
            "--asset-claude",
            assets.hosts.claude.archivePath,
            "--checksum-claude",
            assets.hosts.claude.checksumPath,
            "--asset-codex",
            assets.hosts.codex.archivePath,
            "--checksum-codex",
            assets.hosts.codex.checksumPath,
          ],
          {
            env: {
              ...process.env,
              npm_config_dry_run: "false",
              npm_config_json: "false",
            },
            category: "installation",
            failureMessage: "the transactional all-host installation failed",
          },
        );
        return { installedHosts: [...HOSTS] };
      },
      scratch,
    );

    await performStep(
      report,
      "desired-state",
      "Verify private desired state records both installed hosts",
      () => {
        const stateDirectory = join(homedir(), ".opensocrates");
        const statePath = join(stateDirectory, "desired-state.json");
        const state = parseJson(
          readFileSync(statePath, "utf8"),
          "post-install",
          "the desired-state file is invalid JSON",
        );
        if (
          state?.schema !== DESIRED_STATE_SCHEMA ||
          state?.activeVersion !== VERSION ||
          !sameStrings(state?.installedHosts ?? [], HOSTS) ||
          state?.autoUpdate?.enabled !== false ||
          !sameStrings(state?.autoUpdate?.hosts ?? [], [])
        ) {
          fail("post-install", "desired state does not exactly describe both installed hosts");
        }
        report.assertions.desiredState = {
          schema: state.schema,
          activeVersion: state.activeVersion,
          installedHosts: sorted(state.installedHosts),
          autoUpdateEnabled: state.autoUpdate.enabled,
        };
        report.assertions.statePermissions = {
          directory: requireOwnerOnly(stateDirectory, "permissions", "the state directory"),
          file: requireOwnerOnly(statePath, "permissions", "the desired-state file"),
        };
        return { activeVersion: state.activeVersion, installedHosts: sorted(state.installedHosts) };
      },
      scratch,
    );

    await performStep(
      report,
      "host-registration",
      "Verify exact host registrations and installed versions",
      () => {
        for (const host of HOSTS) {
          const exactMarkets = marketplaceEntries(host).filter(
            (entry) => entry?.name === "opensocrates",
          );
          if (exactMarkets.length !== 1) {
            fail("post-install", `${host} does not have exactly one OpenSocrates marketplace`);
          }
        }
        const claudeMatches = pluginEntries("claude").filter(
          (entry) => entry?.id === "opensocrates@opensocrates",
        );
        const codexMatches = pluginEntries("codex").filter(
          (entry) => entry?.pluginId === "opensocrates@opensocrates",
        );
        if (
          claudeMatches.length !== 1 ||
          claudeMatches[0]?.version !== VERSION ||
          codexMatches.length !== 1 ||
          codexMatches[0]?.version !== VERSION
        ) {
          fail("post-install", "one or both hosts do not report the expected installed version");
        }
        report.assertions.hostRegistrations = {
          claude: { count: claudeMatches.length, version: claudeMatches[0].version },
          codex: { count: codexMatches.length, version: codexMatches[0].version },
        };
        return { claudeVersion: VERSION, codexVersion: VERSION };
      },
      scratch,
    );

    await performStep(
      report,
      "managed-layout",
      "Verify the installed managed trees and Claude's single public skill",
      () => {
        const layout = inspectManagedLayout();
        report.assertions.managedLayout = layout;
        return { claudePublicSkills: layout.claudePublicSkills };
      },
      scratch,
    );

    await performStep(
      report,
      "status",
      "Run the packaged all-host status check and require no drift",
      () => {
        const output = command(
          "npx",
          ["--yes", `--package=${packageArchive}`, "opensocrates", "status", "--host", "all"],
          {
            env: {
              ...process.env,
              npm_config_dry_run: "false",
              npm_config_json: "false",
            },
            category: "post-install",
            failureMessage: "the packaged all-host status check failed",
          },
        );
        const expected = [
          `Desired version: ${VERSION}`,
          `claude: installed ${VERSION} (in sync)`,
          `codex: installed ${VERSION} (in sync)`,
          "Overall: no detected drift",
        ];
        if (expected.some((line) => !output.includes(line))) {
          fail("post-install", "all-host status did not report both hosts in sync");
        }
        report.assertions.status = {
          desiredVersion: VERSION,
          hostsInSync: [...HOSTS],
          drift: false,
        };
        return { drift: false };
      },
      scratch,
    );

    report.automatedResult = "passed";
    report.manualResult = "pending";
    report.overallResult = "pending";
    succeeded = true;
  } catch (error) {
    report.automatedResult = "failed";
    report.manualResult = "not-run";
    report.overallResult = "failed";
    report.failure = {
      category: error instanceof AcceptanceError ? error.category : "harness",
      message: sanitizedMessage(error, scratch),
    };
  } finally {
    report.completedAt = new Date().toISOString();
    writeReports(outputDirectory, report);
    if (!succeeded) {
      try {
        archive = zipReports(outputDirectory);
      } catch (error) {
        console.error(`Result ZIP error: ${sanitizedMessage(error, scratch)}`);
      }
    }
    rmSync(scratch, { recursive: true, force: true });
  }

  if (succeeded) {
    console.log("\nAutomated checks passed. Complete the manual host checks next:");
    console.log(`  ${join(outputDirectory, "manual-observations.md")}`);
    console.log("Set every PENDING check to PASS or FAIL, then create the shareable ZIP:");
    console.log(`  node tools/clean_machine_acceptance.mjs --pack ${JSON.stringify(outputDirectory)}`);
  } else {
    console.error(`\nAutomated checks failed (${report.failure.category}).`);
    console.error(`Share this privacy-safe result ZIP: ${archive ?? "ZIP creation failed"}`);
  }
  process.exitCode = succeeded ? 0 : 1;
}

function packExisting(directoryArgument) {
  if (!directoryArgument) {
    fail("usage", "--pack requires the result directory printed by the automated test");
  }
  const outputDirectory = resolve(directoryArgument);
  if (!pathPresent(outputDirectory) || !lstatSync(outputDirectory).isDirectory()) {
    fail("usage", "--pack requires an existing result directory");
  }
  const resultPath = join(outputDirectory, "result.json");
  const manualPath = join(outputDirectory, "manual-observations.md");
  const report = parseJson(
    readFileSync(resultPath, "utf8"),
    "result-bundle",
    "result.json is invalid",
  );
  if (report?.schema !== RESULT_SCHEMA || report?.automatedResult !== "passed") {
    fail("result-bundle", "only a passed automated result can be completed with --pack");
  }
  const manual = readFileSync(manualPath, "utf8");
  let normalizedManual = manual;
  const checkResults = [];
  for (const label of MANUAL_FIELDS) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
    const matches = [...manual.matchAll(new RegExp(`^${escaped}: (PASS|FAIL|PENDING)$`, "gmu"))];
    if (matches.length !== 1 || matches[0][1] === "PENDING") {
      fail("result-bundle", `set '${label}' to PASS or FAIL before packing`);
    }
    checkResults.push(matches[0][1]);
    normalizedManual = normalizedManual.replace(matches[0][0], `${label}: PENDING`);
  }
  if (normalizedManual !== manualTemplate(report)) {
    fail("result-bundle", "restore the manual checklist template and do not add free-form text");
  }
  report.manualResult = checkResults.every((value) => value === "PASS") ? "passed" : "failed";
  report.overallResult = report.manualResult === "passed" ? "passed" : "failed";
  report.completedAt = new Date().toISOString();
  writeReports(outputDirectory, report, { preserveManual: true });
  const archive = zipReports(outputDirectory);
  console.log(`Share this privacy-safe result ZIP: ${archive}`);
}

function printHelp() {
  console.log(`Usage:
  node tools/clean_machine_acceptance.mjs
  node tools/clean_machine_acceptance.mjs --pack RESULT_DIRECTORY

The first command requires a clean Apple-silicon Mac and installs OpenSocrates
for the real authenticated Claude Code and Codex homes. The second command adds
manual observations and creates a privacy-safe ZIP for review.`);
}

export {
  AcceptanceError,
  inspectManagedLayout,
  makeReport,
  manualTemplate,
  packExisting,
  writeReports,
};

export async function main(args = process.argv.slice(2)) {
  try {
    if (args.length === 0) {
      await runAcceptance();
    } else if (args[0] === "--pack" && args.length === 2) {
      packExisting(args[1]);
    } else if ((args[0] === "--help" || args[0] === "-h") && args.length === 1) {
      printHelp();
    } else {
      fail("usage", "use --help to see the supported clean-machine acceptance commands");
    }
  } catch (error) {
    console.error(`Clean-machine acceptance error: ${sanitizedMessage(error)}`);
    process.exitCode = 1;
  }
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  await main();
}
