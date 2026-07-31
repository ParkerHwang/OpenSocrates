"""Small, explicit dispatch for the stable 1.0 command names.

Compatibility is an invocation boundary, not a second skill registry.  Only
``auto``, ``evidence-audit``, ``reasoning-trace``, and
``opensocrates-status`` are executable.  ``status`` is the documented spelling
of the same status action.  Every other name returns a mapping-only result and
never invokes a v1 service.

The callbacks are deliberately injected.  Hosts can bind them to the current
participation/router policy, public evidence/card rules, public trace
projection, and status/capability projection without this module importing a
host adapter or a persistence implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum

from ..domain.models import CapabilityProfile, UserSettings
from ..domain.validation import validate_model


class CompatibilityError(ValueError):
    """A bounded compatibility-dispatch failure."""

    def __init__(self, code: str, detail: str = "compatibility dispatch failed") -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


class CompatibilityOperation(StrEnum):
    AUTO = "auto"
    EVIDENCE_AUDIT = "evidence_audit"
    PUBLIC_TRACE = "public_trace"
    STATUS = "status"
    MAPPING_ONLY = "mapping_only"


SUPPORTED_COMPATIBILITY_NAMES = (
    "auto",
    "evidence-audit",
    "reasoning-trace",
    "opensocrates-status",
    "status",
)
_CANONICAL_STATUS_NAME = "opensocrates-status"
_MAPPING_SUGGESTION = "manual-mapping-required"


@dataclass(frozen=True, slots=True)
class CompatibilityRequest:
    """Typed inputs for one compatibility dispatch.

    ``participation_input`` and ``routing_features`` are already-normalized
    v1 domain inputs.  ``evidence_input`` and ``trace_input`` are likewise
    public, typed inputs owned by their injected current-v1 services; this
    module never accepts or reads prompts, transcripts, ledgers, or raw host
    envelopes.
    """

    name: str
    participation_input: object | None = None
    routing_features: object | None = None
    evidence_input: object | None = None
    trace_input: object | None = None
    settings: UserSettings | None = None
    capability_profile: CapabilityProfile | None = None
    locale: str = "en"
    private_reasoning_requested: bool = False
    suggestions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name or len(self.name) > 128:
            raise CompatibilityError("invalid_name", "compatibility name is invalid")
        if self.locale not in {"en", "ko"}:
            raise CompatibilityError("invalid_locale", "compatibility locale is unsupported")
        if not isinstance(self.private_reasoning_requested, bool):
            raise CompatibilityError("invalid_request", "private reasoning flag is invalid")
        if not isinstance(self.suggestions, tuple):
            raise CompatibilityError("invalid_request", "compatibility suggestions must be a tuple")


CompatibilityCallback = Callable[..., object]


@dataclass(frozen=True, slots=True)
class CompatibilityServices:
    """Injected current-v1 actions used by :func:`dispatch_compatibility`.

    Callback signatures are stable:

    * ``participation(value)`` returns the current participation decision;
    * ``router(decision, features)`` returns the current router decision;
    * ``evidence_audit(value)`` returns the current public evidence/card audit;
    * ``public_trace(value)`` returns a public trace projection/result; and
    * ``status(settings, capability_profile, locale)`` returns the current
      safe status projection.

    ``None`` selects the corresponding current-v1 pure implementation.
    """

    participation: CompatibilityCallback | None = None
    router: CompatibilityCallback | None = None
    evidence_audit: CompatibilityCallback | None = None
    public_trace: CompatibilityCallback | None = None
    status: CompatibilityCallback | None = None


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    """Stable result envelope shared by generated host wrappers."""

    name: str
    canonical_name: str | None
    operation: CompatibilityOperation
    value: object | None = None
    supported: bool = True
    mapped_name: str | None = None
    suggestions: tuple[str, ...] = ()
    public_only: bool = True
    chain_of_thought: bool = False
    private_reasoning_requested: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise CompatibilityError("invalid_result", "compatibility result name is invalid")
        if not isinstance(self.operation, CompatibilityOperation):
            raise CompatibilityError("invalid_result", "compatibility result operation is invalid")
        if not self.public_only or self.chain_of_thought:
            raise CompatibilityError(
                "privacy_violation", "compatibility results cannot disclose private reasoning"
            )
        if not isinstance(self.private_reasoning_requested, bool):
            raise CompatibilityError("invalid_result", "compatibility reasoning flag is invalid")

    def to_dict(self) -> dict[str, object]:
        """Return a bounded wrapper-friendly representation.

        ``value`` remains the typed public service result.  No private
        reasoning field is ever synthesized; the two privacy flags are always
        explicit and false for chain-of-thought disclosure.
        """

        return {
            "name": self.name,
            "canonical_name": self.canonical_name,
            "operation": self.operation.value,
            "value": _jsonable(self.value),
            "supported": self.supported,
            "mapped_name": self.mapped_name,
            "suggestions": list(self.suggestions),
            "public_only": self.public_only,
            "chain_of_thought": self.chain_of_thought,
            "private_reasoning_requested": self.private_reasoning_requested,
        }


def _jsonable(value: object) -> object:
    """Convert typed public models to JSON-shaped values without introspection."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    if is_dataclass(value):
        return _jsonable(asdict(value))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    return str(value)


