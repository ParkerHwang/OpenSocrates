"""Export only completed, locked synthetic artifacts; retain original hash maps."""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "v2"))
import runner


def export(storage):
    manifest = runner.read(HERE / "v2/manifest.json")
    exported = []
    for cell in manifest["cells"]:
        output = HERE / "v2/results" / cell["id"]
        lock = output / "snapshot.json"
        if not lock.exists() or (output / "export-map.json").exists():
            continue
        base = storage / cell["id"]
        source = base / "locked-artifacts"
        snap = runner.read(lock)
        assert runner.inventory(source) == snap["files"], "locked source changed"
        destination = output / "artifact-export"
        destination.mkdir()
        mapping = {}
        for name, meta in snap["files"].items():
            raw = (source / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
            try:
                text = raw.decode("utf-8")
                public = runner.sanitize(text, base, manifest).encode("utf-8")
            except UnicodeDecodeError:
                public = raw
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(public)
            if meta["executable"]:
                target.chmod(0o755)
            mapping[name] = {
                "original_sha256": meta["sha256"],
                "export_sha256": hashlib.sha256(public).hexdigest(),
                "redacted": public != raw,
                "bytes": len(public),
            }
        runner.save(
            output / "export-map.json",
            {
                "utc": runner.now(),
                "source_lock_sha256": runner.sha(lock),
                "candidate_originals_unchanged": True,
                "qualification_uses": "original locked source, not the redacted export",
                "privacy_transform": "local paths and credential-shaped strings only; raw synthetic originals remain in declared evaluation storage",
                "files": mapping,
            },
        )
        config = base / "profile/home/.codex/config.toml"
        expected = runner.read(output / "inputs.json")["config_sha256"]
        runner.save(
            output / "postflight-profile.json",
            {
                "utc": runner.now(),
                "effective_config_sha256": runner.sha(config),
                "effective_config_unchanged": runner.sha(config) == expected,
                "copied_auth_absent": not (base / "profile/home/.codex/auth.json").exists(),
                "original_artifacts_still_match": runner.inventory(source) == snap["files"],
            },
        )
        exported.append(cell["id"])
    print(json.dumps({"new_exports": exported}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--storage", type=Path, required=True)
    a = p.parse_args()
    export(a.storage)
