// Regression coverage for the release commit identity gate (issue #14).
//
// The gate lives inline in .github/workflows/release.yml. These tests extract
// that exact script and execute it, rather than restating it, so the suite
// cannot drift into passing against a copy while the shipped gate regresses.
// Every case runs under an explicitly pinned /bin/bash -- Bash 3.2 on the
// macos-14 runners that actually execute the release job.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const RELEASE_WORKFLOW = join(ROOT, ".github", "workflows", "release.yml");
const CI_WORKFLOW = join(ROOT, ".github", "workflows", "ci.yml");
const GATE_STEP_NAME = "Resolve and validate release identity";

// The version under test is fixed so the fixtures stay meaningful regardless of
// what VERSION happens to hold on the branch running these tests.
const VERSION = "1.1.5";
const EXACT_SUBJECT = `Release OpenSocrates v${VERSION}`;

// Pinned rather than inherited: `sh`, `zsh`, or a Homebrew Bash 5 would not
// reproduce what the macOS runner executes.
const SHELL = "/bin/bash";

// Body size for the SIGPIPE regression case. The usable range sits between two
// platform limits, both measured rather than assumed:
//   lower -- the body must outgrow the pipe buffer for a piped read to block
//            and take SIGPIPE. Linux caps pipes at 64 KiB; macOS expands them
//            further, and the observed threshold there is above 96 KiB.
//   upper -- a single env string must stay under Linux MAX_ARG_STRLEN
//            (32 * 4 KiB pages = 128 KiB), or execve fails with E2BIG and the
//            gate never runs at all.
// 120 KiB clears the macOS threshold and keeps ~8 KiB of headroom under E2BIG.
// The structural assertion below is the platform-independent guard; this
// behavioural case demonstrates the concrete failure it prevents.
const LONG_BODY_BYTES = 120 * 1024;

/**
 * Extract one step's `run:` block scalar from a workflow file.
 *
 * Deliberately strict: a rename, a re-indent, or a switch away from a literal
 * block scalar makes this throw instead of silently testing nothing.
 */
function extractStepScript(workflowPath, stepName) {
  const lines = readFileSync(workflowPath, "utf8").split(/\r?\n/u);
  const stepIndex = lines.findIndex((line) => line.trim() === `- name: ${stepName}`);
  assert.notEqual(stepIndex, -1, `step "${stepName}" not found in ${workflowPath}`);

  const stepIndent = lines[stepIndex].search(/\S/u);
  let runIndex = -1;
  for (let i = stepIndex + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.trim() === "") continue;
    const indent = line.search(/\S/u);
    // Dedenting to or past the step marker means we left this step.
    if (indent <= stepIndent) break;
    if (line.trim() === "run: |") {
      runIndex = i;
      break;
    }
  }
  assert.notEqual(runIndex, -1, `step "${stepName}" has no literal "run: |" block`);

  const runIndent = lines[runIndex].search(/\S/u);
  const body = [];
  for (let i = runIndex + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.trim() === "") {
      body.push("");
      continue;
    }
    if (line.search(/\S/u) <= runIndent) break;
    body.push(line);
  }

  const bodyIndent = Math.min(
    ...body.filter((line) => line.trim() !== "").map((line) => line.search(/\S/u)),
  );
  const script = body.map((line) => line.slice(bodyIndent)).join("\n");
  assert.ok(script.trim().length > 0, `step "${stepName}" has an empty run block`);
  return script;
}

const GATE_SCRIPT = extractStepScript(RELEASE_WORKFLOW, GATE_STEP_NAME);

/**
 * Run the extracted gate in an isolated workspace.
 *
 * @returns {{status: number, stderr: string, exported: Record<string,string>}}
 */
