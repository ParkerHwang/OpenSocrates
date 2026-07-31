#!/usr/bin/env python3
"""Generate deterministic JSON Schemas from the frozen Python model graph.

The generator intentionally uses only the standard library.  It reads the
small, fixed YAML manifest with a strict line parser, imports the model
registry, and serializes every schema with sorted keys and a terminal LF.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Literal, Mapping, Union, get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opensocrates.constants import MAX_REVIEWED_PROCEDURE_TEXT  # noqa: E402
from opensocrates.domain.models import SCHEMA_TYPES  # noqa: E402
from opensocrates.domain.validation import FrozenModel, canonical_json  # noqa: E402
from opensocrates.errors import SchemaGenerationError  # noqa: E402


def _manifest_entries(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith("#")
            or line in {"schemas:", "schema_manifest_version: 1.0.0"}
        ):
            continue
        if line.startswith("- "):
            if current is not None:
                entries.append(current)
            current = {}
            line = line[2:].strip()
        if ":" not in line or current is None:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip().strip("\"'")
    if current is not None:
        entries.append(current)
    required = {"file", "schema", "python_type", "compatibility"}
    if not entries or any(set(entry) != required for entry in entries):
        raise SchemaGenerationError("schema-manifest.yaml has malformed entries")
    return entries


def _resolve_type(dotted: str) -> type[FrozenModel]:
    module_name, _, type_name = dotted.rpartition(".")
    if not module_name or not type_name:
        raise SchemaGenerationError(f"invalid Python type path: {dotted}")
    module = importlib.import_module(module_name)
    value = getattr(module, type_name, None)
    if not isinstance(value, type) or not issubclass(value, FrozenModel):
        raise SchemaGenerationError(f"{dotted} is not a FrozenModel")
    return value


def _unwrap_new_type(annotation: Any) -> Any:
    while hasattr(annotation, "__supertype__"):
        annotation = annotation.__supertype__
    return annotation


def _is_annotated(annotation: Any) -> bool:
    return get_origin(annotation) is Annotated


def _schema_for_annotation(annotation: Any, metadata: Mapping[str, Any]) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    new_type_name = getattr(annotation, "__name__", None)
    annotation = _unwrap_new_type(annotation)
    if _is_annotated(annotation):
        annotated_args = get_args(annotation)
        annotation = annotated_args[0]
        if len(annotated_args) > 1:
            new_type_name = str(annotated_args[1])
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        options = get_args(annotation)
        if type(None) in options:
            return {
                "anyOf": [
                    _schema_for_annotation(item, metadata)
                    for item in options
                    if item is not type(None)
                ]
                + [{"type": "null"}]
            }
        return {"anyOf": [_schema_for_annotation(item, metadata) for item in options]}
    if origin in (list, tuple, set, frozenset):
        args = get_args(annotation)
        item = args[0] if args else Any
        return {"type": "array", "items": _schema_for_annotation(item, {})}
    if origin in (dict, Mapping):
        args = get_args(annotation)
        key = args[0] if len(args) == 2 else str
        item = args[1] if len(args) == 2 else Any
        result: dict[str, Any] = {
            "type": "object",
            "additionalProperties": _schema_for_annotation(item, {}),
        }
        key = _unwrap_new_type(key)
        if isinstance(key, type) and issubclass(key, Enum):
            result["propertyNames"] = {"enum": [member.value for member in key]}
        return result
    if origin is Literal:
        values = list(get_args(annotation))
        return {"enum": values}
    if annotation is Any or annotation is object:
        return {}
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return {"type": "string", "enum": [item.value for item in annotation]}
    if (
        isinstance(annotation, type)
        and is_dataclass(annotation)
        and issubclass(annotation, FrozenModel)
    ):
        return _object_schema(annotation)
    if annotation is str:
        result: dict[str, Any] = {"type": "string"}
        scalar = metadata.get("scalar")
        if scalar == "task_id":
            result["pattern"] = "^[0-9A-HJKMNP-TV-Z]{26}$"
        elif scalar == "event_id":
            result["pattern"] = (
                r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
            )
        elif scalar == "turn_token":
            result["pattern"] = "^[A-Za-z0-9_-]{43}$"
        elif scalar == "method_id":
            result["pattern"] = "^[a-z0-9]+(?:-[a-z0-9]+)*$"
        elif scalar == "semver":
            result["pattern"] = "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$"
        elif scalar == "sha256":
            result["pattern"] = "^sha256:[0-9a-f]{64}$"
        elif scalar == "decimal":
            result["pattern"] = "^-?(0|[1-9][0-9]*)(\\.[0-9]+)?$"
        elif scalar == "timestamp":
            result["pattern"] = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
        elif scalar == "date":
            result["pattern"] = r"^\d{4}-\d{2}-\d{2}$"
        if new_type_name == "ReviewedProcedureText":
            result["maxLength"] = MAX_REVIEWED_PROCEDURE_TEXT
        if "max_length" in metadata:
            result["maxLength"] = metadata["max_length"]
        return result
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is int:
        result = {"type": "integer"}
        if metadata.get("scalar") == "duration_ms":
            result.update({"minimum": 0, "maximum": 86_400_000})
        return result
    if annotation is float:
        return {"type": "number"}
    return {}


def _object_schema(model_type: type[FrozenModel]) -> dict[str, Any]:
    hints = get_type_hints(model_type, include_extras=True)
    properties: dict[str, Any] = {}
    required: list[str] = []
    required_fields = set(getattr(model_type, "__required_fields__", ()))
    for model_field in fields(model_type):
        properties[model_field.name] = _schema_for_annotation(
            hints.get(model_field.name, model_field.type), model_field.metadata
        )
        if "schema_const" in model_field.metadata:
            properties[model_field.name] = {
                "type": "string",
                "const": model_field.metadata["schema_const"],
            }
        if model_field.default is MISSING and model_field.default_factory is MISSING:
            required.append(model_field.name)
        if model_field.metadata.get("required"):
            required.append(model_field.name)
        if model_field.name in required_fields:
            required.append(model_field.name)
    result: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        result["required"] = sorted(set(required))
    return result


def schema_for_model(model_type: type[FrozenModel]) -> dict[str, Any]:
    schema_id = getattr(model_type, "__schema_id__", None)
    if not isinstance(schema_id, str):
        raise SchemaGenerationError(f"{model_type.__name__} does not declare __schema_id__")
    result = _object_schema(model_type)
    result.update(
        {
            "$id": schema_id,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": model_type.__name__,
        }
    )
    # Keep top-level keys stable and readable while canonical_json sorts them.
    return result


def classify_change(previous: Mapping[str, Any], current: Mapping[str, Any]) -> str:
    """Classify a schema diff as additive or breaking for future freeze checks."""

    previous_properties = previous.get("properties", {})
    current_properties = current.get("properties", {})
    if set(previous_properties) - set(current_properties):
        return "breaking"
    if set(previous.get("required", [])) - set(current.get("required", [])):
        return "breaking"
    for name, old_value in previous_properties.items():
        new_value = current_properties.get(name)
        if (
            new_value is None
            or old_value.get("enum", [])
            and set(old_value["enum"]) - set(new_value.get("enum", []))
        ):
            return "breaking"
    return "additive"


def generate(output_root: Path) -> list[Path]:
    manifest_path = ROOT / "schemas" / "source" / "schema-manifest.yaml"
    entries = _manifest_entries(manifest_path)
    if set(SCHEMA_TYPES) != {entry["file"] for entry in entries}:
        raise SchemaGenerationError("schema manifest and Python registry are out of sync")
    output_dir = output_root / "v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for entry in sorted(entries, key=lambda item: item["file"]):
        model_type = _resolve_type(entry["python_type"])
        if SCHEMA_TYPES.get(entry["file"]) is not model_type:
            raise SchemaGenerationError(f"schema manifest type mismatch for {entry['file']}")
        schema = schema_for_model(model_type)
        if schema["$id"] != entry["schema"]:
            raise SchemaGenerationError(f"schema ID mismatch for {entry['file']}")
        destination = output_dir / entry["file"]
        destination.write_text(canonical_json(schema), encoding="utf-8", newline="\n")
        generated.append(destination)
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "schemas")
    parser.add_argument("--check", action="store_true", help="fail if committed schemas differ")
    args = parser.parse_args(argv)
    if args.check:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            expected = generate(Path(directory))
            for generated in expected:
                committed = ROOT / "schemas" / "v1" / generated.name
                if not committed.exists() or committed.read_bytes() != generated.read_bytes():
                    raise SystemExit(f"generated schema differs: {committed}")
        print(f"schema check: PASS ({len(expected)} schemas)")
        return 0
    generated = generate(args.output_dir)
    print(f"generated {len(generated)} schemas in {args.output_dir / 'v1'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
