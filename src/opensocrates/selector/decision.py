"""Agent-directed decision points. Volatile delivery state, never reasoning traces."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..constants import PUBLIC_ATTRIBUTION_FOOTER
from ..content.injection import ProjectionInstructionAssembler
from ..domain.enums import Participation
from ..domain.models import CompiledContentBundle
from ..domain.routing import RoutingCatalog, route_features, validate_routing_payload
from ..rendering.response_policy import response_guidance, validate_response_policy

LOCALES = frozenset({"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"})
SELECT_KEYS = (
    "operation",
    "context",
    "epoch",
    "decision",
    "revision",
    "locale",
    "participation",
    "routing",
)
# Closed repair vocabulary for rejected input. Responses name schema locations
# and these codes only; submitted values, unknown key names and prose are never
# echoed, logged or retained.
FAULT_CODES = frozenset(
    {
        "invalid_json",
        "invalid_type",
        "missing_field",
        "unknown_field",
        "unknown_operation",
        "invalid_format",
        "invalid_value",
        "stale_epoch",
        "unknown_feature",
        "duplicate_feature",
        "too_many_features",
    }
)
EXPECTED = {
    "request": "one JSON object with exactly the documented keys for its operation",
    "operation": "one of catalog, select, acknowledge, reset",
    "context": "32 lowercase hexadecimal characters [0-9a-f]",
    "epoch": "integer >= 0, never lower than the previous epoch for this context",
    "decision": "1-64 ASCII letters or digits, no hyphen, underscore or space",
    "revision": "integer >= 0",
    "locale": "one of en, ko, zh, ja, fr, de, it, es, pt, th",
    "participation": "one of judgment, mixed, mechanical",
    "routing.schema": "opensocrates.routing-features/1.0.0",
    "routing.answer_shape": "a value from features.json answer_shapes",
    "routing.classification_confidence": "one of high, medium, low",
    "routing.explicit_method": "null, or a catalog method ID the user requested",
    "routing.features": "a list of at most 16 entries with key, strength and basis",
    "key": "a value from features.json features, used once",
    "strength": "integer 1, 2 or 3",
    "basis": "a value from features.json basis",
}


class RequestFault(ValueError):
    """A rejected request location. Carries schema paths and closed codes, never values."""

    def __init__(self, field: str, error: str) -> None:
        if error not in FAULT_CODES:
            raise AssertionError(error)
        super().__init__(error)
        self.field = field
        self.error = error


def fault_response(field: str, error: str) -> dict[str, Any]:
    result = DecisionSession._failure("invalid_decision_request")
    result.update({"field": field, "error": error, "repair": "correct_field_once"})
    expected = EXPECTED.get(field) or EXPECTED.get(field.rsplit(".", 1)[-1])
    if expected is not None:
        result["expected"] = expected
    return result


@dataclass(repr=False)
class DecisionSession:
    """One agent context per process. Acknowledgments are assertions, not host proof.

    No model selector is called. The active agent supplies closed semantic cues.
    Only the last decision and current catalog-sized delivery inventory are kept.
    A new context/epoch retires every availability assertion, without token eviction.
    """

    bundle: CompiledContentBundle = field(repr=False)
    assembler: ProjectionInstructionAssembler = field(repr=False)
    scope: tuple[str, int] | None = None
    last_key: str | None = None
    last_selection: tuple[str, ...] = ()
    last_reason: str = "no_eligible_method"
    delivered: dict[str, str] = field(default_factory=dict)
    available: set[tuple[str, str]] = field(default_factory=set)
    routing_catalog: RoutingCatalog = field(init=False, repr=False)
    busy: bool = False
    response_policy: Mapping[str, Any] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.response_policy is not None:
            validate_response_policy(self.response_policy)
        self.routing_catalog = RoutingCatalog.from_bundle(self.bundle)
        projections = self.assembler.projections
        if self.bundle.content_revision != projections.content_revision:
            raise ValueError("content revision mismatch")
        methods = {m.id: m for m in self.bundle.methods}
        if set(methods) != self.assembler.known_method_ids():
            raise ValueError("catalog identity mismatch")
        for item in projections.injectable_content:
            method = methods[item.method_id]
            if (
                item.theory != method.procedure[item.locale]
                or item.display_name != method.display_name[item.locale]
            ):
                raise ValueError("canonical procedure identity mismatch")

    def handle(self, value: object) -> dict[str, Any]:
        if self.busy:
            return self._failure("recursive_request")
        self.busy = True
        try:
            if not isinstance(value, dict):
                raise RequestFault("request", "invalid_type")
            operation = value.get("operation")
            if operation == "catalog":
                return self._catalog(value)
            if operation == "acknowledge":
                return self._acknowledge(value)
            if operation == "reset":
                if set(value) != {"operation"}:
                    raise RequestFault("request", "unknown_field")
                self._reset()
                return {"status": "reset", "context_eviction": False}
            if operation != "select":
                raise RequestFault(
                    "operation", "unknown_operation" if "operation" in value else "missing_field"
                )
            return self._select(value)
        except RequestFault as fault:
            return fault_response(fault.field, fault.error)
        except (ValueError, TypeError, KeyError):
            # Remaining failures are packaged-content or runtime faults after the
            # request was accepted; they are not input the agent can repair.
            return self._failure("decision_unavailable")
        finally:
            self.busy = False

    @staticmethod
    def _failure(reason: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "reason": reason,
            "applied": "unverified",
            "continue_ordinary_work": True,
            "constraints_remain_binding": True,
        }

    def _reset(self) -> None:
        self.scope = None
        self.last_key = None
        self.last_selection = ()
        self.last_reason = "no_eligible_method"
        self.delivered.clear()
        self.available.clear()

    def _catalog(self, value: dict[str, Any]) -> dict[str, Any]:
        self._closed_keys(value, ("operation", "locale"))
        if not isinstance(value["locale"], str) or value["locale"] not in LOCALES:
            raise RequestFault("locale", "invalid_value")
        locale = value["locale"]
        return {
            "status": "catalog",
            "content_revision": self.bundle.content_revision,
            "methods": [
                {"id": m.id, "use_for": m.plain_action[locale], "routing": dict(m.routing)}
                for m in self.bundle.methods
            ],
            "evidence": "metadata_only",
        }

    def _acknowledge(self, value: dict[str, Any]) -> dict[str, Any]:
        self._closed_keys(value, ("operation", "context", "epoch", "digests"))
        digests = value["digests"]
        if type(value["epoch"]) is not int:
            raise RequestFault("epoch", "invalid_type")
        if (value["context"], value["epoch"]) != self.scope:
            same_context = self.scope is not None and value["context"] == self.scope[0]
            raise RequestFault("epoch" if same_context else "context", "invalid_value")
        if not isinstance(digests, list) or len(digests) > len(self.bundle.methods):
            raise RequestFault("digests", "invalid_type")
        if any(not isinstance(d, str) or d not in self.delivered.values() for d in digests):
            raise RequestFault("digests", "invalid_value")
        self.available.update(
            (identity, digest) for identity, digest in self.delivered.items() if digest in digests
        )
        return {
            "status": "acknowledged",
            "available": "agent_reported",
            "read": "agent_reported",
            "applied": "unverified",
        }

    def _check_scope(self, value: dict[str, Any]) -> None:
        context, epoch = value["context"], value["epoch"]
        # Context handles are random opaque IDs, not prompts, workspace paths or host IDs.
        if not isinstance(context, str):
            raise RequestFault("context", "invalid_type")
        if len(context) != 32 or any(c not in "0123456789abcdef" for c in context):
            raise RequestFault("context", "invalid_format")
        if type(epoch) is not int:
            raise RequestFault("epoch", "invalid_type")
        if epoch < 0:
            raise RequestFault("epoch", "invalid_value")
        if self.scope and self.scope[0] == context and epoch < self.scope[1]:
            raise RequestFault("epoch", "stale_epoch")

    def _scope(self, value: dict[str, Any]) -> None:
        # Called only after the complete request is valid: rejected input never resets state.
        new_scope = (value["context"], value["epoch"])
        if new_scope != self.scope:
            self._reset()
            self.scope = new_scope

    @staticmethod
    def _closed_keys(value: dict[str, Any], keys: tuple[str, ...]) -> None:
        missing = [key for key in keys if key not in value]
        if missing:
            raise RequestFault(missing[0], "missing_field")
        if len(value) != len(keys):
            raise RequestFault("request", "unknown_field")

    def _select(self, value: dict[str, Any]) -> dict[str, Any]:
        self._closed_keys(value, SELECT_KEYS)
        # Faults are reported one at a time in the documented envelope order.
        self._check_scope(value)
        decision = value["decision"]
        if not isinstance(decision, str):
            raise RequestFault("decision", "invalid_type")
        if not decision.isascii() or not decision.isalnum() or len(decision) > 64:
            raise RequestFault("decision", "invalid_format")
        if type(value["revision"]) is not int:
            raise RequestFault("revision", "invalid_type")
        if value["revision"] < 0:
            raise RequestFault("revision", "invalid_value")
        if not isinstance(value["locale"], str) or value["locale"] not in LOCALES:
            raise RequestFault("locale", "invalid_value")
        try:
            participation = Participation(value["participation"])
        except (ValueError, TypeError):
            raise RequestFault("participation", "invalid_value") from None
        payload = validate_routing_payload(value["routing"])
        if (
            not payload.structurally_valid
            or payload.invalid_feature_list
            or payload.features is None
        ):
            # An unknown key is rejected rather than routed: it may conceal a contraindication.
            field, error = payload.fault or ("", "invalid_value")
            raise RequestFault(f"routing.{field}" if field else "routing", error)
        self._scope(value)
        explicit = payload.features.explicit_method
        if explicit is not None and explicit not in self.assembler.known_method_ids():
            return self._failure("unknown_method")
        key = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        reused = key == self.last_key
        if reused:
            selected = self.last_selection
            reason = self.last_reason
        else:
            route = route_features(participation, payload.features, catalog=self.routing_catalog)
            selected = tuple(m for m in (route.primary_method, route.secondary_method) if m)
            reason = route.reason_code.value
        methods = self._deliver(selected, value["locale"])
        self.last_key, self.last_selection, self.last_reason = key, selected, reason
        return {
            "status": "selected" if selected else "no_intervention",
            "selected": list(selected),
            "reason": reason,
            "content_revision": self.bundle.content_revision,
            "methods": methods,
            "selection_reused": reused,
            "selector_model_calls": 0,
            "presentation": (
                response_guidance(
                    self.response_policy, value["locale"], str(payload.features.answer_shape.value)
                )
                if self.response_policy is not None
                and participation is not Participation.MECHANICAL
                else None
            ),
            "scope": {"context": value["context"], "epoch": value["epoch"]},
            "applied": "unverified",
            "audit_if_applied": PUBLIC_ATTRIBUTION_FOOTER if selected else None,
            "context_eviction": False,
        }

    def _deliver(self, selected: tuple[str, ...], locale: str) -> list[dict[str, Any]]:
        result = []
        for method in selected:
            assembled = self.assembler.assemble((method,), requested_locale=locale)  # type: ignore[arg-type]
            if assembled.locale != locale:
                raise ValueError("exact locale required")
            digest = "sha256:" + hashlib.sha256(assembled.instructions.encode()).hexdigest()
            identity = f"{method}:{locale}:{assembled.content_revision}"
            if self.delivered.get(identity) != digest:
                previous = self.delivered.get(identity)
                if previous:
                    self.available.discard((identity, previous))
            retained = (identity, digest) in self.available
            self.delivered[identity] = digest
            result.append(
                {
                    "id": method,
                    "locale": locale,
                    "content_revision": assembled.content_revision,
                    "sha256": digest,
                    "delivery": "reused_agent_reported_available" if retained else "emitted",
                    "read": "agent_reported" if retained else "unverified",
                    "instructions": None if retained else assembled.instructions,
                }
            )
        return result
