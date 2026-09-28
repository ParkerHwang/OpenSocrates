from __future__ import annotations

import unittest

from qualify_main import classification


class QualificationClassificationControls(unittest.TestCase):
    def test_unassessable_does_not_become_subject_defect(self):
        result = classification({"passed": False, "error": None,
                                 "checks": [{"id": "browser", "passed": False,
                                             "status": "unassessable"}]}, 1)
        self.assertEqual(result["status"], "integration_pending_unassessable")
        self.assertIsNone(result["subject_defect"])

    def test_real_failure_survives_unassessable_check(self):
        result = classification({"passed": False, "error": None,
                                 "checks": [{"id": "browser", "passed": False,
                                             "status": "unassessable"},
                                            {"id": "oracle", "passed": False}]}, 1)
        self.assertEqual(result["status"], "mixed_failure_and_unassessable")
        self.assertTrue(result["subject_defect"])
        self.assertEqual(result["failed_obligations"], ["oracle"])


if __name__ == "__main__":
    unittest.main()
