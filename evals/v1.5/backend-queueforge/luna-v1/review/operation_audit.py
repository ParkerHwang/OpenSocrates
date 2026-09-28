"""Audit wrapper and direct native calls without treating missing receipts as OK."""

import collections
import hashlib
import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review"


def read(path):
    return json.loads(path.read_text())


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def request_from_command(command):
    try:
        outer = shlex.split(command)
        shell = outer[-1] if "-lc" in outer or "-c" in outer else command
        for token in shlex.split(shell):
            if token.startswith("{"):
                try:
                    value = json.loads(token)
                except ValueError:
                    continue
                if value.get("schema") == "opensocrates.project-memory.request/1.0.0":
                    return value
    except ValueError:
        pass
    return None


def main():
    operations, failures, checkpoints = [], [], []
    for arm in ("vanilla", "v1.4.0", "v1.5.0-rc"):
        config_path = ROOT / "apps" / arm / "memory_tool.json"
        config = read(config_path) if config_path.exists() else {}
        launcher = config.get("launcher", "")
        base = launcher.split("/profile/")[0] if "/profile/" in launcher else None
        for stage in (1, 2, 3):
            folder = ROOT / "evidence" / arm / f"stage{stage}"
            if not (folder / "call.json").exists():
                continue
            call = read(folder / "call.json")
            wrapper = read(folder / "memory-operations.json") if (folder / "memory-operations.json").exists() else []
            operations.extend({"arm": arm, "stage": stage, "route": "declared_adapter", **x} for x in wrapper)
            actions = {x.get("command_sha256"): x for x in call["tool_actions"] if x.get("command_sha256")}
            for index, command in enumerate(call["commands"]):
                text = command["command"]
                if command.get("exit_code") not in (None, 0):
                    failures.append({"arm": arm, "stage": stage, "command_index": index, "exit_code": command["exit_code"], "public_command_sha256": sha(text), "first_line": text.splitlines()[0][:150], "classification": "Nonzero command; distinguish lookup misses, intermediate checks and retained failures using public messages and independent checks."})
                restored = text.replace("<WORKSPACE>", str(ROOT / "apps" / arm)).replace("<STUDY>", str(ROOT))
                if base:
                    restored = restored.replace("<disposable>", base).replace("<DISPOSABLE>", base)
                action = actions.get(sha(restored))
                request = request_from_command(text)
                direct_marker = "memory" in (action or {}).get("direct_operations_lexical", [])
                if not (request and "launch.sh" in text and "memory" in text) and not direct_marker:
                    continue
                request = request or {}
                typed = [x for x in (action or {}).get("structured_responses", []) if x.get("schema") == "opensocrates.project-memory.response/1.0.0"]
                status = typed[0].get("status") if len(typed) == 1 else None
                operations.append({"arm": arm, "stage": stage, "route": "direct_marketplace_launcher" if "/marketplace/" in text else "direct_launcher", "operation": request.get("operation"), "request_id": request.get("request_id"), "response_request_id": None, "status": status, "exit_code": command.get("exit_code"), "command_index": index, "original_command_sha256": sha(restored) if action else None, "command_hash_correlated": action is not None, "status_evidence": "captured typed response from matching command" if status else "unavailable; process exit alone is not promoted to a typed success", "limitation": "The declared adapter was bypassed. Compact response projection omits request IDs and can miss a response; post-call state is separate evidence."})
            state_path = folder / "memory-state.json"
            if state_path.exists():
                state = read(state_path)
                records = (state.get("inspect", {}).get("response", {}) or {}).get("result", [])
                if isinstance(records, list):
                    checkpoints.append({"arm": arm, "stage": stage, "records": [{"kind": r.get("kind"), "lifecycle": r.get("lifecycle"), "support": r.get("support"), "version": r.get("version"), "record_id": r.get("record_id")} for r in records], "checkpoint_reference": ((state.get("recall", {}).get("response", {}) or {}).get("result", {}) or {}).get("checkpoint_reference")})
    (OUT / "memory-operations.json").write_text(json.dumps({"operations": operations, "total": len(operations), "counts": dict(collections.Counter(x.get("operation") or "unclassified" for x in operations)), "status_counts": dict(collections.Counter(x.get("status") or "unavailable" for x in operations)), "route_counts": dict(collections.Counter(x["route"] for x in operations)), "persisted_state": checkpoints, "integrator_reads_and_seed_writes": "Separate; not counted as model-initiated calls"}, indent=2) + "\n")
    (OUT / "failure-ledger.json").write_text(json.dumps({"count": len(failures), "all_nonzero_commands": failures, "preparation_failures": read(ROOT / "evidence/preparation-failures.json"), "model_retries": 0, "stronger_model_candidate_repairs": 0}, indent=2) + "\n")
    print(json.dumps({"memory_attempts": len(operations), "typed_statuses": dict(collections.Counter(x.get("status") or "unavailable" for x in operations)), "nonzero_commands": len(failures)}))


if __name__ == "__main__":
    main()
