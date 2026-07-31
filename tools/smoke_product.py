"""Focused content-free end-to-end product smoke.

The smoke uses typed in-memory repositories and synthetic callback/card
metadata.  It intentionally emits only scenario names and bounded status
codes; no prompt, transcript, token, task ID, raw tool output, or path is
printed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from opensocrates.application.change_settings import decide_rigor
from opensocrates.application.delete_records import DeleteRequest, RecordHandle, delete_records
from opensocrates.application.handle_stop import StopInput, handle_stop
from opensocrates.application.start_task import issue_turn_state
from opensocrates.application.status import project_status
from opensocrates.cli.runtime import BundleRepository, discover_bundle_path
from opensocrates.content.loader import load_compiled_bundle
from opensocrates.domain.enums import (
    AnswerShape,
    ClassificationConfidence,
    FeatureBasis,
    FeatureKey,
    HostId,
    MetricEventName,
    Participation,
    ParticipationReasonCode,
    Rigor,
    VerificationOutcome,
    ViolationSeverity,
)
from opensocrates.domain.models import (
    LocalMetric,
    ParticipationDecision,
    RoutingFeature,
    RoutingFeatures,
    VerificationResult,
    Violation,
)
from opensocrates.domain.risk import RiskSignals
from opensocrates.domain.routing import route_from_bundle
from opensocrates.hosts.codex.adapter import CodexAdapter, CodexAdapterConfig
from opensocrates.hosts.codex.capability import default_capability_profile
from opensocrates.hosts.prompt_only.adapter import PromptOnlyAdapter
from opensocrates.hosts.prompt_only.capability import (
    default_capability_profile as prompt_only_profile,
)
from opensocrates.persistence import (
    InMemoryMetricsStore,
    InMemorySettingsStore,
    InMemoryTurnStore,
)
from opensocrates.version import PRODUCT_VERSION


@dataclass
class _DeleteStore:
    handles: tuple[RecordHandle, ...]
    deleted: list[str]

    def list_records(self) -> tuple[RecordHandle, ...]:
        return self.handles

    def delete_record(self, record_ref: str, *, include_quarantine: bool = False) -> bool:
        del include_quarantine
        self.deleted.append(record_ref)
        return True


def _route(
    bundle: object,
    participation: ParticipationDecision,
    *,
    feature_key: FeatureKey | None = None,
    explicit_method: str | None = None,
) -> dict[str, object]:
    features = RoutingFeatures(
        answer_shape=AnswerShape.DIRECT_JUDGMENT,
        features=(
            RoutingFeature(
                key=feature_key or FeatureKey.JUDGMENT,
                strength=2,
                basis=FeatureBasis.TASK_SHAPE,
            ),
        ),
        classification_confidence=ClassificationConfidence.HIGH,
        explicit_method=explicit_method,
    )
    decision = route_from_bundle(participation, features, bundle)  # type: ignore[arg-type]
    return {
        "reason": decision.reason_code.value,
        "has_primary": decision.primary_method is not None,
        "has_secondary": decision.secondary_method is not None,
        "explicit": decision.explicit_invocation,
    }


def run() -> dict[str, object]:
    bundle_path = discover_bundle_path()
    bundle = load_compiled_bundle(bundle_path)
    settings = InMemorySettingsStore()
    turns = InMemoryTurnStore(installation_key=b"s25-smoke-installation-key-32bytes!!"[:32])
    metrics = InMemoryMetricsStore()
    profile = default_capability_profile(HostId.CODEX_CLI)
    prompt_profile = prompt_only_profile(host=HostId.PROMPT_ONLY)
    results: dict[str, object] = {"status": "pass", "scenarios": {}}
    scenarios: dict[str, object] = results["scenarios"]  # type: ignore[assignment]

    # Native -> normalized -> content-context seam (mechanical callback).
    adapter = CodexAdapter(
        CodexAdapterConfig(
            bundle_path=bundle_path,
            content_repository=BundleRepository(bundle_path),
            turn_repository=turns,
            settings_repository=settings,
            capability_profile=profile,
            installation_key=turns.installation_key,
        )
    )
    start = adapter.handle(
        {
            "hook_event_name": "SessionStart",
            "source": "startup",
            "version": PRODUCT_VERSION,
        },
        event_name="SessionStart",
    )
    scenarios["mechanical_pass_through"] = (
        start.error_code is None and start.response.get("hookSpecificOutput") is not None
    )

    user = adapter.handle(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "synthetic judgment request",
            "session_id": "synthetic-session",
            "turn_id": "synthetic-turn",
            "version": PRODUCT_VERSION,
        },
        event_name="UserPromptSubmit",
    )
    normalized = user.normalized_event
    scenarios["judgment_start"] = normalized is not None

    mechanical = ParticipationDecision(
        participation=Participation.MECHANICAL,
        reason_code=ParticipationReasonCode.DIRECT_TRANSFORMATION,
        mechanical_targets=("synthetic artifact",),
    )
    judgment = ParticipationDecision(
        participation=Participation.JUDGMENT,
        reason_code=ParticipationReasonCode.JUDGMENT_CHOICE,
        judgment_targets=("synthetic choice",),
    )
    mixed = ParticipationDecision(
        participation=Participation.MIXED,
        reason_code=ParticipationReasonCode.JUDGMENT_THEN_ARTIFACT,
        judgment_targets=("synthetic choice",),
        mechanical_targets=("synthetic artifact",),
    )
    explicit = ParticipationDecision(
        participation=Participation.JUDGMENT,
        reason_code=ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT,
        judgment_targets=("synthetic choice",),
        explicit_method=bundle.method_ids[0],
    )
    scenarios["route_mechanical"] = _route(bundle, mechanical)
    scenarios["route_direct_recommendation"] = _route(
        bundle, judgment, feature_key=FeatureKey.MULTIPLE_OPTIONS
    )
    scenarios["route_mixed"] = _route(bundle, mixed, feature_key=FeatureKey.MIXED)
    scenarios["route_explicit_method"] = _route(
        bundle, explicit, explicit_method=bundle.method_ids[0]
    )

    raised = decide_rigor(
        settings.load(),
        None,
        Participation.JUDGMENT,
        risk_signals=RiskSignals(material_consequence=True),
    )
    scenarios["risk_raise"] = {
        "raised": raised.show_raise_notice,
        "effective": raised.effective_rigor.value,
    }

    # S18 one-repair reservation with a typed invalid-card verification result.
    repair_state = None
    if normalized is not None:
        issued = issue_turn_state(normalized, settings.load(), turns, capability_profile=profile)
        repair_state = issued.state
    violation = Violation(
        rule_id="OSV-SMOKE-001",
        severity=ViolationSeverity.ERROR,
        message_key="card.invalid",
        field="/card",
        repair_hint_key="repair.group",
    )
    verification = VerificationResult(outcome=VerificationOutcome.REPAIR, violations=(violation,))

    def repair_renderer(_violations: object, **_kwargs: object) -> str:
        return "synthetic repair instruction"

    def reserve(expected: object, replacement: object) -> bool:
        if repair_state is None:
            return False
        turns.compare_and_swap(expected, replacement)  # type: ignore[arg-type]
        return True

    if repair_state is not None:
        repaired = handle_stop(
            StopInput(
                verification_result=verification,
                turn_state=repair_state,
                repair_reservation=reserve,
                repair_renderer=repair_renderer,
                continuation_supported=True,
            )
        )
        scenarios["invalid_card_one_repair"] = {
            "decision": repaired.decision.value,
            "reserved": repaired.reserved,
            "repair_count_after": repaired.repair_count_after,
        }
    else:
        scenarios["invalid_card_one_repair"] = {"decision": "unavailable"}

    prompt_only = PromptOnlyAdapter(bundle=bundle, profile=prompt_profile)
    prompt_result = prompt_only.handle({"synthetic": True}, event_name="session_started")
    scenarios["prompt_only_degradation"] = {
        "status": prompt_result.status,
        "capability_tier": prompt_profile.computed_tier.value,
        "persisted": False,
    }

    metric = LocalMetric(
        event=MetricEventName.JUDGMENT_STARTED,
        occurred_at_day="2026-07-16",
        host=HostId.CODEX_CLI,
        locale="en",
        rigor=Rigor.TOGETHER,
    )
    metrics.append(metric)
    scenarios["metrics_aggregate"] = {"count": len(metrics.read())}

    status = project_status(settings.load(), profile)
    scenarios["status_projection"] = {
        "capability_state": status.capability_state.value,
        "recording_effective": status.recording_effective,
    }

    delete_store = _DeleteStore((RecordHandle("01234567", "synthetic-record"),), [])
    deleted = delete_records(
        DeleteRequest(public_short_id="01234567"),
        store=delete_store,
    )
    scenarios["trace_delete"] = {
        "delete_count": deleted.receipt.count,
        "trace_projection": "not_recorded",
    }
    return results


def main() -> int:
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
