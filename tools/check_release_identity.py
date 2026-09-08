"""Pure release identity regressions; no remote reads or writes."""

from __future__ import annotations

import unittest

from release_identity import validate_target


class ReleaseIdentityChecks(unittest.TestCase):
    def test_missing_tag_is_not_created_implicitly(self):
        with self.assertRaises(ValueError):
            validate_target("1.3.0", "refs/tags/v1.3.0", "a" * 40, "")

    def test_exact_lightweight_and_annotated_tag(self):
        for output in (
            "a" * 40 + "\trefs/tags/v1.3.0\n",
            "b" * 40 + "\trefs/tags/v1.3.0\n" + "a" * 40 + "\trefs/tags/v1.3.0^{}\n",
        ):
            validate_target("1.3.0", "refs/tags/v1.3.0", "a" * 40, output)

    def test_wrong_commit_or_branch_dispatch_is_rejected(self):
        output = "b" * 40 + "\trefs/tags/v1.3.0\n"
        for ref in ("refs/tags/v1.3.0", "refs/heads/main", "refs/heads/feature"):
            with self.assertRaises(ValueError):
                validate_target("1.3.0", ref, "a" * 40, output)


if __name__ == "__main__":
    unittest.main()
