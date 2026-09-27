"""Build synthetic requests; this file never invokes a model."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, identity, path):
    return {"id": identity, "path": path, "sha256": digest(root / path)}


def unit(identity, domain, role, paths, sources, dependencies, objective, requirement,
         oracle, argv, specialists=(), seed=None, kind="judgment"):
    return {
        "unit_id": identity, "domain": domain, "task_kind": kind, "role": role,
        "objective": objective, "owned_paths": paths, "dependencies": dependencies,
        "source_ids": sources, "requirement_ids": [requirement],
        "specialists": list(specialists),
        "obligations": [{"id": identity + "-acceptance", "requirement_id": requirement,
                         "description": objective, "required": True}],
        "checks": [{"check_id": oracle, "argv": argv,
                    "obligation_ids": [identity + "-acceptance"],
                    "authorization_reference": "fixture:approved-checks",
                    "expected_exit_code": 0}],
        "seed": seed,
    }


def envelope(args, identity, constraints, sources, units, handoff):
    return {
        "schema": "opensocrates.orchestration.request/1.0.0", "operation": "run",
        "run_id": str(uuid4()), "task_id": str(uuid4()), "revision": 1,
        "authorization": {"reference": "fixture:orchestration-qualification",
                          "attribution": "operator_declared"},
        "model": {"name": "gpt-6-astra", "effort": "max"}, "locale": "en",
        "objective": "Qualify the fixed " + identity + " workflow on disposable synthetic text artifacts.",
        "constraints": constraints,
        "permissions": ["Read only declared source inputs and qualified dependencies. Produce only the explicitly owned candidate text artifacts through the structured result."],
        "prohibitions": ["No external effects, project enrollment, global settings, credential access, deployment, publication, agent redelegation or model substitution.",
                         "No private reasoning, raw transcript or author self-assessment in an acceptance result."],
        "source_root": str(args.fixtures.resolve()), "sources": sources,
        "candidate_root": str((args.output / "candidates" / identity).resolve()),
        "client_path": str(args.client), "repair_limit": 1, "memory": None,
        "handoff": handoff,
        "required_artifacts": [path for item in units for path in item["owned_paths"]],
        "units": units,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "candidates").mkdir(exist_ok=True)
    py = str(args.python.resolve())
    f = args.fixtures
    long_constraint = (f / "fixtures/accepted_constraint.txt").read_text()
    constraints = [{"id": "cost-contract", "text": (f / "fixtures/design_contract.md").read_text()}]
    software_sources = [source(f, i, p) for i, p in [
        ("design-contract", "fixtures/design_contract.md"),
        ("design-oracle", "oracles/check_design.py"),
        ("cost-oracle", "oracles/check_cost.py"),
        ("cost-cases", "fixtures/cost_cases.json"),
    ]]
    design = unit("software-design", "software", "design", ["design.json"],
                  ["design-contract", "design-oracle"], [],
                  "Produce design.json defining the exact interface and all supplied selection/state rules. Preserve the stipulated public JSON structure in the contract.",
                  "cost-contract", "design-oracle",
                  [py, "-B", "inputs/design-oracle/check_design.py", "design.json"],
                  ["contracts"])
    software = unit("software-production", "software", "production", ["pricing.py"],
                    ["design-contract", "cost-oracle", "cost-cases"], ["software-design"],
                    "Own pricing.py and implement the qualified effective_cost contract whenever repair is assigned. Preserve null, missing, zero and input immutability. The supplied initial candidate has a synthetic fixture author; independent review and execution verification are assigned to other roles by the runtime.",
                    "cost-contract", "cost-oracle",
                    [py, "-B", "inputs/cost-oracle/check_cost.py", "pricing.py", "inputs/cost-cases/cost_cases.json"],
                    ["contracts"], {"author": "synthetic_fixture", "files": [
                        {"path": "pricing.py", "content": (f / "fixtures/defective_pricing.py").read_text()}]})
    requests = {"software": envelope(args, "software", constraints, software_sources,
                                    [design, software], ["No product memory is enrolled; the declared current contract supplies continuity for this fixture."])}
    office_sources = [source(f, i, p) for i, p in [
        ("office-contract", "fixtures/data_document_contract.md"),
        ("country-source", "fixtures/country_effects.json"),
        ("calculation-oracle", "oracles/check_calculation.py"),
        ("report-oracle", "oracles/check_report.py"),
    ]]
    data = unit("data-production", "data", "production", ["calculation.json"],
                ["office-contract", "country-source", "calculation-oracle"], [],
                "Produce calculation.json from the exact country source: per-country products then additive total, with source hash. Follow the supplied data contract.",
                "office-contract", "calculation-oracle",
                [py, "-B", "inputs/calculation-oracle/check_calculation.py", "calculation.json", "inputs/country-source/country_effects.json"])
    document = unit("document-production", "document", "production", ["report.md"],
                    ["office-contract", "country-source", "report-oracle"], ["data-production"],
                    "Produce report.md with reconciled table and narrative from the qualified calculation, including exact current source/calculation hashes and the required labels. State that total is the sum of country products.",
                    "office-contract", "report-oracle",
                    [py, "-B", "inputs/report-oracle/check_report.py", "report.md", "calculation.json", "inputs/country-source/country_effects.json"])
    requests["office"] = envelope(args, "office",
                                  [{"id": "office-contract", "text": (f / "fixtures/data_document_contract.md").read_text()}],
                                  office_sources, [data, document],
                                  ["Use the current source and accepted contract. No historical model evaluation or self-rating is part of this assignment."])
    # Continuation consumes the exact qualified software source after that workflow
    # completes; its version-bound request is frozen separately before its calls.
    continuation = {
        "status": "awaiting_qualified_software_source",
        "required_long_constraint": long_constraint,
        "expected_behavior": "Preserve effective_cost contract and add a module docstring only.",
        "memory_mode": "explicit_unavailable_fallback",
        "oracle": [py, "-B", "inputs/cost-oracle/check_cost.py", "pricing.py", "inputs/cost-cases/cost_cases.json"],
    }
    for identity, request in requests.items():
        destination = args.output / (identity + ".request.json")
        destination.write_text(json.dumps(request, indent=2) + "\n")
    (args.output / "continuation.draft.json").write_text(json.dumps(continuation, indent=2) + "\n")
    print("Prepared synthetic wire drafts only; no model calls executed.")


if __name__ == "__main__":
    main()
