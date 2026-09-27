"""Artifact observations for integrated delivery; semantic route review is separate."""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys


def check(case, workspace):
    sys.path.insert(0, str(workspace))
    if case == "needed-en":
        module = importlib.import_module("logquery")
        records = [{"seq": 0, "text": "zero"}, {"seq": 7, "text": "seven"}, {"seq": 11, "text": "eleven"}, {"seq": 20, "text": "twenty"}]
        original = deepcopy(records)
        assert module.query_window(records, 7, 20, 1) == [records[1]]
        assert module.query_window(records, 0, 0, None) == [records[0]]
        assert module.query_window(records, None, None, 0) == []
        assert module.query_window(records, None, None, None) == records
        for values in [(True, None, None), (None, "7", None), (0, None, 1.0), (-1, None, None), (20, 7, None)]:
            try:
                module.query_window(records, *values)
            except ValueError:
                pass
            else:
                raise AssertionError(f"invalid input accepted: {values}")
        assert module.positional_slice(records, -2, None) == records[-2:]
        assert module.export_lines(records, 7, 20, 2) == "seven\neleven"
        assert records == original
        return {"artifact_pass": True, "boundaries": ["strict_contract", "zero_vs_null", "legacy_consumer", "input_preserved"]}
    if case == "mechanical-ko":
        assert json.loads((workspace / "settings.json").read_text()) == {"display_label": "beta", "retry_count": 3, "enabled": True}
        expected = {"settings.json", "TASK.md", "TOOLING.md"}
        actual = {str(p.relative_to(workspace)) for p in workspace.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
        assert actual == expected, sorted(actual-expected)
        return {"artifact_pass": True, "boundaries": ["exact_mechanical_edit", "no_extra_artifacts"]}
    if case == "general-en":
        result = json.loads((workspace / "recommendation.json").read_text())
        assert result["choice"].lower() == "amber"
        assert result["cost"] == 70 and result["waiting_days"] == 2
        assert result["external_action_taken"] is False
        assert isinstance(result["reason"], str) and result["reason"].strip()
        return {"artifact_pass": True, "boundaries": ["feasibility", "priority_order", "no_external_action_claim"]}
    if case == "mixed-ko":
        module = importlib.import_module("callbacks")
        state = {"generation": 4, "result": "old", "keep": 9}
        for generation in [3, 5]:
            old = deepcopy(state)
            assert module.apply_result(state, generation, "stale") is False
            assert state == old
        assert module.apply_result(state, 4, "new") is True
        assert state == {"generation": 4, "result": "new", "keep": 9}
        memo = (workspace / "handoff.md").read_text()
        assert len(memo.strip()) > 80
        return {"artifact_pass": True, "boundaries": ["old_and_future_rejected", "current_applied", "independent_handoff_written"], "remaining_review": "Read all public messages and Korean handoff to assess scoped unknowns and questions."}
    if case == "chinese-static":
        module = importlib.import_module("tagindex")
        index = module.TagIndex()
        incoming = {"tags": ["a", "a", "b"], "options": {"list": [1, 2]}}
        expected = deepcopy(incoming)
        index.put("doc", incoming)
        incoming["tags"].append("injected")
        incoming["options"]["list"][0] = 999
        first = index.summary()
        assert first == {"doc": expected}
        first["doc"]["options"]["list"].append(8)
        assert index.summary() == {"doc": expected}
        retained = index.summary()
        index.put("doc", {"tags": ["new"]})
        assert retained == {"doc": expected}
        assert module.render_count(index) == "documents=1"
        return {"artifact_pass": True, "boundaries": ["input_alias", "result_alias", "retained_result", "order_and_duplicates", "existing_consumer"]}
    raise ValueError(case)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.case, args.workspace.resolve())
    except Exception as error:
        print(json.dumps({"artifact_pass": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))
