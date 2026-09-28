"""Unblinded, post-call O-v2 representation diagnostic; never rewrites outcomes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / "RULES.json").read_text())
MISSING = object()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def equal(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def strict_json_equal(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(strict_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_json_equal(x, y) for x, y in zip(a, b))
    return a == b


def escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def pointer(value: Any, path: str) -> Any:
    if not path.startswith("/"):
        raise ValueError("pointer_not_absolute")
    for raw in path[1:].split("/"):
        segment = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", segment):
                raise ValueError("array_segment_invalid")
            value = value[int(segment)]
        elif isinstance(value, dict):
            value = value[segment]
        else:
            raise ValueError("pointer_scalar_parent")
    return value


def aliases(row: dict, names: list[str], prefix: str) -> tuple[Any, str]:
    found = [(row[name], prefix + "/" + escape(name)) for name in names if name in row]
    if not found:
        raise KeyError("missing_alias:" + prefix + ":" + ",".join(names))
    if any(not equal(found[0][0], value) for value, _ in found[1:]):
        raise ValueError("conflicting_alias:" + prefix + ":" + ",".join(names))
    return found[0]


class FactBook:
    def __init__(self) -> None:
        self.facts: list[dict] = []
        self.errors: list[str] = []
        self.pointer_to_fact: dict[str, set[str]] = {}

    def add(self, fact_id: str, expected: Any, actual: Any = MISSING,
            source_pointer: str | None = None, set_value: bool = False) -> None:
        if actual is MISSING:
            passed = False
            actual_sha = None
        elif set_value:
            passed = isinstance(actual, list) and len(actual) == len(set(actual)) and set(actual) == set(expected)
            actual_sha = digest(actual)
        else:
            passed = equal(actual, expected)
            actual_sha = digest(actual)
        self.facts.append({"id": fact_id, "passed": passed, "candidate_pointer": source_pointer,
                           "candidate_value_sha256": actual_sha})
        if source_pointer:
            self.pointer_to_fact.setdefault(source_pointer, set()).add(fact_id)

    def missing(self, fact_id: str, expected: Any, exc: Exception) -> None:
        self.add(fact_id, expected)
        self.errors.append(type(exc).__name__ + ":" + str(exc)[:120])


def mapped(book: FactBook, fact_id: str, expected: Any, row: dict, names: list[str], prefix: str,
           set_value: bool = False) -> None:
    try:
        actual, path = aliases(row, names, prefix)
        book.add(fact_id, expected, actual, path, set_value=set_value)
    except (KeyError, ValueError, TypeError) as exc:
        book.missing(fact_id, expected, exc)


def object_at(value: dict, name: str) -> dict:
    item = value[name]
    if not isinstance(item, dict):
        raise ValueError("section_not_object:" + name)
    return item


def section_row(book: FactBook, metrics: dict, expected: dict, section: str,
                fields: dict[str, list[str]]) -> None:
    try:
        row = object_at(metrics, section)
    except (KeyError, ValueError) as exc:
        book.errors.append(type(exc).__name__ + ":" + str(exc))
        row = {}
    for field, names in fields.items():
        mapped(book, f"/{section}/{escape(field)}", expected[section][field], row, names,
               "/" + section)


def capacity_rows(metrics: dict, expected: dict, book: FactBook) -> None:
    try:
        raw = metrics["capacity"]
        if isinstance(raw, dict):
            rows = {}
            for facility, months in raw.items():
                if not isinstance(months, dict):
                    raise ValueError("capacity_month_map_missing")
                for month, value in months.items():
                    if not isinstance(value, dict) or value.get("facility", facility) != facility or value.get("month", month) != month:
                        raise ValueError("capacity_map_identity_conflict")
                    rows[(facility, month)] = value, "/capacity/" + escape(facility) + "/" + escape(month)
        elif isinstance(raw, list):
            rows = {}
            for index, row in enumerate(raw):
                if not isinstance(row, dict) or not isinstance(row.get("facility"), str) or not isinstance(row.get("month"), str):
                    raise ValueError("capacity_row_identity_missing")
                key = (row["facility"], row["month"])
                if key in rows:
                    raise ValueError("capacity_duplicate_identity")
                rows[key] = row, f"/capacity/{index}"
        else:
            raise ValueError("capacity_shape_unmapped")
        expected_ids = {(facility, month) for facility, months in expected["capacity"].items()
                        for month in months}
        if set(rows) != expected_ids or len(rows) != 16:
            raise ValueError("capacity_identity_set_mismatch")
        book.add("/capacity/@identity_set", sorted(expected_ids), sorted(rows))
    except (KeyError, ValueError, TypeError) as exc:
        book.missing("/capacity/@identity_set", sorted((f, m) for f, months in expected["capacity"].items() for m in months), exc)
        rows = {}
    for facility, months in expected["capacity"].items():
        for month, facts in months.items():
            row, prefix = rows.get((facility, month), ({}, "/capacity"))
            for field, names in RULES["metrics"]["capacity_aliases"].items():
                mapped(book, f"/capacity/{escape(facility)}/{escape(month)}/{field}",
                       facts[field], row, names, prefix)


def portfolio_rows(metrics: dict, expected: dict, book: FactBook) -> None:
    try:
        raw = metrics["portfolios"]
        if isinstance(raw, dict):
            rows = {}
            for name, value in raw.items():
                if not isinstance(value, dict) or value.get("id", name) != name or value.get("name", name) != name:
                    raise ValueError("portfolio_map_identity_conflict")
                rows[name] = value, "/portfolios/" + escape(name)
        elif isinstance(raw, list):
            rows = {}
            for index, row in enumerate(raw):
                if not isinstance(row, dict):
                    raise ValueError("portfolio_row_not_object")
                name, _ = aliases(row, ["id", "name"], f"/portfolios/{index}")
                if not isinstance(name, str) or name in rows:
                    raise ValueError("portfolio_duplicate_or_invalid_identity")
                rows[name] = row, f"/portfolios/{index}"
        else:
            raise ValueError("portfolios_shape_unmapped")
        names = set(expected["portfolios"])
        if set(rows) != names or len(rows) != 10:
            raise ValueError("portfolio_identity_set_mismatch")
        book.add("/portfolios/@identity_set", sorted(names), sorted(rows))
    except (KeyError, ValueError, TypeError) as exc:
        book.missing("/portfolios/@identity_set", sorted(expected["portfolios"]), exc)
        rows = {}
    for name, facts in expected["portfolios"].items():
        row, prefix = rows.get(name, ({}, "/portfolios"))
        for field, names in RULES["metrics"]["portfolios_aliases"].items():
            expected_field = "fixed_shared_cents" if field == "fixed_shared_cents" else field
            mapped(book, f"/portfolios/{escape(name)}/{field}", facts[expected_field], row, names, prefix)
        try:
            variable, _ = aliases(row, ["known_variable_cents"], prefix)
            fixed, _ = aliases(row, ["fixed_shared_cents", "fixed_plus_shared_cents"], prefix)
            total, _ = aliases(row, ["period_cost_lower_bound_cents"], prefix)
            book.add(f"/portfolios/{escape(name)}/@cost_sum", True,
                     type(variable) is int and type(fixed) is int and type(total) is int and variable + fixed == total)
        except (KeyError, ValueError) as exc:
            book.missing(f"/portfolios/{escape(name)}/@cost_sum", True, exc)


def sensitivity(metrics: dict, expected: dict, book: FactBook) -> None:
    raw = metrics.get("sensitivity")
    if not isinstance(raw, dict):
        raw = {}
        book.errors.append("sensitivity_section_missing_or_not_object")
    details = [
        ("baseline_known_part_cents", "sensitivity_relay_objects", "sensitivity_relay_baseline_aliases"),
        ("relay_plus_10_known_part_cents", "sensitivity_relay_objects", "sensitivity_relay_scenario_aliases"),
        ("west_june_available_baseline", "sensitivity_west_objects", "sensitivity_west_baseline_aliases"),
        ("west_june_available_after_15pct", "sensitivity_west_objects", "sensitivity_west_scenario_aliases"),
    ]
    mr = RULES["metrics"]
    for fact, object_key, alias_key in details:
        options = []
        if fact in raw:
            options.append((raw[fact], "/sensitivity/" + fact))
        for parent in mr[object_key]:
            if isinstance(raw.get(parent), dict):
                for alias in mr[alias_key]:
                    if alias in raw[parent]:
                        options.append((raw[parent][alias], "/sensitivity/" + parent + "/" + alias))
        try:
            if not options:
                raise KeyError("sensitivity_fact_missing:" + fact)
            if any(not equal(options[0][0], value) for value, _ in options[1:]):
                raise ValueError("sensitivity_alias_conflict:" + fact)
            book.add("/sensitivity/" + fact, expected["sensitivity"][fact], *options[0])
        except (KeyError, ValueError) as exc:
            book.missing("/sensitivity/" + fact, expected["sensitivity"][fact], exc)
    for fact in mr["sensitivity_changed_sets"]:
        options = []
        if isinstance(raw.get(fact), list):
            options.append((raw[fact], "/sensitivity/" + fact))
        for parent in mr["sensitivity_west_objects"]:
            obj = raw.get(parent)
            if isinstance(obj, dict) and isinstance(obj.get(fact), list):
                options.append((obj[fact], "/sensitivity/" + parent + "/" + fact))
            if not isinstance(obj, dict):
                continue
            for source_name in ("portfolios", "changed_portfolios"):
                portfolio_changes = obj.get(source_name)
                if not isinstance(portfolio_changes, (dict, list)):
                    continue
                if isinstance(portfolio_changes, list):
                    mapped_changes = {}
                    for row in portfolio_changes:
                        if not isinstance(row, dict):
                            book.errors.append("sensitivity_changed_portfolio_row_invalid")
                            continue
                        try:
                            name, _ = aliases(row, ["id", "name"], "/sensitivity/" + parent + "/" + source_name)
                        except (KeyError, ValueError) as exc:
                            book.errors.append(type(exc).__name__ + ":" + str(exc)[:120])
                            continue
                        if not isinstance(name, str) or name in mapped_changes:
                            book.errors.append("sensitivity_changed_portfolio_duplicate_identity")
                            continue
                        mapped_changes[name] = row
                    portfolio_changes = mapped_changes
                declared = set(expected["portfolios"])
                correct_identity_set = (set(portfolio_changes) == declared if source_name == "portfolios"
                                        else set(portfolio_changes) <= declared)
                if not correct_identity_set:
                    book.errors.append("sensitivity_changed_portfolio_identity_mismatch")
                    continue
                key = "capacity_feasible" if fact == "changed_capacity_feasibility" else "decision_eligible"
                baseline, scenario = "baseline_" + key, "scenario_" + key
                if not all(isinstance(row, dict) and type(row.get(baseline)) is bool and type(row.get(scenario)) is bool
                           for row in portfolio_changes.values()):
                    book.errors.append("sensitivity_changed_portfolio_boolean_missing")
                    continue
                if source_name == "changed_portfolios" and not all(
                    row.get("baseline_capacity_feasible") != row.get("scenario_capacity_feasible")
                    or row.get("baseline_decision_eligible") != row.get("scenario_decision_eligible")
                    for row in portfolio_changes.values()
                ):
                    book.errors.append("sensitivity_changed_portfolio_unchanged_row")
                    continue
                changed = [name for name, row in portfolio_changes.items() if row[baseline] != row[scenario]]
                options.append((changed, "/sensitivity/" + parent + "/" + source_name))
        try:
            if not options:
                raise KeyError("sensitivity_changed_set_missing:" + fact)
            first = options[0][0]
            if any(not isinstance(v, list) or set(v) != set(first) or len(v) != len(first) for v, _ in options[1:]):
                raise ValueError("sensitivity_changed_set_conflict:" + fact)
            book.add("/sensitivity/" + fact, expected["sensitivity"][fact], first,
                     options[0][1], set_value=True)
        except (KeyError, ValueError, TypeError) as exc:
            book.missing("/sensitivity/" + fact, expected["sensitivity"][fact], exc)


def metric_facts(metrics: dict, expected: dict) -> FactBook:
    book = FactBook()
    for section in RULES["metrics"]["required_sections"]:
        if section not in metrics:
            book.errors.append("required_section_missing:" + section)
    section_row(book, metrics, expected, "selection", {k: [k] for k in RULES["metrics"]["selection_fields"]})
    try:
        raw = metrics["backlog"]
        if isinstance(raw, dict):
            value, path = aliases(raw, ["count"], "/backlog")
        else:
            value, path = raw, "/backlog"
        book.add("/backlog", expected["backlog"], value, path)
    except (KeyError, ValueError, TypeError) as exc:
        book.missing("/backlog", expected["backlog"], exc)
    section_row(book, metrics, expected, "sla", RULES["metrics"]["sla_aliases"])
    section_row(book, metrics, expected, "cost", RULES["metrics"]["cost_aliases"])
    capacity_rows(metrics, expected, book)
    portfolio_rows(metrics, expected, book)
    book.add("/eligible_ranking", expected["eligible_ranking"], metrics.get("eligible_ranking", MISSING),
             "/eligible_ranking" if "eligible_ranking" in metrics else None)
    sensitivity(metrics, expected, book)
    try:
        cost_credit = metrics["cost"]["unknown_credit_jobs"]
        sla_credit = metrics["sla"]["unknown_credit_jobs"]
        if not equal(cost_credit, sla_credit):
            book.errors.append("repeated_unknown_credit_conflict")
    except KeyError:
        pass
    return book


def source_register(register: Any, expected_register: list[dict]) -> dict:
    errors: list[str] = []
    wanted = {row["id"]: (row["path"], row["sha256"]) for row in expected_register}
    seen: dict[str, tuple[str, str]] = {}
    if not isinstance(register, list):
        return {"passed": False, "errors": ["source_register_not_array"], "checked_ids": 0}
    for row in register:
        if not isinstance(row, dict) or any(k not in row for k in ("id", "path", "sha256")):
            errors.append("source_register_row_missing_required_field")
            continue
        ident, path, raw = row["id"], row["path"], row["sha256"]
        if not all(isinstance(x, str) for x in (ident, path, raw)):
            errors.append("source_register_field_type")
            continue
        if ident in seen:
            errors.append("source_register_duplicate_id")
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", raw):
            errors.append("source_register_digest_format")
            continue
        seen[ident] = path, raw
    if set(seen) != set(wanted):
        errors.append("source_register_id_set_mismatch")
    for ident in set(seen) & set(wanted):
        if seen[ident] != wanted[ident]:
            errors.append("source_register_path_or_digest_mismatch")
    return {"passed": not errors, "errors": sorted(set(errors)), "checked_ids": len(seen)}


def combined_source_register(metrics: dict, sources: Any, expected_register: list[dict]) -> dict:
    result = source_register(sources, expected_register)
    if "sources" in metrics:
        embedded = source_register(metrics["sources"], expected_register)
        result["embedded_register_present"] = True
        result["embedded_register_passed"] = embedded["passed"]
        if not embedded["passed"]:
            result["passed"] = False
            result["errors"] = sorted(set(result["errors"] + [
                "embedded_source_register_conflicts_with_frozen_sources"] + embedded["errors"]))
    else:
        result["embedded_register_present"] = False
        result["embedded_register_passed"] = None
    return result


def source_requirements(fact: str) -> set[str]:
    events = {"orders-v2", "events-initial-v2", "events-corrections-v2"}
    if fact == "/selection/orders":
        return {"orders-v2"}
    if fact == "/selection/future_ignored":
        return {"events-corrections-v2", "manifest-v2"}
    if fact == "/selection/corrected":
        return {"events-initial-v2", "events-corrections-v2"}
    if fact.startswith("/selection/") or fact == "/backlog":
        return events
    if fact.startswith("/sla/"):
        if fact.endswith("/eligible") or fact.endswith("/zero_charge_completed_jobs"):
            return events
        return events | {"sla-v2"}
    if fact.startswith("/cost/known_part") or fact.startswith("/cost/unknown_part"):
        if fact.endswith("/unknown_part_lines"):
            return {"events-initial-v2", "events-corrections-v2", "rates-v2"}
        return events | {"rates-v2"}
    if fact.startswith("/cost/known_labor") or fact.startswith("/cost/unknown_labor"):
        if fact.endswith("/unknown_labor_jobs"):
            return events
        return events | {"capacity-v2"}
    if fact.startswith("/cost/known_credit"):
        return events | {"sla-v2"}
    if fact.startswith("/capacity/"):
        if fact.endswith("/available_minutes"):
            return {"capacity-v2"}
        return events | {"capacity-v2"}
    if fact.startswith("/portfolios/"):
        if fact.endswith("/fixed_shared_cents"):
            return {"capacity-v2", "shared-v2", "portfolios-v2", "manifest-v2"}
        if fact.endswith("/period_cost_lower_bound_cents"):
            return events | {"sla-v2", "rates-v2", "capacity-v2", "shared-v2", "portfolios-v2", "manifest-v2"}
        if fact.endswith("/decision_eligible"):
            return events | {"capacity-v2", "portfolios-v2", "manifest-v2"}
        if fact.endswith("/capacity_feasible"):
            return events | {"capacity-v2", "portfolios-v2"}
        return events | {"portfolios-v2"}
    if fact.startswith("/sensitivity/relay") or fact == "/sensitivity/baseline_known_part_cents":
        return events | {"rates-v2"}
    if fact.startswith("/sensitivity/west"):
        return {"capacity-v2"}
    if fact == "/sensitivity/changed_capacity_feasibility":
        return events | {"capacity-v2", "portfolios-v2"}
    if fact == "/sensitivity/changed_decision_eligibility":
        return events | {"capacity-v2", "portfolios-v2", "manifest-v2"}
    return set()


def required_memo_facts(expected: dict) -> set[str]:
    required = {"/selection/" + key for key in ("orders", "corrected", "future_ignored", "cancelled", "completed")}
    required.add("/backlog")
    required |= {"/sla/" + key for key in ("eligible", "on_time", "attainment", "unknown_credit_jobs", "zero_charge_completed_jobs")}
    required |= {"/cost/" + key for key in ("known_part_cents", "unknown_part_lines", "unknown_part_jobs", "known_labor_cents", "unknown_labor_jobs", "known_credit_cents")}
    required |= {"/sensitivity/" + key for key in ("relay_plus_10_known_part_cents", "west_june_available_after_15pct", "changed_decision_eligibility")}
    for option in expected["portfolios"]:
        required |= {f"/portfolios/{escape(option)}/{field}" for field in (
            "covered_completed_jobs", "coverage_ratio", "period_cost_lower_bound_cents",
            "capacity_feasible", "decision_eligible")}
    return required


def memo_value_matches(raw: str, actual: Any) -> bool:
    raw = raw.strip()
    if isinstance(actual, str) and raw == actual:
        return True
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return isinstance(actual, str) and raw == actual
    return equal(parsed, actual)


def memo_result(memo: str | None, metrics: dict, book: FactBook,
                expected: dict, expected_register: list[dict]) -> dict:
    if memo is None:
        return {"passed": False, "reason": "memo_absent", "valid_rows": 0,
                "invalid_rows": 0, "missing_fact_count": len(required_memo_facts(expected))}
    known_sources = {row["id"] for row in expected_register}
    facts = {row["id"]: row for row in book.facts}
    found: set[str] = set()
    valid_rows = invalid_rows = 0
    for path, raw_value, raw_refs in re.findall(r"(?m)^\|\s*(/[^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", memo):
        path = path.strip()
        try:
            candidate_value = pointer(metrics, path)
            citations = {item.strip() for item in raw_refs.split(",") if item.strip()}
            fact_ids = book.pointer_to_fact.get(path, set())
            if not citations or not citations <= known_sources or not memo_value_matches(raw_value, candidate_value):
                raise ValueError("bad_citation_or_value")
            if any(not source_requirements(fact_id) <= citations for fact_id in fact_ids):
                raise ValueError("missing_relevant_citation")
            found.update(fact_id for fact_id in fact_ids if facts[fact_id]["passed"])
            valid_rows += 1
        except (KeyError, IndexError, TypeError, ValueError):
            invalid_rows += 1
    required = required_memo_facts(expected)
    recommendation = re.search(r"(?mi)^Recommendation:[ \t]*([^\r\n]*)$", memo)
    criterion = re.search(r"(?mi)^Criterion:[ \t]*([^\r\n]*)$", memo)
    uncertainty = re.search(r"(?mi)^Uncertainty:[ \t]*([^\r\n]*)$", memo)
    choice = recommendation.group(1).strip().lower() if recommendation else None
    eligible = bool(choice in expected["portfolios"] and facts.get(f"/portfolios/{escape(choice)}/decision_eligible", {}).get("passed")
                    and expected["portfolios"][choice]["decision_eligible"])
    lower = memo.lower()
    narrative = bool(eligible and criterion and criterion.group(1).strip() and uncertainty and uncertainty.group(1).strip()
                     and re.search(r"operating plan|action plan|next steps|implementation plan", lower)
                     and "risk" in lower and "assumption" in lower)
    missing = sorted(required - found)
    return {"passed": invalid_rows == 0 and not missing and narrative,
            "valid_rows": valid_rows, "invalid_rows": invalid_rows,
            "required_fact_count": len(required), "missing_fact_count": len(missing),
            "missing_fact_ids": missing, "narrative_structure_passed": narrative,
            "semantic_narrative_quality_reviewed": False}


def program_result(copy: Path, receipt: dict, metrics: dict) -> dict:
    checks = {row["id"]: row["passed"] for row in receipt.get("structured", {}).get("checks", [])}
    if (not checks.get("v2_frozen_input_bytes") or not checks.get("v2_go_build_run")
            or not checks.get("v2_locked_source_integrity")):
        return {"status": "original_build_or_integrity_failure", "exact_generated_vs_committed": None}
    path = copy / ".eval-generated-metrics.json"
    if not path.is_file():
        return {"status": "generated_file_missing", "exact_generated_vs_committed": None}
    generated_hash = "sha256:" + sha(path.read_bytes())
    if receipt.get("after", {}).get(".eval-generated-metrics.json") != generated_hash:
        return {"status": "generated_hash_not_bound_to_original_receipt", "exact_generated_vs_committed": None}
    committed_path = copy / "metrics.json"
    if not committed_path.is_file() or receipt.get("before", {}).get("metrics.json") != "sha256:" + sha(committed_path.read_bytes()):
        return {"status": "committed_hash_not_bound_to_original_receipt", "exact_generated_vs_committed": None}
    try:
        generated = json.loads(path.read_text())
        committed = json.loads(committed_path.read_text())
    except json.JSONDecodeError:
        return {"status": "generated_or_committed_invalid_json", "exact_generated_vs_committed": None}
    exact = strict_json_equal(generated, committed) and strict_json_equal(committed, metrics)
    return {"status": "assessable", "exact_generated_vs_committed": exact,
            "generated_sha256": generated_hash,
            "committed_sha256": "sha256:" + sha(committed_path.read_bytes())}


def load_oracle(fixture: Path) -> tuple[dict, list[dict]]:
    path = fixture / "private/oracle.py"
    spec = importlib.util.spec_from_file_location("o_v2_reassessment_oracle", path)
    if spec is None or spec.loader is None:
        raise ValueError("oracle_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.expected(fixture / "public/data")


def generated_memo(metrics: dict, book: FactBook, expected: dict,
                   expected_register: list[dict], *, add_null: bool = False) -> str:
    lines = ["| JSON pointer | Value | Source IDs |", "| --- | --- | --- |"]
    by_id = {row["id"]: row for row in book.facts}
    for fact in sorted(required_memo_facts(expected)):
        path = by_id[fact]["candidate_pointer"]
        if path is None:
            raise ValueError("control_required_pointer_missing:" + fact)
        value = pointer(metrics, path)
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False)
        citations = sorted(source_requirements(fact) or {expected_register[0]["id"]})
        lines.append(f"| {path} | {encoded} | {', '.join(citations)} |")
    if add_null:
        lines.append("| /note_null | null | orders-v2 |")
    lines += ["Recommendation: east+north", "Criterion: eligible coverage and lower cost",
              "Uncertainty: unknown work and charge data remain", "Operating plan: confirm coverage.",
              "Risk and assumption register: frozen order mix is synthetic."]
    return "\n".join(lines) + "\n"


def reshaped_positive(expected: dict) -> dict:
    data = copy.deepcopy(expected)
    data["note_null"] = None
    data["capacity"] = [
        {"facility": facility, "month": month, "available_minutes": row["available_minutes"],
         "known_used_minutes": row["used_known_minutes"], "unknown_work_jobs": row["unknown_work_jobs"]}
        for facility, months in expected["capacity"].items() for month, row in months.items()
    ]
    data["portfolios"] = [
        {"id": name, "covered_jobs": row["covered_completed_jobs"],
         "covered_job_ratio": row["coverage_ratio"],
         "known_variable_cents": row["known_variable_cents"],
         "fixed_plus_shared_cents": row["fixed_shared_cents"],
         "period_cost_lower_bound_cents": row["period_cost_lower_bound_cents"],
         "capacity_feasible": row["capacity_feasible"],
         "decision_eligible": row["decision_eligible"]}
        for name, row in expected["portfolios"].items()
    ]
    data["cost"]["known_parts_cents"] = data["cost"].pop("known_part_cents")
    data["sla"]["zero_charge_eligible_jobs"] = data["sla"].pop("zero_charge_completed_jobs")
    sens = data["sensitivity"]
    capacity_changes = set(sens.pop("changed_capacity_feasibility"))
    eligibility_changes = set(sens.pop("changed_decision_eligibility"))
    relay_baseline = sens.pop("baseline_known_part_cents")
    relay_scenario = sens.pop("relay_plus_10_known_part_cents")
    west_baseline = sens.pop("west_june_available_baseline")
    west_scenario = sens.pop("west_june_available_after_15pct")
    sens["relay_price_increase"] = {"baseline_known_parts_cents": relay_baseline,
                                    "scenario_known_parts_cents": relay_scenario}
    sens["west_june_capacity"] = {
        "baseline_available_minutes": west_baseline,
        "scenario_available_minutes": west_scenario,
        "changed_capacity_feasibility": sorted(capacity_changes),
        "changed_decision_eligibility": sorted(eligibility_changes),
        "portfolios": {name: {
            "baseline_capacity_feasible": row["capacity_feasible"],
            "scenario_capacity_feasible": not row["capacity_feasible"] if name in capacity_changes else row["capacity_feasible"],
            "baseline_decision_eligible": row["decision_eligible"],
            "scenario_decision_eligible": not row["decision_eligible"] if name in eligibility_changes else row["decision_eligible"],
        } for name, row in expected["portfolios"].items()}
    }
    return data


def controls(fixture: Path) -> dict:
    expected, register = load_oracle(fixture)
    good = copy.deepcopy(expected)
    baseline = metric_facts(good, expected)
    assert all(x["passed"] for x in baseline.facts) and not baseline.errors
    assert source_register(register, register)["passed"]
    base_memo = generated_memo(good, baseline, expected, register)
    assert memo_result(base_memo, good, baseline, expected, register)["passed"]
    cases = {"known_good_map": True}
    eligible_row = next(line for line in base_memo.splitlines() if line.startswith("| /sla/eligible |"))
    assert "sla-v2" not in eligible_row
    assert memo_result(base_memo, good, baseline, expected, register)["passed"]
    cases["eligible_count_minimal_event_citation"] = True
    assert memo_result((fixture / "private/controls/good/memo.md").read_text(),
                       good, baseline, expected, register)["passed"]
    cases["frozen_good_memo"] = True

    shaped = reshaped_positive(expected)
    shaped_book = metric_facts(shaped, expected)
    assert all(x["passed"] for x in shaped_book.facts) and not shaped_book.errors
    shaped_memo = generated_memo(shaped, shaped_book, expected, register, add_null=True)
    assert memo_result(shaped_memo, shaped, shaped_book, expected, register)["passed"]
    cases["equivalent_list_alias_nested_null_array_pointer"] = True
    changed_list = copy.deepcopy(shaped)
    west = changed_list["sensitivity"]["west_june_capacity"]
    west.pop("changed_capacity_feasibility")
    west.pop("changed_decision_eligibility")
    portfolio_states = west.pop("portfolios")
    west["changed_portfolios"] = [dict(id=name, **state) for name, state in portfolio_states.items()
                                  if state["baseline_capacity_feasible"] != state["scenario_capacity_feasible"]
                                  or state["baseline_decision_eligible"] != state["scenario_decision_eligible"]]
    changed_book = metric_facts(changed_list, expected)
    assert all(x["passed"] for x in changed_book.facts) and not changed_book.errors
    cases["equivalent_changed_portfolios_list"] = True
    dual = copy.deepcopy(shaped)
    west_dual = dual["sensitivity"]["west_june_capacity"]
    unchanged = next(name for name in expected["portfolios"]
                     if name not in expected["sensitivity"]["changed_capacity_feasibility"])
    state = dict(west_dual["portfolios"][unchanged])
    state["scenario_capacity_feasible"] = not state["baseline_capacity_feasible"]
    west_dual["changed_portfolios"] = [dict(id=unchanged, **state)]
    assert not all(row["passed"] for row in metric_facts(dual, expected).facts)
    cases["contradictory_dual_sensitivity_rejected"] = True

    extra_register = [dict(row, bytes=123) for row in register]
    assert source_register(extra_register, register)["passed"]
    cases["additive_source_bytes"] = True
    embedded_good = copy.deepcopy(good)
    embedded_good["sources"] = extra_register
    assert combined_source_register(embedded_good, register, register)["passed"]
    embedded_bad = copy.deepcopy(embedded_good)
    embedded_bad["sources"][0]["sha256"] = "0" * 64
    assert not combined_source_register(embedded_bad, register, register)["passed"]
    cases["embedded_source_conflict_rejected"] = True
    for name, altered in (
        ("wrong_order_count", lambda x: x["selection"].__setitem__("orders", x["selection"]["orders"] + 1)),
        ("wrong_rounded_coverage", lambda x: x["portfolios"].__setitem__("east+north", dict(x["portfolios"]["east+north"], coverage_ratio="0.0000"))),
        ("missing_option", lambda x: x["portfolios"].pop("east+north")),
        ("missing_cost_field", lambda x: x["cost"].pop("known_labor_cents")),
    ):
        mutated = copy.deepcopy(good)
        altered(mutated)
        assert not all(row["passed"] for row in metric_facts(mutated, expected).facts)
        cases[name + "_rejected"] = True
    conflict = copy.deepcopy(shaped)
    conflict["cost"]["known_part_cents"] = conflict["cost"]["known_parts_cents"] + 1
    assert metric_facts(conflict, expected).errors
    cases["conflicting_alias_rejected"] = True
    map_identity_conflict = copy.deepcopy(good)
    map_identity_conflict["capacity"]["east"]["2026-03"]["facility"] = "west"
    assert metric_facts(map_identity_conflict, expected).errors
    cases["contradictory_map_identity_rejected"] = True
    duplicate = [*register, register[0]]
    assert not source_register(duplicate, register)["passed"]
    wrong_digest = copy.deepcopy(register)
    wrong_digest[0]["sha256"] = "0" * 64
    assert not source_register(wrong_digest, register)["passed"]
    prefixed_digest = copy.deepcopy(register)
    prefixed_digest[0]["sha256"] = "sha256:" + prefixed_digest[0]["sha256"]
    assert not source_register(prefixed_digest, register)["passed"]
    cases["duplicate_wrong_or_prefixed_source_rejected"] = True
    malformed_id = copy.deepcopy(register)
    malformed_id[0]["id"] = "private-sentinel-" + "x" * 1000
    redacted = source_register(malformed_id, register)
    assert not redacted["passed"] and "private-sentinel" not in json.dumps(redacted)
    cases["malformed_source_id_redacted"] = True
    for name, bad_memo in (
        ("bad_pointer", base_memo.replace("/selection/orders", "/selection/not_a_field", 1)),
        ("bad_value", base_memo.replace("/selection/orders | 160", "/selection/orders | 161", 1)),
        ("bad_citation", base_memo.replace("/selection/orders | 160 | orders-v2", "/selection/orders | 160 | bogus-v2", 1)),
    ):
        assert not memo_result(bad_memo, good, baseline, expected, register)["passed"]
        cases[name + "_rejected"] = True
    missing_known_source = base_memo.replace(
        "/selection/future_ignored | 10 | events-corrections-v2, manifest-v2",
        "/selection/future_ignored | 10 | events-corrections-v2", 1)
    assert missing_known_source != base_memo
    assert not memo_result(missing_known_source, good, baseline, expected, register)["passed"]
    cases["missing_required_known_citation_rejected"] = True
    with tempfile.TemporaryDirectory(prefix="o-v2-diagnostic-control-") as tmp:
        root = Path(tmp)
        (root / "metrics.json").write_text(json.dumps(good))
        (root / ".eval-generated-metrics.json").write_text(json.dumps(good))
        receipt = {"structured": {"checks": [
            {"id": "v2_frozen_input_bytes", "passed": True},
            {"id": "v2_go_build_run", "passed": True},
            {"id": "v2_locked_source_integrity", "passed": True}]},
            "before": {"metrics.json": "sha256:" + sha((root / "metrics.json").read_bytes())},
            "after": {".eval-generated-metrics.json": "sha256:" + sha((root / ".eval-generated-metrics.json").read_bytes())}}
        assert program_result(root, receipt, good)["exact_generated_vs_committed"] is True
        (root / ".eval-generated-metrics.json").write_text(json.dumps(shaped))
        receipt["after"][".eval-generated-metrics.json"] = "sha256:" + sha((root / ".eval-generated-metrics.json").read_bytes())
        assert program_result(root, receipt, good)["exact_generated_vs_committed"] is False
    cases["generated_vs_committed_divergence_rejected"] = True
    return {"schema": "opensocrates.go-ts.O-v2-diagnostic-controls/1", "model_calls": 0,
            "cases": cases, "passed": all(cases.values()), "case_count": len(cases)}


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def study_paths(study_root: Path) -> tuple[Path, Path, Path]:
    fixture = study_root / "evals/v1.5/orchestration/comparison-go-ts-v1/fixtures/o_service_network_v2"
    freeze = Path("/private/tmp/opensocrates-go-ts-o24-freeze-v2-20260928.json")
    original_index = Path("/private/tmp/opensocrates-go-ts-o24-results-20260928/external-qualification/index.json")
    return fixture, freeze, original_index


def require_disjoint_output(path: Path, study_root: Path, original_index: Path) -> None:
    resolved = path.resolve(strict=False)
    for protected in (study_root.resolve(), original_index.parent.parent.resolve()):
        if resolved == protected or protected in resolved.parents:
            raise ValueError("diagnostic_output_inside_frozen_study_or_original_results")


def native_variant_files(episode: Path, variant: str, scope: str) -> dict[str, str]:
    response = read_json(episode / "response.json")
    if variant == "single-v1":
        files = response.get("candidate_hashes") or {}
        if scope != "full" or not isinstance(files, dict):
            raise ValueError("single_variant_lineage_mismatch")
        return files
    pattern = re.fullmatch(r"O-analysis-v([0-9]+)(?:-O-document-v([0-9]+))?", variant)
    if not pattern:
        raise ValueError("orchestration_variant_label_invalid")
    units = {row["unit_id"]: row for row in response["units"]}
    if set(units) != {"O-analysis", "O-document"}:
        raise ValueError("native_unit_set_mismatch")
    a_version, d_version = int(pattern.group(1)), int(pattern.group(2)) if pattern.group(2) else None
    analysis = next((row for row in units["O-analysis"]["versions"] if row["version"] == a_version), None)
    if analysis is None or scope != ("full" if d_version is not None else "analysis"):
        raise ValueError("native_analysis_lineage_mismatch")
    files = {item["path"]: item["sha256"] for item in analysis["artifacts"]}
    if d_version is not None:
        if not analysis["qualified"]:
            raise ValueError("document_on_unqualified_analysis")
        document = next((row for row in units["O-document"]["versions"] if row["version"] == d_version), None)
        if document is None:
            raise ValueError("native_document_lineage_mismatch")
        if set(files) & {item["path"] for item in document["artifacts"]}:
            raise ValueError("native_overlap_in_assembled_versions")
        files.update({item["path"]: item["sha256"] for item in document["artifacts"]})
    return files


def preflight_inventory(original_index: Path, expected_cell_ids: set[str]) -> list[dict]:
    index = read_json(original_index)
    if index.get("scheduled_cells") != 24 or len(index.get("variants", [])) != 28:
        raise ValueError("original_variant_inventory_changed")
    base = original_index.parent
    inventory = []
    seen_pairs = set()
    seen_cells = set()
    for row in index["variants"]:
        cell_id = row["cell_id"]
        if cell_id not in expected_cell_ids:
            raise ValueError("unexpected_cell_id")
        seen_cells.add(cell_id)
        variant = row.get("variant")
        scope = row.get("scope")
        pair = (cell_id, variant if variant is not None else "sentinel")
        if pair in seen_pairs:
            raise ValueError("duplicate_variant_row")
        seen_pairs.add(pair)
        record = {"cell_id": cell_id, "variant": variant, "scope": scope,
                  "original_status": row["status"], "original_row_sha256": digest(row)}
        if scope in {"analysis", "full"}:
            if not isinstance(variant, str) or not re.fullmatch(r"(?:single-v[0-9]+|O-analysis-v[0-9]+(?:-O-document-v[0-9]+)?)", variant):
                raise ValueError("unexpected_variant_id")
            folder = base / cell_id / variant
            files = ["receipt.json", "candidate-copy/analysis.go", "candidate-copy/metrics.json",
                     "candidate-copy/sources.json", "candidate-copy/.eval-copy"]
            if scope == "full":
                files.append("candidate-copy/memo.md")
            if (folder / "candidate-copy/.eval-generated-metrics.json").is_file():
                files.append("candidate-copy/.eval-generated-metrics.json")
            record["source_files"] = {name: sha((folder / name).read_bytes())
                                      for name in files if (folder / name).is_file()}
            if "receipt.json" not in record["source_files"]:
                raise ValueError("original_receipt_missing:" + cell_id + ":" + variant)
            native_files = native_variant_files(original_index.parent.parent / cell_id, variant, scope)
            expected_owned = {"analysis.go", "metrics.json", "sources.json"}
            if scope == "full":
                expected_owned.add("memo.md")
            if set(native_files) != expected_owned:
                raise ValueError("native_owned_artifact_set_mismatch")
            for name, expected in native_files.items():
                actual = record["source_files"].get("candidate-copy/" + name)
                if actual is None or "sha256:" + actual != expected:
                    raise ValueError("candidate_copy_differs_from_native_version")
        inventory.append(record)
    if seen_cells != expected_cell_ids:
        raise ValueError("frozen_cell_coverage_mismatch")
    return inventory


def prepare(study_root: Path, controls_path: Path, freeze_path: Path) -> dict:
    fixture, original_freeze, original_index = study_paths(study_root)
    require_disjoint_output(controls_path, study_root, original_index)
    require_disjoint_output(freeze_path, study_root, original_index)
    if controls_path.exists() or freeze_path.exists():
        raise FileExistsError("diagnostic_prepare_output_exists")
    original = read_json(original_index)
    if original.get("generation_complete_before_start") is not True or original.get("model_calls") != 0:
        raise ValueError("original_qualification_not_terminal")
    control = controls(fixture)
    if not control["passed"]:
        raise ValueError("diagnostic_controls_failed")
    write_new(controls_path, control)
    data = fixture / "public/data"
    checkout_head = subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=study_root, text=True).strip()
    frozen = {
        "schema": "opensocrates.go-ts.O-v2-reassessment-freeze/1",
        "status": "ready_for_independent_audit_no_candidate_assessment_yet",
        "study_execution_checkout": str(study_root),
        "study_execution_commit": checkout_head,
        "original_freeze_sha256": sha(original_freeze.read_bytes()),
        "original_index_sha256": sha(original_index.read_bytes()),
        "original_index_path": str(original_index),
        "original_export_path": "/private/tmp/opensocrates-go-ts-o24-export-20260928.zip",
        "original_export_sha256": sha(Path("/private/tmp/opensocrates-go-ts-o24-export-20260928.zip").read_bytes()),
        "diagnostic_code_sha256": sha(Path(__file__).read_bytes()),
        "rules_sha256": sha((HERE / "RULES.json").read_bytes()),
        "controls_sha256": sha(controls_path.read_bytes()),
        "controls_path": str(controls_path),
        "oracle_sha256": sha((fixture / "private/oracle.py").read_bytes()),
        "public_data_sha256": {path.name: sha(path.read_bytes()) for path in sorted(data.glob("*.json"))},
        "original_variant_inventory": preflight_inventory(original_index, set(read_json(original_freeze)["cell_ids"])),
        "output_allowlist": ["index.json", "<frozen-cell>/<frozen-variant>/receipt.json"],
        "raw_model_or_oracle_values_retained": False,
        "model_calls": 0,
        "subject_candidate_modifications": 0,
        "score_rewrite": False,
    }
    if len(frozen["original_variant_inventory"]) != 28:
        raise ValueError("diagnostic_inventory_incomplete")
    write_new(freeze_path, frozen)
    return {"freeze": str(freeze_path), "freeze_sha256": sha(freeze_path.read_bytes()),
            "controls": str(controls_path), "controls_sha256": frozen["controls_sha256"],
            "variant_rows": len(frozen["original_variant_inventory"])}


def verify_diagnostic_freeze(freeze_path: Path, expected_sha: str) -> tuple[dict, Path, Path]:
    if sha(freeze_path.read_bytes()) != expected_sha:
        raise ValueError("diagnostic_freeze_hash_mismatch")
    frozen = read_json(freeze_path)
    if frozen.get("schema") != "opensocrates.go-ts.O-v2-reassessment-freeze/1":
        raise ValueError("diagnostic_freeze_schema_mismatch")
    study_root = Path(frozen["study_execution_checkout"])
    fixture, original_freeze, original_index = study_paths(study_root)
    checks = (
        (Path(__file__), frozen["diagnostic_code_sha256"]),
        (HERE / "RULES.json", frozen["rules_sha256"]),
        (Path(frozen["controls_path"]), frozen["controls_sha256"]),
        (original_freeze, frozen["original_freeze_sha256"]),
        (original_index, frozen["original_index_sha256"]),
        (Path(frozen["original_export_path"]), frozen["original_export_sha256"]),
        (fixture / "private/oracle.py", frozen["oracle_sha256"]),
    )
    for path, expected in checks:
        if sha(path.read_bytes()) != expected:
            raise ValueError("diagnostic_input_changed:" + path.name)
    if subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=study_root, text=True).strip() != frozen["study_execution_commit"]:
        raise ValueError("study_execution_commit_changed")
    for name, expected in frozen["public_data_sha256"].items():
        if sha((fixture / "public/data" / name).read_bytes()) != expected:
            raise ValueError("public_data_changed:" + name)
    if preflight_inventory(original_index, set(read_json(original_freeze)["cell_ids"])) != frozen["original_variant_inventory"]:
        raise ValueError("original_variant_artifact_changed")
    return frozen, fixture, original_index


def assess_row(row: dict, original: dict, original_index: Path,
               expected: dict, register: list[dict]) -> dict:
    result = {"schema": "opensocrates.go-ts.O-v2-reassessment-receipt/1",
              "cell_id": row["cell_id"], "variant": row["variant"], "scope": row["scope"],
              "original_status": row["original_status"],
              "original_failed_obligations": original.get("failed_obligations", []),
              "original_row_sha256": row["original_row_sha256"],
              "diagnostic_only": True, "model_calls": 0, "subject_candidate_modifications": 0}
    if row["scope"] not in {"analysis", "full"}:
        result["status"] = "not_assessed_original_candidate_unavailable_or_blocked"
        return result
    folder = original_index.parent / row["cell_id"] / row["variant"]
    receipt = read_json(folder / "receipt.json")
    copy_root = folder / "candidate-copy"
    for name in ("analysis.go", "metrics.json", "sources.json", *(["memo.md"] if row["scope"] == "full" else [])):
        path = copy_root / name
        if not path.is_file() or receipt.get("before", {}).get(name) != "sha256:" + sha(path.read_bytes()):
            result["status"] = "unassessable_original_artifact_provenance_mismatch"
            result["provenance_field"] = name
            return result
    try:
        metrics = read_json(copy_root / "metrics.json")
        sources = read_json(copy_root / "sources.json")
        if not isinstance(metrics, dict):
            raise ValueError("metrics_not_object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result["status"] = "unassessable_unparseable_candidate_artifact"
        result["error_type"] = type(exc).__name__
        return result
    book = metric_facts(metrics, expected)
    result["metrics"] = {
        "selected_contract_fact_count": len(book.facts),
        "matching_fact_count": sum(item["passed"] for item in book.facts),
        "failed_fact_ids": [item["id"] for item in book.facts if not item["passed"]],
        "representation_errors": sorted(set(book.errors)),
        "selected_contract_facts_passed": all(item["passed"] for item in book.facts) and not book.errors,
    }
    result["source_register"] = combined_source_register(metrics, sources, register)
    result["program"] = program_result(copy_root, receipt, metrics)
    if row["scope"] == "full":
        result["memo"] = memo_result((copy_root / "memo.md").read_text(), metrics, book, expected, register)
    else:
        result["memo"] = {"status": "not_applicable_analysis_scope"}
    result["status"] = "bounded_diagnostic_all_gates_passed" if (
        result["metrics"]["selected_contract_facts_passed"]
        and result["source_register"]["passed"]
        and result["program"]["exact_generated_vs_committed"] is True
        and (row["scope"] == "analysis" or result["memo"]["passed"])
    ) else "bounded_diagnostic_gate_failed_or_unassessable"
    result["human_recommendation_quality_reviewed"] = False
    return result


def run(freeze_path: Path, freeze_sha: str, output: Path) -> dict:
    frozen, fixture, original_index = verify_diagnostic_freeze(freeze_path, freeze_sha)
    require_disjoint_output(output, Path(frozen["study_execution_checkout"]), original_index)
    if output.exists():
        raise FileExistsError(output)
    expected, register = load_oracle(fixture)
    original_rows = read_json(original_index)["variants"]
    rows = []
    for frozen_row, original in zip(frozen["original_variant_inventory"], original_rows):
        if frozen_row["original_row_sha256"] != digest(original):
            raise ValueError("variant_row_order_or_hash_changed")
        receipt = assess_row(frozen_row, original, original_index, expected, register)
        if frozen_row["scope"] in {"analysis", "full"}:
            path = output / frozen_row["cell_id"] / frozen_row["variant"] / "receipt.json"
            write_new(path, receipt)
            receipt_sha = sha(path.read_bytes())
        else:
            receipt_sha = digest(receipt)
        rows.append({"cell_id": frozen_row["cell_id"], "variant": frozen_row["variant"],
                     "scope": frozen_row["scope"], "status": receipt["status"],
                     "original_status": original["status"], "diagnostic_receipt_sha256": receipt_sha,
                     "selected_contract_facts_passed": receipt.get("metrics", {}).get("selected_contract_facts_passed"),
                     "source_register_passed": receipt.get("source_register", {}).get("passed"),
                     "exact_program_equals_committed": receipt.get("program", {}).get("exact_generated_vs_committed"),
                     "memo_evidence_passed": receipt.get("memo", {}).get("passed")})
    index = {"schema": "opensocrates.go-ts.O-v2-reassessment-index/1",
             "diagnostic_freeze_sha256": freeze_sha,
             "original_index_sha256": frozen["original_index_sha256"],
             "original_scores_unchanged": True,
             "model_calls": 0,
             "subject_candidate_modifications": 0,
             "human_recommendation_quality_reviewed": False,
             "rows": rows, "status_counts": dict(Counter(row["status"] for row in rows))}
    write_new(output / "index.json", index)
    return {"index": str(output / "index.json"), "index_sha256": sha((output / "index.json").read_bytes()),
            "rows": len(rows), "status_counts": index["status_counts"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="operation", required=True)
    control_parser = commands.add_parser("controls")
    control_parser.add_argument("--study-root", type=Path, required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--study-root", type=Path, required=True)
    prepare_parser.add_argument("--controls", type=Path, required=True)
    prepare_parser.add_argument("--freeze", type=Path, required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--freeze", type=Path, required=True)
    run_parser.add_argument("--freeze-sha256", required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "controls":
        fixture, _, _ = study_paths(args.study_root)
        result = controls(fixture)
    elif args.operation == "prepare":
        result = prepare(args.study_root, args.controls, args.freeze)
    else:
        result = run(args.freeze, args.freeze_sha256, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
