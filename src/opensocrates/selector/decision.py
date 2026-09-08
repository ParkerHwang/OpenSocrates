"""Agent-directed decision points. Volatile delivery state, never reasoning traces."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..content.injection import ProjectionInstructionAssembler
from ..domain.enums import Participation
from ..domain.models import CompiledContentBundle
from ..domain.routing import RoutingCatalog, route_features, validate_routing_payload
from ..rendering.response_policy import response_guidance, validate_response_policy


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
                raise ValueError
            operation = value.get("operation")
            if operation == "catalog":
                return self._catalog(value)
            if operation == "acknowledge":
                return self._acknowledge(value)
            if operation == "reset":
                if set(value) != {"operation"}:
                    raise ValueError
                self._reset()
                return {"status": "reset", "context_eviction": False}
            return self._select(value)
        except (ValueError, TypeError, KeyError):
            return self._failure("invalid_decision_request")
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
        if set(value) != {"operation", "locale"} or value["locale"] not in {"en", "ko"}:
            raise ValueError
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
        if set(value) != {"operation", "context", "epoch", "digests"}:
            raise ValueError
        digests = value["digests"]
        if (
            type(value["epoch"]) is not int
            or (value["context"], value["epoch"]) != self.scope
            or not isinstance(digests, list)
            or len(digests) > len(self.bundle.methods)
            or any(not isinstance(d, str) or d not in self.delivered.values() for d in digests)
        ):
            raise ValueError
        self.available.update(
            (identity, digest) for identity, digest in self.delivered.items() if digest in digests
        )
        return {
            "status": "acknowledged",
            "available": "agent_reported",
            "read": "agent_reported",
            "applied": "unverified",
        }

    def _scope(self, value: dict[str, Any]) -> None:
        context, epoch = value["context"], value["epoch"]
        # Context handles are random opaque IDs, not prompts, workspace paths or host IDs.
        if (
            not isinstance(context, str)
            or len(context) != 32
            or any(c not in "0123456789abcdef" for c in context)
            or type(epoch) is not int
            or epoch < 0
        ):
            raise ValueError
        new_scope = (context, epoch)
        if self.scope and self.scope[0] == context and epoch < self.scope[1]:
            raise ValueError
        if new_scope != self.scope:
            self._reset()
            self.scope = new_scope

    def _select(self, value: dict[str, Any]) -> dict[str, Any]:
        expected = {
            "operation",
            "context",
            "epoch",
            "decision",
            "revision",
            "locale",
            "participation",
            "routing",
        }
        if set(value) != expected or value["operation"] != "select":
            raise ValueError
        if (
            value["locale"] not in {"en", "ko"}
            or type(value["revision"]) is not int
            or value["revision"] < 0
            or not isinstance(value["decision"], str)
            or not value["decision"].isascii()
            or not value["decision"].isalnum()
            or len(value["decision"]) > 64
        ):
            raise ValueError
        self._scope(value)
        participation = Participation(value["participation"])
        payload = validate_routing_payload(value["routing"])
        if (
            not payload.structurally_valid
            or payload.invalid_feature_list
            or payload.features is None
        ):
            raise ValueError
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
            "audit_if_applied": (
                "OpenSocrates grounding: "
                + ", ".join(f"{method}@{self.bundle.content_revision}" for method in selected)
                if selected
                else None
            ),
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