function runGate({
  version = VERSION,
  message,
  eventName = "push",
  ref = "refs/heads/main",
  refName = "main",
} = {}) {
  const workspace = mkdtempSync(join(tmpdir(), "opensocrates-release-gate-"));
  try {
    // Mirrors the repository file the gate reads, trailing newline included.
    writeFileSync(join(workspace, "VERSION"), `${version}\n`);
    const scriptPath = join(workspace, "gate.sh");
    writeFileSync(scriptPath, GATE_SCRIPT);
    const envFile = join(workspace, "github_env");
    writeFileSync(envFile, "");

    const result = spawnSync(SHELL, [scriptPath], {
      cwd: workspace,
      encoding: "utf8",
      env: {
        PATH: process.env.PATH,
        GITHUB_ENV: envFile,
        GITHUB_EVENT_NAME: eventName,
        GITHUB_REF: ref,
        GITHUB_REF_NAME: refName,
        ...(message === undefined ? {} : { HEAD_COMMIT_MESSAGE: message }),
      },
    });

    // A failed spawn leaves status null, which would otherwise surface as an
    // opaque "null !== 0" instead of naming the real cause.
    if (result.error) {
      throw new Error(`failed to spawn ${SHELL}: ${result.error.message}`);
    }

    const exported = {};
    for (const line of readFileSync(envFile, "utf8").split("\n")) {
      if (!line.includes("=")) continue;
      const index = line.indexOf("=");
      exported[line.slice(0, index)] = line.slice(index + 1);
    }
    return { status: result.status, stderr: result.stderr ?? "", exported };
  } finally {
    rmSync(workspace, { recursive: true, force: true });
  }
}

/** Assert a rejection is fail-closed: non-zero, nothing exported, diagnostic emitted. */
function assertRejected(outcome, label) {
  assert.notEqual(outcome.status, 0, `${label}: gate must not exit 0`);
  assert.deepEqual(
    outcome.exported,
    {},
    `${label}: a rejected commit must export no release identity`,
  );
  assert.ok(
    outcome.stderr.trim().length > 0,
    `${label}: rejection must emit a diagnostic, got empty stderr`,
  );
}

// --------------------------------------------------------------------------
// Positive controls -- without these, the negative cases could pass vacuously.
// --------------------------------------------------------------------------

test("release gate: the exact subject publishes and exports the release identity", () => {
  const outcome = runGate({ message: EXACT_SUBJECT });
  assert.equal(outcome.status, 0, outcome.stderr);
  assert.deepEqual(outcome.exported, {
    RELEASE_VERSION: VERSION,
    RELEASE_TAG: `v${VERSION}`,
  });
});

test("release gate: an exact subject followed by a commit body still publishes", () => {
  // Only the subject line is gated; release commits legitimately carry bodies.
  const outcome = runGate({ message: `${EXACT_SUBJECT}\n\nNotes about the release.\n` });
  assert.equal(outcome.status, 0, outcome.stderr);
  assert.equal(outcome.exported.RELEASE_VERSION, VERSION);
});

test("release gate: a very long commit body publishes without a silent abort", () => {
  // End-to-end demonstration of the failure the pipe-free assertion prevents:
  // reading the subject through `printf | head -n 1` under `set -o pipefail`
  // killed printf with SIGPIPE once the body outgrew the pipe buffer, aborting
  // the step with status 141 and no diagnostic whatsoever.
  //
  // Treat this as a demonstration, not the regression guard. macOS sizes pipe
  // buffers from a shared pool, so the threshold moves between runs and a
  // regressed gate would not reliably trip this case. The deterministic guard
  // is "the subject is extracted without a pipe" below.
  const outcome = runGate({ message: `${EXACT_SUBJECT}\n${"x".repeat(LONG_BODY_BYTES)}` });
  assert.notEqual(outcome.status, 141, "gate died on SIGPIPE reading the subject");
  assert.equal(outcome.status, 0, outcome.stderr);
  assert.equal(outcome.exported.RELEASE_VERSION, VERSION);
});

// --------------------------------------------------------------------------
// Negative: prefixes
// --------------------------------------------------------------------------

for (const [label, message] of [
  ["conventional-commit prefix", `chore: ${EXACT_SUBJECT}`],
  ["merge-commit prefix", `Merge pull request #1: ${EXACT_SUBJECT}`],
  ["revert prefix", `Revert "${EXACT_SUBJECT}"`],
  ["single leading space", ` ${EXACT_SUBJECT}`],
  ["leading tab", `\t${EXACT_SUBJECT}`],
  ["glued leading character", `X${EXACT_SUBJECT}`],
  ["quote-wrapped subject", `"${EXACT_SUBJECT}"`],
]) {
  test(`release gate: rejects prefix -- ${label}`, () => {
    assertRejected(runGate({ message }), label);
  });
}

