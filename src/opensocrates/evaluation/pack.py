"""Freeze authored public fixtures before any host is granted a task folder."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from .model import PHASES, LabError, enum, fields, identifier, text
from .storage import atomic_write, read_bytes, read_json, write_json


def material_name(value: Any) -> str:
    name = text(value, 240)
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
        or path.suffix != ".md"
        or str(path) != name
        or len(path.parts) > 4
    ):
        raise LabError("invalid_material")
    return name


def _case(case: Any) -> dict[str, Any]:
    required = {
        "id",
        "phase",
        "family",
        "title",
        "locale",
        "prompt",
        "deliverable",
        "materials",
        "clarification_reply",
        "evaluator_checks",
    }
    fields(case, required, required)
    identifier(case["id"])
    enum(case["phase"], PHASES)
    enum(case["locale"], ("en", "ko"))
    for key in ("family", "title", "prompt", "deliverable", "clarification_reply"):
        text(case[key], 16000)
    for key in ("materials", "evaluator_checks"):
        if not isinstance(case[key], list) or len(case[key]) > 30:
            raise LabError("invalid_pack")
    for value in case["materials"]:
        material_name(value)
    for value in case["evaluator_checks"]:
        text(value, 4000)
    if len(set(case["materials"])) != len(case["materials"]):
        raise LabError("invalid_pack")
    return dict(case)


def load_pack(source: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    manifest_bytes = read_bytes(source / "pack.json", 512000)
    manifest = read_json(source / "pack.json", 512000)
    required = {"schema", "id", "version", "public_synthetic", "b_instruction", "cases"}
    fields(manifest, required, required)
    if (
        manifest["schema"] != "opensocrates.office-pack/1"
        or manifest["public_synthetic"] is not True
    ):
        raise LabError("invalid_pack")
    identifier(manifest["id"])
    text(manifest["version"], 100)
    instructions = manifest["b_instruction"]
    fields(instructions, {"en", "ko"}, {"en", "ko"})
    for value in instructions.values():
        text(value, 8000)
    cases = manifest["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 60:
        raise LabError("invalid_pack")
    manifest["cases"] = [_case(case) for case in cases]
    if len({case["id"] for case in cases}) != len(cases):
        raise LabError("invalid_pack")
    materials: dict[str, bytes] = {}
    for case in cases:
        for name in case["materials"]:
            content = read_bytes(source / name, 65536)
            text(content.decode("utf-8"), 65536)
            materials[name] = content
    digest = hashlib.sha256(manifest_bytes)
    for name, content in sorted(materials.items()):
        digest.update(name.encode() + b"\x00" + content + b"\x00")
    return manifest, materials, digest.hexdigest()


def freeze_pack(source: Path, destination: Path) -> dict[str, Any]:
    manifest, materials, digest = load_pack(source)
    write_json(destination / "pack.json", manifest)
    for name, content in materials.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(target, content)
    # The original pack serialization is included in identity; retain its exact bytes.
    atomic_write(destination / "pack.json", read_bytes(source / "pack.json", 512000))
    return {"id": manifest["id"], "version": manifest["version"], "sha256": digest}
