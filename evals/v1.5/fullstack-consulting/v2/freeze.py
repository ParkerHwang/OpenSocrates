"""Non-model preparation, validation and immutable manifest creation."""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runner
import office_check


def manifest_base():
    runtime = "/Users/parkerhwang/.cache/codex-runtimes/codex-primary-runtime/dependencies"
    m = {
        "schema": "opensocrates.fullstack-consulting-observation/1",
        "execution_revision": 2,
        "prior_boundary": "../v1: 36 setup failures, zero model calls; preserved",
        "storage_layout": "per-user OS temporary directory, not /private/tmp; explicit /tmp read denial",
        "product_commit": "035fafcd208bf9577ca55ff5e42a93df4ca608ea",
        "client": {
            "version": "codex-cli 0.158.0-alpha.2",
            "launcher": "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
            "actual_executable": "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex",
        },
        "tools": {
            "runtime_root": runtime,
            "python": runtime + "/python/bin/python3",
            "node": runtime + "/node/bin/node",
            "node_modules": runtime + "/node/node_modules",
            "browser_root": "/Users/parkerhwang/Library/Caches/ms-playwright/chromium_headless_shell-1223",
            "browser_executable": "/Users/parkerhwang/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell",
        },
        "subject_budgets": {
            "wall_clock_seconds": None,
            "tokens": None,
            "tool_calls": None,
            "output_length": None,
            "internal_retries": None,
        },
        "disabled_features": [
            "fast_mode",
            "memories",
            "external_agent_memory_import",
            "apps",
            "remote_plugin",
            "multi_agent",
            "multi_agent_v2",
            "hooks",
        ],
        "common_prompt": "Complete the task in TASK.md in this disposable project. TOOLING.md describes available local tools and source access. Choose ordinary implementation/analysis decisions yourself and produce the actual deliverables with appropriate verification. There is no experimenter-imposed time, token, tool-call, retry or answer-length budget. Work independently; do not invoke helper agents or other models, read another evaluation cell or the evaluator repository, access credentials/account settings/native memories, enroll product memory, modify installed guidance or change global settings. Keep all writes in your supplied workspace/profile. Public research and local dependency installation are allowed. Do not deploy, publish, create paid services or use real customer data. Preserve TASK.md and TOOLING.md. Record actual checks and material limitations; no private reasoning is requested. Use English for development work and deliverables.",
        "arms": {"vanilla": {"package_version": None, "archive_sha256": None, "members": {}}},
        "delivery": "fresh installed package with explicit controller cue; hooks disabled",
        "model_access_policy": "first planned outcome for each exact tuple is its actual access observation; catalog is metadata only",
        "failure_policy": "No automatic outer retries or integrator repair/coaching. Count every attempted call and failure. Stable tuple blockers skip pending same-tuple cells; account blockers skip pending calls without touching active calls. Null usage remains null.",
        "isolation": "fresh HOME/CODEX_HOME, native memory/import disabled, ephemeral, no shared daemon, named read/write scope, no cross-cell input; account-side transfer unproven",
        "fast_mode": {
            "enabled": False,
            "requested_service_tier": "default",
            "independent_backend_echo": None,
        },
        "observation": "timestamped public events; numeric token categories; process/host samples every 15 seconds, no termination deadline; source HTTP logs; immutable artifact lock",
        "human_review": None,
        "primary_review": "provisional unblinded; no extra judge calls",
        "max_simultaneously_scheduled_subjects": 3,
        "official_settings_sources": [
            "https://learn.chatgpt.com/docs/config-file/config-reference",
            "https://learn.chatgpt.com/docs/agent-configuration/speed",
        ],
        "helper_files": {},
        "cells": [],
    }
    for key in ("launcher", "actual_executable"):
        m["client"][key + "_sha256"] = runner.sha(m["client"][key])
    account = (runner.read(runner.AUTH).get("tokens") or {}).get("account_id")
    m["account_id_sha256"] = hashlib.sha256(account.encode()).hexdigest() if account else None
    for key, path, version, expected in [
        (
            "v14",
            "/private/tmp/opensocrates-hard-eval-packages/opensocrates-1.4.0-codex-plugin.zip",
            "1.4.0",
            "74efeab5797de766dabf8394506e29bcb39df3d1b3aac93a5a9ec17a32909a33",
        ),
        (
            "v15",
            "/private/tmp/opensocrates-specialist-package-20260927/opensocrates-1.5.0-codex-plugin.zip",
            "1.5.0",
            "52994553d51e8fd65285165d39ea004be819e56da8dab99c22968591a165dc76",
        ),
    ]:
        assert runner.sha(path) == expected
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            members = {
                i.filename: hashlib.sha256(z.read(i)).hexdigest()
                for i in z.infolist()
                if not i.is_dir()
            }
            assert json.loads(z.read(".codex-plugin/plugin.json"))["version"] == version
        m["arms"][key] = {
            "archive_path": path,
            "archive_name": Path(path).name,
            "archive_sha256": expected,
            "package_version": version,
            "members": members,
            "publication": "released" if key == "v14" else "unpublished release candidate",
        }
    for p in [
        ROOT / "evals/v1.5/practical/runner.py",
        ROOT / "evals/v1.5/practical/checks.py",
        *sorted((ROOT / "evals/v1.5/expanded").glob("*.py")),
        ROOT / "evals/v1.5/native_plugin_runner.py",
    ]:
        m["helper_files"][str(p.relative_to(ROOT))] = runner.sha(p)
    tuples = [
        ("gpt-6-sol", "high"),
        ("gpt-6-luna", "max"),
        ("gpt-6-luna", "high"),
        ("gpt-5.6-luna", "max"),
        ("gpt-5.6-luna", "high"),
        ("gpt-6-astra", "xhigh"),
    ]
    for round_ in range(3):
        for task_index, task in enumerate(("fullstack", "consulting")):
            for tuple_index, (model, effort) in enumerate(tuples):
                arm = ("vanilla", "v14", "v15")[(round_ + tuple_index + task_index) % 3]
                t = model + "-" + effort
                m["cells"].append(
                    dict(
                        id=f"{task}-{t}-{arm}",
                        task=task,
                        model=model,
                        effort=effort,
                        tuple=t,
                        arm=arm,
                        order=len(m["cells"]) + 1,
                    )
                )
    return m


