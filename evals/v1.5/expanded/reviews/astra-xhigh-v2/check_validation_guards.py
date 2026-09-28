"""Reject in-memory corruptions of a retained assessment without changing it."""

from copy import deepcopy

from validate_review import validate
from verify_review import HERE, ROOT, read


def main() -> None:
    manifest = read(HERE / "manifest.json")
    assignment = manifest["assignment_order"][0]
    identifier = assignment["assignment_id"]
    original = read(HERE / "assessments" / f"{identifier}-evidence.json")
    first = read(HERE / "assessments" / f"{identifier}-first_pass.json")
    inputs = {
        key: {
            packet["packet_id"]: {
                "content": read(ROOT / packet[f"{prefix}_path"]),
                "sha256": packet[f"{prefix}_sha256"],
            }
            for packet in manifest["packets"]
        }
        for key, prefix in (("packets", "first_pass"), ("deterministic", "evidence"))
    }
    arguments = {
        **inputs,
        "schema": read(HERE / "response.schema.json"),
        "assignment": assignment,
        "rubric": manifest["rubric"],
        "phase": "evidence",
        "locked": first,
    }
    validate(original, **arguments)
    mutations = [
        ("model substitution", ("assessor", "configured_model"), "gpt-6-sol"),
        ("effort substitution", ("assessor", "configured_effort"), "medium"),
        ("human substitution", ("assessor", "human_assessor"), True),
        ("fabricated backend echo", ("assessor", "backend_model_echo"), "gpt-6-astra"),
        ("altered packet bytes", ("packets", 0, "packet_sha256"), "0" * 64),
        ("missing packet", ("packets",), original["packets"][1:]),
        (
            "rewritten initial ground",
            ("packets", 0, "first_pass_scores", "communication", "reason"),
            "Mutation guard: this text was never in the locked judgment.",
        ),
        (
            "boolean rating",
            ("packets", 0, "post_evidence_scores", "task_outcome", "score"),
            True,
        ),
        (
            "invented citation",
            ("packets", 0, "post_evidence_scores", "task_outcome", "evidence"),
            ["packet:/nonexistent_mutation_probe"],
        ),
        (
            "wrong evidence identity",
            ("packets", 0, "deterministic_evidence_status", "sha256"),
            "0" * 64,
        ),
    ]
    for label, path, replacement in mutations:
        changed = deepcopy(original)
        target = changed
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            validate(changed, **arguments)
        except ValueError:
            continue
        raise AssertionError(f"Validator accepted {label}")
    print(f"Review validation guards: PASS ({len(mutations)} rejected mutations)")


if __name__ == "__main__":
    main()
