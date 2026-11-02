"""Local 2.0 foundation entry point; no existing desktop host is auto-enabled."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from uuid import uuid4

from .service import (
    AuthorizationRequest,
    DeliveryState,
    Permission,
    RuntimeService,
    ServiceSession,
    SessionCreation,
    TransientPayload,
)


class _SyntheticHost:
    """Fixed public demonstration only; does not retain delivered bodies."""

    def __init__(self) -> None:
        self.sessions: set[str] = set()
        self.deliveries = 0

    def create_session(self, task_id: str) -> SessionCreation:
        reference = uuid4().hex
        self.sessions.add(reference)
        return SessionCreation(reference, "created")

    def deliver(
        self, session: ServiceSession, request_id: str, payload: TransientPayload
    ) -> DeliveryState:
        if session.session_ref not in self.sessions:
            return DeliveryState.REFUSED
        self.deliveries += 1
        return DeliveryState.DELIVERED


def _synthetic_authority(request: AuthorizationRequest) -> Permission:
    if (
        request.task.project_ref == "synthetic_project"
        and request.authority_ref == "synthetic_grant"
        and request.task.host_ref == "synthetic_host"
    ):
        return Permission.ALLOW
    return Permission.DENY


def _demo() -> dict[str, object]:
    host = _SyntheticHost()
    service = RuntimeService(authorizer=_synthetic_authority)
    service.register_host("synthetic_host", host)
    service.start()
    tasks = [
        service.submit(
            task_id=f"synthetic_{name}",
            project_ref="synthetic_project",
            intake_ref="synthetic_intake",
            host_ref="synthetic_host",
            authority_ref="synthetic_grant",
            payload=TransientPayload("Public synthetic assignment."),
        )
        for name in ("a", "b")
    ]
    first, second = tasks
    if first.execution_ref is None or second.execution_ref is None:
        return {"evidence": "synthetic_only", "outcome": "session_creation_unavailable"}
    for task_id, source, target in (
        (first.task_id, first.execution_ref, second.execution_ref),
        (second.task_id, second.execution_ref, first.execution_ref),
    ):
        service.relay(
            task_id=task_id,
            sender_ref=source,
            destination_ref=target,
            authority_ref="synthetic_grant",
            request_id=uuid4().hex,
            payload=TransientPayload("Public synthetic round trip."),
        )
    result = service.status()
    result.update(
        evidence="synthetic_only",
        outcome="synthetic_round_trip",
        real_host_delivery="not_tested",
        retained_message_bodies=False,
    )
    service.close()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenSocrates 2.0 local foundation")
    parser.add_argument(
        "command", choices=("status", "demo", "observe-file"), nargs="?", default="status"
    )
    parser.add_argument("--path", help="Single file explicitly selected for a read-only fingerprint")
    parser.add_argument("--previous", help="Previously obtained sha256 fingerprint")
    args = parser.parse_args(argv)
    if args.command == "observe-file":
        if args.path is None:
            parser.error("observe-file requires --path")
        result = _observe_file(args.path, args.previous)
    elif args.path is not None or args.previous is not None:
        parser.error("file arguments are only available for observe-file")
    elif args.command == "demo":
        result = _demo()
    else:
        service = RuntimeService()
        result = service.status()
        result["evidence"] = "local_foundation"
        result["persistence"] = "in_memory"
        service.close()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _observe_file(path: str, previous: str | None) -> dict[str, object]:
    """The direct CLI request selects one path; no path or content is printed."""
    from .artifacts import observe_named_file

    try:
        observation = observe_named_file(path, previous)
    except (ValueError, TypeError, OSError):
        return {"evidence": "local_file_observation", "outcome": "invalid_or_unavailable"}
    return {
        "evidence": "local_file_observation",
        "availability": observation.availability.value,
        "exists": observation.exists,
        "fingerprint": observation.fingerprint,
        "comparison": observation.comparison.value,
        "content_retained": False,
        "author": "unknown",
        "intent": "unknown",
    }


if __name__ == "__main__":
    raise SystemExit(main())
