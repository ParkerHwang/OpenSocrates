"""Render completed observations, including failures and unavailable measurements."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review"
ARMS = ["vanilla", "v1.4.0", "v1.5.0-rc"]


def read(path):
    return json.loads(path.read_text())


def main():
    assert (ROOT / "evidence/execution.completed.json").exists()
    data = read(OUT / "summary.json")
    manifest = read(ROOT / "protocol/manifest.json")
    memory = read(OUT / "memory-operations.json")
    audit = read(OUT / "measurement-audit.json")
    assert len(data["stages"]) == 9 and len(data["cells"]) == 99

    def stage(arm, number):
        return next(x for x in data["stages"] if x["arm"] == arm and x["stage"] == number)

    def score(arm, number):
        row = stage(arm, number)
        counts = row["scenario_counts"]
        if row.get("unavailable_reason"):
            return "unavailable"
        return f"{counts['pass']}/{row['expected_scenarios']}" + (f"; {counts['unassessable']} unassessable" if counts['unassessable'] else "")

    def numeric(value, digits=1):
        return "unavailable" if value is None else f"{value:,.{digits}f}"

    def measurement(arm, work, concurrency, metric, rate=0):
        group = next(x for x in data["groups"] if (x["arm"], x["stage"], x["workload"], x["concurrency"], x["rate"]) == (arm, 3, work, concurrency, rate))
        value = group[metric]
        if not value:
            return "unavailable"
        return f"{value['median']:,.2f} ({value['min']:,.2f}–{value['max']:,.2f}; n={value['n']})"

    count = len(data["calls"])
    completed = sum(c["process_success"] is True for c in data["calls"])
    lines = ["# QueueForge with Luna: vanilla, OpenSocrates 1.4 and 1.5 RC", "",
    f"The bounded Luna experiment made **{count} outcome calls; {completed} completed successfully as CLI turns**. Task correctness is reported separately below. There was no model substitution, stronger-model outcome assistance, automatic retry or integrator repair of a candidate artifact. All original Sol and Luna outcomes remain unchanged.", "",
    "This repeats the same durable backend task: tenant isolation, idempotent single/batch writes, leased workers and fencing, retry/dead-letter state, scheduled priority work, quotas, cancellation, keyset pagination and migration of genuine preceding-stage data. It is one English three-session implementation episode per condition, not a broad model-quality study.", "",
    "## Prospective controls and exact identities", "",
    "All three conditions request **gpt-6-luna / medium / codex-cli 0.158.0-alpha.2**, with Go1.26.3 and modernc.org/sqlite1.59.0 locked. The first planned vanilla call checks current access before other calls start. A maximum of two independent builders then run at once; timed API loads never overlap models or builds. The invocation limit is nine, 1200s each, with no escalation. Model/backend echo and billing remain null.", "",
    "Vanilla uses a disposable home/profile with zero additional plugins. The other profiles contain exactly one pinned local OpenSocrates package. Account-remote plugins/apps, hooks, native memories/import and subagents are disabled. Vanilla and 1.4 receive a maintained-note control with the same accepted intent as the explicitly enrolled 1.5 memory condition. No prior Sol code, answers, outcomes or repair hints enter the Luna workspaces. Compilation caches were primed from the common driver seed only.", "",
    "| Identity | Value |", "| --- | --- |",
    "| Pre-outcome local freeze | `fa962c8dfa676e765b640d2327372de3e8a7d63e` |",
    "| Luna manifest SHA-256 | `48964310f8c6c1b1db0821312bc9c6e903fa1deab7f1d37e9a00c8510db044a7` |",
    "| Product input | `a8aaba572693c63419188ee2d45f59688b564b16` |",
    f"| Client SHA-256 | `{manifest['client']['sha256']}` |",
    f"| Released 1.4 ZIP SHA-256 | `{manifest['arms'][1]['archive_sha256']}` |",
    f"| Unpublished 1.5 RC ZIP SHA-256 | `{manifest['arms'][2]['archive_sha256']}` |", "",
    "The task texts, common starter and independent API checker are identical to the preceding Sol comparison. The corrected meter is used **before** outcomes here, so Luna's final session can receive valid own-arm preliminary performance feedback. The Sol final sessions received invalid/unavailable original meter feedback. Cross-model differences are therefore descriptive and confounded; they are not a controlled causal gap or gap-closing estimate.", "",
    "## Correctness, tests and repairs", "",
    "| Condition | Initial API | Extended API | Final API | Final own Go suite | Named domain Go test results |",
    "| --- | --- | --- | --- | --- | ---: |"]
    for arm in ARMS:
        final = stage(arm, 3)
        own = "pass" if final["own_tests_pass"] else "fail/unavailable"
        lines.append(f"| {arm} | {score(arm,1)} | {score(arm,2)} | {score(arm,3)} | {own} | {final['domain_tests_seen']} |")
    lines += ["", "A successful `go test` invocation can cover only the supplied driver test; it does not prove authored domain tests. The named count excludes that driver test and can include subtests. Separate process scripts, their retained evidence and gaps are assessed in the [source review](SOURCE_REVIEW.md). External API scenarios use race builds, two processes sharing a database, controlled clocks, actual preceding-stage executables, atomic rollback and SIGKILL/restart. Passing these finite scenarios does not prove production security or physical power-loss behavior.", "",
    "| Non-passing external scenario | Condition / stage | Recorded result |", "| --- | --- | --- |"]
    for arm in ARMS:
        for number in (1, 2, 3):
            report = read(ROOT / "evidence" / arm / f"stage{number}/acceptance.json")
            if report.get("unavailable_reason"):
                lines.append(f"| Entire check unavailable | {arm} / {number} | {report['unavailable_reason']} |")
            for case in report.get("scenarios", []):
                if case["status"] != "pass":
                    error = (case.get("error") or "").replace("|", "/").replace("\n", " ")
                    lines.append(f"| {case['name']} | {arm} / {number} | {case['status']}: {error} |")
    lines += ["", "## Server performance", "",
    "The fixed schedule contains 18 preliminary and 81 final cells. Each available final cell uses 3s warmup and 10s measurement, with three repetitions per condition/workload. One server (GOMAXPROCS4) and one generator (GOMAXPROCS2) run serially on the same shared Apple-silicon Mac. Fresh copies of stopped, public-API-seeded databases contain 50,000 jobs across four tenants, 256-byte payloads and 10,000 read references. Timeouts, drops, scheduler lag, CPU, peak RSS, DB/WAL bytes and state conservation are retained. Unavailable cells stay null, never zero.", "",
    "Cells whose correctness/self-test/dependency gates fail are diagnostic. Valid timing is not sufficient to qualify a speed advantage. The source review separately assesses durability settings and reuse. Values below are median (observed min–max; available repetitions), not confidence intervals.", "",
    "| Final metric | Vanilla | 1.4 | 1.5 RC |", "| --- | ---: | ---: | ---: |"]
    for work, metric, label in [("read", "http_success_rps", "successful read HTTP/s"), ("lifecycle", "completed_jobs_per_second", "completed jobs/s")]:
        for concurrency in (1, 16, 64):
            lines.append(f"| {label}, concurrency {concurrency} | " + " | ".join(measurement(a, work, concurrency, metric) for a in ARMS) + " |")
    for work in ("read", "lifecycle"):
        for metric, label in [("send_p99_ms", "HTTP p99 ms"), ("server_cpu_seconds", "process CPU seconds"), ("server_peak_rss_mib", "process peak RSS MiB")]:
            lines.append(f"| {work} {label}, concurrency64 | " + " | ".join(measurement(a, work, 64, metric) for a in ARMS) + " |")
    for rate in (100, 500, 1000):
        lines.append(f"| fixed {rate}/s reads, scheduled p99 ms | " + " | ".join(measurement(a, "read", 1, "scheduled_p99_ms", rate) for a in ARMS) + " |")
    final_cells = [x for x in data["cells"] if x["stage"] == 3]
    valid = [x for x in final_cells if x["measurement_valid"]]
    lines += ["", "![Luna performance](performance.png)", "",
    f"There are {len(valid)}/81 final cells with valid meter observations and {sum(x['frozen_artifact_and_load_gates_pass'] for x in final_cells)}/81 passing both the frozen artifact and observable load gates. The independent numerical audit checked {len([x for x in audit['cells'] if x['status']=='pass'])} available cells and {audit['total_samples_including_warmup']:,} retained samples including warmup. See [all cells](performance-cells.csv) and [the audit](measurement-audit.json).", "",
    "Throughput counts matching start-cohort responses completed inside the measurement window; cohort/drain counts and latency remain separate. Lifecycle latency is per HTTP request, not end-to-end job latency. CPU/RSS cover process lifetime including startup/warmup/drain/state reads. Scheduled-arrival latency includes dispatch delay. This shared-host sweep is not a production maximum-capacity estimate.", "",
    "## Development work and memory", "",
    "| Observed sum across attempted sessions | Vanilla | 1.4 | 1.5 RC |", "| --- | ---: | ---: | ---: |"]
    totals = data["development_totals"]
    for label, get in [("CLI invocation minutes", lambda x: x['model_seconds']/60 if x['model_seconds'] is not None else None), ("Tool actions", lambda x:x['tool_actions']), ("Nonzero tool actions", lambda x:x['failed_tool_actions']), ("Input tokens",lambda x:x['usage']['input_tokens']), ("Cached input subset",lambda x:x['usage']['cached_input_tokens']), ("Uncached input difference",lambda x:x['uncached_input_tokens']), ("Output tokens",lambda x:x['usage']['output_tokens']), ("Reasoning-output subset",lambda x:x['usage']['reasoning_output_tokens'])]:
        lines.append("| " + label + " | " + " | ".join(numeric(get(totals[a]), 2 if 'minutes' in label else 0) for a in ARMS) + " |")
    lines += ["", "![Luna development work](development.png)", "",
    "Cached input and reasoning output are subsets, not additive costs. Missing usage is null; explicitly reported zero stays zero. No new preparation-agent model calls occurred. The reused task/checker/meter were authored outside all treatments. All command attempts and nonzero results are retained; lookup misses are not automatically coding defects.", "",
    f"Observed native memory attempts: {memory['total']}; operations {json.dumps(memory['counts'],sort_keys=True)}; captured status counts {json.dumps(memory['status_counts'],sort_keys=True)}. Routes: {json.dumps(memory['route_counts'],sort_keys=True)}. Integrator enrollment and post-call reads are separate. [Operation audit](memory-operations.json) links direct commands to retained typed responses where possible, and keeps missing response IDs/statuses null. Direct launcher calls bypass the declared adapter; source/package bytes and persisted checkpoint state are separate supporting evidence. An emitted pack is not universal application proof, and proposed checkpoints are not accepted decisions.", "",
    "## Interpretation, boundaries and handoff", "",
    "Read the [separate descriptive Sol context](sol-context.json) and [source and semantic review](SOURCE_REVIEW.md) for the actual defects, reusable paths, retained verification gaps and the resulting bounded conclusion. Report improvements, ties and regressions without repairing historical artifacts. One implementation per condition cannot establish broad quality/efficiency superiority, validate model profiles or isolate a memory effect. This is an English backend exercise; it does not establish Korean collaboration or every general-assistance capability.", "",
    "The first cache priming attempt raced a still-running module-cache copy and failed before any outcome call. The failed cache was retained, a new copy completed synchronously, and common-seed priming then passed. A native method-selection request also needed its decision identifier corrected. Both are in the preparation ledger, separate from model outcomes. No old source or result was rewritten to pass.", "",
    "Exact evidence includes the frozen manifest, all source stages, model/public-message receipts, checker results, [failure ledger](failure-ledger.json), [numeric summary](summary.json), [host/source preservation](preservation.json) and [reproduction instructions](REPRODUCE.md). The compact public export declares path/command-body transformations and original/export digests. Full raw timing samples remain only in the local synthetic evaluation boundary; aggregate exports cannot reconstruct every percentile without those samples.", "",
    "Human scores, billed cost and independent backend model echo remain unavailable. Account-side native-memory transfer remains unproven. No global settings/memories or active plugin installation are changed, and no real project is enrolled. Live Windows Codex, destructive host tests and production deployment are outside this comparison. OpenSocrates remains an unpublished release candidate and PR95 remains Draft. Publication and active-install replacement require separate explicit authority.", "",
    "`plan_objective_measure`: matched within-Luna backend comparison against vanilla and released controls, under the existing practical completion standard.", "",
    "`do_scope`: at most nine fresh outcome sessions and the fixed 18+81 load schedule; no stronger-model answers, repairs or escalation inside a treatment.", "",
    "`check_rule`: frozen input/source identities, actual API/state checks, qualified performance, all attempts and explicit missingness.", "",
    "`act_standardize_decision`: retain observed bounded differences and failures; stop this experiment and do not promote a profile or expand a study automatically.", "",
    "OpenSocrates grounding: pdca-cycle@3", ""]
    known_attempts = sum(x["attempts"] for x in final_cells if x["attempts"] is not None)
    observed_errors = sum(x["errors"] for x in final_cells if x["errors"] is not None)
    delayed = sum(x["scheduler_misses"] for x in final_cells if x["scheduler_misses"] is not None)
    preliminary_errors = sum(x["errors"] for x in data["cells"] if x["stage"] == 2 and x["arm"] == "vanilla" and x["errors"] is not None)
    paragraph = f"Available final measurement cohorts contain {known_attempts:,} HTTP attempts and {observed_errors:,} recorded response/validation errors. All other counters, missingness and state conservation remain in the CSV. There are {delayed:,} dispatches later than one arrival interval. Preliminary vanilla cells retain {preliminary_errors:,} request failures; final load behavior does not erase its remaining API/legacy obligations."
    rendered = "\n".join(lines).replace("## Development work and memory", paragraph + "\n\n## Development work and memory")
    (OUT / "REPORT.md").write_text(rendered)


if __name__ == "__main__":
    main()
