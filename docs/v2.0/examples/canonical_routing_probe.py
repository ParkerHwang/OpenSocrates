"""Probe a hand-authored 1.x decision envelope, not a live host response."""

import io
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from opensocrates.cli.decision import run_decision  # noqa: E402


def main() -> None:
    request = {
        "operation": "select",
        "context": secrets.token_hex(16),
        "epoch": 0,
        "decision": "synthetic1",
        "revision": 0,
        "locale": "ko",
        "participation": "judgment",
        "routing": {
            "schema": "opensocrates.routing-features/1.0.0",
            "answer_shape": "risk_assessment",
            "classification_confidence": "high",
            "explicit_method": None,
            "features": [
                {"key": "diagnose", "strength": 3, "basis": "task_shape"},
                {"key": "failure_risk", "strength": 3, "basis": "task_shape"},
            ],
        },
    }
    output = io.StringIO()
    run_decision(io.StringIO(json.dumps(request)), output)
    result = json.loads(output.getvalue())
    fields = ("status", "reason", "selected", "applied", "selector_model_calls")
    print(json.dumps({key: result.get(key) for key in fields}, ensure_ascii=False))


if __name__ == "__main__":
    main()
