"""Lossless synthetic HTTP/timing export after frozen execution and measurement.

No candidate modifications, database copies, credentials or model event streams.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from runner import HERE, read, sanitize, save, sha


def export(storage):
    exported = []
    for cell in read(HERE / "manifest.json")["cells"]:
        base = storage / cell["id"]
        directory = HERE / "results" / cell["id"]
        if cell["task"] != "coding" or not (directory / "call.json").exists():
            continue
        files = []
        for boundary in ("acceptance", "performance"):
            for root in sorted(base.glob(boundary + "-artifacts-*")):
                for path in sorted(root.rglob("*")):
                    if not path.is_file() or not (
                        path.name.endswith("-http.json") or path.suffix == ".log"
                    ):
                        continue
                    relative = Path("http-evidence") / root.name / path.relative_to(root)
                    target = directory / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    text = sanitize(path.read_text(encoding="utf-8", errors="replace"), base)
                    with target.open("x", encoding="utf-8") as stream:
                        stream.write(text)
                    files.append(
                        {
                            "path": str(relative),
                            "original_sha256": sha(path),
                            "export_sha256": sha(target),
                        }
                    )
        raw = base / "performance.json"
        if raw.exists():
            # Preserve every timing row, including warmup, failed requests and drain.
            # gzip is a transport encoding, not sampling or rounding.
            value = read(raw)
            payload = []
            for measurement in value["cells"]:
                payload.append(
                    {
                        key: measurement.get(key)
                        for key in (
                            "workload",
                            "concurrency",
                            "repetition",
                            "stats",
                            "raw_attempts",
                        )
                    }
                )
            content = sanitize(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")), base
            ).encode("utf-8")
            target = directory / "timing-samples.json.gz"
            with target.open("xb") as stream:
                stream.write(gzip.compress(content, mtime=0))
            assert json.loads(gzip.decompress(target.read_bytes())) == json.loads(content)
            files.append(
                {
                    "path": target.name,
                    "raw_performance_sha256": sha(raw),
                    "export_sha256": sha(target),
                    "samples": sum(len(x["raw_attempts"]) for x in payload),
                    "compressed_bytes": target.stat().st_size,
                }
            )
        receipt = {
            "schema": "opensocrates.hard-evidence-export/1",
            "cell": cell["id"],
            "files": files,
            "scope": "Synthetic HTTP traces/server logs and all timing rows only; private paths normalized; no raw model events or databases",
        }
        save(directory / "evidence-export.json", receipt)
        exported.append({"cell": cell["id"], "files": len(files)})
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.storage), indent=2))