def _safe_suggestions(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        return (_MAPPING_SUGGESTION,)
    result: list[str] = []
    for value in values:
        if (
            isinstance(value, str)
            and value
            and len(value) <= 96
            and "\n" not in value
            and "\r" not in value
            and "\x00" not in value
        ):
            result.append(value)
    return tuple(dict.fromkeys(result)) or (_MAPPING_SUGGESTION,)


def _service(services: object | None, name: str) -> CompatibilityCallback | None:
    if services is None:
        return None
    if isinstance(services, CompatibilityServices):
        value = getattr(services, name)
    elif isinstance(services, Mapping):
        value = services.get(name)
    else:
        value = getattr(services, name, None)
    return value if callable(value) else None


def _default_participation(value: object) -> object:
    from ..domain.participation import classify_participation

    return classify_participation(value)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.


def _default_router(decision: object, features: object) -> object:
    from ..domain.routing import route_features

    return route_features(decision, features)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.


def _default_evidence_audit(value: object) -> object:
    """Use the current public card/evidence verifier for typed input."""

    from ..domain.models import ConclusionCard
    from ..verification.card_rules import collect_card_violations
    from ..verification.evidence_rules import collect_evidence_violations
    from ..verification.verifier import VerificationRequest, verify_completion

    if isinstance(value, VerificationRequest):
        return verify_completion(value)
    if isinstance(value, ConclusionCard):
        return {"card_violations": collect_card_violations(value)}
    if isinstance(value, Mapping):
        # A mapping is accepted only as a public verifier request.  The
        # verifier itself enforces its typed card/evidence boundary.
        if "card" in value or "markdown" in value:
            allowed = {
                "markdown",
                "card",
                "locale",
                "task_projection",
                "framing",
                "current_judgment",
                "claim_versions",
                "sources",
                "alternatives",
                "conflicts",
                "criterion_statuses",
                "capability_profile",
                "public_claim_changed",
                "repair_count_before",
                "candidate_sequence",
                "parser",
                "card_rules",
                "evidence_rules",
                "source_rules",
                "calculation_rules",
                "parser_kwargs",
            }
            return verify_completion(
                **{str(key): item for key, item in value.items() if str(key) in allowed}
            )
        claims = value.get("claims", value.get("claim_versions"))
        if claims is None:
            raise CompatibilityError(
                "missing_input", "evidence audit requires typed claims or a public card"
            )
        kwargs = {
            str(key): item
            for key, item in value.items()
            if str(key)
            in {
                "sources",
                "known_claims",
                "strength",
                "required_criteria",
                "required_criterion_unverified",
                "missing_decisive_evidence",
                "blocking_conflict",
                "conflicts",
                "require_current_projection",
            }
        }
        return collect_evidence_violations(claims, **kwargs)
    if value is None:
        raise CompatibilityError("missing_input", "evidence audit requires typed public input")
    return collect_evidence_violations(value)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.


def _default_public_trace(value: object) -> object:
    from ..application.render_trace import project_trace_result

    if isinstance(value, Mapping):
        projection = value.get("projection")
        events = value.get("events")
        if projection is None or events is None:
            raise CompatibilityError(
                "missing_input", "public trace requires projection and typed events"
            )
        allowed = {"public_short_id", "current_card", "capability_notes"}
        options = {str(key): item for key, item in value.items() if str(key) in allowed}
        return project_trace_result(projection, events, **options)
    if isinstance(value, tuple) and len(value) == 2:
        return project_trace_result(value[0], value[1])
    raise CompatibilityError(
        "missing_input", "public trace requires a typed projection and event sequence"
    )


def _default_status(settings: UserSettings, profile: CapabilityProfile, locale: str) -> object:
    from .status import project_status

    return project_status(settings, profile, locale=locale)


def _invoke(callback: CompatibilityCallback, *args: object) -> object:
    try:
        return callback(*args)
    except CompatibilityError:
        raise
    except Exception as error:
        raise CompatibilityError(
            "service_failed", "current v1 compatibility service failed"
        ) from error


def _request_from_values(
    name: str,
    *,
    request: CompatibilityRequest | None,
    participation_input: object | None,
    routing_features: object | None,
    evidence_input: object | None,
    trace_input: object | None,
    settings: UserSettings | None,
    capability_profile: CapabilityProfile | None,
    locale: str,
    private_reasoning_requested: bool,
    suggestions: tuple[str, ...],
) -> CompatibilityRequest:
    if request is not None:
        if request.name != name:
            raise CompatibilityError("invalid_request", "request name does not match dispatch name")
        if (
            any(
                value is not None
                for value in (
                    participation_input,
                    routing_features,
                    evidence_input,
                    trace_input,
                    settings,
                    capability_profile,
                )
            )
            or locale != "en"
            or private_reasoning_requested
            or suggestions
        ):
            raise CompatibilityError(
                "invalid_request", "request cannot be combined with direct inputs"
            )
        return request
    return CompatibilityRequest(
        name=name,
        participation_input=participation_input,
        routing_features=routing_features,
        evidence_input=evidence_input,
        trace_input=trace_input,
        settings=settings,
        capability_profile=capability_profile,
        locale=locale,
        private_reasoning_requested=private_reasoning_requested,
        suggestions=suggestions,
    )


def _dispatch(request: CompatibilityRequest, services: object | None) -> CompatibilityResult:
    name = request.name
    if name == "auto":
        if request.participation_input is None or request.routing_features is None:
            raise CompatibilityError(
                "missing_input", "auto requires participation input and routing features"
            )
        participation = _service(services, "participation") or _default_participation
        router = _service(services, "router") or _default_router
        decision = _invoke(participation, request.participation_input)
        value = _invoke(router, decision, request.routing_features)
        return CompatibilityResult(
            name=name,
            canonical_name=name,
            operation=CompatibilityOperation.AUTO,
            value=value,
            private_reasoning_requested=request.private_reasoning_requested,
        )

    if name == "evidence-audit":
        if request.evidence_input is None:
            raise CompatibilityError(
                "missing_input", "evidence-audit requires public typed evidence input"
            )
        callback = _service(services, "evidence_audit") or _default_evidence_audit
        value = _invoke(callback, request.evidence_input)
        return CompatibilityResult(
            name=name,
            canonical_name=name,
            operation=CompatibilityOperation.EVIDENCE_AUDIT,
            value=value,
            private_reasoning_requested=request.private_reasoning_requested,
        )

    if name == "reasoning-trace":
        if request.trace_input is None:
            raise CompatibilityError(
                "missing_input", "reasoning-trace requires public typed trace input"
            )
        callback = _service(services, "public_trace") or _default_public_trace
        value = _invoke(callback, request.trace_input)
        return CompatibilityResult(
            name=name,
            canonical_name=name,
            operation=CompatibilityOperation.PUBLIC_TRACE,
            value=value,
            private_reasoning_requested=request.private_reasoning_requested,
        )

    if name in {"opensocrates-status", "status"}:
        if not isinstance(request.settings, UserSettings) or not isinstance(
            request.capability_profile, CapabilityProfile
        ):
            raise CompatibilityError(
                "missing_input", "status requires current settings and capability profile"
            )
        # Validate the typed capability truth at the compatibility boundary;
        # project_status performs its own closed capability derivation too.
        try:
            validate_model(request.settings)
            validate_model(request.capability_profile)
        except Exception as error:
            raise CompatibilityError(
                "invalid_input", "status inputs failed current model validation"
            ) from error
        callback = _service(services, "status") or _default_status
        value = _invoke(callback, request.settings, request.capability_profile, request.locale)
        return CompatibilityResult(
            name=name,
            canonical_name=_CANONICAL_STATUS_NAME,
            operation=CompatibilityOperation.STATUS,
            value=value,
            mapped_name=_CANONICAL_STATUS_NAME if name == "status" else None,
            private_reasoning_requested=request.private_reasoning_requested,
        )

    return CompatibilityResult(
        name=name,
        canonical_name=None,
        operation=CompatibilityOperation.MAPPING_ONLY,
        value=None,
        supported=False,
        mapped_name=None,
        suggestions=_safe_suggestions(request.suggestions),
        private_reasoning_requested=request.private_reasoning_requested,
    )


def dispatch_compatibility(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    name: str | CompatibilityRequest,
    *,
    services: CompatibilityServices | Mapping[str, CompatibilityCallback] | object | None = None,
    request: CompatibilityRequest | None = None,
    participation_input: object | None = None,
    routing_features: object | None = None,
    evidence_input: object | None = None,
    trace_input: object | None = None,
    settings: UserSettings | None = None,
    capability_profile: CapabilityProfile | None = None,
    locale: str = "en",
    private_reasoning_requested: bool = False,
    suggestions: tuple[str, ...] = (),
    participation: object | None = None,
    features: object | None = None,
    evidence: object | None = None,
    trace: object | None = None,
    profile: CapabilityProfile | None = None,
) -> CompatibilityResult:
    """Dispatch one exact compatibility name to current v1 policy/actions.

    The four preferred input names are explicit above.  ``participation``,
    ``features``, ``evidence``, ``trace``, and ``profile`` are input spelling
    conveniences only; they do not create additional executable skill names.
    """

    if isinstance(name, CompatibilityRequest):
        if request is not None:
            raise CompatibilityError("invalid_request", "a request was supplied twice")
        request = name
        dispatch_name = name.name
    elif isinstance(name, str):
        dispatch_name = name
    else:
        raise CompatibilityError("invalid_name", "compatibility name is invalid")
    aliases = (
        ("participation_input", participation),
        ("routing_features", features),
        ("evidence_input", evidence),
        ("trace_input", trace),
        ("capability_profile", profile),
    )
    for field_name, alias in aliases:
        if alias is None:
            continue
        if field_name == "participation_input" and participation_input is None:
            participation_input = alias
        elif field_name == "routing_features" and routing_features is None:
            routing_features = alias
        elif field_name == "evidence_input" and evidence_input is None:
            evidence_input = alias
        elif field_name == "trace_input" and trace_input is None:
            trace_input = alias
        elif field_name == "capability_profile" and capability_profile is None:
            capability_profile = alias  # type: ignore[assignment]  # Closed runtime boundary validates this value.
        else:
            raise CompatibilityError(
                "invalid_request", f"duplicate compatibility input: {field_name}"
            )
    checked = _request_from_values(
        dispatch_name,
        request=request,
        participation_input=participation_input,
        routing_features=routing_features,
        evidence_input=evidence_input,
        trace_input=trace_input,
        settings=settings,
        capability_profile=capability_profile,
        locale=locale,
        private_reasoning_requested=private_reasoning_requested,
        suggestions=suggestions,
    )
    return _dispatch(checked, services)


class CompatibilityDispatcher:
    """Reusable dispatcher façade for generated host wrappers."""

    def __init__(
        self,
        services: CompatibilityServices
        | Mapping[str, CompatibilityCallback]
        | object
        | None = None,
    ) -> None:
        self.services = services

    def dispatch(self, name: str | CompatibilityRequest, **kwargs: object) -> CompatibilityResult:
        return dispatch_compatibility(name, services=self.services, **kwargs)  # type: ignore[arg-type]

    def __call__(self, name: str | CompatibilityRequest, **kwargs: object) -> CompatibilityResult:
        return self.dispatch(name, **kwargs)


dispatch = dispatch_compatibility


__all__ = [
    "CompatibilityDispatcher",
    "CompatibilityError",
    "CompatibilityOperation",
    "CompatibilityRequest",
    "CompatibilityResult",
    "CompatibilityServices",
    "SUPPORTED_COMPATIBILITY_NAMES",
    "dispatch",
    "dispatch_compatibility",
]
