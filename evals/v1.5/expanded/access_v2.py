"""Exact-tuple access probes, separate from pilot task outcomes."""

from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from harness_v2 import HERE, invoke, native_counts, profile, save_new, verify_freeze


def probe(freeze: dict, model: str) -> dict:
    output = HERE / "access-results" / f"{model}.json"
    with tempfile.TemporaryDirectory(prefix="os-v15-access-v2-") as temporary:
        base = Path(temporary)
        workspace = base / "workspace"
        workspace.mkdir()
        codex, env = profile(base / "profile")
        result, final = invoke(
            client=freeze["client"]["path"],
            workspace=workspace,
            env=env,
            model=model,
            prompt=freeze["prompt"],
            receipt=output,
            timeout=freeze["timeout_seconds"],
        )
        observation = {
            "model": model,
            "effort": "medium",
            "process_success": result["process_success"],
            "exact_reply": final.strip() == "V15_ACCESS_OK",
            "native_tables": native_counts(codex),
            "client_sha256": freeze["client"]["sha256"],
            "account": "existing ChatGPT login copied to disposable profile; identity withheld",
            "auth_copy_removed": True,
            "server_echoed_model": None,
        }
        (codex / "auth.json").unlink(missing_ok=True)
        save_new(output.with_suffix(".observation.json"), observation)
        return observation


def main() -> None:
    freeze, commit = verify_freeze(HERE / "access-freeze.v2.json")
    with ThreadPoolExecutor(max_workers=2) as pool:
        observations = list(pool.map(lambda model: probe(freeze, model), freeze["models"]))
    save_new(
        HERE / "access-results" / "summary.json",
        {"freeze_commit": commit, "held_out": False, "observations": observations},
    )
    print(json.dumps(observations, indent=2))


if __name__ == "__main__":
    main()
