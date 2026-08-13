#!/usr/bin/env python3
"""Validate canonical content and compile the deterministic JSON bundle.

This is build tooling. It is the only v1 content surface allowed to parse YAML;
production imports only the compiled JSON loader.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensocrates.content.hashes import source_tree_hash
from opensocrates.content.locale import load_locale, validate_locale_parity
from opensocrates.content.manifest import build_content_bundle, serialize_bundle
from opensocrates.content.method import (
    build_reasoning_content_projections,
    compile_method,
    compile_method_content_projections,
    validate_cases,
    validate_procedure,
    validate_teacher_question_catalog,
)
from opensocrates.content.schema import (
    FROZEN_FAMILIES,
    FROZEN_METHOD_FAMILIES,
    FROZEN_METHOD_IDS,
    ContentValidationError,
    validate_catalog,
    validate_compiled_bundle_shape,
    validate_method_authoring,
    validate_routing_policy,
)
from opensocrates.domain.models import (
    InjectableReasoningContent,
    MethodAuthoring,
    ReasoningContentProjections,
    SelectionCatalogEntry,
)
from opensocrates.domain.validation import model_from_dict
from opensocrates.version import PRODUCT_VERSION

_POLICY_FILES = {
    "participation": "participation-policy.yaml",
    "risk": "risk-policy.yaml",
    "routing": "routing-policy.yaml",
    "card": "card-policy.yaml",
}
_PROMPT_KEYS = (
    "controller",
    "participation_rigor",
    "routing_classifier",
    "framing",
    "evidence_card_completion",
    "cross_exam",
    "strict_second_pass",
    "capability_notice",
)


def _parse_scalar(value: str) -> Any:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    value = value.strip()
    if value in ("", "null", "~"):
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            inner = value[1:-1].strip()
            return [] if not inner else [_parse_scalar(part) for part in inner.split(",")]
    if value.startswith("{") and value.endswith("}"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value
    if value[:1] in ("'", '"') and value[-1:] == value[:1]:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _minimal_yaml(text: str) -> Any:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    rows: list[tuple[int, str]] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw.strip() in {"---", "..."}:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        rows.append((indent, raw.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        if index >= len(rows) or rows[index][0] < indent:
            return {}, index
        is_list = rows[index][1].startswith("- ")
        result: Any = [] if is_list else {}
        while index < len(rows) and rows[index][0] == indent:
            line = rows[index][1]
            if is_list:
                if not line.startswith("- "):
                    break
                rest = line[2:].strip()
                if ":" in rest and not rest.startswith(("http://", "https://")):
                    key, raw_value = rest.split(":", 1)
                    item: dict[str, Any] = {key.strip().strip("'\""): _parse_scalar(raw_value)}
                    index += 1
                    if index < len(rows) and rows[index][0] > indent:
                        child, index = parse_block(index, rows[index][0])
                        if isinstance(child, Mapping):
                            item.update(child)
                    result.append(item)
                else:
                    result.append(_parse_scalar(rest))
                    index += 1
                continue
            if ":" not in line:
                raise ContentValidationError(f"YAML fallback: expected key/value at {line!r}")
            key, raw_value = line.split(":", 1)
            key = key.strip().strip("'\"")
            raw_value = raw_value.strip()
            index += 1
            if raw_value in {"|", ">", "|-", ">-"}:
                block_lines: list[str] = []
                while index < len(rows) and rows[index][0] > indent:
                    block_lines.append(rows[index][1])
                    index += 1
                result[key] = "\n".join(block_lines) + ("\n" if raw_value in {"|", ">"} else "")
            elif raw_value:
                result[key] = _parse_scalar(raw_value)
            elif index < len(rows) and rows[index][0] > indent:
                result[key], index = parse_block(index, rows[index][0])
            else:
                result[key] = {}
        return result, index

    if not rows:
        return {}
    value, index = parse_block(0, rows[0][0])
    if index != len(rows):
        raise ContentValidationError("YAML fallback: unparsed trailing content")
    return value


def parse_yaml_text(text: str) -> Any:
    """Parse JSON-compatible YAML, PyYAML when installed, or the build fallback."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore
    except ImportError:
        return _minimal_yaml(text)
    result = yaml.safe_load(text)
    return {} if result is None else result


