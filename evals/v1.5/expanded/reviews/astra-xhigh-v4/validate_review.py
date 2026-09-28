"""Structural and evidence-reference validation; never alter assessor ratings."""

from __future__ import annotations

import json
import re
from typing import Any

AXES = (
    "task_outcome",
    "evidence_factual_accuracy",
    "initiative_continuity",
    "communication",
    "coding_maintainability",
    "efficiency_discipline",
)


def shape(value: Any, schema: dict, path: str = "$") -> None:  # noqa: C901
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                shape(value, alternative, path)
                return
            except ValueError:
                pass
        raise ValueError(f"{path}: no matching shape")
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        raise ValueError(f"{path}: wrong fixed value")
    if "enum" in schema and not any(
        type(value) is type(option) and value == option for option in schema["enum"]
    ):
        raise ValueError(f"{path}: unknown enum")
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "boolean": type(value) is bool,
        "null": value is None,
    }
    if kinds and not any(matches[kind] for kind in kinds):
        raise ValueError(f"{path}: wrong type")
    if isinstance(value, dict) and "properties" in schema:
        properties = schema["properties"]
        if not set(schema.get("required", [])) <= value.keys() or set(value) - properties.keys():
            raise ValueError(f"{path}: missing or extra fields")
        for key, child in value.items():
            shape(child, properties[key], path + "." + key)
    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            shape(child, schema["items"], f"{path}[{index}]")
    if type(value) is int and not schema.get("minimum", value) <= value <= schema.get(
        "maximum", value
    ):
        raise ValueError(f"{path}: score outside anchors")


def pointer(reference: str, packet: dict, deterministic: dict | None) -> None:
    if reference.startswith("deterministic:"):
        current = deterministic
        reference = reference.removeprefix("deterministic:")
        if current is None:
            raise ValueError("deterministic evidence cited before disclosure")
    else:
        current = packet
        reference = reference.removeprefix("packet:")
    path, separator, line = reference.partition("#L")
    if not path.startswith("/"):
        raise ValueError("evidence must use packet:/ or deterministic:/ JSON pointers")
    for component in path[1:].split("/"):
        component = component.replace("~1", "/").replace("~0", "~")
        if isinstance(current, str):
            try:
                current = json.loads(current)
            except ValueError as error:
                raise ValueError("cannot descend into non-JSON text") from error
        if isinstance(current, list) and component.isdigit() and int(component) < len(current):
            current = current[int(component)]
        elif isinstance(current, dict) and component in current:
            current = current[component]
        else:
            raise ValueError("citation points to absent packet evidence")
    if separator and (
        not line.isdigit()
        or not isinstance(current, str)
        or not 1 <= int(line) <= len(current.splitlines())
    ):
        raise ValueError("citation line outside artifact")


def scores(values: dict, packet: dict, evidence: dict | None) -> None:
    if set(values) != set(AXES):
        raise ValueError("all six axes required")
    for axis, item in values.items():
        if item["status"] == "scored":
            if (
                type(item["score"]) is not int
                or not 0 <= item["score"] <= 4
                or not item["evidence"]
            ):
                raise ValueError(f"{axis}: scored axis needs anchored integer and evidence")
        elif item["score"] is not None:
            raise ValueError(f"{axis}: missing/inapplicable score must be null")
        if not item["reason"].strip():
            raise ValueError(f"{axis}: reason required")
        for citation in item["evidence"]:
            pointer(citation, packet, evidence)