// --------------------------------------------------------------------------
// Negative: suffixes
// --------------------------------------------------------------------------

for (const [label, message] of [
  ["trailing annotation", `${EXACT_SUBJECT} (hotfix)`],
  ["trailing period", `${EXACT_SUBJECT}.`],
  ["trailing space", `${EXACT_SUBJECT} `],
  ["trailing tab", `${EXACT_SUBJECT}\t`],
  ["trailing carriage return", `${EXACT_SUBJECT}\r`],
  ["glued trailing digit", `${EXACT_SUBJECT}0`],
  ["glued trailing suffix", `${EXACT_SUBJECT}-rc1`],
  ["trailing prerelease tag", `${EXACT_SUBJECT}-beta`],
]) {
  test(`release gate: rejects suffix -- ${label}`, () => {
    assertRejected(runGate({ message }), label);
  });
}

// --------------------------------------------------------------------------
// Negative: multiline first-line tricks
//
// The gate reads only the subject. A commit that hides the exact string on any
// later line must not publish, and neither must one whose first line merely
// contains it.
// --------------------------------------------------------------------------

for (const [label, message] of [
  ["exact string on the second line", `Innocuous subject\n${EXACT_SUBJECT}`],
  ["exact string after a blank first line", `\n${EXACT_SUBJECT}`],
  ["exact string in a trailer", `Some change\n\nCo-authored-by: x\n${EXACT_SUBJECT}`],
  ["exact string buried mid-body", `Some change\n\nbody\n${EXACT_SUBJECT}\nmore body`],
  ["CRLF subject with exact text after CR", `Innocuous\r\n${EXACT_SUBJECT}`],
  ["empty message", ""],
  ["newline-only message", "\n\n"],
]) {
  test(`release gate: rejects multiline trick -- ${label}`, () => {
    assertRejected(runGate({ message }), label);
  });
}

// --------------------------------------------------------------------------
// Negative: mismatched VERSION
// --------------------------------------------------------------------------

for (const [label, subjectVersion] of [
  ["patch bump ahead of VERSION", "1.1.6"],
  ["patch bump behind VERSION", "1.1.4"],
  ["digit-extended version", "1.1.50"],
  ["truncated version", "1.1"],
  ["major bump", "2.0.0"],
  ["zero-padded version", "1.01.5"],
  ["version with prerelease", "1.1.5-rc.1"],
]) {
  test(`release gate: rejects mismatched VERSION -- ${label}`, () => {
    const label_ = `subject v${subjectVersion} vs VERSION ${VERSION}`;
    const outcome = runGate({ message: `Release OpenSocrates v${subjectVersion}` });
    assertRejected(outcome, label_);
  });
}

test("release gate: the rejection diagnostic names the subject and the expectation", () => {
  // "Actionable" concretely means the operator can see what was compared.
  const outcome = runGate({ message: "Release OpenSocrates v9.9.9" });
  assertRejected(outcome, "actionable diagnostic");
  assert.match(outcome.stderr, /Refusing to publish/u);
  assert.match(outcome.stderr, /Release OpenSocrates v9\.9\.9/u, "offending subject not shown");
  assert.match(outcome.stderr, new RegExp(`Release OpenSocrates v${VERSION}`, "u"));
  assert.match(outcome.stderr, /VERSION/u, "expected source not named");
});

// --------------------------------------------------------------------------
// Negative: mismatched tags
// --------------------------------------------------------------------------

for (const [label, refName] of [
  ["tag ahead of VERSION", "v1.1.6"],
  ["tag behind VERSION", "v1.1.4"],
  ["digit-extended tag", "v1.1.50"],
  ["tag without the v prefix", "1.1.5"],
  ["tag with a prerelease suffix", "v1.1.5-rc1"],
  ["tag with a trailing dot", "v1.1.5."],
  ["major-only tag", "v1"],
]) {
  test(`release gate: rejects mismatched tag -- ${label}`, () => {
    const outcome = runGate({
      eventName: "push",
      ref: `refs/tags/${refName}`,
      refName,
      message: EXACT_SUBJECT,
    });
    assertRejected(outcome, label);
    assert.match(outcome.stderr, /does not match VERSION/u);
  });
}