def parse_yaml_file(path: Path) -> Any:
    return parse_yaml_text(path.read_text(encoding="utf-8"))


def _read(root: Path, relative: str) -> Any:
    path = root / relative
    if not path.is_file():
        raise ContentValidationError(f"missing required content source: {relative}")
    return parse_yaml_file(path)


def _validate_policy_shape(policy_id: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContentValidationError(f"policy.{policy_id}: expected object")
    schema = value.get("schema")
    if schema != f"opensocrates.{policy_id}-policy/1.0.0":
        raise ContentValidationError(f"policy.{policy_id}.schema: unsupported schema")
    if value.get("version") != "1.0.0":
        raise ContentValidationError(f"policy.{policy_id}.version: expected 1.0.0")
    return dict(value)


def _catalog_phase(
    content_root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, tuple[str, ...]]],
]:
    catalog = validate_catalog(_read(content_root, "catalog.yaml"))
    policies = {
        policy_id: _validate_policy_shape(policy_id, _read(content_root, filename))
        for policy_id, filename in _POLICY_FILES.items()
    }
    validate_routing_policy(policies["routing"])
    en = load_locale(_read(content_root, "locales/en.yaml"), expected_locale="en")
    ko = load_locale(_read(content_root, "locales/ko.yaml"), expected_locale="ko")
    validate_locale_parity(en, ko)
    method_data: dict[str, Any] = {}
    for method_id in FROZEN_METHOD_IDS:
        relative = f"methods/{method_id}/method.yaml"
        authored = validate_method_authoring(_read(content_root, relative), expected_id=method_id)
        try:
            model_from_dict(MethodAuthoring, authored)
        except Exception as exc:
            raise ContentValidationError(
                f"{relative}: domain MethodAuthoring contract: {exc}"
            ) from exc
        method_data[method_id] = authored
    teacher_questions = validate_teacher_question_catalog(
        _read(content_root, "teacher-questions.yaml")
    )
    return catalog, method_data, policies, {"en": en, "ko": ko}, teacher_questions


def _asset_paths(content_root: Path, method_id: str) -> dict[str, Path]:
    directory = content_root / "methods" / method_id
    return {
        "procedure.en": directory / "procedure.en.md",
        "procedure.ko": directory / "procedure.ko.md",
        "cases.en": directory / "cases.en.yaml",
        "cases.ko": directory / "cases.ko.yaml",
    }


