"""Condition slots and the skill bytes each slot would attach."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bench.cases import forced_headers
from bench.contract import CONDITION_IDS, CONDITIONS_SCHEMA


def load_conditions(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / "bench" / "conditions" / "manifest.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [], [f"bench/conditions/manifest.json: {exc}"]
    if not isinstance(document, Mapping):
        return [], ["bench/conditions/manifest.json: manifest is not an object"]
    if document.get("schema") != CONDITIONS_SCHEMA:
        return [], [f"manifest schema must be {CONDITIONS_SCHEMA}"]
    raw = document.get("conditions")
    if not isinstance(raw, list):
        return [], ["manifest conditions must be a list"]
    by_id: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for item in raw:
        condition, item_errors = _one_condition(root, item)
        errors.extend(item_errors)
        if condition is not None:
            if condition["id"] in by_id:
                errors.append(f"duplicate condition {condition['id']}")
            by_id[condition["id"]] = condition
    missing = [condition_id for condition_id in CONDITION_IDS if condition_id not in by_id]
    if missing:
        errors.append("manifest is missing conditions: " + ", ".join(missing))
    ordered = [by_id[condition_id] for condition_id in CONDITION_IDS if condition_id in by_id]
    return ordered, errors


def _one_condition(root: Path, item: object) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(item, Mapping):
        return None, ["condition entry is not an object"]
    condition_id = item.get("id")
    if condition_id not in CONDITION_IDS:
        return None, [f"unknown condition id: {condition_id!r}"]
    future = item.get("future")
    description = item.get("description")
    if not isinstance(future, bool) or not isinstance(description, str) or not description.strip():
        return None, [f"{condition_id}: future must be boolean and description must be text"]
    skill = item.get("skill")
    if skill is None:
        return _without_skill(condition_id, future, description.strip()), []
    if not isinstance(skill, Mapping):
        return None, [f"{condition_id}: skill must be an object or null"]
    relative = skill.get("path")
    provenance = skill.get("provenance")
    if not isinstance(relative, str) or not isinstance(provenance, str) or not provenance.strip():
        return None, [f"{condition_id}: skill path and provenance are required"]
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None, [f"{condition_id}: skill path escapes the repository"]
    if not path.is_file():
        return None, [f"{condition_id}: skill file is missing: {relative}"]
    data = path.read_bytes()
    text = data.decode("utf-8")
    blob = skill.get("expected_git_blob")
    blob_errors = _check_blob(path, blob, condition_id) if isinstance(blob, str) else []
    if blob is not None and not isinstance(blob, str):
        blob_errors.append(f"{condition_id}: expected_git_blob must be a string")
    loaded = {
        "id": condition_id,
        "future": future,
        "description": description.strip(),
        "skill_path": relative,
        "skill_text": text,
        "skill_sha256": hashlib.sha256(data).hexdigest(),
        "skill_bytes": len(data),
        "provenance": provenance.strip(),
        "expected_git_blob": blob if isinstance(blob, str) else None,
        "forces_fixed_english_headers": bool(forced_headers(text)),
        "forced_headers": forced_headers(text),
    }
    return loaded, blob_errors


def _without_skill(condition_id: str, future: bool, description: str) -> dict[str, Any]:
    return {
        "id": condition_id,
        "future": future,
        "description": description,
        "skill_path": None,
        "skill_text": None,
        "skill_sha256": None,
        "skill_bytes": 0,
        "provenance": None,
        "expected_git_blob": None,
        "forces_fixed_english_headers": False,
        "forced_headers": [],
    }


def _check_blob(path: Path, expected: str, condition_id: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "hash-object", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return [f"{condition_id}: could not hash skill blob: {exc}"]
    actual = result.stdout.strip()
    if result.returncode != 0 or not actual:
        detail = result.stderr.strip() or "git hash-object failed"
        return [f"{condition_id}: {detail}"]
    if actual != expected:
        return [f"{condition_id}: skill blob {actual} does not match pinned {expected}"]
    return []


def audit_status(conditions: list[dict[str, Any]], errors: list[str]) -> str:
    if errors:
        return "fail"
    if any(item["forces_fixed_english_headers"] for item in conditions):
        return "fail"
    return "pass"
