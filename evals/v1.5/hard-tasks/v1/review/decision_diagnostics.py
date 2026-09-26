"""Post-outcome native-only field diagnostics. Never feeds help to a treatment."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main(package, output):
    template = package / "skills/opensocrates/references/decision/request.json"
    request = json.loads(template.read_text())
    office = copy.deepcopy(request)
    office["locale"] = "ko"
    office["routing"]["answer_shape"] = "decision_memo"
    office["routing"]["features"] = [
        {"key": k, "strength": s, "basis": b}
        for k, s, b in [
            ("multiple_options", 3, "decision_need"),
            ("multiple_objectives", 3, "decision_need"),
            ("choose", 3, "decision_need"),
            ("reconcile_evidence", 2, "evidence_need"),
            ("conflicting_sources", 2, "evidence_need"),
            ("source_quality", 2, "evidence_need"),
            ("explicit_rules", 2, "task_shape"),
            ("plan", 1, "task_shape"),
        ]
    ]
    bad_id = copy.deepcopy(office)
    bad_id["decision"] = "regional-launch-choice"
    missing = copy.deepcopy(office)
    del missing["operation"]
    bad_basis = copy.deepcopy(request)
    bad_basis["routing"]["answer_shape"] = "completion_review"
    bad_basis["routing"]["features"] = [
        {"key": "mechanical", "strength": 3, "basis": "task_shape"},
        {"key": "binding_rule_without_discretion", "strength": 3, "basis": "governing_rule"},
    ]
    repaired_basis = copy.deepcopy(bad_basis)
    repaired_basis["routing"]["features"][1]["basis"] = "task_shape"
    rows = []
    with tempfile.TemporaryDirectory(prefix="hard-decision-diagnostic-") as temp:
        env = {
            "PATH": os.environ["PATH"],
            "HOME": temp,
            "CODEX_HOME": temp + "/codex",
            "OPENSOCRATES_DATA_DIR": temp + "/data",
            "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
        }
        for name, value in [
            ("office_invalid_decision_id", bad_id),
            ("office_same_features_valid_id", office),
            ("office_missing_operation", missing),
            ("coding_invalid_basis", bad_basis),
            ("coding_same_features_valid_basis", repaired_basis),
        ]:
            process = subprocess.run(
                [str(package / "bin/launch.sh"), "decision", "codex"],
                input=json.dumps(value),
                text=True,
                capture_output=True,
                env=env,
                timeout=30,
            )
            response = json.loads(process.stdout)
            rows.append(
                {
                    "case": name,
                    "request": value,
                    "exit_code": process.returncode,
                    "response": {
                        key: response.get(key)
                        for key in (
                            "status",
                            "reason",
                            "selected",
                            "applied",
                            "continue_ordinary_work",
                        )
                    },
                    "response_sha256": hashlib.sha256(process.stdout.encode()).hexdigest(),
                }
            )
        memory_created = (Path(temp) / "data").exists()
    result = {
        "schema": "opensocrates.native-decision-diagnostic/1",
        "model_calls": 0,
        "native_calls": len(rows),
        "package_condition": "Frozen v1.5 candidate; separate disposable data/home; no candidate workspace mutation",
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "rows": rows,
        "data_directory_created": memory_created,
        "application": "not applied; response projected before inspection; no method content used",
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "cases": [{"name": row["case"], **row["response"]} for row in rows],
                "data_directory_created": memory_created,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.package, args.output)
