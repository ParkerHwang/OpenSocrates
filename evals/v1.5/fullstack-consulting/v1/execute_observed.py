"""Add complete post-install configuration receipts to the frozen observer.

The original manifest/runner stay immutable. This additive instrumentation is
separately hash-frozen before the first subject call and does not alter treatment.
"""

from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import runner

HERE = Path(__file__).resolve().parent
original_preflight = runner.preflight


def full_configuration(manifest, base, workspace, codex, env, output):
    original_preflight(manifest, base, workspace, codex, env, output)
    config = (codex / "config.toml").read_text()
    runner.save(
        output / "effective-config.json",
        {
            "utc": runner.now(),
            "stage": "after disposable plugin registration, before model call",
            "sha256": hashlib.sha256(config.encode()).hexdigest(),
            "config": runner.clean(config, base, manifest),
            "base_manifest_sha256": runner.sha(HERE / "manifest.json"),
            "execution_manifest_sha256": runner.sha(HERE / "execution-manifest.json"),
            "note": "inputs.json config is the common pre-install profile; this includes marketplace/plugin registration.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path, required=True)
    args = parser.parse_args()
    boundary = runner.read(HERE / "execution-manifest.json")
    assert runner.sha(HERE / "manifest.json") == boundary["base_manifest_sha256"]
    assert runner.sha(__file__) == boundary["observer_sha256"]
    manifest = runner.read(HERE / "manifest.json")
    runner.verify(manifest)
    runner.preflight = full_configuration
    runner.execute(manifest, args.storage)
