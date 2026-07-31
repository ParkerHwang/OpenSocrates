"""Deterministic, bilingual prompt assembly from the validated content bundle.

The compiler is intentionally a pure projection boundary.  It accepts one
validated :class:`CompiledContentBundle` and typed domain decisions, never a
user prompt or raw host event.  It emits only canonical prompt text and
bounded metadata about the fragments used to assemble that text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..content.hashes import sha256_hex
from ..content.schema import PROMPT_FRAGMENT_IDS
from ..domain.capability import validate_capability_profile
from ..domain.enums import CapabilityStatus, Participation, Rigor, TaskState
from ..domain.models import (
    CapabilityProfile,
    CompiledContentBundle,
    CompiledMethod,
    ParticipationDecision,
    RigorDecision,
    RouterDecision,
)
from ..domain.validation import Locale
from .completion_prompt import completion_fragment
from .context_budget import (
    BudgetFragment,
    PromptBudgetReport,
    enforce_context_budget,
)
from .cross_exam_prompt import cross_exam_fragment
from .evidence_prompt import evidence_fragment
from .framing_prompt import framing_fragment, get_prompt_fragment
from .strict_prompt import strict_second_pass_fragment

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RELEVANT_CAPABILITY_KEYS = frozenset(
    {
        "prompt_context_injection",
        "local_control_execution",
        "method_skill_invocation",
        "model_initiated_method_skill_activation",
        "method_invocation_observation",
        "post_tool_observation",
        "post_tool_batch_observation",
        "completion_candidate_observation",
        "bounded_completion_continuation",
        "compaction_reinjection",
        "published_artifact_confirmation",
        "local_record_write",
        "deterministic_trace_render",
    }
)


class PromptEvent(StrEnum):
    """Event-specific prompt projection surfaces."""

    START = "start"
    TOOL_OBSERVATION = "tool_observation"
    STOP_REPAIR = "stop_repair"
    BEGIN = "start"
    TOOL = "tool_observation"
    STOP = "stop_repair"


# Names used by host/application callers in early integration work.
CompileEvent = PromptEvent
PromptContextEvent = PromptEvent


class PromptCompilerError(ValueError):
    """Base error for a fail-closed prompt compilation request."""


class MissingLocaleError(PromptCompilerError):
    """The bundle does not provide the requested locale at every layer."""


class ContentRevisionError(PromptCompilerError):
    """The request or selected method is from a different content revision."""


class MissingMethodContentError(PromptCompilerError):
    """A selected method or required locale-specific procedure is absent."""


class MissingFragmentError(PromptCompilerError):
    """A required fixed prompt fragment is absent or has no versioned text."""


@dataclass(frozen=True, slots=True)
class PromptFragmentRef:
    """Non-user-visible fragment identity included in a compiler result."""

    id: str
    version: int
    locale: str


FragmentMetadata = PromptFragmentRef


@dataclass(frozen=True, slots=True, kw_only=True)
class PromptCompileRequest:
    """Typed compiler input with no prompt/prose persistence field."""

    bundle: CompiledContentBundle
    locale: Locale | str
    event: PromptEvent | str
    participation: ParticipationDecision
    rigor: RigorDecision
    route: RouterDecision | None = None
    phase: TaskState | str = TaskState.FRAMING
    capability_profile: CapabilityProfile | None = None
    expected_content_revision: int | None = None


CompileRequest = PromptCompileRequest


@dataclass(frozen=True, slots=True)
class PromptCompileResult:
    """Canonical prompt text plus bounded compiler-owned metadata."""

    text: str
    event: PromptEvent
    locale: str
    fragments: tuple[PromptFragmentRef, ...]
    compiled_prompt_bundle_hash: str
    estimated_tokens: int
    context_bytes: int
    content_revision: int
    budget: PromptBudgetReport

    @property
    def prompt(self) -> str:
        """Compatibility alias for host adapters that call the field prompt."""

        return self.text

    @property
    def fragment_metadata(self) -> tuple[PromptFragmentRef, ...]:
        return self.fragments

    @property
    def fragment_ids(self) -> tuple[str, ...]:
        return tuple(fragment.id for fragment in self.fragments)


CompileResult = PromptCompileResult


def _event(value: PromptEvent | str) -> PromptEvent:
    try:
        if isinstance(value, PromptEvent):
            return value
        raw = str(getattr(value, "value", value))
        aliases = {
            "user_prompt_submitted": PromptEvent.START.value,
            "tool": PromptEvent.TOOL_OBSERVATION.value,
            "tool_succeeded": PromptEvent.TOOL_OBSERVATION.value,
            "tool_failed": PromptEvent.TOOL_OBSERVATION.value,
            "tool_batch_completed": PromptEvent.TOOL_OBSERVATION.value,
            "observation": PromptEvent.TOOL_OBSERVATION.value,
            "stop": PromptEvent.STOP_REPAIR.value,
            "repair": PromptEvent.STOP_REPAIR.value,
            "completion_candidate": PromptEvent.STOP_REPAIR.value,
        }
        return PromptEvent(aliases.get(raw, raw))
    except (TypeError, ValueError) as exc:
        raise PromptCompilerError(f"unknown prompt event: {value!r}") from exc


def _locale(value: Locale | str) -> str:
    normalized = str(value)
    if normalized not in {"en", "ko"}:
        raise MissingLocaleError(f"unsupported locale: {normalized!r}")
    return normalized


def _phase(value: TaskState | str) -> TaskState:
    try:
        return value if isinstance(value, TaskState) else TaskState(str(value))
    except (TypeError, ValueError) as exc:
        raise PromptCompilerError(f"unknown task phase: {value!r}") from exc


def _assemble(parts: list[str]) -> str:
    if not parts:
        return ""
    # Fragments are authored source and are never truncated or normalized
    # beyond removing the join boundary's duplicate terminal LF.
    return "\n\n".join(part.rstrip("\n") for part in parts) + "\n"


def _hash(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def _validate_bundle(bundle: CompiledContentBundle, locale: str) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if not isinstance(bundle, CompiledContentBundle):
        raise PromptCompilerError("compiler requires a validated CompiledContentBundle")
    revision = bundle.content_revision
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ContentRevisionError("bundle content_revision is missing or invalid")
    if not isinstance(bundle.normalized_semantic_hash, str) or not _SHA256_RE.fullmatch(
        bundle.normalized_semantic_hash
    ):
        raise ContentRevisionError("bundle normalized semantic content hash is missing or invalid")
    if len(set(bundle.method_ids)) != len(bundle.method_ids) or list(bundle.method_ids) != sorted(
        bundle.method_ids
    ):
        raise PromptCompilerError("bundle method IDs are not deterministically ordered")
    if set(bundle.locale_messages) != {"en", "ko"}:
        raise MissingLocaleError("bundle must contain exactly en and ko locale messages")
    if locale not in bundle.locale_messages or not isinstance(
        bundle.locale_messages[locale], Mapping
    ):
        raise MissingLocaleError(f"bundle has no locale message catalog for {locale}")
    if set(bundle.prompt_fragments) != set(PROMPT_FRAGMENT_IDS):
        missing = sorted(set(PROMPT_FRAGMENT_IDS) - set(bundle.prompt_fragments))
        extra = sorted(set(bundle.prompt_fragments) - set(PROMPT_FRAGMENT_IDS))
        detail = f"missing={missing}" if missing else f"extra={extra}"
        raise MissingFragmentError(f"bundle fixed prompt fragment set mismatch: {detail}")
    for fragment_id in PROMPT_FRAGMENT_IDS:
        localized = bundle.prompt_fragments.get(fragment_id)
        if not isinstance(localized, Mapping) or set(localized) != {"en", "ko"}:
            raise MissingFragmentError(f"fragment {fragment_id} is missing an en/ko version")
        for fragment_locale, text in localized.items():
            if fragment_locale not in {"en", "ko"} or not isinstance(text, str) or not text.strip():
                raise MissingFragmentError(
                    f"fragment {fragment_id}.{fragment_locale} is empty or invalid"
                )
    method_ids = [method.id for method in bundle.methods]
    if len(bundle.methods) != len(bundle.method_ids) or method_ids != list(bundle.method_ids):
        raise MissingMethodContentError("bundle methods do not match its ordered method IDs")


def _validate_method(
    method: CompiledMethod,
    bundle: CompiledContentBundle,
    locale: str,
    *,
    complement: bool = False,
) -> str:
    if not isinstance(method, CompiledMethod):
        raise MissingMethodContentError("selected method content is not typed CompiledMethod")
    if method.content_revision != bundle.content_revision:
        raise ContentRevisionError(
            f"method {method.id} revision {method.content_revision} does not match "
            f"bundle revision {bundle.content_revision}"
        )
    field_name = "complement_fragment" if complement else "procedure"
    localized = getattr(method, field_name)
    if not isinstance(localized, Mapping) or set(localized) != {"en", "ko"}:
        raise MissingMethodContentError(
            f"method {method.id} has no complete {field_name} locale map"
        )
    if locale not in localized:
        raise MissingLocaleError(f"method {method.id} has no {locale} {field_name}")
    text = localized[locale]
    if not isinstance(text, str) or not text.strip():
        raise MissingMethodContentError(f"method {method.id} has empty {field_name}.{locale}")
    return text


def _needs_capability_notice(profile: CapabilityProfile | None) -> bool:
    if profile is None:
        return False
    validate_capability_profile(profile)
    return any(
        profile.capabilities[key].status is not CapabilityStatus.SUPPORTED
        for key in _RELEVANT_CAPABILITY_KEYS
    )


class PromptCompiler:
    """Pure compiler for typed request objects."""

    def __init__(self, bundle: CompiledContentBundle | None = None) -> None:
        if bundle is not None and not isinstance(bundle, CompiledContentBundle):
            raise PromptCompilerError("PromptCompiler bundle must be CompiledContentBundle")
        self._bundle = bundle

    def compile(self, request: PromptCompileRequest) -> PromptCompileResult:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        if not isinstance(request, PromptCompileRequest):
            raise PromptCompilerError("compile requires PromptCompileRequest")
        if self._bundle is not None and request.bundle != self._bundle:
            raise PromptCompilerError("request bundle differs from compiler-bound bundle")
        locale = _locale(request.locale)
        event = _event(request.event)
        phase = _phase(request.phase)
        _validate_bundle(request.bundle, locale)
        if not isinstance(request.participation, ParticipationDecision):
            raise PromptCompilerError("participation must be ParticipationDecision")
        if not isinstance(request.rigor, RigorDecision):
            raise PromptCompilerError("rigor must be RigorDecision")
        if request.route is not None and not isinstance(request.route, RouterDecision):
            raise PromptCompilerError("route must be RouterDecision or null")
        if request.capability_profile is not None and not isinstance(
            request.capability_profile, CapabilityProfile
        ):
            raise PromptCompilerError("capability_profile must be CapabilityProfile or null")
        if request.expected_content_revision is not None:
            expected = request.expected_content_revision
            if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
                raise ContentRevisionError("expected_content_revision must be a positive integer")
            if expected != request.bundle.content_revision:
                raise ContentRevisionError(
                    f"requested content revision {expected} does not match "
                    f"bundle {request.bundle.content_revision}"
                )

        # The mechanical path is deliberately empty.  It creates no visible
        # OpenSocrates apparatus, while bundle validation above still prevents a
        # stale/malformed bundle from being silently accepted.
        if request.participation.participation is Participation.MECHANICAL:
            if request.route is not None and (
                request.route.primary_method is not None
                or request.route.secondary_method is not None
            ):
                raise PromptCompilerError(
                    "mechanical participation cannot inject a method procedure"
                )
            text = ""
            report = enforce_context_budget(event.value, (), text)
            return PromptCompileResult(
                text=text,
                event=event,
                locale=locale,
                fragments=(),
                compiled_prompt_bundle_hash=_hash(text),
                estimated_tokens=report.total_tokens,
                context_bytes=report.context_bytes,
                content_revision=request.bundle.content_revision,
                budget=report,
            )

        if (
            request.route is not None
            and request.route.secondary_method is not None
            and request.route.primary_method is None
        ):
            raise MissingMethodContentError("secondary method requires a primary method")
        method_by_id = {method.id: method for method in request.bundle.methods}
        primary_method: CompiledMethod | None = None
        secondary_method: CompiledMethod | None = None
        primary_procedure: str | None = None
        secondary_complement: str | None = None
        if request.route is not None and request.route.primary_method is not None:
            primary_method = method_by_id.get(request.route.primary_method)
            if primary_method is None:
                raise MissingMethodContentError(
                    f"missing primary method content: {request.route.primary_method}"
                )
            if (
                request.route.primary_family is not None
                and primary_method.family != request.route.primary_family
            ):
                raise MissingMethodContentError(
                    f"primary method family mismatch for {request.route.primary_method}: "
                    f"{request.route.primary_family}"
                )
            # Validate the locale/revision even for observation/Stop events;
            # an event projection never silently falls back to stale method
            # content merely because the full procedure is not injected there.
            primary_procedure = _validate_method(primary_method, request.bundle, locale)
            if request.route.secondary_method is not None:
                secondary_method = method_by_id.get(request.route.secondary_method)
                if secondary_method is None:
                    raise MissingMethodContentError(
                        f"missing secondary method content: {request.route.secondary_method}"
                    )
                if secondary_method.id == primary_method.id:
                    raise MissingMethodContentError("primary and secondary methods must differ")
                if (
                    request.route.secondary_family is not None
                    and secondary_method.family != request.route.secondary_family
                ):
                    raise MissingMethodContentError(
                        f"secondary method family mismatch for {request.route.secondary_method}: "
                        f"{request.route.secondary_family}"
                    )
                secondary_complement = _validate_method(
                    secondary_method,
                    request.bundle,
                    locale,
                    complement=True,
                )

        refs: list[PromptFragmentRef] = []
        budget_fragments: list[BudgetFragment] = []
        texts: list[str] = []

        def add_common(fragment_id: str, text: str, bucket: str) -> None:
            refs.append(
                PromptFragmentRef(
                    id=fragment_id,
                    version=request.bundle.content_revision,
                    locale=locale,
                )
            )
            budget_fragments.append(BudgetFragment(id=fragment_id, text=text, bucket=bucket))
            texts.append(text)

        def add_method(fragment_id: str, version: int, text: str, bucket: str) -> None:
            refs.append(PromptFragmentRef(id=fragment_id, version=version, locale=locale))
            budget_fragments.append(BudgetFragment(id=fragment_id, text=text, bucket=bucket))
            texts.append(text)

        # The controller/invariant is always first for a judgment prompt.  The
        # text is bundle-owned, so its injection/no-hidden-reasoning boundary is
        # never recreated or weakened in this module.
        add_common(
            "controller",
            get_prompt_fragment(request.bundle, locale, "controller"),
            "participation_rigor",
        )

        if event is PromptEvent.START:
            add_common(
                "participation_rigor",
                get_prompt_fragment(request.bundle, locale, "participation_rigor"),
                "participation_rigor",
            )
            if request.route is None:
                add_common(
                    "routing_classifier",
                    get_prompt_fragment(request.bundle, locale, "routing_classifier"),
                    "participation_rigor",
                )
            framing = framing_fragment(request.bundle, locale, phase=phase)
            if framing is not None:
                add_common("framing", framing, "evidence_card_completion")

            # Only the primary full procedure is included.  The secondary is
            # represented by its authored Complement handoff below.
            if primary_method is not None and primary_procedure is not None:
                add_method(
                    f"procedure:{primary_method.id}",
                    primary_method.content_revision,
                    primary_procedure,
                    "primary_procedure",
                )
                if secondary_method is not None and secondary_complement is not None:
                    add_method(
                        f"complement:{secondary_method.id}",
                        secondary_method.content_revision,
                        secondary_complement,
                        "secondary_complement",
                    )
            add_common(
                "evidence_card_completion",
                evidence_fragment(request.bundle, locale),
                "evidence_card_completion",
            )
        elif event is PromptEvent.TOOL_OBSERVATION:
            add_common(
                "evidence_card_completion",
                evidence_fragment(request.bundle, locale),
                "evidence_card_completion",
            )
        else:  # stop_repair
            add_common(
                "evidence_card_completion",
                completion_fragment(request.bundle, locale),
                "evidence_card_completion",
            )
            add_common(
                "cross_exam",
                cross_exam_fragment(request.bundle, locale),
                "evidence_card_completion",
            )
            if request.rigor.effective_rigor is Rigor.STRICT:
                add_common(
                    "strict_second_pass",
                    strict_second_pass_fragment(request.bundle, locale),
                    "evidence_card_completion",
                )

        if _needs_capability_notice(request.capability_profile):
            add_common(
                "capability_notice",
                get_prompt_fragment(request.bundle, locale, "capability_notice"),
                "capability_notice",
            )

        text = _assemble(texts)
        report = enforce_context_budget(event.value, budget_fragments, text)
        return PromptCompileResult(
            text=text,
            event=event,
            locale=locale,
            fragments=tuple(refs),
            compiled_prompt_bundle_hash=_hash(text),
            estimated_tokens=report.total_tokens,
            context_bytes=report.context_bytes,
            content_revision=request.bundle.content_revision,
            budget=report,
        )

    __call__ = compile


def compile_prompt(
    request: PromptCompileRequest | CompiledContentBundle,
    **kwargs: Any,
) -> PromptCompileResult:
    """Compile a typed request, with a convenience bundle-first form.

    The convenience form still requires all domain decisions as typed keyword
    arguments; it exists for small host adapters and focused build walkthroughs.
    """

    if isinstance(request, PromptCompileRequest):
        if kwargs:
            raise TypeError("kwargs are not accepted with PromptCompileRequest")
        return PromptCompiler().compile(request)
    if isinstance(request, CompiledContentBundle):
        try:
            typed_request = PromptCompileRequest(bundle=request, **kwargs)
        except TypeError as exc:
            raise TypeError(
                "bundle-first compile requires locale, event, participation, and rigor"
            ) from exc
        return PromptCompiler().compile(typed_request)
    raise PromptCompilerError(
        "compile_prompt requires PromptCompileRequest or CompiledContentBundle"
    )


compile = compile_prompt


__all__ = [
    "CompileEvent",
    "CompileRequest",
    "CompileResult",
    "ContentRevisionError",
    "FragmentMetadata",
    "MissingFragmentError",
    "MissingLocaleError",
    "MissingMethodContentError",
    "PromptCompileRequest",
    "PromptCompileResult",
    "PromptCompiler",
    "PromptCompilerError",
    "PromptContextEvent",
    "PromptEvent",
    "PromptFragmentRef",
    "compile",
    "compile_prompt",
]
