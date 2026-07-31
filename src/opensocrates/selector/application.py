"""Fail-open application service for one Codex UserPromptSubmit selector call."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..application.ports import (
    CanonicalInstructionAssembler,
    InstructionArtifactStore,
    ReasoningSelector,
)
from .context import handles_for_request
from .models import (
    SelectorConfig,
    SelectorDecision,
    SelectorModelError,
    SelectorRequest,
    validate_raw_candidate,
)
from .policy import (
    CurrentPromptLocalePolicy,
    MediumReasoningEffortPolicy,
    PromptLocalePolicy,
    ReasoningEffortPolicy,
)


@dataclass(slots=True, repr=False)
class SelectorApplication:
    """Coordinate one fresh selection without retaining prompt or raw context.

    All errors deliberately resolve to ``None``.  The host layer alone maps that
    fail-open result to literal empty stdout; this layer never writes output.
    """

    selector: ReasoningSelector = field(repr=False)
    assembler: CanonicalInstructionAssembler = field(repr=False)
    config: SelectorConfig = field(default_factory=SelectorConfig, repr=False)
    locale_policy: PromptLocalePolicy = field(default_factory=CurrentPromptLocalePolicy, repr=False)
    effort_policy: ReasoningEffortPolicy = field(
        default_factory=MediumReasoningEffortPolicy, repr=False
    )
    artifact_store: InstructionArtifactStore | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.config, SelectorConfig):
            raise SelectorModelError("selector application requires selector configuration")

    def select_for_user_prompt_submit(self, request: SelectorRequest) -> SelectorDecision | None:
        """Select and canonically assemble one fresh UserPromptSubmit decision.

        The raw SDK candidate determines only intervention and selected IDs.  Its
        instruction string is validated for shape but is never used in the final
        decision; the content-owned assembler creates the only injectable text.
        """

        try:
            effective_request, context = handles_for_request(request, self.config)
            known_method_ids = self.assembler.known_method_ids()
            candidate = self.selector.select(
                effective_request,
                context,
                deadline_seconds=self.config.deadline_seconds,
                reasoning_effort=self.effort_policy.effort_for(effective_request),
            )
            raw = validate_raw_candidate(candidate, known_method_ids=known_method_ids)
            if not raw.intervene:
                return None

            requested_locale = self.locale_policy.locale_for(effective_request)
            assembled = self.assembler.assemble(
                raw.selected_reasoning_systems,
                requested_locale=requested_locale,
            )
            if self.artifact_store is None:
                return None
            artifact = self.artifact_store.create(
                effective_request.session_id,
                effective_request.turn_id,
                assembled,
            )
            decision = SelectorDecision(
                intervene=True,
                selected_reasoning_systems=raw.selected_reasoning_systems,
                instructions=artifact.reference_message(),
            )
        except Exception:
            return None

        return decision

    def __repr__(self) -> str:
        return "SelectorApplication(<transient-redacted>)"


__all__ = ["SelectorApplication"]
