"""Check this development package; this is not a product/schema-quality test."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path


def validate() -> dict[str, object]:
    package = Path(__file__).resolve().parent
    root = package.parents[1]
    documents = sorted(package.rglob("*.md"))
    examples = sorted((package / "examples").glob("*.json"))
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    for path in documents:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(package).as_posix()
        require(text.endswith("\n"), f"{name}: missing final newline")
        require(not re.search(r"[\uac00-\ud7af\u3400-\u9fff]", text), f"{name}: language script")
        fences = sum(line.startswith("```") for line in text.splitlines())
        require(fences % 2 == 0, f"{name}: unbalanced code fences")
        require(all(line.rstrip() == line for line in text.splitlines()), f"{name}: whitespace")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("http:", "https:", "#")):
                continue
            require((path.parent / target.split("#")[0]).resolve().exists(),
                    f"{name}: missing link {target}")

    parsed: dict[str, dict[str, object]] = {}
    for path in examples:
        value = json.loads(path.read_text(encoding="utf-8"))
        parsed[path.name] = value
        require(value.get("schema", "").startswith("opensocrates.project-memory."),
                f"{path.name}: schema family")
        for key in ("project_id", "workspace_id", "task_id", "record_id", "snapshot_id",
                    "pack_id", "request_id"):
            if value.get(key):
                try:
                    uuid.UUID(value[key])
                except (ValueError, TypeError, AttributeError):
                    errors.append(f"{path.name}: invalid {key}")

    observation = parsed["observation-record.json"]
    pack = parsed["context-pack.json"]
    request = parsed["checkpoint-request.json"]
    payload = request["payload"]
    reference = observation["source_refs"][0]
    evidence = pack["evidence"][0]
    require(observation["project_id"] == pack["project_id"] == request["project_id"],
            "cross-example project identity")
    require(observation["snapshot_id"] == pack["snapshot_id"] == payload["snapshot_id"],
            "cross-example snapshot identity")
    require(evidence["record_id"] == observation["record_id"], "record reference")
    require(evidence["digest"] == reference["digest"], "source digest reference")
    require(evidence["locator"] == reference["locator"], "usable citation locator")
    require(pack["application"] == "unverified" and pack["delivery"] == "emitted",
            "delivery/application distinction")
    require(all(action["support"] in {"agent_reported", "inferred", "imported"}
                for action in payload["completed_actions"]),
            "caller checkpoint actions cannot claim native observation")
    require(all(action["support"] == "agent_reported"
                for action in payload["completed_actions"]),
            "example source inspection and test remain agent reported")
    require("checkpoint_version" not in payload and payload["expected_checkpoint_version"] == 0,
            "new checkpoint version must be server assigned")
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", reference["digest"])), "digest shape")
    require("def main(" in (root / "src/opensocrates/cli/main.py").read_text(),
            "baseline CLI dispatcher anchor")

    verification = (package / "06-verification-and-evaluation.md").read_text()
    cases = [("G", 5), ("A", 8), ("U", 6), ("T", 26), ("C", 6), ("H", 3), ("P", 2)]
    for prefix, count in cases:
        for number in range(1, count + 1):
            require(f"| {prefix}{number:02d} |" in verification,
                    f"missing acceptance case {prefix}{number:02d}")
    require("paired second-session replay" in verification, "isolated memory-effect replay")
    for study in range(1, 6):
        require(f"## EVAL-{study:02d}:" in verification, f"missing evaluation lane {study}")
    kickoff = (package / "08-implementation-kickoff.md").read_text()
    require("11-adaptive-assistance-and-collaboration.md" in kickoff,
            "kickoff includes adaptive behavior contract")
    require("pitch-rehearsals" not in kickoff, "kickoff is independent of pitch history")
    require(pack["workspace_id"] == request["workspace_id"] == observation["scope"]["workspace_id"],
            "cross-example workspace identity")
    require(pack["workspace_kind"] == "git_worktree", "example workspace discriminator")
    return {
        "status": "pass" if not errors else "fail",
        "markdown_documents": len(documents),
        "json_examples": len(examples),
        "acceptance_cases": sum(count for _, count in cases),
        "checks": ["local link targets", "balanced fences", "whitespace",
                   "English-language script scan", "JSON parsing", "UUID and digest shapes",
                   "cross-example identities and evidence states", "source dispatch anchor",
                   "acceptance case coverage", "five evaluation lanes", "evaluation replay contract",
                   "self-contained kickoff", "workspace identity contract"],
        "errors": errors,
        "limitations": ["Not production JSON Schema validation",
                        "Not implementation or model-quality testing",
                        "External URLs are not fetched by this check"],
    }


if __name__ == "__main__":
    report = validate()
    print(json.dumps(report, indent=2))
    raise SystemExit(report["status"] != "pass")