def validate(  # noqa: C901  # Explicit immutable first/evidence-phase contract.
    value: dict,
    *,
    schema: dict,
    assignment: dict,
    packets: dict,
    rubric: dict,
    phase: str,
    deterministic: dict | None = None,
    locked: dict | None = None,
) -> list[str]:
    shape(value, schema)
    if value["assignment_id"] != assignment["assignment_id"] or value["phase"] != phase:
        raise ValueError("assignment/phase mismatch")
    if value["rubric"] != rubric:
        raise ValueError("rubric identity mismatch")
    identifiers = [packet["packet_id"] for packet in value["packets"]]
    if sorted(identifiers) != sorted(assignment["packet_ids"]) or value["unreviewed_packets"]:
        raise ValueError(
            "all and only assigned packets required; unknown evidence can be unassessable"
        )
    warnings = []
    previous = {packet["packet_id"]: packet for packet in locked["packets"]} if locked else {}
    for assessment in value["packets"]:
        identifier = assessment["packet_id"]
        source = packets[identifier]
        if (
            assessment["packet_sha256"] != source["sha256"]
            or assessment["locale"] != source["content"]["locale"]
        ):
            raise ValueError("packet identity mismatch")
        supplied = (deterministic or {}).get(identifier)
        evidence = supplied["content"] if supplied else None
        scores(assessment["first_pass_scores"], source["content"], None)
        for item in [*assessment["critical_gates"], *assessment["findings"]]:
            if not item["evidence"]:
                raise ValueError("every gate/finding needs a packet citation")
            for citation in item["evidence"]:
                pointer(citation, source["content"], None)
        if not assessment["critical_gates"]:
            raise ValueError("material critical gates must be assessed")
        status = assessment["deterministic_evidence_status"]
        if phase == "first_pass":
            if (
                status["status"] != "withheld"
                or status["sha256"] is not None
                or assessment["post_evidence_scores"] is not None
                or assessment["post_evidence_critical_gates"]
                or assessment["disagreements"]
            ):
                raise ValueError("first pass must precede deterministic evidence")
        else:
            for key in (
                "packet_sha256",
                "locale",
                "blinding_status",
                "non_blindable_cues",
                "first_pass_scores",
                "critical_gates",
                "findings",
                "assessment_status",
                "human_scores",
            ):
                if assessment[key] != previous[identifier][key]:
                    raise ValueError(f"locked first-pass field changed: {key}")
            if status["status"] != "reviewed" or status["sha256"] != supplied["sha256"]:
                raise ValueError("deterministic evidence identity mismatch")
            if assessment["post_evidence_scores"] is None:
                raise ValueError("post-evidence axes required, including explicit nulls")
            scores(assessment["post_evidence_scores"], source["content"], evidence)
            for item in [*assessment["post_evidence_critical_gates"], *assessment["disagreements"]]:
                if not item["evidence"]:
                    raise ValueError("evidence-phase finding/gate needs citations")
                for citation in item["evidence"]:
                    pointer(citation, source["content"], evidence)
        if (
            any(gate["status"] == "fail" for gate in assessment["critical_gates"])
            and assessment["first_pass_scores"]["task_outcome"]["score"] == 4
        ):
            warnings.append(
                identifier
                + ": full outcome score alongside a critical failure; preserve both for synthesis"
            )
        narrative = json.dumps(
            {key: child for key, child in assessment.items() if key not in {"packet_sha256"}},
            ensure_ascii=False,
        )
        if re.search(r"gpt-6-(?:luna|sol|astra)", narrative, re.I):
            warnings.append(
                identifier + ": candidate model name appears; check blinding disclosure"
            )
    return warnings


def selftest() -> None:
    packet = {
        "stages": [{"artifacts": {"x.py": "def f():\n    return 1\n", "plan.json": '{"a":1}'}}]
    }
    pointer("packet:/stages/0/artifacts/x.py#L2", packet, None)
    pointer("/stages/0/artifacts/plan.json/a", packet, None)
    for bad in ("/missing", "/stages/0/artifacts/x.py#L4", "deterministic:/checks"):
        try:
            pointer(bad, packet, None)
        except ValueError:
            continue
        raise AssertionError(bad)
    try:
        shape(True, {"type": ["integer", "null"], "minimum": 0, "maximum": 4})
    except ValueError:
        pass
    else:
        raise AssertionError("boolean is not a rating")
    print("review validation selftest: PASS")


if __name__ == "__main__":
    selftest()
