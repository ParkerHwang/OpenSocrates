"""Method authoring validation and deterministic compiled-method projection."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from ..domain.models import (
    InjectableReasoningContent,
    ReasoningContentProjections,
    SelectionCatalog,
    SelectionCatalogEntry,
    TemplateExample,
)
from .hashes import normalize_markdown
from .schema import (
    CASES_SCHEMA,
    FROZEN_FEATURES,
    FROZEN_METHOD_IDS,
    ContentValidationError,
    validate_method_authoring,
    validate_reasoning_content_projections_shape,
)

PROCEDURE_HEADINGS = (
    "Purpose",
    "Use when",
    "Do not use when",
    "Inputs to establish",
    "Procedure",
    "Public output contract",
    "Evidence and uncertainty rules",
    "Stop conditions",
    "Complement handoff",
)
TEACHER_QUESTION_HEADING = "Teacher questions"
TEACHER_QUESTION_COUNT = 3
TEACHER_QUESTION_MIN_CHARS = 20
TEACHER_QUESTION_MAX_CHARS = 220
TEACHER_QUESTIONS_SCHEMA = "opensocrates.teacher-questions/1.0.0"
_CASE_FIELDS = {
    "id",
    "kind",
    "prompt",
    "expected_route",
    "expected_behavior",
    "decisive_features",
    "rationale",
}
_CASE_KINDS = {"positive", "negative", "mechanical", "explicit", "insufficiency"}
_CASE_BEHAVIORS = {"route", "no_route", "explicit_primary", "hold", "refuse"}
_CASE_ID_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*-(?:positive|negative|mechanical|explicit|insufficiency)-[0-9]+$"
)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_STEP_RE = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _heading_positions(text: str) -> list[tuple[str, int]]:
    positions: list[tuple[str, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        match = _HEADING_RE.match(line)
        if match:
            positions.append((match.group(1), offset))
        offset += len(line)
    return positions


def validate_procedure(text: str, *, method_id: str, locale: str) -> str:
    normalized = normalize_markdown(text)
    headings = [heading for heading, _ in _heading_positions(normalized)]
    if headings != list(PROCEDURE_HEADINGS):
        raise ContentValidationError(
            f"{method_id}.procedure.{locale}: expected exact nine headings"
        )
    words = _word_count(normalized)
    if not 350 <= words <= 900:
        raise ContentValidationError(
            f"{method_id}.procedure.{locale}: expected 350-900 words, got {words}"
        )
    procedure_index = headings.index("Procedure")
    next_heading_index = procedure_index + 1
    positions = _heading_positions(normalized)
    start = positions[procedure_index][1]
    end = (
        positions[next_heading_index][1] if next_heading_index < len(positions) else len(normalized)
    )
    step_count = len(_STEP_RE.findall(normalized[start:end]))
    if not 5 <= step_count <= 9:
        raise ContentValidationError(
            f"{method_id}.procedure.{locale}: expected 5-9 numbered steps, got {step_count}"
        )
    return normalized


def complement_fragment(text: str, *, method_id: str, locale: str) -> str:
    normalized = validate_procedure(text, method_id=method_id, locale=locale)
    positions = _heading_positions(normalized)
    index = [heading for heading, _ in positions].index("Complement handoff")
    start = positions[index][1]
    heading_end = normalized.find("\n", start)
    body = normalized[heading_end + 1 :] if heading_end >= 0 else ""
    if not body.strip():
        raise ContentValidationError(
            f"{method_id}.procedure.{locale}: complement handoff cannot be empty"
        )
    return normalize_markdown(body)


def validate_cases(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    value: Any, *, method_id: str, known_features: set[str] | frozenset[str] = FROZEN_FEATURES
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContentValidationError(f"{method_id}.cases: expected an object")
    if set(value) != {"schema", "cases"} or value.get("schema") != CASES_SCHEMA:
        raise ContentValidationError(f"{method_id}.cases: expected schema and cases only")
    cases = value.get("cases")
    if not isinstance(cases, list):
        raise ContentValidationError(f"{method_id}.cases: cases must be a list")
    seen: set[str] = set()
    counts = {kind: 0 for kind in _CASE_KINDS}
    for index, raw_case in enumerate(cases):
        if not isinstance(raw_case, Mapping) or set(raw_case) != _CASE_FIELDS:
            raise ContentValidationError(
                f"{method_id}.cases[{index}]: fields must be exactly {sorted(_CASE_FIELDS)}"
            )
        case = dict(raw_case)
        case_id = case["id"]
        if (
            not isinstance(case_id, str)
            or not _CASE_ID_RE.fullmatch(case_id)
            or not case_id.startswith(f"{method_id}-")
            or case_id in seen
        ):
            raise ContentValidationError(
                f"{method_id}.cases[{index}].id: expected unique {method_id}-<kind>-<ordinal> ID"
            )
        seen.add(case_id)
        kind = case["kind"]
        if kind not in _CASE_KINDS:
            raise ContentValidationError(f"{method_id}.cases[{index}].kind: unknown case kind")
        counts[kind] += 1
        for field in ("prompt", "rationale"):
            if (
                not isinstance(case[field], str)
                or not case[field].strip()
                or len(case[field]) > 4000
            ):
                raise ContentValidationError(
                    f"{method_id}.cases[{index}].{field}: bounded non-empty string required"
                )
        route = case["expected_route"]
        if route is not None and route not in FROZEN_METHOD_IDS:
            raise ContentValidationError(
                f"{method_id}.cases[{index}].expected_route: unknown MethodId"
            )
        behavior = case["expected_behavior"]
        if behavior not in _CASE_BEHAVIORS:
            raise ContentValidationError(
                f"{method_id}.cases[{index}].expected_behavior: unknown behavior"
            )
        features = case["decisive_features"]
        if not isinstance(features, list) or any(
            not isinstance(feature, str) or feature not in known_features for feature in features
        ):
            raise ContentValidationError(
                f"{method_id}.cases[{index}].decisive_features: unknown feature"
            )
        expected_behavior = {
            "positive": {"route"},
            "negative": {"route", "no_route", "hold"},
            "mechanical": {"no_route", "refuse"},
            "explicit": {"explicit_primary", "refuse"},
            "insufficiency": {"hold", "refuse"},
        }[kind]
        if behavior not in expected_behavior:
            raise ContentValidationError(
                f"{method_id}.cases[{index}]: behavior does not match kind {kind}"
            )
        if kind == "negative" and behavior == "route" and route == method_id:
            raise ContentValidationError(
                f"{method_id}.cases[{index}]: close-negative route must target a different method"
            )
    required = {"positive": 3, "negative": 2, "mechanical": 1, "explicit": 1, "insufficiency": 1}
    missing = [f"{kind}>={amount}" for kind, amount in required.items() if counts[kind] < amount]
    if missing:
        raise ContentValidationError(
            f"{method_id}.cases: distribution missing {', '.join(missing)}"
        )
    return {"schema": CASES_SCHEMA, "cases": [dict(item) for item in cases]}


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    """Keep canonical-source order while omitting repeated catalog metadata values."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _template_examples(cases: Mapping[str, Any]) -> tuple[TemplateExample, ...]:
    return tuple(
        TemplateExample(
            case_id=case["id"],
            kind=case["kind"],
            template_prompt=case["prompt"],
            expected_route=case["expected_route"],
            expected_behavior=case["expected_behavior"],
            decisive_features=tuple(case["decisive_features"]),
            rationale=case["rationale"],
        )
        for case in cases["cases"]
    )