def _full_phase(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    content_root: Path,
    method_data: Mapping[str, Mapping[str, Any]],
    teacher_questions: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> tuple[
    list[dict[str, Any]],
    ReasoningContentProjections | None,
    list[str],
]:
    compiled: list[dict[str, Any]] = []
    catalog_entries: list[SelectionCatalogEntry] = []
    injectable_content: list[InjectableReasoningContent] = []
    problems: list[str] = []
    for method_id in FROZEN_METHOD_IDS:
        paths = _asset_paths(content_root, method_id)
        missing = [
            f"methods/{method_id}/{label.split('.', 1)[0]}.{label.split('.', 1)[1]}.{'md' if label.startswith('procedure') else 'yaml'}"
            for label, path in paths.items()
            if not path.is_file()
        ]
        for relative in missing:
            problems.append(f"MISSING_ASSET {relative}")
        procedures: dict[str, str] = {}
        cases_by_locale: dict[str, Any] = {}
        for locale in ("en", "ko"):
            path = paths[f"procedure.{locale}"]
            if path.is_file():
                try:
                    procedures[locale] = validate_procedure(
                        path.read_text(encoding="utf-8"), method_id=method_id, locale=locale
                    )
                except ContentValidationError as exc:
                    problems.extend(f"INVALID {item}" for item in exc.errors)
        for locale in ("en", "ko"):
            path = paths[f"cases.{locale}"]
            if path.is_file():
                try:
                    cases_by_locale[locale] = validate_cases(
                        parse_yaml_file(path), method_id=method_id
                    )
                except ContentValidationError as exc:
                    problems.extend(f"INVALID {item}" for item in exc.errors)
        if (
            len(procedures) == 2
            and len(cases_by_locale) == 2
            and not any(f"MISSING_ASSET methods/{method_id}" in problem for problem in problems)
        ):
            try:
                compiled.append(
                    compile_method(
                        method_data[method_id],
                        procedures,
                        teacher_questions[method_id],
                    )
                )
                catalog_entry, injectable = compile_method_content_projections(
                    method_data[method_id],
                    procedures,
                    cases_by_locale,
                    teacher_questions[method_id],
                )
                catalog_entries.append(catalog_entry)
                injectable_content.extend(injectable)
            except ContentValidationError as exc:
                problems.extend(f"INVALID {item}" for item in exc.errors)
    if problems:
        return compiled, None, problems
    revisions = {entry.content_revision for entry in catalog_entries}
    if len(revisions) != 1:
        return compiled, None, ["INVALID reasoning content projections: mixed content revisions"]
    try:
        projections = build_reasoning_content_projections(
            content_revision=revisions.pop(),
            catalog_entries=tuple(catalog_entries),
            injectable_content=tuple(injectable_content),
        )
    except ContentValidationError as exc:
        return compiled, None, [*(f"INVALID {item}" for item in exc.errors)]
    return compiled, projections, problems


def _compile(
    root: Path,
    content_root: Path,
    methods: list[dict[str, Any]],
    locales: Mapping[str, Mapping[str, Any]],
    policies: Mapping[str, Mapping[str, Any]],
    output: Path,
    product_version: str,
) -> None:
    tree_hash = source_tree_hash(content_root, parse_yaml_file)
    first = build_content_bundle(
        product_version=product_version,
        content_revision=1,
        methods=methods,
        locales=locales,
        policies=policies,
        source_tree_hash=tree_hash,
    )
    second = build_content_bundle(
        product_version=product_version,
        content_revision=1,
        methods=methods,
        locales=locales,
        policies=policies,
        source_tree_hash=tree_hash,
    )
    first_bytes = serialize_bundle(first)
    second_bytes = serialize_bundle(second)
    if first_bytes != second_bytes:
        raise ContentValidationError("compiler is not byte-deterministic across two builds")
    validate_compiled_bundle_shape(first)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(first_bytes)
    print(
        f"COMPILED {output} bytes={len(first_bytes)} source_tree_hash={tree_hash} semantic_hash={first['normalized_semantic_hash']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="validate catalog, policies, locales, and method metadata only",
    )
    parser.add_argument("--content-root", type=Path, default=ROOT / "content")
    parser.add_argument("--output", type=Path, default=None, help="compiled bundle output path")
    parser.add_argument(
        "--reasoning-projections-output",
        type=Path,
        default=None,
        help="optional output path for the canonical OpenSocrates selector-content projection",
    )
    parser.add_argument("--product-version", default=PRODUCT_VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    content_root = args.content_root.resolve()
    try:
        _catalog_phase(content_root)
    except (ContentValidationError, OSError, json.JSONDecodeError) as exc:
        errors = exc.errors if isinstance(exc, ContentValidationError) else [str(exc)]
        print("CONTENT_INVALID", file=sys.stderr)
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    catalog, method_data, policies, locales, teacher_questions = _catalog_phase(content_root)
    family_counts = {
        family: len(
            [
                method_id
                for method_id in FROZEN_METHOD_IDS
                if FROZEN_METHOD_FAMILIES[method_id] == family
            ]
        )
        for family in FROZEN_FAMILIES
    }
    print(
        f"CATALOG_OK methods={len(method_data)} families={len(FROZEN_FAMILIES)} family_counts={family_counts}"
    )
    if args.catalog_only:
        return 0
    compiled, projections, problems = _full_phase(content_root, method_data, teacher_questions)
    if problems:
        print("CONTENT_INVALID", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    if projections is None:
        print("CONTENT_INVALID", file=sys.stderr)
        print("INVALID reasoning content projections were not built", file=sys.stderr)
        return 1
    if args.reasoning_projections_output is not None:
        projection_output = args.reasoning_projections_output.resolve()
        projection_output.parent.mkdir(parents=True, exist_ok=True)
        projection_output.write_text(projections.to_json(), encoding="utf-8", newline="\n")
    output = args.output.resolve() if args.output else content_root / "compiled-content.bundle.json"
    try:
        _compile(ROOT, content_root, compiled, locales, policies, output, args.product_version)
    except (ContentValidationError, OSError) as exc:
        errors = exc.errors if isinstance(exc, ContentValidationError) else [str(exc)]
        print("CONTENT_INVALID", file=sys.stderr)
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"CONTENT_OK methods={len(compiled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
