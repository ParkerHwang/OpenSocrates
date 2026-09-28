"""Bounded public completion/dependency projection; no semantic proof or I/O."""

from __future__ import annotations

from typing import Any

from ..domain.completion import all_required_criteria_met, criterion_is_met


def _resolve_graph(items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, bool]]:
    """Validate and resolve an acyclic bounded graph."""
    by_id = {item["obligation_id"]: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("duplicate_obligation")
    for item in items:
        deps = item["depends_on"]
        if len(set(deps)) != len(deps) or not set(deps) <= by_id.keys():
            raise ValueError("invalid_dependency")
        if len(set(item["evidence_refs"])) != len(item["evidence_refs"]):
            raise ValueError("duplicate_evidence")
    resolved: dict[str, bool] = {}
    active: set[str] = set()

    def visit(identifier: str) -> bool:
        if identifier in active:
            raise ValueError("cyclic_dependency")
        if identifier in resolved:
            return resolved[identifier]
        active.add(identifier)
        item = by_id[identifier]
        # Visit every edge even when a preceding dependency is unresolved.
        dependencies = [visit(dep) for dep in item["depends_on"]]
        result = (
            criterion_is_met({"required": True, "status": item["status"]})
            and bool(item["evidence_refs"])
            and item["attribution"] != "unknown"
            and all(dependencies)
        )
        active.remove(identifier)
        resolved[identifier] = result
        return result

    for identifier in by_id:
        visit(identifier)
    return by_id, resolved


def summarize_obligations(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Retain independent work beside scoped blockers; completion remains reported."""
    by_id, resolved = _resolve_graph(items)
    criteria = [
        {
            "required": item["required"],
            "status": "met" if resolved[item["obligation_id"]] else "unverified",
        }
        for item in items
    ]
    blocking = [
        item["obligation_id"]
        for item in items
        if item["required"] and not resolved[item["obligation_id"]]
    ]
    required_closure: set[str] = set()

    def require(identifier: str) -> None:
        if identifier in required_closure:
            return
        required_closure.add(identifier)
        for dependency in by_id[identifier]["depends_on"]:
            require(dependency)

    for identifier in blocking:
        require(identifier)
    open_ids = [identifier for identifier in by_id if not resolved[identifier]]
    ready = [
        identifier
        for identifier in open_ids
        if by_id[identifier]["kind"] == "work"
        and all(resolved[dep] for dep in by_id[identifier]["depends_on"])
    ]
    questions = []
    for question in dict.fromkeys(item["question_id"] for item in items):
        required = [
            item["obligation_id"]
            for item in items
            if item["question_id"] == question and item["required"]
        ]
        questions.append(
            {
                "question_id": question,
                "required_complete": bool(required) and all(resolved[key] for key in required),
                "blocking_ids": [key for key in required if key in blocking],
            }
        )
    return {
        "finish_eligible": all_required_criteria_met(criteria),
        "blocking_ids": blocking,
        "ready_ids": ready,
        "input_ids": [
            identifier for identifier in open_ids if by_id[identifier]["kind"] == "input"
        ],
        "required_input_ids": [
            identifier
            for identifier in open_ids
            if identifier in required_closure and by_id[identifier]["kind"] == "input"
        ],
        "waiting_ids": [
            identifier
            for identifier in open_ids
            if by_id[identifier]["kind"] == "work" and identifier not in ready
        ],
        "questions": questions,
    }
