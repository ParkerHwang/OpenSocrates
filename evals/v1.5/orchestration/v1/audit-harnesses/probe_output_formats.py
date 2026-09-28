"""Two bounded same-model provider-schema diagnostics; no artifact task claims."""

import hashlib
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from opensocrates.orchestration.adapter import CodexAdapter, _role_environment
from opensocrates.orchestration.contracts import MAX_OUTPUT, checked, schema
from opensocrates.orchestration.paths import encoded

ROOT = Path(__file__).parent
OUT = ROOT / "transport-diagnostic-v2"
CLIENT = "$CODEX_CLIENT"
MODEL = {"name": "gpt-6-astra", "effort": "max"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    OUT.mkdir(mode=0o700)
    cases = []
    for kind in ("candidate", "assessment"):
        assignment_id = str(uuid4())
        value = {"schema": f"opensocrates.orchestration.{kind}/1.0.0", "assignment_id": assignment_id}
        if kind == "candidate":
            value.update(files=[], blocked_reason="missing_input")
        else:
            value.update(candidate_sha256="sha256:" + "0" * 64, verdict="blocked", findings=[],
                         obligations=[{"id": "format-probe", "status": "unknown",
                                       "expected": "Provider accepts the declared output schema.",
                                       "observed": "This is a transport diagnostic only.",
                                       "reproduction": "No tools or artifact checks were requested.",
                                       "evidence_ids": ["diagnostic:format-probe"]}])
        prompt = "Return exactly this JSON object under the supplied schema. Do not use tools. This is only a format diagnostic: " + json.dumps(value)
        cases.append({"kind": kind, "assignment_id": assignment_id, "expected": value,
                      "prompt": prompt, "schema_bytes": encoded(schema(kind))})
    manifest = {"schema": "opensocrates.orchestration.transport-diagnostic/2",
                "frozen_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": "7893996357b7fcfaa058e91d4bc2694d5f1cb63c", "model": MODEL,
                "calls": 2, "max_parallel_calls": 2, "wall_clock_cutoff": None,
                "purpose": "Verify both repaired provider-facing schema forms; no workflow/outcome acceptance claim.",
                "cases": [{"kind": c["kind"], "schema_sha256": sha(c["schema_bytes"]),
                           "prompt_sha256": sha(c["prompt"].encode())} for c in cases]}
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def run(case):
        events, usage, final, tool_items = [], None, None, 0
        with tempfile.TemporaryDirectory(prefix="opensocrates-format-probe-") as raw:
            cwd = Path(raw).resolve()
            output_schema = cwd / "output.schema.json"
            output_schema.write_bytes(case["schema_bytes"])
            assignment = {"role": "production" if case["kind"] == "candidate" else "review", "model": MODEL}
            argv = CodexAdapter(CLIENT)._argv(assignment, cwd, output_schema)
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, env=_role_environment(), cwd=cwd)
            process.stdin.write(case["prompt"].encode()); process.stdin.close()
            for line in process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                kind = event.get("type")
                if kind == "error":
                    events.append({"type": kind, "message": str(event.get("message", ""))[:1500]})
                elif kind == "turn.failed":
                    events.append({"type": kind, "error": str(event.get("error", ""))[:1500]})
                elif kind == "turn.completed":
                    usage = event.get("usage"); events.append({"type": kind})
                elif kind == "thread.started":
                    events.append({"type": kind, "thread_sha256": sha(str(event.get("thread_id")).encode())})
                elif kind == "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "agent_message":
                        final = item.get("text")
                    elif item.get("type") != "reasoning":
                        tool_items += 1
            code = process.wait()
        parsed, matches = None, False
        if final is not None:
            try:
                parsed = checked(json.loads(final), case["kind"], MAX_OUTPUT)
                matches = parsed == case["expected"]
            except (ValueError, TypeError):
                pass
        result = {"kind": case["kind"], "exit_code": code, "events": events,
                  "usage": usage, "tool_items": tool_items, "schema_valid": parsed is not None,
                  "matches_stipulated_diagnostic": matches, "output_sha256": sha(final.encode()) if final else None,
                  "model": MODEL, "source_commit": manifest["source_commit"]}
        (OUT / (case["kind"] + ".result.json")).write_text(json.dumps(result, indent=2) + "\n")
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, cases))
    print(json.dumps(results, indent=2))
    return 0 if all(r["exit_code"] == 0 and r["schema_valid"] and r["matches_stipulated_diagnostic"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
