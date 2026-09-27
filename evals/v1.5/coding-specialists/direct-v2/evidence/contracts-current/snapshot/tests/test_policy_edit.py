import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from quotadesk.api import handle_edit
from quotadesk.policy import PolicyError, Store, apply_policy


class StrictPolicyEditContracts(unittest.TestCase):
    def setUp(self):
        self.store = Store(default_limit=80)
        self.store.seed("batch", 20, "operations")

    def test_edits_are_revisioned_atomic_and_detached(self):
        first = apply_policy(self.store, "batch", {
            "expected_revision": 1,
            "label": "night shift",
        })
        self.assertEqual(
            set(first),
            {"namespace", "revision", "configured_max_jobs", "effective_max_jobs", "label"},
        )
        self.assertEqual(first, {
            "namespace": "batch",
            "revision": 2,
            "configured_max_jobs": 20,
            "effective_max_jobs": 20,
            "label": "night shift",
        })
        self.assertEqual(self.store.audit_entries(), [{
            "namespace": "batch", "old_revision": 1, "new_revision": 2,
        }])

        first["label"] = "changed by caller"
        first_audit = self.store.audit_entries()
        first_audit[0]["namespace"] = "changed by caller"
        self.assertEqual(self.store.read("batch")["label"], "night shift")
        self.assertEqual(self.store.audit_entries()[0]["namespace"], "batch")

        status, second = handle_edit(self.store, "batch", {
            "expected_revision": 2,
            "max_jobs": 0,
            "label": None,
        })
        self.assertEqual(status, 200)
        self.assertEqual(second, {
            "namespace": "batch",
            "revision": 3,
            "configured_max_jobs": 0,
            "effective_max_jobs": 0,
            "label": "",
        })
        self.assertEqual(len(self.store.audit_entries()), 2)

        reset = apply_policy(self.store, "batch", {
            "expected_revision": 3,
            "max_jobs": None,
        })
        self.assertEqual(reset["revision"], 4)
        self.assertIsNone(reset["configured_max_jobs"])
        self.assertEqual(reset["effective_max_jobs"], 80)

        audit_before_noop = self.store.audit_entries()
        no_op = apply_policy(self.store, "batch", {"expected_revision": 4})
        self.assertEqual(no_op, reset)
        self.assertEqual(self.store.read("batch")["revision"], 4)
        self.assertEqual(self.store.audit_entries(), audit_before_noop)

    def test_validation_is_strict_and_rejections_leave_state_unchanged(self):
        invalid_payloads = [
            None,
            [],
            {},
            {"expected_revision": True},
            {"expected_revision": 0},
            {"expected_revision": 1, "unexpected": 1},
            {"expected_revision": 1, "max_jobs": "12"},
            {"expected_revision": 1, "max_jobs": 1.0},
            {"expected_revision": 1, "max_jobs": True},
            {"expected_revision": 1, "max_jobs": -1},
            {"expected_revision": 1, "max_jobs": 1001},
            {"expected_revision": 1, "label": False},
            {"expected_revision": 1, "label": "x" * 41},
            # Invalid fields are rejected before a stale revision is compared.
            {"expected_revision": 99, "max_jobs": "12"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                original_payload = copy.deepcopy(payload)
                row_before = self.store.read("batch")
                audit_before = self.store.audit_entries()
                with self.assertRaises(PolicyError) as raised:
                    apply_policy(self.store, "batch", payload)
                self.assertEqual(raised.exception.code, "invalid")
                self.assertEqual(payload, original_payload)
                self.assertEqual(self.store.read("batch"), row_before)
                self.assertEqual(self.store.audit_entries(), audit_before)

    def test_inclusive_value_boundaries_and_explicit_empty_label(self):
        label = "x" * 40
        at_upper_bounds = apply_policy(self.store, "batch", {
            "expected_revision": 1,
            "max_jobs": 1000,
            "label": label,
        })
        self.assertEqual(at_upper_bounds["configured_max_jobs"], 1000)
        self.assertEqual(at_upper_bounds["label"], label)

        with_empty_label = apply_policy(self.store, "batch", {
            "expected_revision": 2,
            "max_jobs": 1,
            "label": "",
        })
        self.assertEqual(with_empty_label["revision"], 3)
        self.assertEqual(with_empty_label["configured_max_jobs"], 1)
        self.assertEqual(with_empty_label["label"], "")
        self.assertEqual(len(self.store.audit_entries()), 2)

    def test_concurrent_edits_cannot_commit_the_same_revision(self):
        start_together = Barrier(2)

        def edit(label):
            start_together.wait()
            try:
                return apply_policy(self.store, "batch", {
                    "expected_revision": 1,
                    "label": label,
                })
            except PolicyError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ["first", "second"]))

        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.store.read("batch")["revision"], 2)
        self.assertEqual(self.store.audit_entries(), [{
            "namespace": "batch", "old_revision": 1, "new_revision": 2,
        }])

    def test_conflicts_and_api_error_mapping(self):
        status, body = handle_edit(self.store, "missing", {"expected_revision": 1})
        self.assertEqual((status, body), (404, {"error": "not_found"}))

        status, body = handle_edit(self.store, "batch", {"expected_revision": 1, "max_jobs": "20"})
        self.assertEqual((status, body), (400, {"error": "invalid"}))

        self.assertEqual(apply_policy(self.store, "batch", {
            "expected_revision": 1, "label": "operations",
        })["revision"], 1)
        status, body = handle_edit(self.store, "batch", {
            "expected_revision": 0,
            "label": "operations",
        })
        self.assertEqual((status, body), (400, {"error": "invalid"}))

        # A valid stale request conflicts even when its requested value is current.
        status, body = handle_edit(self.store, "batch", {
            "expected_revision": 2,
            "label": "operations",
        })
        self.assertEqual((status, body), (409, {"error": "conflict"}))
        self.assertEqual(self.store.audit_entries(), [])

        with patch("quotadesk.api.apply_policy", side_effect=RuntimeError("bug")):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                handle_edit(self.store, "batch", {"expected_revision": 1})


if __name__ == "__main__":
    unittest.main()
