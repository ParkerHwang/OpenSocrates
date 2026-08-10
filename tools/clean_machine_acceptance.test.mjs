import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

import {
  makeReport,
  packExisting,
  writeReports,
} from "./clean_machine_acceptance.mjs";

function acceptanceFixture() {
  const root = mkdtempSync(join(tmpdir(), "opensocrates-acceptance-test-"));
  const directory = join(root, "result");
  mkdirSync(directory, { mode: 0o700 });
  const report = makeReport();
  report.automatedResult = "passed";
  report.manualResult = "pending";
  report.overallResult = "pending";
  report.completedAt = new Date().toISOString();
  writeReports(directory, report);
  return {
    root,
    directory,
    manual: join(directory, "manual-observations.md"),
    cleanup: () => rmSync(root, { recursive: true, force: true }),
  };
}

test("clean-machine evidence: completed categorical checks produce a constrained ZIP", () => {
  const fixture = acceptanceFixture();
  try {
    const manual = readFileSync(fixture.manual, "utf8").replace(/: PENDING$/gmu, ": PASS");
    writeFileSync(fixture.manual, manual);
    packExisting(fixture.directory);

    const result = JSON.parse(readFileSync(join(fixture.directory, "result.json"), "utf8"));
    assert.equal(result.manualResult, "passed");
    assert.equal(result.overallResult, "passed");
    const archive = `${fixture.directory}.zip`;
    assert.equal(existsSync(archive), true);
    const listing = spawnSync("/usr/bin/unzip", ["-Z1", archive], { encoding: "utf8" });
    assert.equal(listing.status, 0);
    assert.deepEqual(listing.stdout.trim().split(/\r?\n/u).sort(), [
      "manual-observations.md",
      "result.json",
      "result.md",
    ]);
  } finally {
    fixture.cleanup();
  }
});

test("clean-machine evidence: free-form manual text is rejected", () => {
  const fixture = acceptanceFixture();
  try {
    const manual = readFileSync(fixture.manual, "utf8")
      .replace(/: PENDING$/gmu, ": PASS")
      .concat("\nextra notes are not accepted\n");
    writeFileSync(fixture.manual, manual);
    assert.throws(
      () => packExisting(fixture.directory),
      /restore the manual checklist template/u,
    );
    assert.equal(existsSync(`${fixture.directory}.zip`), false);
  } finally {
    fixture.cleanup();
  }
});
