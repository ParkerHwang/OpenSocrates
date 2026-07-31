"""Adapter-neutral composition of card, evidence, and completion rules."""

from __future__ import annotations

import importlib
import inspect
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from ..domain.completion import build_completion_result
from ..domain.enums import CriterionStatus, VerificationOutcome, ViolationSeverity
from ..domain.models import (
    CompletionCriterion,
    ConclusionCard,
    VerificationResult,
    Violation,
)
from ..version import RULESET_VERSION, VERIFIER_VERSION
from .completion_rules import (
    collect_completion_violations,
    evaluate_completion_criteria,
)


class CardParser(Protocol):
    def parse(self, markdown: str, **kwargs: object) -> ConclusionCard: ...


class ViolationRules(Protocol):
    def __call__(self, value: object, **kwargs: object) -> Iterable[Violation]: ...


@runtime_checkable
class CompletionCandidate(Protocol):
    markdown: str


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    """All trusted inputs needed for one final public completion candidate."""

    markdown: str | None = None
    card: ConclusionCard | None = None
    locale: str = "en"
    locale_catalog: object | None = None
    task_projection: object | None = None
    framing: object | None = None
    current_judgment: object | None = None
    claim_versions: object = ()
    sources: object = ()
    alternatives: object = ()
    conflicts: object = ()
    criterion_statuses: object | None = None
    capability_profile: object | None = None
    public_claim_changed: bool = False
    repair_count_before: int = 0
    candidate_sequence: int = 1
    parser: object | None = None
    card_rules: object | None = None
    evidence_rules: object | None = None
    source_rules: object | None = None
    calculation_rules: object | None = None
    parser_kwargs: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class _RuleRun:
    violations: tuple[Violation, ...] = ()
    failed: bool = False


