"""Resumable human-operated study engine; never invokes a model or host."""

from __future__ import annotations

import hashlib
import hmac
import random
import re
import secrets
import shutil
import stat
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import (
    ARMS,
    FINAL_LIMIT,
    PHASES,
    TERMINAL,
    LabError,
    boolean,
    cells,
    controller_environment,
    enum,
    fields,
    identifier,
    integer,
    text,
)
from .pack import freeze_pack, load_pack
from .report import make_export
from .storage import Storage, atomic_write, ensure_plain, read_bytes, write_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return secrets.token_hex(12)


class Lab:
    """One owned directory, one serialized ledger, no ambient data collection."""

    def __init__(self, root: Path, pack: Path, payloads: Path | None = None) -> None:
        self.store = Storage(root)
        self.pack_source = pack
        self.payloads = payloads
        self._approvals: dict[str, tuple[str, str]] = {}

    def _pack(self, state: dict[str, Any]) -> dict[str, Any]:
        manifest, _, digest = load_pack(self.store.root / "inputs")
        if digest != state["pack"]["sha256"]:
            raise LabError("frozen_pack_changed")
        return manifest

    def _case(self, state: dict[str, Any], case_id: str) -> dict[str, Any]:
        for case in self._pack(state)["cases"]:
            if case["id"] == case_id:
                return dict(case)
        raise LabError("unknown_case")

    @staticmethod
    def _find(items: list[dict[str, Any]], value: Any) -> dict[str, Any]:
        if not isinstance(value, str):
            raise LabError("unknown_id")
        for item in items:
            if item["id"] == value:
                return item
        raise LabError("unknown_id")

    def _run(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        return self._find(state["runs"], data["run_id"])

    def _group(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        return self._find(state["groups"], data["group_id"])

    def _actor(self, run: dict[str, Any]) -> Path:
        run_id = identifier(run["id"])
        actor = self.store.root / "actors" / run_id
        ensure_plain(actor)
        return actor

    def _approved_path(self, run_id: Any) -> Path:
        return self.store.root / "approved" / f"{identifier(run_id)}.md"

    def _public_run(self, run: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(run)
        if "setup" in run:
            actor = self._actor(run)
            result["actor_path"] = str(actor)
            result["prompt"] = read_bytes(actor / "TASK.md", FINAL_LIMIT).decode("utf-8")
        return result

    def _snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        manifest = self._pack(state)
        identity = deepcopy(state["pack"])
        visible = state["phase"] != "confirmation" or state["criteria"] is not None
        identity["approval"] = {
            "b_instruction": manifest["b_instruction"],
            "cases": [
                {key: case[key] for key in ("id", "title", "deliverable")}
                for case in manifest["cases"]
                if case["phase"] == state["phase"] and visible
            ],
        }
        return {
            "schema": "opensocrates.office-snapshot/1",
            "initialized": True,
            "study_id": state["study_id"],
            "criteria_frozen": state["criteria"] is not None,
            "pack": identity,
            "cells": deepcopy(state["cells"]),
            "phase": state["phase"],
            "budget": state["budget"],
            "started_count": state["started_count"],
            "runs": [self._public_run(run) for run in state["runs"]],
            "controller_environment": deepcopy(state["controller_environment"]),
            "groups": [
                {
                    key: group[key]
                    for key in (
                        "id",
                        "cell_id",
                        "case_id",
                        "status",
                        "judged",
                    )
                }
                for group in state["groups"]
            ],
            "judgments": list(deepcopy(state["judgments"]).values()),
            "warnings": ["partial_blinding", "operator_attested_environment"],
        }

    def snapshot(self) -> dict[str, Any]:
        try:
            if not self.store.owned():
                return {
                    "schema": "opensocrates.office-snapshot/1",
                    "initialized": False,
                    "study_id": None,
                    "criteria_frozen": False,
                    "pack": None,
                    "cells": cells(),
                    "phase": None,
                    "budget": 0,
                    "started_count": 0,
                    "runs": [],
                    "groups": [],
                    "judgments": [],
                    "warnings": [],
                    "controller_environment": controller_environment(),
                }
            with self.store.locked():
                state = self.store.load()
                self._pack(state)
                return self._snapshot(state)
        except (OSError, ValueError, UnicodeError) as exc:
            raise LabError("storage_unavailable") from exc

    def action(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "prepare": self._prepare,
            "preflight": self._preflight,
            "start": self._start,
            "monitor": self._monitor,
            "preview": self._preview,
            "finish": self._finish,
            "retry": self._retry,
            "packet": self._packet,
            "judge": self._judge,
            "reveal": self._reveal,
            "freeze": self._freeze,
            "export": self._export,
        }
        try:
            if name == "create":
                return self._create(data)
            if name not in handlers:
                raise LabError("unknown_action")
            with self.store.locked():
                state = self.store.load()
                self._pack(state)
                result = handlers[name](state, data)
                if name not in ("monitor", "preview", "packet", "reveal"):
                    self.store.save(state)
                return result
        except (OSError, ValueError, UnicodeError) as exc:
            raise LabError("storage_unavailable") from exc

    def _create(self, data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"phase", "cells", "budget", "seed"}, {"phase", "cells", "budget"})
        phase = enum(data["phase"], PHASES)
        budget = integer(data["budget"], 1, 180)
        selected = data["cells"]
        if not isinstance(selected, list) or not selected or len(selected) > 6:
            raise LabError("invalid_cells")
        if any(not isinstance(item, str) for item in selected) or len(set(selected)) != len(
            selected
        ):
            raise LabError("invalid_cells")
        available = {cell["id"]: cell for cell in cells()}
        if any(cell not in available for cell in selected):
            raise LabError("invalid_cells")
        seed = integer(data.get("seed", secrets.randbelow(2**31)), 0, 2**31 - 1)
        manifest, _, _ = load_pack(self.pack_source)
        case_ids = [case["id"] for case in manifest["cases"] if case["phase"] == phase]
        if not case_ids or len(case_ids) * len(selected) * 3 > 180:
            raise LabError("invalid_plan")
        self.store.initialize()
        with self.store.locked():
            identity = freeze_pack(self.pack_source, self.store.root / "inputs")
            state: dict[str, Any] = {
                "schema": "opensocrates.office-state/1",
                "study_id": _id(),
                "pack": identity,
                "phase": phase,
                "budget": budget,
                "started_count": 0,
                "seed": seed,
                "cells": [available[cell] for cell in selected],
                "runs": [],
                "groups": [],
                "judgments": {},
                "criteria": None,
                "controller_environment": controller_environment(),
            }
            self._assign(state, case_ids, random.Random(seed))
            self.store.save(state)
        return self._snapshot(state)

    @staticmethod
    def _new_run(group: dict[str, Any], arm: str, attempt: int) -> dict[str, Any]:
        return {
            "id": _id(),
            "group_id": group["id"],
            "cell_id": group["cell_id"],
            "case_id": group["case_id"],
            "arm": arm,
            "attempt": attempt,
            "status": "planned",
            "preflight": None,
            "started_at": None,
            "finished_at": None,
            "metrics": {},
        }

    def _assign(self, state: dict[str, Any], case_ids: list[str], rng: random.Random) -> None:
        for cell in state["cells"]:
            for case_id in case_ids:
                arms = list(ARMS)
                rng.shuffle(arms)
                aliases = [f"Answer-{_id()[:8]}" for _ in arms]
                group = {
                    "id": _id(),
                    "cell_id": cell["id"],
                    "case_id": case_id,
                    "status": "incomplete",
                    "judged": False,
                    "mapping": dict(zip(aliases, arms, strict=True)),
                }
                state["groups"].append(group)
                state["runs"].extend(self._new_run(group, arm, 1) for arm in arms)
        rng.shuffle(state["runs"])

    def _prepare(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        from .hosts import prepare_content, setup_guide

        fields(data, {"run_id"}, {"run_id"})
        run = self._run(state, data)
        if run["status"] == "prepared":
            return self._prepared_response(state, run)
        if run["status"] != "planned":
            raise LabError("invalid_transition")
        if state["phase"] == "confirmation" and state["criteria"] is None:
            raise LabError("criteria_not_frozen")
        case = self._case(state, run["case_id"])
        actor = self._actor(run)
        actor.mkdir(mode=0o700)
        try:
            return self._prepare_actor(state, run, case, actor, prepare_content, setup_guide)
        except (OSError, ValueError, LabError):
            ensure_plain(actor)
            shutil.rmtree(actor)
            raise

    def _prepare_actor(
        self,
        state: dict[str, Any],
        run: dict[str, Any],
        case: dict[str, Any],
        actor: Path,
        prepare_content: Any,
        setup_guide: Any,
    ) -> dict[str, Any]:
        (actor / "out").mkdir(mode=0o700)
        for name in case["materials"]:
            destination = actor / name
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            atomic_write(destination, read_bytes(self.store.root / "inputs" / name, FINAL_LIMIT))
        prompt = case["prompt"] + "\n\n" + case["deliverable"]
        if run["arm"] == "B":
            prompt += "\n\n" + self._pack(state)["b_instruction"][case["locale"]]
        prompt += "\n\nSave only the final deliverable to out/final.md. Do not modify other files."
        atomic_write(actor / "TASK.md", prompt.encode("utf-8"))
        cell = self._find(state["cells"], run["cell_id"])
        setup = setup_guide(cell["host"], run["arm"], actor, self.payloads)
        if run["arm"] == "C":
            setup = prepare_content(actor, cell["host"], self.payloads)
        run["status"] = "prepared"
        run["setup_status"] = setup["status"]
        run["setup"] = setup
        return self._prepared_response(state, run)

    def _prepared_response(self, state: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
        case = self._case(state, run["case_id"])
        actor = self._actor(run)
        return {
            "run": self._public_run(run),
            "actor_path": str(actor),
            "prompt": read_bytes(actor / "TASK.md", FINAL_LIMIT).decode("utf-8"),
            "setup": deepcopy(run["setup"]),
            "clarification_reply": case["clarification_reply"],
        }

    def _preflight(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        keys = {
            "run_id",
            "observed_model",
            "observed_effort",
            "host_version",
            "execution_mode",
            "isolation",
            "environment",
            "opensocrates",
            "model_mapping_confirmed",
            "exploratory",
            "pack_approved",
        }
        fields(data, keys, keys)
        run = self._run(state, data)
        if run["status"] != "prepared":
            raise LabError("invalid_transition")
        record = self._validate_preflight(data)
        run["preflight"] = record
        blockers, warnings = self._blockers(state, run)
        return {
            "run": self._public_run(run),
            "can_start": not blockers,
            "blockers": blockers,
            "warnings": warnings,
        }

    @staticmethod
    def _validate_preflight(data: dict[str, Any]) -> dict[str, Any]:
        record = {key: value for key, value in data.items() if key != "run_id"}
        for key, options in (
            (
                "observed_model",
                ("gpt-6-luna", "claude-haiku-5-5", "gemini-3.8-flash-medium", "unknown"),
            ),
            ("observed_effort", ("max", "medium", "unknown")),
            ("execution_mode", ("local", "cloud", "sync", "unknown")),
            ("isolation", ("clear", "contaminated", "unknown")),
            ("environment", ("fresh_os", "clean_snapshot", "new_user", "new_folder", "unknown")),
            ("opensocrates", ("absent", "enabled", "unknown")),
        ):
            enum(data[key], options)
        version = text(data["host_version"], 64)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}", version):
            raise LabError("invalid_host_version")
        for key in ("model_mapping_confirmed", "exploratory", "pack_approved"):
            boolean(data[key])
        return record

    def _blockers(self, state: dict[str, Any], run: dict[str, Any]) -> tuple[list[str], list[str]]:
        preflight = run["preflight"]
        if preflight is None:
            return ["preflight_required"], []
        cell = self._find(state["cells"], run["cell_id"])
        blockers = self._preflight_blockers(preflight, cell, run)
        if cell["os"] != controller_environment()["os"]:
            blockers.append("controller_os_mismatch")
        if state["controller_environment"] != controller_environment():
            blockers.append("controller_environment_changed")
        if state["phase"] == "confirmation" and state["criteria"] is None:
            blockers.append("criteria_not_frozen")
        blockers.extend(self._group_blockers(state, run))
        warnings = ["operator_attested_environment", "partial_blinding"]
        if preflight["isolation"] == "unknown":
            warnings.append("exploratory_isolation")
        if preflight["execution_mode"] == "unknown":
            warnings.append("execution_mode_unknown")
        return list(dict.fromkeys(blockers)), warnings

    @staticmethod
    def _group_blockers(state: dict[str, Any], run: dict[str, Any]) -> list[str]:
        blockers = []
        for other in state["runs"]:
            if (
                other["group_id"] == run["group_id"]
                and other["attempt"] == 1
                and other["started_at"]
            ):
                previous = other["preflight"]
                preflight = run["preflight"]
                if previous["host_version"] != preflight["host_version"]:
                    blockers.append("group_host_version_mismatch")
                modes = (previous["execution_mode"], preflight["execution_mode"])
                if "unknown" not in modes and modes[0] != modes[1]:
                    blockers.append("group_execution_mode_mismatch")
        return blockers

    @staticmethod
    def _preflight_blockers(
        record: dict[str, Any], cell: dict[str, Any], run: dict[str, Any]
    ) -> list[str]:
        conditions = {
            "model_mismatch": record["observed_model"] != cell["expected_model"],
            "effort_mismatch": record["observed_effort"] != cell["expected_effort"],
            "known_contamination": record["isolation"] == "contaminated",
            "isolation_unknown": record["isolation"] == "unknown" and not record["exploratory"],
            "opensocrates_state_mismatch": record["opensocrates"]
            != ("enabled" if run["arm"] == "C" else "absent"),
            "mapping_confirmation_required": cell["host"] == "antigravity"
            and not record["model_mapping_confirmed"],
            "pack_approval_required": not record["pack_approved"],
            "content_unavailable": run.get("setup_status") == "unavailable",
            "host_version_unknown": record["host_version"] == "unknown",
        }
        return [key for key, value in conditions.items() if value]

    def _start(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"run_id"}, {"run_id"})
        run = self._run(state, data)
        if run["status"] != "prepared":
            raise LabError("invalid_transition")
        if self._blockers(state, run)[0]:
            raise LabError("preflight_blocked")
        if any(item["status"] == "running" for item in state["runs"]):
            raise LabError("run_already_running")
        if state["started_count"] >= state["budget"]:
            raise LabError("budget_exhausted")
        state["started_count"] += 1
        run["status"] = "running"
        run["started_at"] = _now()
        return {"run": self._public_run(run)}

    def _monitor(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"run_id"}, {"run_id"})
        run = self._run(state, data)
        path = self._actor(run) / "out" / "final.md"
        ensure_plain(path)
        exists = path.exists()
        size = self._outbox_size(path) if exists else 0
        elapsed = 0.0
        if run["started_at"]:
            elapsed = (
                datetime.now(timezone.utc) - datetime.fromisoformat(run["started_at"])
            ).total_seconds()
        return {
            "exists": exists,
            "bytes": size,
            "ready": exists and 0 < size <= FINAL_LIMIT,
            "source": "local_outbox",
            "overdue": run["status"] == "running" and elapsed > 1800,
        }

    @staticmethod
    def _outbox_size(path: Path) -> int:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise LabError("unsafe_file")
        return info.st_size

    def _preview(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"run_id"}, {"run_id"})
        run = self._run(state, data)
        if run["status"] != "running":
            raise LabError("invalid_transition")
        content = read_bytes(self._actor(run) / "out" / "final.md", FINAL_LIMIT)
        final = text(content.decode("utf-8"))
        token = secrets.token_urlsafe(32)
        self._approvals[run["id"]] = (token, hashlib.sha256(content).hexdigest())
        return {"text": final, "approval_token": token}

    def _approved_final(self, run: dict[str, Any], data: dict[str, Any]) -> str:
        if data.get("synthetic_approved") is not True:
            raise LabError("approval_required")
        intake = enum(data.get("intake", "file"), ("file", "manual"))
        if intake == "manual":
            if "approval_token" in data:
                raise LabError("invalid_fields")
            return text(data.get("final_text"))
        if "final_text" in data:
            raise LabError("invalid_fields")
        approval = self._approvals.get(run["id"])
        token = data.get("approval_token")
        if (
            approval is None
            or not isinstance(token, str)
            or not hmac.compare_digest(token, approval[0])
        ):
            raise LabError("preview_required")
        content = read_bytes(self._actor(run) / "out" / "final.md", FINAL_LIMIT)
        if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), approval[1]):
            self._approvals.pop(run["id"], None)
            raise LabError("preview_changed")
        return text(content.decode("utf-8"))

    @staticmethod
    def _metrics(data: dict[str, Any]) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "intake": enum(data.get("intake", "file"), ("file", "manual")),
            "clarification_count": integer(data.get("clarification_count", 0), 0, 100),
            "delivery": enum(
                data.get("delivery", "unknown"), ("observed", "operator_reported", "unknown")
            ),
            "application": enum(data.get("application", "unknown"), ("self_reported", "unknown")),
        }
        for key in ("tokens", "elapsed_seconds"):
            metrics[key] = None if data.get(key) is None else integer(data[key], 0, 10**9)
        return metrics

    def _finish(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "run_id",
            "status",
            "synthetic_approved",
            "approval_token",
            "final_text",
            "intake",
            "clarification_count",
            "delivery",
            "application",
            "tokens",
            "elapsed_seconds",
        }
        fields(data, allowed, {"run_id", "status"})
        run = self._run(state, data)
        status = enum(data["status"], TERMINAL)
        if run["status"] in TERMINAL:
            raise LabError("invalid_transition")
        if status == "completed" and run["status"] != "running":
            raise LabError("invalid_transition")
        metrics = self._metrics(data)
        if "synthetic_approved" in data:
            boolean(data["synthetic_approved"])
        if status == "completed":
            final = self._approved_final(run, data)
            atomic_write(self._approved_path(run["id"]), final.encode("utf-8"))
        elif any(key in data for key in ("final_text", "approval_token")):
            raise LabError("invalid_fields")
        run["status"] = status
        run["metrics"] = metrics
        run["finished_at"] = _now()
        self._approvals.pop(run["id"], None)
        self._update_group(state, run["group_id"])
        return {"run": self._public_run(run)}

    def _update_group(self, state: dict[str, Any], group_id: str) -> None:
        group = self._find(state["groups"], group_id)
        primary = [
            item for item in state["runs"] if item["group_id"] == group_id and item["attempt"] == 1
        ]
        group["status"] = (
            "complete" if all(item["status"] == "completed" for item in primary) else "incomplete"
        )

    def _retry(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"run_id"}, {"run_id"})
        run = self._run(state, data)
        if run["status"] not in TERMINAL:
            raise LabError("invalid_transition")
        related = [
            item
            for item in state["runs"]
            if item["group_id"] == run["group_id"] and item["arm"] == run["arm"]
        ]
        if any(item["status"] not in TERMINAL for item in related):
            raise LabError("retry_already_pending")
        if state["started_count"] >= state["budget"] or len(state["runs"]) >= 360:
            raise LabError("budget_exhausted")
        group = self._find(state["groups"], run["group_id"])
        retry = self._new_run(group, run["arm"], max(item["attempt"] for item in related) + 1)
        state["runs"].append(retry)
        return {"run": self._public_run(retry)}

    def _packet(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"group_id"}, {"group_id"})
        group = self._group(state, data)
        if group["status"] != "complete":
            raise LabError("group_incomplete")
        case = self._case(state, group["case_id"])
        primary = {
            item["arm"]: item
            for item in state["runs"]
            if item["group_id"] == group["id"] and item["attempt"] == 1
        }
        answers = [
            {
                "alias": alias,
                "text": read_bytes(self._approved_path(primary[arm]["id"]), FINAL_LIMIT).decode(
                    "utf-8"
                ),
            }
            for alias, arm in group["mapping"].items()
        ]
        result = {
            "group_id": group["id"],
            "title": case["title"],
            "prompt": case["prompt"],
            "deliverable": case["deliverable"],
            "materials": [
                {
                    "name": name,
                    "text": read_bytes(self.store.root / "inputs" / name, FINAL_LIMIT).decode(
                        "utf-8"
                    ),
                }
                for name in case["materials"]
            ],
            "answers": answers,
            "judged": group["judged"],
            "partial_blinding": True,
        }
        if group["judged"]:
            result["judgment"] = deepcopy(state["judgments"][group["id"]])
        return result

    def _judge(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        required = {
            "group_id",
            "choice",
            "confidence",
            "recognition",
            "reproduced_experience",
            "synthetic_approved",
        }
        fields(data, required | {"first_reaction", "edit"}, required)
        group = self._group(state, data)
        if group["judged"]:
            raise LabError("judgment_locked")
        if group["status"] != "complete":
            raise LabError("group_incomplete")
        if boolean(data["synthetic_approved"]) is not True:
            raise LabError("approval_required")
        judgment = {
            "group_id": group["id"],
            "choice": enum(data["choice"], (*group["mapping"], "tie", "all_unusable")),
            "first_reaction": text(data.get("first_reaction", ""), 16000, empty=True),
            "confidence": enum(data["confidence"], ("low", "medium", "high")),
            "recognition": enum(data["recognition"], ("unknown", "guessed", "known")),
            "reproduced_experience": enum(
                data["reproduced_experience"], ("yes", "no", "uncertain")
            ),
            "created_at": _now(),
        }
        if len(judgment["first_reaction"]) > 4000:
            raise LabError("invalid_text")
        if "edit" in data:
            judgment["edit"] = text(data["edit"], FINAL_LIMIT, empty=True)
        state["judgments"][group["id"]] = judgment
        group["judged"] = True
        return {"judgment": deepcopy(judgment)}

    def _reveal(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, {"group_id"}, {"group_id"})
        group = self._group(state, data)
        if not group["judged"]:
            raise LabError("judgment_required")
        return {
            "mapping": deepcopy(group["mapping"]),
            "evaluator_checks": self._case(state, group["case_id"])["evaluator_checks"],
            "judgment": deepcopy(state["judgments"][group["id"]]),
        }

    def _freeze(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(
            data,
            {"criteria", "discovery_reference", "synthetic_approved"},
            {"criteria", "discovery_reference", "synthetic_approved"},
        )
        if state["criteria"] is not None:
            raise LabError("criteria_locked")
        if boolean(data["synthetic_approved"]) is not True:
            raise LabError("approval_required")
        state["criteria"] = {
            "text": text(data["criteria"], 16000),
            "discovery_reference": text(data["discovery_reference"], 1000),
            "created_at": _now(),
        }
        return {"frozen": True}

    def _export(self, state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        fields(data, set(), set())
        answers = {
            run["id"]: read_bytes(self._approved_path(run["id"]), FINAL_LIMIT).decode("utf-8")
            for run in state["runs"]
            if run["status"] == "completed"
        }
        result = make_export(state, answers)
        filename = f"office-study-{identifier(state['study_id'])}.json"
        write_json(self.store.root / "exports" / filename, result)
        return {"filename": filename, "report": result["report"], "export": result}