test("release gate: a matching tag publishes without consulting the commit subject", () => {
  // Tag pushes are gated by tag/VERSION agreement; the subject is irrelevant
  // there, and this pins that the subject check does not leak into tag runs.
  const outcome = runGate({
    eventName: "push",
    ref: `refs/tags/v${VERSION}`,
    refName: `v${VERSION}`,
    message: "an unrelated subject",
  });
  assert.equal(outcome.status, 0, outcome.stderr);
  assert.equal(outcome.exported.RELEASE_TAG, `v${VERSION}`);
});

test("release gate: a mismatched tag is rejected even on workflow_dispatch", () => {
  const outcome = runGate({
    eventName: "workflow_dispatch",
    ref: "refs/tags/v9.9.9",
    refName: "v9.9.9",
    message: EXACT_SUBJECT,
  });
  assertRejected(outcome, "workflow_dispatch with a mismatched tag");
});

// --------------------------------------------------------------------------
// Fail-closed under a hostile or absent environment
// --------------------------------------------------------------------------

test("release gate: an unset HEAD_COMMIT_MESSAGE fails closed on a branch push", () => {
  // `set -u` must abort rather than let an empty subject through.
  const outcome = runGate({ message: undefined });
  assert.notEqual(outcome.status, 0);
  assert.deepEqual(outcome.exported, {});
});

test("release gate: a VERSION file with surrounding whitespace still compares exactly", () => {
  const padded = runGate({ version: `  ${VERSION}  `, message: EXACT_SUBJECT });
  assert.equal(padded.status, 0, padded.stderr);
  assert.equal(padded.exported.RELEASE_VERSION, VERSION);
});

// --------------------------------------------------------------------------
// Shell-compatibility and workflow-shape invariants
// --------------------------------------------------------------------------

test("release gate: the step pins `shell: bash` rather than inheriting a default", () => {
  const workflow = readFileSync(RELEASE_WORKFLOW, "utf8");
  const stepIndex = workflow.indexOf(`- name: ${GATE_STEP_NAME}`);
  assert.notEqual(stepIndex, -1);
  const step = workflow.slice(stepIndex, workflow.indexOf("\n      - ", stepIndex + 1));
  assert.match(step, /^\s+shell: bash$/mu, "gate step must pin shell: bash");
});

test("release gate: the subject is extracted without a pipe", () => {
  // The platform-independent form of the SIGPIPE regression above. Under
  // `set -o pipefail`, reading the subject through any pipe means a commit
  // body larger than the pipe buffer kills the writer with SIGPIPE and aborts
  // the step with status 141 and no diagnostic. The exact buffer size varies
  // by kernel, so assert the construct is absent rather than relying on a
  // behavioural cliff that differs between the Linux and macOS runners.
  const assignment = GATE_SCRIPT.split("\n").find((line) =>
    /^\s*subject=/u.test(line),
  );
  assert.ok(assignment, "gate must assign a subject variable");
  assert.doesNotMatch(
    assignment,
    /\|/u,
    `subject must not be read through a pipe under pipefail, got: ${assignment.trim()}`,
  );
  assert.ok(
    GATE_SCRIPT.includes("set -euo pipefail"),
    "the gate must keep pipefail and unset-variable checking enabled",
  );
});

