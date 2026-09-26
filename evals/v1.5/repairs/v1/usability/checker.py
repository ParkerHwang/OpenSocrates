"""Deterministic native-state/artifact assertions; no semantic model judging."""


def check(stage, task_id, fixture, state, artifact, operations, initial_record_id):
    records = state.get("records") or []
    checkpoints = [
        r
        for r in records
        if r.get("kind") == "checkpoint" and r.get("scope", {}).get("task_id") == task_id
    ]
    latest = max(
        checkpoints, key=lambda r: r.get("payload", {}).get("checkpoint_version", 0), default={}
    )
    actions = latest.get("payload", {}).get("completed_actions", [])
    version = latest.get("payload", {}).get("checkpoint_version", 0)
    expected = {
        "schema": "venue-plan/1",
        "attendees": 48,
        "step_free_required": True,
        "venue": "Cedar" if stage == 1 else "Bay",
        "capacity": 64 if stage == 1 else 80,
        "step_free": True,
        "source_revision": stage,
        "booking_status": "unbooked",
    }
    reference = state.get("recall", {}).get("result", {}).get("checkpoint_reference")
    # The unchanged adapter audits target IDs; successful inspect is observable,
    # while actual prompt/schema/task semantics require integrator review.
    inspect_ids = {
        o.get("target_record_id")
        for o in operations
        if o.get("operation") == "inspect" and o.get("status") == "ok"
    }
    successful = [o for o in operations if o.get("status") == "ok"]
    return {
        "checkpoint_nonempty": len(actions) >= 2,
        "checkpoint_version_at_least_two": version >= 2,
        "same_task": bool(latest) and latest.get("scope", {}).get("task_id") == task_id,
        "caller_action_shape_support": bool(actions)
        and all(
            isinstance(a, dict)
            and isinstance(a.get("action"), str)
            and bool(a["action"].strip())
            and a.get("execution_state") == "completed"
            and a.get("support") == "agent_reported"
            and isinstance(a.get("source_refs"), list)
            for a in actions
        ),
        "accepted_intent_persists": any(
            r.get("record_id") == initial_record_id
            and r.get("lifecycle") == "accepted"
            and r.get("summary") == fixture["accepted_intent"]
            for r in records
        ),
        "dependent_artifact_exact": artifact == expected
        and isinstance(artifact, dict)
        and all(type(artifact.get(key)) is type(value) for key, value in expected.items()),
        "native_checkpoint_writes_observed": sum(
            o.get("operation") == "checkpoint" for o in successful
        )
        >= 2
        if stage == 1
        else None,
        "fresh_recall_and_reference_inspection": any(
            o.get("operation") == "recall" for o in successful
        )
        and bool(reference)
        and reference in inspect_ids
        if stage == 2
        else None,
        "failed_tool_actions": sum(
            o.get("status") != "ok" or o.get("exit_code") != 0 for o in operations
        ),
        "checkpoint_record_id": latest.get("record_id"),
        "checkpoint_version": version,
        "limitations": "Public synthetic operation receipts and saved state; inspect order and source-read/validation commands require integrator review. No backend echo or billing proof.",
    }
