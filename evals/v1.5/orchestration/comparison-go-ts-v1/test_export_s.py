"""S-only post-call export path and lineage controls; no subject invocation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import export_s
from export_s import (
    allowed_candidate_path, approved_variant, candidate_lineage,
    indexed_bundle_hash, require_disjoint_output, sha,
)


class SExportControls(unittest.TestCase):
    def setUp(self) -> None:
        self.required = {"design.json", "design.md", "api.go", "web/index.html"}
        self.by_unit = {"S-design": {"design.json", "design.md"},
                        "S-implementation": {"api.go", "web/index.html"}}

    def test_candidate_path_exact_ownership(self) -> None:
        root = Path("/synthetic/candidate")
        for name in ("artifacts/design.md", "artifacts/web/index.html",
                     "versions/S-design/v2/design.json",
                     "versions/S-implementation/v1/web/index.html"):
            self.assertTrue(allowed_candidate_path(root / name, root, self.required, self.by_unit, "D"))
        self.assertTrue(allowed_candidate_path(root / "versions/single/v1/web/index.html",
                                               root, self.required, self.by_unit, "A"))
        self.assertFalse(allowed_candidate_path(root / "versions/single/v1/web/index.html",
                                                root, self.required, self.by_unit, "C"))
        for name in ("artifacts/private/oracle.json", "versions/S-design/v2/api.go",
                     "versions/S-implementation/v0/api.go", "candidate-copy/api.go",
                     "versions/S-other/v1/design.json", "versions/single/v2/design.json"):
            self.assertFalse(allowed_candidate_path(root / name, root, self.required, self.by_unit, "D"))

    def test_variant_labels_and_scopes(self) -> None:
        self.assertTrue(approved_variant("single-v1-design", "design"))
        self.assertTrue(approved_variant("single-v1-full", "full"))
        self.assertTrue(approved_variant("S-design-v2", "design"))
        self.assertTrue(approved_variant("S-design-v1-S-implementation-v2", "full"))
        self.assertFalse(approved_variant("S-design-v1-S-implementation-v2", "design"))
        self.assertFalse(approved_variant("S-design-v0", "design"))
        self.assertFalse(approved_variant("../receipt.json", "full"))

    def test_output_cannot_enter_results_or_frozen_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, checkout = root / "results", root / "checkout"
            results.mkdir(); checkout.mkdir()
            for output in (results / "archive.zip", checkout / "archive.zip"):
                with self.assertRaises(ValueError):
                    require_disjoint_output(output, results, checkout)
            require_disjoint_output(root / "archive.zip", results, checkout)

    def test_single_candidate_hash_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "S-gpt-6-sol-high-A"
            candidate = episode / "candidate"
            (candidate / "artifacts").mkdir(parents=True)
            data = b"synthetic"
            (candidate / "artifacts/design.md").write_bytes(data)
            (episode / "response.json").write_text(json.dumps({
                "candidate_hashes": {"design.md": "sha256:" + sha(data)}}))
            with self.assertRaises(ValueError):
                candidate_lineage(episode, candidate, self.required, self.by_unit)
            (episode / "response.json").write_text(json.dumps({
                "candidate_hashes": {"design.md": "sha256:" + sha(data),
                                     "api.go": "sha256:" + sha(b"missing")}}))
            with self.assertRaises(ValueError):
                candidate_lineage(episode, candidate, self.required, self.by_unit)

    def test_successful_single_has_exact_matching_v1_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "S-gpt-6-sol-high-A"
            candidate = episode / "candidate"
            hashes = {}
            for name in self.required:
                data = name.encode()
                for prefix in ("artifacts", "versions/single/v1"):
                    path = candidate / prefix / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                hashes[name] = "sha256:" + sha(data)
            (episode / "response.json").write_text(json.dumps({"candidate_hashes": hashes}))
            candidate_lineage(episode, candidate, self.required, self.by_unit)
            (candidate / "versions/single/v1/design.md").write_bytes(b"different")
            with self.assertRaises(ValueError):
                candidate_lineage(episode, candidate, self.required, self.by_unit)

    def test_orchestrated_bundle_requires_native_qualified_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "S-gpt-6-sol-high-D"
            candidate = episode / "candidate/versions"
            for name in self.by_unit["S-design"]:
                path = candidate / "S-design/v1" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            for name in self.by_unit["S-implementation"]:
                path = candidate / "S-implementation/v1" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            response = {"units": [{"unit_id": "S-design", "versions": [
                {"version": 1, "qualified": False}]},
                {"unit_id": "S-implementation", "versions": [{"version": 1}]}]}
            (episode / "response.json").write_text(json.dumps(response))
            with self.assertRaises(ValueError):
                indexed_bundle_hash(episode, "S-design-v1-S-implementation-v1",
                                    self.required, self.by_unit)
            response["units"][0]["versions"][0]["qualified"] = True
            (episode / "response.json").write_text(json.dumps(response))
            self.assertTrue(indexed_bundle_hash(
                episode, "S-design-v1-S-implementation-v1", self.required, self.by_unit).startswith("sha256:"))

    def test_published_partial_uses_only_exact_qualified_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp) / "S-gpt-6-sol-high-D"
            candidate = episode / "candidate"
            versions = []
            for version, qualified in [(1, True), (2, False)]:
                artifacts = []
                for name in self.by_unit["S-design"]:
                    data = f"{name}-v{version}".encode()
                    path = candidate / "versions/S-design" / f"v{version}" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    artifacts.append({"path": name, "sha256": "sha256:" + sha(data)})
                    if qualified:
                        published = candidate / "artifacts" / name
                        published.parent.mkdir(parents=True, exist_ok=True)
                        published.write_bytes(data)
                versions.append({"version": version, "qualified": qualified, "artifacts": artifacts})
            (episode / "response.json").write_text(json.dumps({"units": [
                {"unit_id": "S-design", "versions": versions},
                {"unit_id": "S-implementation", "versions": []}]}))
            candidate_lineage(episode, candidate, self.required, self.by_unit)
            (candidate / "artifacts/design.json").write_bytes(b"design.json-v2")
            with self.assertRaises(ValueError):
                candidate_lineage(episode, candidate, self.required, self.by_unit)
            (candidate / "artifacts/design.json").write_bytes(b"design.json-v1")
            (candidate / "artifacts/design.md").unlink()
            with self.assertRaises(ValueError):
                candidate_lineage(episode, candidate, self.required, self.by_unit)

    def test_only_exact_S_qualification_receipts_enter_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, checkout = root / "results", root / "checkout"
            results.mkdir(); checkout.mkdir()
            freeze = root / "freeze.json"
            freeze.write_text("{}\n")
            cells = [f"S-synthetic-{i:02d}-A" for i in range(24)]
            cells[0] = "S-synthetic-00-C"
            frozen = {"cell_ids": cells, "execution_checkout_root": str(checkout),
                      "export_allowlist": ["external_structured_receipts"],
                      "export_excluded": ["candidate_copies", "auth"]}
            task = {"required_artifacts": sorted(self.required), "units": [
                {"unit_id": unit, "owned_paths": sorted(paths)} for unit, paths in self.by_unit.items()]}
            (results / "dispatch-index.json").write_text(json.dumps({"scheduled_cells": 24}))
            for cell in cells:
                episode = results / cell
                episode.mkdir()
                (episode / "terminal.json").write_text("{}\n")
            first = results / cells[0]
            artifacts = []
            for name in self.by_unit["S-design"]:
                data = name.encode()
                version_path = first / "candidate/versions/S-design/v1" / name
                version_path.parent.mkdir(parents=True, exist_ok=True)
                version_path.write_bytes(data)
                published = first / "candidate/artifacts" / name
                published.parent.mkdir(parents=True, exist_ok=True)
                published.write_bytes(data)
                artifacts.append({"path": name, "sha256": "sha256:" + sha(data)})
            response = {"units": [
                {"unit_id": "S-design", "versions": [{"version": 1, "qualified": True,
                                                        "artifacts": artifacts}]},
                {"unit_id": "S-implementation", "versions": []}]}
            (first / "response.json").write_text(json.dumps(response))
            qualification = results / "external-qualification-S"
            receipt = qualification / cells[0] / "S-design-v1" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"structured":{"passed":true}}\n')
            index = {"schema": "opensocrates.go-ts.S-serial-qualification/1",
                     "generation_complete_before_start": True, "scheduled_cells": 24,
                     "model_calls": 0, "variants": [
                         {"cell_id": cells[0], "variant": "S-design-v1", "scope": "design",
                          "status": "deterministic_pass", "candidate_sha256": indexed_bundle_hash(
                              first, "S-design-v1", self.required, self.by_unit)},
                         *({"cell_id": cell, "status": "candidate_unavailable"} for cell in cells[1:])
                     ]}
            (qualification / "index.json").write_text(json.dumps(index))
            archive = root / "S-export.zip"
            with patch.object(export_s, "frozen_context", return_value=(frozen, task)):
                result = export_s.export(results, freeze, sha(freeze.read_bytes()), archive)
                self.assertEqual(result["qualification_receipts"], 1)
                with ZipFile(archive) as zipped:
                    self.assertIn("qualification/index.json", zipped.namelist())
                    self.assertIn(f"qualification/{cells[0]}/S-design-v1/receipt.json", zipped.namelist())
                    self.assertFalse(any("candidate-copy" in name for name in zipped.namelist()))
                unindexed = qualification / cells[1] / "single-v1-design" / "receipt.json"
                unindexed.parent.mkdir(parents=True)
                unindexed.write_text("{}\n")
                with self.assertRaises(ValueError):
                    export_s.export(results, freeze, sha(freeze.read_bytes()), root / "S-export-negative.zip")
                unindexed.unlink()
                saved_hash = index["variants"][0].pop("candidate_sha256")
                (qualification / "index.json").write_text(json.dumps(index))
                with self.assertRaises(ValueError):
                    export_s.export(results, freeze, sha(freeze.read_bytes()), root / "S-export-missing-hash.zip")
                index["variants"][0]["candidate_sha256"] = saved_hash
                index["variants"][0]["variant"] = "single-v1-design"
                (qualification / "index.json").write_text(json.dumps(index))
                with self.assertRaises(ValueError):
                    export_s.export(results, freeze, sha(freeze.read_bytes()), root / "S-export-wrong-arm.zip")
                index["variants"][0]["variant"] = "S-design-v1"
                (qualification / "index.json").write_text(json.dumps(index))
                second_artifacts = []
                for name in self.by_unit["S-design"]:
                    data = (name + " v2").encode()
                    version_path = first / "candidate/versions/S-design/v2" / name
                    version_path.parent.mkdir(parents=True, exist_ok=True)
                    version_path.write_bytes(data)
                    second_artifacts.append({"path": name, "sha256": "sha256:" + sha(data)})
                response["units"][0]["versions"].append(
                    {"version": 2, "qualified": False, "artifacts": second_artifacts})
                (first / "response.json").write_text(json.dumps(response))
                with self.assertRaises(ValueError):
                    export_s.export(results, freeze, sha(freeze.read_bytes()), root / "S-export-omitted-version.zip")


if __name__ == "__main__":
    unittest.main()