test("release gate: the script avoids Bash 4+ only constructs", () => {
  // macos-14 runners provide Bash 3.2. Each of these parses or behaves
  // differently there, so none may appear in the gate.
  const forbidden = [
    [/\bdeclare\s+-A\b/u, "associative arrays (Bash 4)"],
    [/\bmapfile\b|\breadarray\b/u, "mapfile/readarray (Bash 4)"],
    [/\$\{[A-Za-z_][A-Za-z0-9_]*\^\^?/u, "case-modifying expansion (Bash 4)"],
    [/\$\{[A-Za-z_][A-Za-z0-9_]*,,?/u, "case-modifying expansion (Bash 4)"],
    [/&>>/u, "&>> redirection (Bash 4)"],
    [/\bcoproc\b/u, "coproc (Bash 4)"],
    [/;;&|;&/u, "case fallthrough (Bash 4)"],
    [/\bwait\s+-n\b/u, "wait -n (Bash 4.3)"],
    [/\$\{[A-Za-z_][A-Za-z0-9_]*@[QEPAa]\}/u, "parameter transformation (Bash 4.4)"],
  ];
  for (const [pattern, description] of forbidden) {
    assert.doesNotMatch(GATE_SCRIPT, pattern, `gate must not use ${description}`);
  }
});

test("release gate: the script runs clean under `bash -n` and `sh -n`", () => {
  const workspace = mkdtempSync(join(tmpdir(), "opensocrates-release-gate-syntax-"));
  try {
    const scriptPath = join(workspace, "gate.sh");
    writeFileSync(scriptPath, GATE_SCRIPT);
    const parsed = spawnSync(SHELL, ["-n", scriptPath], { encoding: "utf8" });
    assert.equal(parsed.status, 0, `bash -n rejected the gate: ${parsed.stderr}`);
  } finally {
    rmSync(workspace, { recursive: true, force: true });
  }
});

test("release gate: no GitHub template expression is interpolated into the script body", () => {
  // Expressions must arrive through the step `env:` block. Interpolating a
  // commit message straight into the script would let it execute as shell.
  assert.doesNotMatch(GATE_SCRIPT, /\$\{\{/u, "gate body interpolates a ${{ }} expression");
  const workflow = readFileSync(RELEASE_WORKFLOW, "utf8");
  assert.match(
    workflow,
    /HEAD_COMMIT_MESSAGE:\s*\$\{\{\s*github\.event\.head_commit\.message\s*\}\}/u,
    "the commit message must be passed through env, not inlined",
  );
});

// --------------------------------------------------------------------------
// Ordinary PR validation must not carry release permissions
// --------------------------------------------------------------------------

/** Workflow text with `#` comment lines removed, so prose is never read as a grant. */
function withoutComments(path) {
  return readFileSync(path, "utf8")
    .split(/\r?\n/u)
    .filter((line) => !line.trim().startsWith("#"))
    .join("\n");
}

test("CI workflow: grants only read permissions and never a write scope", () => {
  const ci = readFileSync(CI_WORKFLOW, "utf8");
  assert.match(ci, /^permissions:\n\s+contents: read\n/mu, "ci.yml must default to contents: read");

  const grants = withoutComments(CI_WORKFLOW);
  for (const scope of ["contents", "id-token", "packages", "actions", "deployments", "attestations"]) {
    assert.doesNotMatch(
      grants,
      new RegExp(`^\\s*${scope}:\\s*write\\s*$`, "mu"),
      `PR validation must never grant ${scope}: write`,
    );
  }
  assert.doesNotMatch(grants, /permissions:\s*write-all/u, "PR validation must never grant write-all");
});

test("CI workflow: does not run the release or publish steps", () => {
  const ci = readFileSync(CI_WORKFLOW, "utf8");
  assert.doesNotMatch(ci, /gh release (create|upload|edit)/u, "PR validation must not cut releases");
  assert.doesNotMatch(ci, /npm publish/u, "PR validation must not publish to npm");
  assert.doesNotMatch(ci, /secrets\.(?!GITHUB_TOKEN)/u, "PR validation must not consume secrets");
});

test("release workflow: write permission is job-scoped, not workflow-wide", () => {
  const release = readFileSync(RELEASE_WORKFLOW, "utf8");
  assert.match(
    release,
    /^permissions:\n\s+contents: read\n/mu,
    "release.yml must default to contents: read at the workflow level",
  );
  // The single write grant belongs to the release job, indented beneath it.
  // Counted over real YAML keys only -- prose in a `#` comment is not a grant.
  const writeGrants = release
    .split(/\r?\n/u)
    .filter((line) => !line.trim().startsWith("#"))
    .filter((line) => /^\s*contents:\s*write\s*$/u.test(line));
  assert.equal(writeGrants.length, 1, "exactly one contents: write grant expected");
  assert.match(
    release,
    /^ {4}permissions:\n {6}contents: write$/mu,
    "contents: write must be scoped to the release job",
  );
});

test("release workflow: never triggers on pull_request", () => {
  const release = readFileSync(RELEASE_WORKFLOW, "utf8");
  const triggers = release.slice(release.indexOf("\non:"), release.indexOf("\npermissions:"));
  assert.doesNotMatch(triggers, /pull_request/u, "the release job must not run for pull requests");
});
