"""Strict model adapters and shared scalar/cross-field validators.

The validator is deliberately fail-closed: dataclass construction is never a
permission to accept an unknown field or enum value, and canonical JSON is
always emitted with sorted keys, compact separators, and one final LF.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Mapping as ABCMapping
from dataclasses import MISSING, Field, dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import UnionType
from typing import (
    Annotated,
    Any,
    Literal,
    Mapping,
    TypeAlias,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from urllib.parse import parse_qsl, urlsplit

from ..constants import MAX_DURATION_MS, MAX_REVIEWED_PROCEDURE_TEXT, MAX_SAFE_TEXT
from ..errors import (
    IdentifierError,
    MissingFieldError,
    SerializationError,
    UnknownEnumValueError,
    UnknownFieldError,
    ValidationError,
)
from ..ids import (
    validate_decimal_string,
    validate_event_id,
    validate_local_id,
    validate_method_id,
    validate_semver,
    validate_sha256,
    validate_task_id,
    validate_timestamp,
    validate_turn_token,
)
from .enums import (
    FAMILY_IDS,
    CapabilityEvidenceKind,
    CapabilityStatus,
    ConflictResolution,
    CriterionStatus,
    EventType,
    EvidenceState,
    FeatureKey,
    HostControlStatus,
    JudgmentState,
    Participation,
    RecordingMode,
    Rigor,
    RoundingMode,
    RouterReasonCode,
    VerificationOutcome,
)

TaskId: TypeAlias = Annotated[str, "TaskId"]
JudgmentId: TypeAlias = Annotated[str, "JudgmentId"]
ClaimId: TypeAlias = Annotated[str, "ClaimId"]
EvidenceId: TypeAlias = Annotated[str, "EvidenceId"]
AlternativeId: TypeAlias = Annotated[str, "AlternativeId"]
CriterionId: TypeAlias = Annotated[str, "CriterionId"]
InterventionId: TypeAlias = Annotated[str, "InterventionId"]
EventId: TypeAlias = Annotated[str, "EventId"]
TurnToken: TypeAlias = Annotated[str, "TurnToken"]
MethodId: TypeAlias = Annotated[str, "MethodId"]
FamilyId: TypeAlias = Annotated[str, "FamilyId"]
Locale: TypeAlias = Annotated[str, "Locale"]
SemVer: TypeAlias = Annotated[str, "SemVer"]
Sha256: TypeAlias = Annotated[str, "Sha256"]
SafeText: TypeAlias = Annotated[str, "SafeText"]
ReviewedProcedureText: TypeAlias = Annotated[str, "ReviewedProcedureText"]
DecimalString: TypeAlias = Annotated[str, "DecimalString"]
DurationMs: TypeAlias = Annotated[int, "DurationMs"]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_QUERY_KEYS = {"token", "key", "secret", "signature", "sig", "auth", "code", "session"}
_FORBIDDEN_KEYS = {
    "reasoning",
    "thoughts",
    "chain_of_thought",
    "transcript",
    "transcript_path",
    "prompt",
    "raw_output",
    "tool_output",
    "messages",
    "password",
    "secret",
    "token",
    "api_key",
    "credential",
    "cookie",
}
_INTERNAL_VOCABULARY = {
    "opensocrates",
    "host-control",
    "turn_token",
    "record_event",
    "chain_of_thought",
}
_NON_PROSE_PAYLOAD_KEYS = frozenset(
    {
        "schema",
        "message_id",
        "turn_token",
        "message_type",
        "event_id",
        "event_type",
        "host",
        "host_version",
        "adapter_version",
        "task_id",
        "judgment_id",
        "claim_id",
        "source_id",
        "criterion_id",
        "alternative_id",
        "method_id",
        "primary_method",
        "secondary_method",
        "family",
        "primary_family",
        "secondary_family",
        "locale",
        "answer_shape",
        "allowed_answer_shapes",
        "classification_confidence",
        "key",
        "basis",
        "feature",
        "features",
        "reason_code",
        "risk_reason",
        "stored_rigor",
        "task_override",
        "risk_floor",
        "effective_rigor",
        "participation",
        "confidence_basis",
        "explicit_method",
        "status",
        "outcome",
        "kind",
        "state",
        "strength",
        "direction",
        "source_kind",
        "event",
        "duration_bucket_ms",
        "id",
        "next_action",
        "error_code",
        "host_session_key",
        "host_turn_key",
        "payload_tag",
        "token_tag",
        "tool_category",
        "recording_mode",
        "metrics_consent",
        "reason",
        "class",
        "feedback_class",
        "feedback_outcome",
    }
)
_CATEGORY_PAYLOAD_KEYS = frozenset(
    {"judgment_targets", "mechanical_targets", "target", "targets", "category", "categories"}
)
_CODE_VALUE_RE = re.compile(r"^[A-Za-z0-9_./:+-]+$")


@dataclass(frozen=True, slots=True)
class FrozenModel:
    """Base class for immutable, schema-shaped domain models."""

    def to_dict(self) -> dict[str, Any]:
        return model_to_dict(self)

    def to_json(self) -> str:
        return canonical_json(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Any:
        return model_from_dict(cls, value)

    @classmethod
    def from_json(cls, value: str | bytes) -> Any:
        return model_from_json(cls, value)

    def __post_init__(self) -> None:
        # Dataclass-generated constructors invoke inherited __post_init__, so
        # direct construction is held to the same contract as from_dict.
        validate_model(self)


def _is_new_type(annotation: Any) -> bool:
    return hasattr(annotation, "__supertype__")


def _unwrap_annotation(annotation: Any) -> Any:
    while _is_new_type(annotation):
        annotation = annotation.__supertype__
    if get_origin(annotation) is Literal:
        return annotation
    if get_origin(annotation) is not None and str(get_origin(annotation)).endswith("Annotated"):
        return get_args(annotation)[0]
    return annotation


def _convert_value(annotation: Any, value: Any, path: str) -> Any:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Convert a JSON-compatible value to a typed model value, fail-closed."""

    if _is_new_type(annotation):
        return _convert_value(annotation.__supertype__, value, path)
    origin = get_origin(annotation)
    if origin is not None and str(origin).endswith("Annotated"):
        return _convert_value(get_args(annotation)[0], value, path)
    if annotation is Any or annotation is object:
        return value
    if origin in (Union, UnionType):
        options = get_args(annotation)
        if value is None and type(None) in options:
            return None
        errors: list[Exception] = []
        for option in options:
            if option is type(None):
                continue
            try:
                return _convert_value(option, value, path)
            except (ValidationError, TypeError, ValueError) as exc:
                errors.append(exc)
        raise ValidationError(f"{path}: value does not match any allowed type") from errors[-1]
    if origin in (list, tuple, set, frozenset):
        if not isinstance(value, (list, tuple)):
            raise ValidationError(f"{path}: expected an array")
        args = get_args(annotation)
        item_annotation = args[0] if args else Any
        converted = [
            _convert_value(item_annotation, item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
        if origin is tuple:
            return tuple(converted)
        if origin is set:
            return set(converted)
        if origin is frozenset:
            return frozenset(converted)
        return converted
    if origin in (dict, Mapping, ABCMapping):
        if not isinstance(value, Mapping):
            raise ValidationError(f"{path}: expected an object")
        args = get_args(annotation)
        key_annotation = args[0] if len(args) == 2 else str
        value_annotation = args[1] if len(args) == 2 else Any
        if any(not isinstance(key, str) for key in value):
            raise ValidationError(f"{path}: object keys must be strings")
        return {
            _convert_value(key_annotation, key, f"{path}.{key}"): _convert_value(
                value_annotation, item, f"{path}.{key}"
            )
            for key, item in value.items()
        }
    if origin is not None and str(origin).endswith("Mapping"):
        if not isinstance(value, Mapping):
            raise ValidationError(f"{path}: expected an object")
        args = get_args(annotation)
        key_annotation = args[0] if len(args) == 2 else str
        value_annotation = args[1] if len(args) == 2 else Any
        return {
            _convert_value(key_annotation, key, f"{path}.{key}"): _convert_value(
                value_annotation, item, f"{path}.{key}"
            )
            for key, item in value.items()
        }
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if not isinstance(value, str):
            raise ValidationError(f"{path}: closed enum values must be strings")
        try:
            return annotation(value)
        except ValueError as exc:
            raise UnknownEnumValueError(f"{path}: unknown enum value {value!r}") from exc
    if (
        isinstance(annotation, type)
        and is_dataclass(annotation)
        and issubclass(annotation, FrozenModel)
    ):
        if not isinstance(value, Mapping):
            raise ValidationError(f"{path}: expected an object")
        return model_from_dict(annotation, value, require_schema=False)
    if annotation is str:
        if not isinstance(value, str):
            raise ValidationError(f"{path}: expected a string")
        return value
    if annotation is bool:
        if not isinstance(value, bool):
            raise ValidationError(f"{path}: expected a boolean")
        return value
    if annotation is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(f"{path}: expected an integer")
        return value
    if annotation is float:
        if (
            not isinstance(value, (float, int))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValidationError(f"{path}: expected a finite number")
        return float(value)
    if annotation is datetime:
        if not isinstance(value, str):
            raise ValidationError(f"{path}: expected a timestamp string")
        return value
    if annotation is date:
        if not isinstance(value, str):
            raise ValidationError(f"{path}: expected a date string")
        return value
    return value


def model_from_dict(
    model_type: type[Any], value: Mapping[str, Any], *, require_schema: bool = True
) -> Any:
    """Construct a model while rejecting unknown and missing contract fields."""

    if not isinstance(value, Mapping):
        raise ValidationError(f"{model_type.__name__}: expected an object")
    model_fields = fields(model_type)
    allowed = {field.name for field in model_fields}
    unknown = [key for key in value if key not in allowed]
    if unknown:
        raise UnknownFieldError(
            f"{model_type.__name__}: unknown field(s): {', '.join(sorted(unknown))}"
        )
    if require_schema and "schema" in allowed and "schema" not in value:
        raise MissingFieldError(f"{model_type.__name__}: schema is required")
    required_fields = set(getattr(model_type, "__required_fields__", ()))
    if not require_schema:
        required_fields.discard("schema")
    hints = get_type_hints(model_type, include_extras=True)
    converted: dict[str, Any] = {}
    for field in model_fields:
        if field.name not in value:
            if field.name not in required_fields and (
                field.default is not MISSING or field.default_factory is not MISSING
            ):
                continue
            raise MissingFieldError(f"{model_type.__name__}: missing field {field.name}")
        converted[field.name] = _convert_value(
            hints.get(field.name, field.type), value[field.name], field.name
        )
    try:
        model = model_type(**converted)
    except TypeError as exc:
        raise ValidationError(f"{model_type.__name__}: invalid fields") from exc
    validate_model(model)
    return model


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {
            (key.value if isinstance(key, Enum) else str(key)): _json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def model_to_dict(model: Any) -> dict[str, Any]:
    if not is_dataclass(model):
        raise SerializationError("canonical adapter requires a dataclass model")
    result = _json_value(model)
    if not isinstance(result, dict):
        raise SerializationError("canonical model did not produce an object")
    return result


def canonical_json(value: Any) -> str:
    """Serialize a model or JSON-compatible value canonically with a final LF."""

    try:
        encoded = json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SerializationError("value is not canonical JSON compatible") from exc
    return encoded + "\n"


def model_from_json(model_type: type[Any], value: str | bytes) -> Any:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SerializationError("JSON must be UTF-8") from exc
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SerializationError("invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise SerializationError("model JSON must be an object")
    return model_from_dict(model_type, decoded)


def validate_safe_text(
    value: Any,
    *,
    field_name: str = "text",
    max_length: int = MAX_SAFE_TEXT,
    allow_newline: bool = True,
    allow_tab: bool = True,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name}: expected text")
    if len(value) > max_length:
        raise ValidationError(f"{field_name}: exceeds {max_length} Unicode scalar values")
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError(f"{field_name}: text must be Unicode NFC")
    for character in value:
        if character == "\n" and allow_newline:
            continue
        if character == "\t" and allow_tab:
            continue
        if ord(character) < 0x20 or ord(character) == 0x7F:
            raise ValidationError(f"{field_name}: contains a forbidden control character")
    return value


def validate_date(value: Any, *, field_name: str = "date") -> str:
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        raise ValidationError(f"{field_name}: expected YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field_name}: invalid calendar date") from exc
    return value


def validate_locale(value: Any, *, field_name: str = "locale") -> str:
    if not isinstance(value, str) or value not in {"en", "ko"}:
        raise ValidationError(f"{field_name}: locale must be en or ko")
    return value


def validate_url(
    value: Any,
    *,
    field_name: str = "uri",
    allow_none: bool = True,
    sanitize_credentials: bool = False,
) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field_name}: expected URL text or null")
    parsed = urlsplit(value)
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError(f"{field_name}: URL userinfo is not allowed")
    if parsed.scheme == "file" or not parsed.netloc:
        raise ValidationError(f"{field_name}: only network URLs are persistable")
    if parsed.scheme not in {"https", "http"}:
        raise ValidationError(f"{field_name}: unsupported URL scheme")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValidationError(f"{field_name}: HTTP is only allowed for localhost fixtures")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SAFE_QUERY_KEYS:
            if sanitize_credentials:
                return None
            raise ValidationError(f"{field_name}: credential-like query key is not allowed")
    return value


def sanitize_persistable_uri(value: Any) -> str | None:
    """Validate a URI and drop it when its query resembles a credential."""

    return validate_url(value, allow_none=True, sanitize_credentials=True)


def validate_sha_or_none(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return validate_sha256(value)
    except IdentifierError as exc:
        raise ValidationError(f"{field_name}: invalid SHA-256") from exc


def check_forbidden_keys(value: Any, *, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _FORBIDDEN_KEYS:
                raise ValidationError(f"{path}.{key}: forbidden field")
            check_forbidden_keys(child, path=f"{path}.{key}".strip("."))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            check_forbidden_keys(child, path=f"{path}[{index}]")


def _validate_scalar(field: Field[Any], value: Any) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    scalar = field.metadata.get("scalar")
    name = field.name
    if scalar == "safe_text":
        validate_safe_text(
            value, field_name=name, max_length=field.metadata.get("max_length", MAX_SAFE_TEXT)
        )
    elif scalar == "timestamp":
        try:
            validate_timestamp(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid timestamp") from exc
    elif scalar == "date":
        validate_date(value, field_name=name)
    elif scalar == "task_id":
        try:
            validate_task_id(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid TaskId") from exc
    elif scalar == "event_id":
        try:
            validate_event_id(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid EventId") from exc
    elif scalar == "turn_token":
        try:
            validate_turn_token(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid TurnToken") from exc
    elif scalar == "method_id":
        try:
            validate_method_id(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid MethodId") from exc
    elif scalar == "semver":
        try:
            validate_semver(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid SemVer") from exc
    elif scalar == "sha256":
        try:
            validate_sha256(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid Sha256") from exc
    elif scalar == "decimal":
        try:
            validate_decimal_string(value)
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid DecimalString") from exc
    elif scalar == "duration_ms":
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_DURATION_MS
        ):
            raise ValidationError(f"{name}: invalid DurationMs")
    elif scalar and scalar.startswith("local_id:"):
        try:
            validate_local_id(value, scalar.split(":", 1)[1])
        except IdentifierError as exc:
            raise ValidationError(f"{name}: invalid task-local identifier") from exc

    max_length = field.metadata.get("max_length")
    if (
        max_length is not None
        and isinstance(value, (str, list, tuple, dict))
        and len(value) > max_length
    ):
        raise ValidationError(f"{name}: exceeds maximum length/count {max_length}")
    min_length = field.metadata.get("min_length")
    if (
        min_length is not None
        and isinstance(value, (str, list, tuple, dict))
        and len(value) < min_length
    ):
        raise ValidationError(f"{name}: is shorter than minimum length/count {min_length}")


def validate_model(model: Any) -> Any:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Validate scalar metadata, nested models, and Document-04 invariants."""

    if not is_dataclass(model):
        raise ValidationError("validation requires a dataclass model")
    expected_schema = getattr(type(model), "__schema_id__", None)
    if expected_schema is not None and getattr(model, "schema", None) != expected_schema:
        raise ValidationError(f"{type(model).__name__}: schema must be {expected_schema}")
    hints = get_type_hints(type(model), include_extras=True)
    for field in fields(model):
        value = getattr(model, field.name)
        if value is None:
            if field.metadata.get("nullable", True) is False:
                raise ValidationError(f"{field.name}: null is not allowed")
            continue
        _validate_declared_scalar(hints.get(field.name, field.type), value, field.name)
        _validate_scalar(field, value)
        _validate_declared_enum(hints.get(field.name, field.type), value, field.name)
        if isinstance(value, FrozenModel):
            validate_model(value)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                if isinstance(item, FrozenModel):
                    validate_model(item)
        elif isinstance(value, Mapping):
            check_forbidden_keys(value, path=field.name)
    check_forbidden_keys(model_to_dict(model))

    name = type(model).__name__
    validator = _MODEL_VALIDATORS.get(name)
    if validator is not None:
        validator(model)
    return model


def _validate_declared_enum(annotation: Any, value: Any, field_name: str) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if _is_new_type(annotation):
        return _validate_declared_enum(annotation.__supertype__, value, field_name)
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        for option in get_args(annotation):
            if option is type(None):
                continue
            if isinstance(option, type) and issubclass(option, Enum):
                if not isinstance(value, option):
                    raise ValidationError(f"{field_name}: expected {option.__name__}")
                return
        return
    if origin in (list, tuple, set, frozenset):
        item_annotation = get_args(annotation)[0] if get_args(annotation) else Any
        for index, item in enumerate(value):
            _validate_declared_enum(item_annotation, item, f"{field_name}[{index}]")
        return
    if origin in (dict, Mapping, ABCMapping) or (
        origin is not None and str(origin).endswith("Mapping")
    ):
        args = get_args(annotation)
        key_annotation = args[0] if len(args) == 2 else str
        value_annotation = args[1] if len(args) == 2 else Any
        for key, item in value.items():
            _validate_declared_enum(key_annotation, key, f"{field_name}.{key}")
            _validate_declared_enum(value_annotation, item, f"{field_name}.{key}")
        return
    if (
        isinstance(annotation, type)
        and issubclass(annotation, Enum)
        and not isinstance(value, annotation)
    ):
        raise ValidationError(f"{field_name}: expected {annotation.__name__}")


def _validate_declared_scalar(annotation: Any, value: Any, field_name: str) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Validate branded aliases even when field metadata is not repeated."""

    if _is_new_type(annotation):
        marker = getattr(annotation, "__name__", "")
    elif get_origin(annotation) is Annotated:
        marker = str(get_args(annotation)[1])
    else:
        marker = ""
    if marker:
        if marker == "SafeText":
            validate_safe_text(value, field_name=field_name)
        elif marker == "ReviewedProcedureText":
            validate_safe_text(value, field_name=field_name, max_length=MAX_REVIEWED_PROCEDURE_TEXT)
        elif marker == "Locale":
            validate_locale(value, field_name=field_name)
        elif marker == "FamilyId":
            if value not in FAMILY_IDS:
                raise ValidationError(f"{field_name}: unknown family ID")
        elif marker == "TaskId":
            _validate_identifier(validate_task_id, value, field_name, "TaskId")
        elif marker == "EventId":
            _validate_identifier(validate_event_id, value, field_name, "EventId")
        elif marker == "TurnToken":
            _validate_identifier(validate_turn_token, value, field_name, "TurnToken")
        elif marker == "MethodId":
            _validate_identifier(validate_method_id, value, field_name, "MethodId")
        elif marker == "SemVer":
            _validate_identifier(validate_semver, value, field_name, "SemVer")
        elif marker == "Sha256":
            _validate_identifier(validate_sha256, value, field_name, "Sha256")
        elif marker == "DecimalString":
            _validate_identifier(validate_decimal_string, value, field_name, "DecimalString")
        elif marker == "DurationMs":
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= MAX_DURATION_MS
            ):
                raise ValidationError(f"{field_name}: invalid DurationMs")
        elif marker in {
            "JudgmentId",
            "ClaimId",
            "EvidenceId",
            "AlternativeId",
            "CriterionId",
            "InterventionId",
        }:
            _validate_identifier(validate_local_id, value, field_name, "task-local identifier")
        return
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        for option in get_args(annotation):
            if option is not type(None):
                _validate_declared_scalar(option, value, field_name)
                return
    if origin in (list, tuple, set, frozenset):
        item_annotation = get_args(annotation)[0] if get_args(annotation) else Any
        for index, item in enumerate(value):
            _validate_declared_scalar(item_annotation, item, f"{field_name}[{index}]")
    elif origin in (dict, Mapping, ABCMapping) or (
        origin is not None and str(origin).endswith("Mapping")
    ):
        args = get_args(annotation)
        key_annotation = args[0] if len(args) == 2 else str
        value_annotation = args[1] if len(args) == 2 else Any
        for key, item in value.items():
            _validate_declared_scalar(key_annotation, key, f"{field_name}.{key}")
            _validate_declared_scalar(value_annotation, item, f"{field_name}.{key}")


def _validate_identifier(validator: Any, value: Any, field_name: str, label: str) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name}: invalid {label}")
    try:
        validator(value)
    except IdentifierError as exc:
        raise ValidationError(f"{field_name}: invalid {label}") from exc


def _require_nonempty(value: str, field_name: str, maximum: int) -> None:
    validate_safe_text(
        value, field_name=field_name, max_length=maximum, allow_newline=False, allow_tab=False
    )
    if not value.strip():
        raise ValidationError(f"{field_name}: must not be blank")


def _unique(values: list[Any] | tuple[Any, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValidationError(f"{field_name}: values must be unique")


def _validate_capability_entry(model: Any) -> None:
    if (
        model.status
        in {CapabilityStatus.DEGRADED, CapabilityStatus.UNAVAILABLE, CapabilityStatus.UNKNOWN}
        and not model.limitation_key
    ):
        raise ValidationError(
            "capability entry: degraded/unavailable/unknown requires limitation_key"
        )
    if model.status is CapabilityStatus.SUPPORTED and model.limitation_key is not None:
        raise ValidationError("capability entry: supported cannot carry a limitation key")
    if (
        model.evidence_kind is CapabilityEvidenceKind.HOST_CONTRACT
        and model.status is not CapabilityStatus.UNKNOWN
    ):
        if not model.source_url:
            raise ValidationError("capability entry: host contract requires source_url")
        validate_url(model.source_url, allow_none=False)


def _validate_capability_profile(model: Any) -> None:
    from ..constants import CAPABILITY_KEYS

    if tuple(sorted(model.capabilities)) != tuple(sorted(CAPABILITY_KEYS)):
        raise ValidationError("capability profile: exact closed capability key set is required")
    for entry in model.capabilities.values():
        _validate_capability_entry(entry)


def _validate_user_settings(model: Any) -> None:
    if model.revision < 1 or not 7 <= model.record_retention_days <= 3650:
        raise ValidationError("user settings: revision/retention out of range")
    if not 10 * 1024 * 1024 <= model.record_size_limit_bytes <= 10 * 1024 * 1024 * 1024:
        raise ValidationError("user settings: record size limit out of range")
    if model.metrics_consent.value != "none":
        raise ValidationError("user settings: metrics consent is closed to none in v1")
    if (
        model.recording_mode is RecordingMode.LOCAL_PUBLIC_ARTIFACTS
        and model.onboarding_version_seen is None
    ):
        raise ValidationError("user settings: recording requires completed onboarding")


def _validate_participation_decision(model: Any) -> None:
    if len(model.judgment_targets) > 3 or len(model.mechanical_targets) > 3:
        raise ValidationError("participation decision: at most three targets per kind")
    for target in (*model.judgment_targets, *model.mechanical_targets):
        _require_nonempty(target, "target", 120)
    if model.participation is Participation.MECHANICAL and model.judgment_targets:
        raise ValidationError("mechanical participation cannot carry judgment targets")


def _validate_rigor_decision(model: Any) -> None:
    # A one-task override replaces the stored preference before the risk floor
    # is applied.  The floor is the only raise-only part of this computation;
    # a quiet override is therefore allowed to lower a stored strict setting
    # when no risk rule raises it again.
    requested = model.task_override if model.task_override is not None else model.stored_rigor
    effective = max((requested, model.risk_floor), key=_rigor_rank)
    if _rigor_rank(model.effective_rigor) < _rigor_rank(effective):
        raise ValidationError("rigor decision: effective_rigor must apply the raise-only floor")
    if _rigor_rank(model.effective_rigor) != _rigor_rank(effective):
        raise ValidationError("rigor decision: effective_rigor must equal the recomputed value")
    if model.show_raise_notice != (_rigor_rank(model.effective_rigor) > _rigor_rank(requested)):
        raise ValidationError("rigor decision: show_raise_notice does not match effective raise")


def _rigor_rank(value: Rigor) -> int:
    return {Rigor.QUIET: 0, Rigor.TOGETHER: 1, Rigor.STRICT: 2}[value]


def _validate_routing_features(model: Any) -> None:
    keys = [feature.key for feature in model.features]
    if any(key not in {item.value for item in FeatureKey} for key in keys):
        raise ValidationError("routing features: unknown feature key")
    _unique(keys, "routing features.features")
    for feature in model.features:
        if not 1 <= feature.strength <= 3:
            raise ValidationError("routing feature strength must be 1..3")


def _validate_router_decision(model: Any) -> None:
    if (model.secondary_family is None) != (model.secondary_method is None):
        raise ValidationError("router decision: secondary family/method are paired")
    same_family = (
        model.primary_family is not None
        and model.secondary_family is not None
        and model.primary_family == model.secondary_family
    )
    same_method = (
        model.primary_method is not None
        and model.secondary_method is not None
        and model.primary_method == model.secondary_method
    )
    fallback_reasons = {
        RouterReasonCode.ANSWER_SHAPE_FALLBACK,
        RouterReasonCode.INVALID_FEATURES_FALLBACK,
    }
    if same_method or (same_family and model.reason_code not in fallback_reasons):
        raise ValidationError("router decision: primary and secondary must differ")
    if model.primary_method is None and model.reason_code not in {
        RouterReasonCode.NO_ELIGIBLE_METHOD,
        RouterReasonCode.CONTRAINDICATED_EXPLICIT_METHOD,
    }:
        raise ValidationError("router decision: missing primary method for successful reason")


def _validate_source_reference(model: Any) -> None:
    _require_nonempty(model.display_name, "display_name", 200)
    validate_url(model.uri, allow_none=True)
    if model.safe_locator is not None:
        _require_nonempty(model.safe_locator, "safe_locator", 200)
        if "/" in model.safe_locator or "\\" in model.safe_locator:
            raise ValidationError("safe_locator: directory paths are not allowed")
    if model.published_at is not None:
        validate_date(model.published_at, field_name="published_at")
    validate_sha_or_none(model.content_hash, field_name="content_hash")


def _validate_calculation(model: Any) -> None:
    _require_nonempty(model.expression, "expression", 1000)
    if not model.operands:
        raise ValidationError("calculation: at least one operand is required")
    names = [operand.name for operand in model.operands]
    _unique(names, "calculation.operands.name")
    validate_decimal_string(model.result)
    if not model.unit or any(character.isspace() for character in model.unit):
        raise ValidationError("calculation: unit must be a non-empty token")
    computed = _evaluate_expression(
        model.expression,
        {operand.name: Decimal(operand.value) for operand in model.operands},
    )
    expected = Decimal(model.result)
    if model.rounding is RoundingMode.HALF_EVEN_0:
        computed = computed.quantize(Decimal("1"))
    elif model.rounding is RoundingMode.HALF_EVEN_1:
        computed = computed.quantize(Decimal("0.1"))
    elif model.rounding is RoundingMode.HALF_EVEN_2:
        computed = computed.quantize(Decimal("0.01"))
    elif model.rounding is RoundingMode.FLOOR:
        computed = computed.to_integral_value(rounding="ROUND_FLOOR")
    elif model.rounding is RoundingMode.CEILING:
        computed = computed.to_integral_value(rounding="ROUND_CEILING")
    if computed != expected:
        raise ValidationError(f"calculation result {model.result} does not match expression")


def _validate_claim_version(model: Any) -> None:
    _require_nonempty(model.text, "claim.text", 600)
    _unique(model.source_ids, "claim.source_ids")
    _unique(model.basis_claim_ids, "claim.basis_claim_ids")
    if model.evidence_state is EvidenceState.VERIFIED and not model.source_ids:
        raise ValidationError("verified claim requires at least one source")
    if model.evidence_state is EvidenceState.COMPUTED and model.calculation is None:
        raise ValidationError("computed claim requires calculation")
    if model.evidence_state is EvidenceState.INFERRED and not model.basis_claim_ids:
        raise ValidationError("inferred claim requires basis claims")
    if model.evidence_state is EvidenceState.ASSUMED and (
        model.source_ids or model.basis_claim_ids or model.calculation
    ):
        raise ValidationError("assumed claim cannot carry source, basis, or calculation")
    if model.evidence_state is EvidenceState.CONFLICTED:
        if model.conflict is None:
            raise ValidationError("conflicted claim requires conflict")
        if len(model.source_ids) < 2 and not (model.basis_claim_ids or model.calculation):
            raise ValidationError("conflicted claim requires two sources or a second public basis")


def _validate_conflict(model: Any) -> None:
    _require_nonempty(model.summary, "conflict.summary", 600)
    _require_nonempty(model.subject, "conflict.subject", 300)
    if len(model.source_ids) < 2 and not model.affected_claim_ids:
        raise ValidationError("conflict requires at least two sources or an affected claim")
    if model.resolution is ConflictResolution.UNRESOLVED and model.resolution_reason is not None:
        raise ValidationError("unresolved conflict cannot carry resolution_reason")
    if model.resolution is not ConflictResolution.UNRESOLVED and not model.resolution_reason:
        raise ValidationError("resolved conflict requires public resolution_reason")


def _validate_framing(model: Any) -> None:
    _require_nonempty(model.decision_question, "decision_question", 500)
    if (
        len(model.assumptions) > 3
        or len(model.decisive_evidence) > 3
        or not 1 <= len(model.completion_criteria) <= 8
    ):
        raise ValidationError("framing: assumptions/evidence/criteria counts are outside limits")
    _unique(
        [criterion.criterion_id for criterion in model.completion_criteria], "framing.criterion_id"
    )


def _validate_judgment_version(model: Any) -> None:
    if model.version < 1:
        raise ValidationError("judgment version must be positive")
    if model.version == 1 and model.supersedes_version is not None:
        raise ValidationError("version one cannot supersede another version")
    if model.version > 1 and (
        model.supersedes_version != model.version - 1 or not model.change_reason
    ):
        raise ValidationError(
            "revised judgment must name the immediately superseded version and reason"
        )
    if model.state in {JudgmentState.ACTIVE, JudgmentState.PUBLISHED} and not model.conclusion:
        raise ValidationError("active/published judgment requires conclusion")
    if model.state is JudgmentState.PUBLISHED:
        if not 1 <= len(model.ground_claim_ids) <= 5 or not 1 <= len(model.flip_conditions) <= 2:
            raise ValidationError("published judgment requires grounds and flip conditions")
    if len(model.uncertainty_claim_ids) > 2 or len(model.alternative_ids) > 3:
        raise ValidationError("judgment version exceeds uncertainty/alternative limits")


def _validate_flip_condition(model: Any) -> None:
    _require_nonempty(model.condition, "flip.condition", 300)
    _require_nonempty(model.check, "flip.check", 240)
    if model.affected_conclusion is not None:
        _require_nonempty(model.affected_conclusion, "flip.affected_conclusion", 240)
    if model.condition.strip().lower() in {
        "if circumstances change",
        "if new information emerges",
        "if the analysis is wrong",
    }:
        raise ValidationError("flip condition must be observable and concrete")


def _validate_alternative(model: Any) -> None:
    _require_nonempty(model.name, "alternative.name", 160)
    _require_nonempty(model.reason, "alternative.reason", 400)
    _unique(model.material_claim_ids, "alternative.material_claim_ids")


def _validate_conclusion_card(model: Any) -> None:
    _require_nonempty(model.conclusion, "card.conclusion", 500)
    if len(model.grounds) > 5 or not model.grounds:
        raise ValidationError("card requires one through five grounds")
    if len(model.uncertainties) > 2 or len(model.flip_conditions) > 2:
        raise ValidationError("card exceeds uncertainty/flip limits")
    estimated_lines = (
        1 + len(model.grounds) + len(model.uncertainties) + len(model.flip_conditions) + 1
    )
    estimated_scalars = (
        len(model.conclusion)
        + len(model.alternatives_summary)
        + sum(len(ground.text) for ground in model.grounds)
        + sum(len(item) for item in model.uncertainties)
    )
    if estimated_lines > 14 or estimated_scalars > 2200:
        raise ValidationError("card exceeds collapsed UX limits")
    for ground in model.grounds:
        if ground.state is not EvidenceState.VERIFIED and ground.source_refs:
            # A source can be useful context for other states, but a verified
            # source is the only state that makes a source reference required.
            continue
        if ground.state is EvidenceState.VERIFIED and not ground.source_refs:
            raise ValidationError("verified card ground requires source reference")
    check_forbidden_keys(model.to_dict())


def _validate_completion_result(model: Any) -> None:
    if model.repair_count_before not in {0, 1}:
        raise ValidationError("completion result repair count must be 0 or 1")
    if model.outcome is VerificationOutcome.PASS:
        if any(item.status is not CriterionStatus.MET for item in model.criteria if item.required):
            raise ValidationError("completion pass requires every required criterion to be met")
        if model.violations:
            raise ValidationError("completion pass cannot carry violations")
    if model.outcome is VerificationOutcome.REPAIR and not model.may_continue:
        raise ValidationError("repair outcome must allow one continuation")
    if model.repair_count_before == 1 and model.may_continue:
        raise ValidationError("second completion failure cannot continue")


def _validate_verification_result(model: Any) -> None:
    if model.duration_ms < 0 or model.duration_ms > MAX_DURATION_MS:
        raise ValidationError("verification duration outside DurationMs range")
    if model.outcome is VerificationOutcome.PASS and model.parsed_card is None:
        raise ValidationError("verification pass requires parsed_card")
    if model.outcome is VerificationOutcome.ERROR and model.parsed_card is not None:
        raise ValidationError("verification error cannot carry parsed_card")


def _validate_normalized_event(model: Any) -> None:
    if len(canonical_json(model.payload).encode("utf-8")) > 4 * 1024 * 1024:
        raise ValidationError("normalized event payload exceeds 4 MiB")
    if model.event_type in {
        EventType.TOOL_SUCCEEDED,
        EventType.TOOL_FAILED,
        EventType.TOOL_BATCH_COMPLETED,
    }:
        category = model.payload.get("tool_category")
        if category is None:
            raise ValidationError("tool event requires tool_category")


def _validate_judgment_event(model: Any) -> None:
    if model.sequence < 1:
        raise ValidationError("record sequence begins at one")
    if len(canonical_json(model.payload).encode("utf-8")) > 64 * 1024:
        raise ValidationError("judgment event payload exceeds 64 KiB")
    check_forbidden_keys(model.payload, path="payload")


def _validate_ephemeral_turn_state(model: Any) -> None:
    if model.expires_at <= model.issued_at:
        raise ValidationError("ephemeral turn state must expire after issuance")
    if len(model.accepted_controls) > 16 or len(model.observation_tags) > 384:
        raise ValidationError("ephemeral turn state exceeds bounded replay/dedupe capacity")
    if model.repair_count not in {0, 1}:
        raise ValidationError("ephemeral repair_count must be 0 or 1")


def _validate_host_control(model: Any) -> None:
    check_forbidden_keys(model.to_dict())
    if len(canonical_json(model.to_dict()).encode("utf-8")) > 32 * 1024:
        raise ValidationError("host control exceeds 32 KiB")
    if not model.published and _contains_public_prose(model.payload):
        raise ValidationError("unpublished host control cannot carry public prose")


def _validate_host_control_result(model: Any) -> None:
    if model.status is HostControlStatus.REJECTED:
        if model.error_code is None or model.durable_mutation or model.assigned_ids.has_any():
            raise ValidationError("rejected host control result must not mutate or assign IDs")
    elif model.error_code is not None:
        raise ValidationError("accepted host control result cannot carry error_code")
    if len(model.capability_limitations) != len(set(model.capability_limitations)):
        raise ValidationError("capability limitations must be unique")


def _contains_public_prose(value: Any, *, key: str | None = None) -> bool:
    if isinstance(value, str):
        if key in _CATEGORY_PAYLOAD_KEYS:
            return False
        if key in _NON_PROSE_PAYLOAD_KEYS and _CODE_VALUE_RE.fullmatch(value):
            return False
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(
            _contains_public_prose(child, key=str(child_key).lower().replace("-", "_"))
            for child_key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_public_prose(child, key=key) for child in value)
    return False


def _validate_compiled_content_bundle(model: Any) -> None:
    if len(model.method_ids) != 48 or len(set(model.method_ids)) != 48:
        raise ValidationError("compiled content bundle must contain exactly 48 unique methods")
    if list(model.method_ids) != sorted(model.method_ids):
        raise ValidationError("compiled content method_ids must be lexicographically sorted")
    if [method.id for method in model.methods] != list(model.method_ids):
        raise ValidationError("compiled content methods must align with method_ids")
    if set(model.locale_messages) != {"en", "ko"}:
        raise ValidationError("compiled content requires en and ko locale messages")


def _validate_trace_view(model: Any) -> None:
    if model.public_short_id and len(model.public_short_id) != 8:
        raise ValidationError("trace public_short_id must be eight characters")


def _validate_local_metric(model: Any) -> None:
    if model.attributes is None:
        raise ValidationError("local metric attributes must be an object")
    check_forbidden_keys(model.attributes, path="attributes")


def _validate_method_participation(model: Any) -> None:
    if not model.judgment_only:
        raise ValidationError("method participation must be judgment-only in v1")
    if not model.allowed_answer_shapes:
        raise ValidationError("method participation requires at least one answer shape")
    _unique(list(model.allowed_answer_shapes), "method participation.answer shapes")


def _validate_method_routing(model: Any) -> None:
    for name, weights in (
        ("positive_features", model.positive_features),
        ("negative_features", model.negative_features),
    ):
        if any(
            not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= 3
            for weight in weights.values()
        ):
            raise ValidationError(f"method routing.{name} weights must be integers 1..3")
    if not 3 <= model.minimum_score <= 9:
        raise ValidationError("method routing minimum_score must be 3..9")
    _unique(list(model.contraindications), "method routing.contraindications")


def _validate_method_output_contract(model: Any) -> None:
    if not model.required_sections or any(
        not section.strip() for section in model.required_sections
    ):
        raise ValidationError("method output contract requires non-empty sections")
    for section in model.required_sections:
        validate_safe_text(
            section,
            field_name="required_sections",
            max_length=128,
            allow_newline=False,
            allow_tab=False,
        )
    if (
        not isinstance(model.max_questions, int)
        or isinstance(model.max_questions, bool)
        or not 0 <= model.max_questions <= 3
    ):
        raise ValidationError("method output contract max_questions must be 0..3")


def _validate_method_complements(model: Any) -> None:
    _unique(list(model.preferred), "method complements.preferred")
    _unique(list(model.incompatible_secondary), "method complements.incompatible_secondary")


def _validate_method_authoring(model: Any) -> None:
    if set(model.locales) != {"en", "ko"} or tuple(model.locales) != ("en", "ko"):
        raise ValidationError("method authoring requires exactly en and ko locales in en,ko order")
    if len(model.routing.positive_features) < 2:
        raise ValidationError("method authoring requires at least two positive routing features")
    if not model.participation.judgment_only:
        raise ValidationError("method authoring methods must be judgment-only")
    if not model.complements.preferred:
        raise ValidationError("method authoring requires a preferred complement")
    if model.complements.incompatible_secondary:
        raise ValidationError("method authoring incompatible_secondary must be empty in v1")


def _evaluate_expression(expression: str, operands: dict[str, Decimal]) -> Decimal:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Evaluate the bounded arithmetic grammar with Decimal, never eval()."""

    token_re = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_]*)|([()+\-*/%]))")
    position = 0
    tokens: list[str] = []
    while position < len(expression):
        match = token_re.match(expression, position)
        if match is None:
            raise ValidationError("calculation expression contains an unsupported token")
        tokens.append(next(group for group in match.groups() if group is not None))
        position = match.end()
    if not tokens:
        raise ValidationError("calculation expression is empty")
    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def consume(expected: str | None = None) -> str:
        nonlocal position
        token = peek()
        if token is None or (expected is not None and token != expected):
            raise ValidationError("calculation expression is malformed")
        position += 1
        return token

    def parse_primary() -> Decimal:
        token = peek()
        if token == "(":
            consume("(")
            result = parse_sum()
            consume(")")
            return result
        if token is None:
            raise ValidationError("calculation expression is incomplete")
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            consume()
            result = Decimal(token)
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
            consume()
            if token not in operands:
                raise ValidationError(f"calculation expression references unknown operand {token}")
            result = operands[token]
        else:
            raise ValidationError("calculation expression has an unexpected token")
        if peek() == "%":
            consume("%")
            result /= Decimal(100)
        return result

    def parse_factor() -> Decimal:
        token = peek()
        if token in {"+", "-"}:
            consume()
            result = parse_factor()
            return result if token == "+" else -result
        return parse_primary()

    def parse_product() -> Decimal:
        result = parse_factor()
        while peek() in {"*", "/"}:
            operator = consume()
            right = parse_factor()
            if operator == "/":
                if right == 0:
                    raise ValidationError("calculation expression divides by zero")
                result /= right
            else:
                result *= right
        return result

    def parse_sum() -> Decimal:
        result = parse_product()
        while peek() in {"+", "-"}:
            operator = consume()
            right = parse_product()
            result = result + right if operator == "+" else result - right
        return result

    try:
        result = parse_sum()
    except (InvalidOperation, ZeroDivisionError) as exc:
        raise ValidationError("calculation expression is not computable") from exc
    if peek() is not None:
        raise ValidationError("calculation expression has trailing tokens")
    return result


_MODEL_VALIDATORS = {
    "CapabilityProfile": _validate_capability_profile,
    "UserSettings": _validate_user_settings,
    "ParticipationDecision": _validate_participation_decision,
    "RigorDecision": _validate_rigor_decision,
    "RoutingFeatures": _validate_routing_features,
    "RouterDecision": _validate_router_decision,
    "SourceReference": _validate_source_reference,
    "Calculation": _validate_calculation,
    "ClaimVersion": _validate_claim_version,
    "Conflict": _validate_conflict,
    "Framing": _validate_framing,
    "JudgmentVersion": _validate_judgment_version,
    "FlipCondition": _validate_flip_condition,
    "Alternative": _validate_alternative,
    "ConclusionCard": _validate_conclusion_card,
    "CompletionResult": _validate_completion_result,
    "VerificationResult": _validate_verification_result,
    "NormalizedEvent": _validate_normalized_event,
    "JudgmentEvent": _validate_judgment_event,
    "EphemeralTurnState": _validate_ephemeral_turn_state,
    "HostControl": _validate_host_control,
    "HostControlResult": _validate_host_control_result,
    "MethodParticipation": _validate_method_participation,
    "MethodRouting": _validate_method_routing,
    "MethodOutputContract": _validate_method_output_contract,
    "MethodComplements": _validate_method_complements,
    "MethodAuthoring": _validate_method_authoring,
    "CompiledContentBundle": _validate_compiled_content_bundle,
    "TraceView": _validate_trace_view,
    "LocalMetric": _validate_local_metric,
}


__all__ = [
    "AlternativeId",
    "ClaimId",
    "CriterionId",
    "DecimalString",
    "DurationMs",
    "EventId",
    "EvidenceId",
    "FamilyId",
    "FrozenModel",
    "InterventionId",
    "JudgmentId",
    "Locale",
    "MethodId",
    "SafeText",
    "ReviewedProcedureText",
    "SemVer",
    "Sha256",
    "TaskId",
    "TurnToken",
    "canonical_json",
    "check_forbidden_keys",
    "model_from_dict",
    "model_from_json",
    "model_to_dict",
    "sanitize_persistable_uri",
    "validate_date",
    "validate_locale",
    "validate_model",
    "validate_safe_text",
    "validate_url",
]