def attach_teacher_questions(procedure: str, questions: Sequence[str]) -> str:
    """Prefix authored teacher questions without altering the validated procedure body."""

    if len(questions) != TEACHER_QUESTION_COUNT:
        raise ContentValidationError("teacher questions: expected exactly three questions")
    bullets = "\n".join(f"- {question}" for question in questions)
    return normalize_markdown(f"## {TEACHER_QUESTION_HEADING}\n\n{bullets}\n\n{procedure}")


def _validate_question_list(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != TEACHER_QUESTION_COUNT:
        raise ContentValidationError(f"{path}: expected {TEACHER_QUESTION_COUNT} questions")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(raw, str):
            raise ContentValidationError(f"{item_path}: expected text")
        question = raw.strip()
        if question != raw:
            raise ContentValidationError(f"{item_path}: surrounding whitespace is not allowed")
        length = len(question)
        if not TEACHER_QUESTION_MIN_CHARS <= length <= TEACHER_QUESTION_MAX_CHARS:
            raise ContentValidationError(
                f"{item_path}: expected {TEACHER_QUESTION_MIN_CHARS}-{TEACHER_QUESTION_MAX_CHARS} characters"
            )
        if not question.endswith("?"):
            raise ContentValidationError(f"{item_path}: must end with a question mark")
        if "\n" in question or "\x00" in question:
            raise ContentValidationError(f"{item_path}: must be a single line")
        if question in seen:
            raise ContentValidationError(f"{item_path}: duplicate question")
        seen.add(question)
        normalized.append(question)
    return tuple(normalized)


def validate_teacher_question_catalog(
    value: Any,
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Validate the bilingual teacher-question catalog for the frozen 48 methods."""

    if not isinstance(value, Mapping):
        raise ContentValidationError("teacher-questions: expected an object")
    data = dict(value)
    if set(data) != {"schema", "content_revision", "methods"}:
        raise ContentValidationError(
            "teacher-questions: expected schema, content revision, methods"
        )
    if data["schema"] != TEACHER_QUESTIONS_SCHEMA:
        raise ContentValidationError("teacher-questions.schema: unsupported schema")
    if data["content_revision"] != 1:
        raise ContentValidationError("teacher-questions.content_revision: expected 1")
    methods = data["methods"]
    if not isinstance(methods, Mapping):
        raise ContentValidationError("teacher-questions.methods: expected an object")
    if set(methods) != set(FROZEN_METHOD_IDS):
        raise ContentValidationError(
            "teacher-questions.methods: expected exactly the frozen 48 IDs"
        )
    catalog: dict[str, dict[str, tuple[str, ...]]] = {}
    for method_id in FROZEN_METHOD_IDS:
        localized = methods[method_id]
        if not isinstance(localized, Mapping) or set(localized) != {"en", "ko"}:
            raise ContentValidationError(f"teacher-questions.{method_id}: expected en and ko")
        catalog[method_id] = {
            locale: _validate_question_list(
                localized[locale], f"teacher-questions.{method_id}.{locale}"
            )
            for locale in ("en", "ko")
        }
    return catalog


def compile_method_content_projections(
    authoring: Mapping[str, Any],
    procedures: Mapping[str, str],
    cases_by_locale: Mapping[str, Any],
    teacher_questions: Mapping[str, Sequence[str]] | None = None,
) -> tuple[SelectionCatalogEntry, tuple[InjectableReasoningContent, ...]]:
    """Project one validated method into compact selector data and injectable source text.

    The projection intentionally keeps the legacy ``CompiledMethod`` unchanged.
    It derives catalog fields from existing metadata/routing cases and carries every
    case only in the separate injectable projection as untrusted template data.
    """

    data = validate_method_authoring(authoring)
    method_id = data["id"]
    if set(procedures) != {"en", "ko"} or set(cases_by_locale) != {"en", "ko"}:
        raise ContentValidationError(f"{method_id}: expected en and ko procedures/cases")
    normalized_procedures = {
        locale: validate_procedure(procedures[locale], method_id=method_id, locale=locale)
        for locale in ("en", "ko")
    }
    normalized_cases = {
        locale: validate_cases(cases_by_locale[locale], method_id=method_id)
        for locale in ("en", "ko")
    }
    routing = data["routing"]
    suitable_features = _ordered_unique(list(routing["positive_features"]))
    unsuitable_features = _ordered_unique(
        [*routing["negative_features"], *routing["contraindications"]]
    )
    confused_features = _ordered_unique(
        [
            feature
            for case in normalized_cases["en"]["cases"]
            if case["kind"] == "negative"
            for feature in case["decisive_features"]
        ]
    )
    related_method_ids = _ordered_unique(
        [
            *data["complements"]["preferred"],
            *[
                case["expected_route"]
                for case in normalized_cases["en"]["cases"]
                if case["kind"] == "negative"
                and case["expected_route"] is not None
                and case["expected_route"] != method_id
            ],
        ]
    )
    content_revision = data["content_revision"]
    catalog_entry = SelectionCatalogEntry(
        method_id=method_id,
        family=data["family"],
        content_revision=content_revision,
        display_name=dict(data["display_name"]),
        core_purpose=dict(data["plain_action"]),
        suitable_features=suitable_features,
        unsuitable_features=unsuitable_features,
        commonly_confused_features=confused_features,
        related_method_ids=related_method_ids,
        injectable_content_locator=f"injectable-content/{content_revision}/{method_id}",
    )
    injectable = tuple(
        InjectableReasoningContent(
            method_id=method_id,
            content_revision=content_revision,
            locale=locale,
            display_name=data["display_name"][locale],
            theory=_theory_with_questions(normalized_procedures[locale], teacher_questions, locale),
            template_examples=_template_examples(normalized_cases[locale]),
        )
        for locale in ("en", "ko")
    )
    return catalog_entry, injectable


def build_reasoning_content_projections(
    *,
    content_revision: int,
    catalog_entries: tuple[SelectionCatalogEntry, ...],
    injectable_content: tuple[InjectableReasoningContent, ...],
) -> ReasoningContentProjections:
    """Bind catalog and injectable content to one immutable, validated revision."""

    projections = ReasoningContentProjections(
        content_revision=content_revision,
        selection_catalog=SelectionCatalog(
            content_revision=content_revision,
            entries=catalog_entries,
        ),
        injectable_content=injectable_content,
    )
    try:
        validate_reasoning_content_projections_shape(projections.to_dict())
    except ContentValidationError:
        raise
    except Exception as exc:  # Defensive boundary for the typed-to-JSON projection.
        raise ContentValidationError(
            f"reasoning content projections: invalid typed projection: {exc}"
        ) from exc
    return projections


def _theory_with_questions(
    procedure: str,
    teacher_questions: Mapping[str, Sequence[str]] | None,
    locale: str,
) -> str:
    if teacher_questions is None:
        return procedure
    if locale not in teacher_questions:
        raise ContentValidationError(f"teacher questions: missing {locale}")
    return attach_teacher_questions(procedure, teacher_questions[locale])


def compile_method(
    authoring: Mapping[str, Any],
    procedures: Mapping[str, str],
    teacher_questions: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    data = validate_method_authoring(authoring)
    method_id = data["id"]
    if set(procedures) != {"en", "ko"}:
        raise ContentValidationError(f"{method_id}.procedure: expected en and ko")
    normalized = {
        locale: _theory_with_questions(
            validate_procedure(procedures[locale], method_id=method_id, locale=locale),
            teacher_questions,
            locale,
        )
        for locale in ("en", "ko")
    }
    fragments = {
        locale: complement_fragment(procedures[locale], method_id=method_id, locale=locale)
        for locale in ("en", "ko")
    }
    participation_data = data["participation"]
    routing_data = data["routing"]
    output_data = data["output_contract"]
    complements_data = data["complements"]
    participation = {
        "judgment_only": participation_data["judgment_only"],
        "allowed_answer_shapes": list(participation_data["allowed_answer_shapes"]),
    }
    routing = {
        "positive_features": dict(routing_data["positive_features"]),
        "negative_features": dict(routing_data["negative_features"]),
        "minimum_score": routing_data["minimum_score"],
        "contraindications": list(routing_data["contraindications"]),
    }
    output_contract = {
        "required_sections": list(output_data["required_sections"]),
        "max_questions": output_data["max_questions"],
    }
    complements = {
        "preferred": list(complements_data["preferred"]),
        "incompatible_secondary": list(complements_data["incompatible_secondary"]),
    }
    routing["negative_features"] = {**routing["negative_features"], "mechanical": 3}
    routing["contraindications"] = [*routing["contraindications"], "mechanical"]
    result = {
        "schema": "opensocrates.compiled-method/1.0.0",
        "id": method_id,
        "family": data["family"],
        "content_revision": data["content_revision"],
        "display_name": data["display_name"],
        "plain_action": data["plain_action"],
        "participation": participation,
        "routing": routing,
        "output_contract": output_contract,
        "complements": complements,
        "procedure": normalized,
        "complement_fragment": fragments,
    }
    if (
        routing["negative_features"].get("mechanical") != 3
        or "mechanical" not in routing["contraindications"]
    ):
        raise ContentValidationError(f"{method_id}: mechanical routing guard was not compiled")
    return result