def preflight(m):
    root = Path(tempfile.mkdtemp(prefix="opensocrates-matrix-setup-")).resolve()
    out = HERE / "preparation"
    out.mkdir(exist_ok=True)
    records = []
    for name in ("vanilla", "v14", "v15"):
        base = root / name
        base.mkdir()
        work = base / "workspace"
        work.mkdir()
        output = out / name
        output.mkdir()
        codex, env, config = runner.make_profile(base, m)
        browser_proc = None
        try:
            if name != "vanilla":
                runner.installer.install(
                    {"client": {"path": m["client"]["launcher"]}},
                    m["arms"][name],
                    base,
                    env,
                    output,
                )
            browser_proc = runner.browser_tool(base, m, env, work, output)
            runner.preflight(m, base, work, codex, env, output)
            # Verify headless browser capability inside the same filesystem profile.
            browser_js = "const {chromium}=require('playwright'); (async()=>{const b=await chromium.connect(process.env.EVAL_BROWSER_WS);const p=await b.newPage();await p.setContent('<h1>Isolated browser probe</h1>');console.log(await p.locator('h1').innerText());await b.close()})().catch(e=>{console.error(String(e));process.exitCode=1});"
            p = runner.command(
                [
                    m["client"]["launcher"],
                    "sandbox",
                    "-P",
                    "evaluation",
                    "-C",
                    str(work),
                    m["tools"]["node"],
                    "-e",
                    browser_js,
                ],
                env,
            )
            runner.save(
                output / "browser-preflight.json",
                dict(
                    exit_code=p.returncode, stdout=p.stdout, stderr=runner.clean(p.stderr, base, m)
                ),
            )
            assert p.returncode == 0, "headless browser preflight failed"
            # Catalog metadata is not an outcome/access probe; no completion call.
            if name == "vanilla":
                p = runner.command(
                    [m["client"]["launcher"], "--no-daemon", "debug", "models"], env, work
                )
                assert p.returncode == 0
                catalog = json.loads(p.stdout)["models"]
                wanted = {c["model"] for c in m["cells"]}
                selected = [
                    {
                        k: x.get(k)
                        for k in (
                            "slug",
                            "supported_reasoning_levels",
                            "default_reasoning_level",
                            "service_tiers",
                        )
                    }
                    for x in catalog
                    if x.get("slug") in wanted
                ]
                runner.save(
                    out / "model-catalog.json",
                    {"model_calls": 0, "metadata_only": True, "models": selected},
                )
            records.append({"arm": name, "passed": True, "model_calls": 0})
        finally:
            runner.close_browser(browser_proc, output, base, m)
            (codex / "auth.json").unlink(missing_ok=True)
    # Passive observer self-test: private reasoning must never be retained; null
    # usage is not changed to zero; repeated public tools remain separate events.
    base = root / "observer"
    base.mkdir()
    output = out / "observer"
    output.mkdir()
    codex, env, _ = runner.make_profile(base, m)
    work = base / "workspace"
    work.mkdir()
    fake = """import sys,json
sys.stdin.read()
for e in [
 {'type':'thread.started','thread_id':'synthetic'},
 {'type':'item.completed','item':{'id':'r','type':'reasoning','text':'PRIVATE_CANARY_NEVER_SAVE'}},
 {'type':'item.started','item':{'id':'t','type':'command_execution','command':'synthetic'}},
 {'type':'item.completed','item':{'id':'t','type':'command_execution','command':'synthetic','exit_code':1,'aggregated_output':'synthetic failure'}},
 {'type':'item.completed','item':{'id':'a','type':'agent_message','text':'Public synthetic observation'}},
 {'type':'turn.completed','usage':{'input_tokens':11,'output_tokens':3}}]:print(json.dumps(e),flush=True)
"""
    try:
        r = runner.observe(
            [m["tools"]["python"], "-c", fake],
            "synthetic",
            env,
            work,
            base,
            output,
            m,
            {"attempt": 0, "call_attempted": False, "fake_process": True},
        )
        assert (
            r["usage"]["input_tokens"] == 11
            and r["usage"]["reasoning_output_tokens"] is None
            and r["failed_tool_actions"] == 1
        )
        assert "PRIVATE_CANARY_NEVER_SAVE" not in (output / "observation.jsonl").read_text()
        runner.save(
            output / "selftest.json",
            {
                "passed": True,
                "model_calls": 0,
                "missing_usage_preserved": True,
                "reasoning_text_not_saved": True,
                "failed_tool_count": r["failed_tool_actions"],
            },
        )
    finally:
        (codex / "auth.json").unlink(missing_ok=True)
    reference = office_check.expected()
    assert (
        len(reference["monthly"]) == 72
        and len(reference["countries"]) == 6
        and len(reference["fx_monthly"]) == 24
        and len(reference["market_context"]) == 18
        and len(reference["hub_scenarios"]) == 24
    )
    assert all(
        abs(
            r["gross_sales_eur"]
            - r["refunds_eur"]
            - r["net_cogs_eur"]
            - r["fulfillment_eur"]
            - r["contribution_eur"]
        )
        < 1e-6
        for r in reference["monthly"]
    )
    assert sum(r["shipped_orders"] for r in reference["countries"]) == 1254
    runner.save(out / "office-reference.json", reference)
    runner.save(
        out / "preflight.json",
        {
            "utc": runner.now(),
            "model_calls": 0,
            "arms": records,
            "observer_selftest": True,
            "reference_checks": True,
            "pre_freeze_repairs": [
                "First matrix batch failed all 36 pre-call isolation checks because /private/tmp is readable under the minimal shell profile. Zero model calls. v2 explicitly denies /tmp and uses the verified per-user temp layout; pending calls stop after a common setup error.",
                "Native decision catalog envelope and alphanumeric decision ID corrected; no model calls.",
                "codex --strict-config is unsupported on sandbox/debug; removed from those non-model inspection commands.",
                "Preparation Python urllib certificate-chain failure; fetched sources using system curl with normal certificate verification.",
                "Bundled Playwright default headless-shell 1234 was not installed; pin the existing Chromium 1223 executable equally for all arms and verify it before any call. Original failure retained under attempt-01; subsequent direct Chromium startup failures retained under attempts 02/03. A dedicated per-cell browser tool preserves filesystem isolation while permitting browser IPC.",
            ],
            "no_model_calls_before_freeze": True,
        },
    )
    print(json.dumps({"preflight": "pass", "storage": str(root), "model_calls": 0}))


def freeze(m):
    assert (HERE / "preparation/preflight.json").is_file()
    m["frozen_at"] = datetime.now(timezone.utc).isoformat()
    m["frozen_files"] = {
        str(p.relative_to(HERE)): runner.sha(p)
        for p in sorted(HERE.rglob("*"))
        if p.is_file()
        and p.name != "manifest.json"
        and not any(x in p.parts for x in ("results", "__pycache__"))
    }
    runner.save(HERE / "manifest.json", m)
    print(
        json.dumps(
            {
                "manifest_sha256": runner.sha(HERE / "manifest.json"),
                "cells": len(m["cells"]),
                "frozen_files": len(m["frozen_files"]),
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["preflight", "freeze"])
    a = p.parse_args()
    assert not (HERE / "manifest.json").exists(), "immutable manifest already exists"
    m = manifest_base()
    (preflight if a.action == "preflight" else freeze)(m)