def _violation(
    rule_id: str,
    message_key: str,
    *,
    field: str | None = None,
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> Violation:
    return Violation(
        rule_id=rule_id,
        severity=severity,
        message_key=message_key,
        field=field,
        repair_hint_key="repair.group",
    )


def _stable(values: Iterable[Violation]) -> tuple[Violation, ...]:
    result: list[Violation] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in values:
        if not isinstance(item, Violation):
            continue
        if not isinstance(item.repair_hint_key, str) or not item.repair_hint_key.startswith(
            "repair."
        ):
            item = replace(item, repair_hint_key="repair.group")
        key = (str(item.rule_id), str(item.field or ""), str(item.message_key), str(item.severity))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    result.sort(
        key=lambda item: (
            str(item.rule_id),
            str(item.field or ""),
            str(item.message_key),
            str(item.severity),
        )
    )
    return tuple(result)


def _iter_values(value: object) -> tuple[object, ...]:
    if value is None or isinstance(value, (str, bytes)):
        return ()
    if isinstance(value, Mapping):
        return tuple(value.values())
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def _field(value: object | None, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _materialize(value: object) -> object:
    if value is None or isinstance(value, Mapping):
        return value
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(value)
    return _iter_values(value)


def _materialize_request(request: VerificationRequest) -> VerificationRequest:
    changes: dict[str, object] = {}
    for field_name in (
        "claim_versions",
        "sources",
        "alternatives",
        "conflicts",
        "criterion_statuses",
    ):
        value = getattr(request, field_name)
        materialized = _materialize(value)
        if materialized is not value:
            changes[field_name] = materialized
    return replace(request, **changes) if changes else request  # type: ignore[arg-type]  # Closed runtime boundary validates this value.


def _normalise_violations(value: object) -> tuple[Violation, ...]:
    if value is None:
        return ()
    if isinstance(value, Violation):
        return (value,)
    nested = getattr(value, "violations", None)
    if nested is not None and nested is not value:
        return _normalise_violations(nested)
    if isinstance(value, (tuple, list, set, frozenset)):
        result: list[Violation] = []
        for item in value:
            result.extend(_normalise_violations(item))
        return tuple(result)
    return ()


def _call_supported(function: Callable[..., object], *args: object, **kwargs: object) -> object:
    """Call an injected rule/parser without assuming its final signature."""

    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(*args, **kwargs)
    parameters = tuple(signature.parameters.values())
    accepts_kwargs = any(item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters)
    accepted = (
        kwargs
        if accepts_kwargs
        else {key: value for key, value in kwargs.items() if key in signature.parameters}
    )
    return function(*args, **accepted)


def _function(provider: object | None, names: Sequence[str]) -> Callable[..., object] | None:
    if provider is None:
        return None
    if callable(provider):
        return provider  # type: ignore[return-value, unused-ignore]  # Closed runtime boundary validates this value.
    for name in names:
        value = getattr(provider, name, None)
        if callable(value):
            return value  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.
    return None


def _named_function(provider: object | None, names: Sequence[str]) -> Callable[..., object] | None:
    """Resolve only named methods; a bare aggregate callable is not a source/calc port."""

    if provider is None:
        return None
    for name in names:
        value = getattr(provider, name, None)
        if callable(value):
            return value  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.
    return None


def _load_optional(module_name: str) -> object | None:
    try:
        return importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError):
        return None
    except Exception:
        # A present but broken rule provider is handled by the verifier as an
        # error when explicitly requested; auto-loading simply yields no
        # provider so the local completion rules still report non-pass gaps.
        return None


def _parse(request: VerificationRequest) -> tuple[ConclusionCard | None, bool, Violation | None]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if request.card is not None:
        if not isinstance(request.card, ConclusionCard):
            return None, True, _violation("OSV-CARD-000", "card.invalid", field="/card")
        return request.card, False, None
    if not isinstance(request.markdown, str) or not request.markdown.strip():
        return (
            None,
            True,
            _violation("OSV-CARD-000", "card.missing", field="/last_assistant_message"),
        )

    parser = request.parser
    if parser is None:
        module = _load_optional("opensocrates.verification.parse_card")
        parser = module
    function = _function(
        parser, ("parse_card", "parse", "parse_conclusion_card", "parse_markdown_card")
    )
    if function is None:
        return (
            None,
            True,
            _violation("OSV-CAPABILITY-002", "capability.card_parser_unavailable", field="/parser"),
        )

    parser_catalog = request.locale_catalog
    if request.parser is None:
        if isinstance(parser_catalog, Mapping):
            nested = parser_catalog.get("locale_messages")
            if isinstance(nested, Mapping):
                parser_catalog = nested
        else:
            nested = getattr(parser_catalog, "locale_messages", None)
            if isinstance(nested, Mapping):
                parser_catalog = nested

    task_id = _field(request.task_projection, "task_id")
    judgment_id = _field(request.current_judgment, "judgment_id")
    claim_ids = _field(request.current_judgment, "ground_claim_ids")
    judgment_version = _field(request.current_judgment, "version", 1)
    kwargs: dict[str, object] = {
        "locale": request.locale,
        "locale_catalog": parser_catalog,
        "task_id": task_id,
        "judgment_id": judgment_id,
        "claim_ids": claim_ids,
        "judgment_version": judgment_version,
    }
    if request.parser_kwargs:
        kwargs.update(request.parser_kwargs)
    try:
        parsed = _call_supported(function, request.markdown, **kwargs)
    except Exception:
        return (
            None,
            True,
            _violation("OSV-CARD-000", "card.parse_failed", field="/last_assistant_message"),
        )
    if not isinstance(parsed, ConclusionCard):
        return None, True, _violation("OSV-CARD-000", "card.parser_result_invalid", field="/card")
    return parsed, False, None


def _card_rules(request: VerificationRequest, card: ConclusionCard) -> _RuleRun:
    provider = request.card_rules
    if provider is None:
        module = _load_optional("opensocrates.verification.card_rules")
        provider = module
    function = _function(
        provider, ("collect_card_violations", "validate_card_rules", "collect_violations")
    )
    if function is None:
        return _RuleRun(
            violations=(
                _violation(
                    "OSV-CAPABILITY-002", "capability.card_rules_unavailable", field="/card_rules"
                ),
            ),
            failed=True,
        )
    try:
        value = _call_supported(function, card, markdown=request.markdown)
    except Exception:
        return _RuleRun(
            violations=(
                _violation(
                    "OSV-CAPABILITY-002", "capability.card_rules_failed", field="/card_rules"
                ),
            ),
            failed=True,
        )
    return _RuleRun(violations=_normalise_violations(value))


def _evidence_rules(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    request: VerificationRequest, card: ConclusionCard, criteria: Sequence[object]
) -> _RuleRun:
    provider = request.evidence_rules
    if provider is None:
        provider = _load_optional("opensocrates.verification.evidence_rules")
    result: list[Violation] = []
    claims = _iter_values(request.claim_versions)
    sources = request.sources
    if provider is not None:
        # A callable provider is the aggregate evidence seam.  A module/object
        # provider exposes the narrower S15 functions below by name.
        if callable(provider) and not any(
            callable(getattr(provider, name, None))
            for name in (
                "collect_claim_violations",
                "collect_evidence_violations",
                "collect_strength_violations",
            )
        ):
            try:
                result.extend(
                    _normalise_violations(
                        _call_supported(
                            provider,
                            claims,
                            strength=card.strength,
                            sources=sources,
                            known_claims=request.claim_versions,
                            required_criteria=criteria,
                        )
                    )
                )
            except Exception:
                result.append(
                    _violation(
                        "OSV-CAPABILITY-002",
                        "capability.evidence_rules_failed",
                        field="/evidence_rules",
                    )
                )
                return _RuleRun(violations=_stable(result), failed=True)
        else:
            claim_function = _function(provider, ("collect_claim_violations",))
            if claim_function is not None:
                try:
                    for claim in claims:
                        result.extend(
                            _normalise_violations(
                                _call_supported(
                                    claim_function,
                                    claim,
                                    known_claims=request.claim_versions,
                                    sources=sources,
                                )
                            )
                        )
                except Exception:
                    result.append(
                        _violation(
                            "OSV-CAPABILITY-002",
                            "capability.evidence_rules_failed",
                            field="/evidence_rules",
                        )
                    )
                    return _RuleRun(violations=_stable(result), failed=True)

            evidence_function = _function(provider, ("collect_evidence_violations",))
            if evidence_function is not None:
                try:
                    result.extend(
                        _normalise_violations(
                            _call_supported(
                                evidence_function,
                                claims,
                                strength=card.strength,
                                sources=sources,
                                known_claims=request.claim_versions,
                                required_criteria=criteria,
                            )
                        )
                    )
                except Exception:
                    result.append(
                        _violation(
                            "OSV-CAPABILITY-002",
                            "capability.evidence_rules_failed",
                            field="/evidence_rules",
                        )
                    )
                    return _RuleRun(violations=_stable(result), failed=True)

            strength_function = _function(provider, ("collect_strength_violations",))
            if strength_function is not None:
                try:
                    result.extend(
                        _normalise_violations(
                            _call_supported(
                                strength_function,
                                claims,
                                card.strength,
                                required_criteria=criteria,
                                sources=sources,
                            )
                        )
                    )
                except Exception:
                    result.append(
                        _violation(
                            "OSV-CAPABILITY-002",
                            "capability.evidence_rules_failed",
                            field="/evidence_rules",
                        )
                    )
                    return _RuleRun(violations=_stable(result), failed=True)

    source_provider = request.source_rules
    source_function = _function(source_provider, ("collect_source_violations",))
    if source_provider is None:
        source_function = _named_function(provider, ("collect_source_violations",))
    if source_function is not None:
        try:
            for source in _iter_values(sources):
                result.extend(_normalise_violations(_call_supported(source_function, source)))
        except Exception:
            result.append(
                _violation(
                    "OSV-CAPABILITY-002", "capability.source_rules_failed", field="/source_rules"
                )
            )
            return _RuleRun(violations=_stable(result), failed=True)

    # Calculation rules are intentionally called only for typed current claims;
    # card prose is never interpreted as executable input.
    calculation_provider = request.calculation_rules
    calculation_function = _function(calculation_provider, ("calculation_violations",))
    if calculation_provider is None:
        calculation_function = _named_function(provider, ("calculation_violations",))
    if calculation_function is not None:
        for claim in claims:
            calculation = getattr(claim, "calculation", None)
            if calculation is None:
                continue
            try:
                result.extend(
                    _normalise_violations(
                        _call_supported(
                            calculation_function,
                            calculation,
                            sources=sources,
                            required_source_ids=_field(claim, "source_ids", ()),
                        )
                    )
                )
            except Exception:
                result.append(
                    _violation(
                        "OSV-CAPABILITY-002",
                        "capability.calculation_rules_failed",
                        field="/calculation_rules",
                    )
                )
                return _RuleRun(violations=_stable(result), failed=True)
    return _RuleRun(violations=_stable(result))


def _judgment_id(request: VerificationRequest, card: ConclusionCard) -> str:
    value = _field(request.current_judgment, "judgment_id") or card.judgment_id
    return str(value)


def _build_result(
    request: VerificationRequest,
    card: ConclusionCard | None,
    violations: Sequence[Violation],
    criteria: Sequence[CompletionCriterion],
    *,
    parse_error: bool,
    provider_error: bool,
    elapsed_ms: int,
) -> VerificationResult:
    stable = _stable(violations)
    blocking = sum(item.severity is ViolationSeverity.ERROR for item in stable)
    if parse_error or provider_error:
        outcome = VerificationOutcome.ERROR
    elif (
        not criteria
        or not any(item.required for item in criteria)
        or any(item.required and item.status is not CriterionStatus.MET for item in criteria)
    ):
        outcome = VerificationOutcome.INSUFFICIENT
    elif blocking:
        outcome = (
            VerificationOutcome.REPAIR
            if request.repair_count_before == 0
            else VerificationOutcome.DEGRADED
        )
    else:
        outcome = VerificationOutcome.PASS

    completion: object | None = None
    if card is not None:
        try:
            completion = build_completion_result(
                judgment_id=_judgment_id(request, card),
                candidate_sequence=request.candidate_sequence,
                criteria=criteria,
                violations=stable,
                repair_count_before=request.repair_count_before,
                blocking_violation_count=blocking,
                outcome=outcome,
            )
        except Exception:
            # A malformed trusted projection is a verifier error, never a pass.
            outcome = VerificationOutcome.ERROR
            completion = None
            stable = _stable(
                (
                    *stable,
                    _violation(
                        "OSV-CAPABILITY-004",
                        "capability.completion_result_failed",
                        field="/completion_result",
                    ),
                )
            )

    return VerificationResult(
        outcome=outcome,
        verifier_version=VERIFIER_VERSION,
        ruleset_version=RULESET_VERSION,
        violations=stable,
        parsed_card=None if outcome is VerificationOutcome.ERROR else card,
        completion_result=completion if hasattr(completion, "judgment_id") else None,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        duration_ms=max(0, min(int(elapsed_ms), 86_400_000)),
    )


def verify_completion(
    request: VerificationRequest | ConclusionCard | str | None = None, **kwargs: object
) -> VerificationResult:
    """Verify one typed card or native final Markdown candidate."""

    started = time.monotonic_ns()
    if isinstance(request, VerificationRequest):
        value = request
    elif isinstance(request, ConclusionCard):
        value = VerificationRequest(card=request, **kwargs)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    elif isinstance(request, str):
        value = VerificationRequest(markdown=request, **kwargs)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    elif request is None:
        value = VerificationRequest(**kwargs)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    else:
        value = VerificationRequest(**kwargs)

    value = _materialize_request(value)

    card, parse_error, parse_violation = _parse(value)
    if parse_error or card is None:
        elapsed = (time.monotonic_ns() - started) // 1_000_000
        return _build_result(
            value,
            None,
            (parse_violation,) if parse_violation is not None else (),
            (),
            parse_error=True,
            provider_error=False,
            elapsed_ms=elapsed,
        )

    card_run = _card_rules(value, card)
    privacy_violation = any(
        str(item.rule_id).startswith("OSV-PRIVACY-") for item in card_run.violations
    )
    criteria = evaluate_completion_criteria(
        value.framing,
        card_valid=not any(
            item.severity is ViolationSeverity.ERROR for item in card_run.violations
        ),
        claim_versions=value.claim_versions,
        criterion_statuses=value.criterion_statuses,
        privacy_violation=privacy_violation,
    )
    evidence_run = _evidence_rules(value, card, criteria)
    completion = collect_completion_violations(
        card,
        value.task_projection,
        value.framing,
        value.current_judgment,
        value.claim_versions,
        criterion_statuses=value.criterion_statuses,
        alternatives=value.alternatives,
        conflicts=value.conflicts,
        card_violations=card_run.violations,
        evidence_violations=evidence_run.violations,
        capability_profile=value.capability_profile,
        public_claim_changed=value.public_claim_changed,
    )
    elapsed = (time.monotonic_ns() - started) // 1_000_000
    return _build_result(
        value,
        card,
        completion,
        criteria,
        parse_error=False,
        provider_error=card_run.failed or evidence_run.failed,
        elapsed_ms=elapsed,
    )


class CompletionVerifier:
    """Reusable verifier façade with injected S12/S15 providers."""

    def __init__(self, **providers: object) -> None:
        self.providers = dict(providers)

    def verify(
        self, request: VerificationRequest | None = None, **values: object
    ) -> VerificationResult:
        if request is not None:
            for key, provider in self.providers.items():
                if getattr(request, key, None) is None:
                    request = replace(request, **{key: provider})  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            return verify_completion(request)
        values = {**self.providers, **values}
        return verify_completion(**values)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.


verify = verify_completion
verify_candidate = verify_completion
verify_card_completion = verify_completion


__all__ = [
    "CardParser",
    "CompletionCandidate",
    "CompletionVerifier",
    "VerificationRequest",
    "ViolationRules",
    "verify",
    "verify_candidate",
    "verify_card_completion",
    "verify_completion",
]
