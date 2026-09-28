import unittest
from unittest.mock import patch

from quotadesk.api import handle_edit
from quotadesk.policy import PolicyError, Store, apply_policy


class PolicyEditContracts(unittest.TestCase):
    def setUp(self):
        self.store = Store(default_limit=70)
        self.store.seed("team", 30, "operations")

    def test_edit_updates_fields_once_and_returns_exact_public_record(self):
        payload = {"expected_revision": 1, "max_jobs": 0, "label": " night shift "}

        result = apply_policy(self.store, "team", payload)

        self.assertEqual(result, {
            "namespace": "team",
            "revision": 2,
            "configured_max_jobs": 0,
            "effective_max_jobs": 0,
            "label": " night shift ",
        })
        self.assertEqual(set(result), {
            "namespace", "revision", "configured_max_jobs", "effective_max_jobs", "label"
        })
        self.assertEqual(
            payload,
            {"expected_revision": 1, "max_jobs": 0, "label": " night shift "},
        )
        self.assertEqual(self.store.audit_entries(), [
            {"namespace": "team", "old_revision": 1, "new_revision": 2}
        ])

    def test_omission_null_and_empty_values_keep_their_distinct_meaning(self):
        cleared = apply_policy(self.store, "team", {"expected_revision": 1, "label": None})
        self.assertEqual(cleared["configured_max_jobs"], 30)
        self.assertEqual(cleared["label"], "")
        self.assertEqual(cleared["revision"], 2)

        unlimited_override = apply_policy(
            self.store, "team", {"expected_revision": 2, "max_jobs": None}
        )
        self.assertEqual(unlimited_override["configured_max_jobs"], None)
        self.assertEqual(unlimited_override["effective_max_jobs"], 70)
        self.assertEqual(unlimited_override["label"], "")
        self.assertEqual(unlimited_override["revision"], 3)

        unchanged = apply_policy(
            self.store, "team", {"expected_revision": 3, "max_jobs": None, "label": ""}
        )
        self.assertEqual(unchanged, unlimited_override)
        self.assertEqual(len(self.store.audit_entries()), 2)

    def test_noop_does_not_increment_and_stale_noop_still_conflicts(self):
        unchanged = apply_policy(self.store, "team", {"expected_revision": 1})
        self.assertEqual(unchanged["revision"], 1)
        self.assertEqual(self.store.audit_entries(), [])

        with self.assertRaises(PolicyError) as raised:
            apply_policy(self.store, "team", {"expected_revision": 2, "max_jobs": 30})
        self.assertEqual(raised.exception.code, "conflict")
        self.assertEqual(self.store.read("team")["revision"], 1)
        self.assertEqual(self.store.audit_entries(), [])

    def test_maximum_limit_and_label_length_boundaries_are_accepted(self):
        label = "x" * 40
        record = apply_policy(
            self.store, "team", {"expected_revision": 1, "max_jobs": 1000, "label": label}
        )
        self.assertEqual(record["configured_max_jobs"], 1000)
        self.assertEqual(record["label"], label)
        self.assertEqual(record["revision"], 2)

    def test_rejected_input_has_no_partial_record_or_audit_change(self):
        invalid_payloads = [
            None,
            [],
            {},
            {"expected_revision": True},
            {"expected_revision": 1.0},
            {"expected_revision": 1, "unexpected": 5},
            {"expected_revision": 1, "max_jobs": True},
            {"expected_revision": 1, "max_jobs": "30"},
            {"expected_revision": 1, "max_jobs": 1.5},
            {"expected_revision": 1, "max_jobs": -1},
            {"expected_revision": 1, "max_jobs": 1001},
            {"expected_revision": 1, "label": 3},
            {"expected_revision": 1, "label": "x" * 41},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                before = self.store.read("team")
                audit_before = self.store.audit_entries()
                with self.assertRaises(PolicyError) as raised:
                    apply_policy(self.store, "team", payload)
                self.assertEqual(raised.exception.code, "invalid")
                self.assertEqual(self.store.read("team"), before)
                self.assertEqual(self.store.audit_entries(), audit_before)

    def test_request_types_are_validated_before_stale_revision(self):
        status, body = handle_edit(
            self.store, "team", {"expected_revision": 999, "max_jobs": "30"}
        )
        self.assertEqual((status, body), (400, {"error": "invalid"}))

    def test_api_maps_policy_errors_and_keeps_programming_errors_visible(self):
        status, record = handle_edit(
            self.store, "team", {"expected_revision": 1, "max_jobs": 25}
        )
        self.assertEqual(status, 200)
        self.assertEqual(record["configured_max_jobs"], 25)
        self.assertEqual(record["revision"], 2)

        self.store.seed("team", 30, "operations")
        self.assertEqual(
            handle_edit(self.store, "missing", {"expected_revision": 1}),
            (404, {"error": "not_found"}),
        )
        self.assertEqual(
            handle_edit(self.store, "team", {"expected_revision": 2}),
            (409, {"error": "conflict"}),
        )
        self.assertEqual(
            handle_edit(self.store, "team", {"expected_revision": 1, "label": 2}),
            (400, {"error": "invalid"}),
        )
        with patch("quotadesk.api.apply_policy", side_effect=RuntimeError("bug")):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                handle_edit(self.store, "team", {"expected_revision": 1})

    def test_returned_record_and_audit_entries_are_detached(self):
        returned = apply_policy(
            self.store, "team", {"expected_revision": 1, "label": "updated"}
        )
        returned["label"] = "outside"
        self.assertEqual(self.store.read("team")["label"], "updated")

        entries = self.store.audit_entries()
        entries[0]["new_revision"] = -1
        self.assertEqual(self.store.audit_entries()[0]["new_revision"], 2)


if __name__ == "__main__":
    unittest.main()
