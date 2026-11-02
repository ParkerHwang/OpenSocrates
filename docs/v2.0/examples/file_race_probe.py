"""Demonstrate a check/replace race with synthetic files in a temporary directory.

The ordered interleaving models two writers in one process; it is not a test of
OpenSocrates, concurrent host apps, locking, crash recovery or every filesystem.
"""

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with TemporaryDirectory(prefix="opensocrates-file-race-") as temp:
        root = Path(temp)
        target = root / "synthetic-report.txt"
        first = root / "writer-a.tmp"
        second = root / "writer-b.tmp"
        target.write_text("synthetic original\n", encoding="utf-8")
        first.write_text("synthetic writer A\n", encoding="utf-8")
        second.write_text("synthetic writer B\n", encoding="utf-8")

        expected = digest(target)
        b_check_before_a = digest(target) == expected
        os.replace(first, target)
        observer_check_after_a = digest(target) == expected
        # Model B continuing from its earlier successful check without an
        # atomic compare-and-replace operation; B overwrites A's later update.
        os.replace(second, target)
        final_is_b = target.read_text(encoding="utf-8") == "synthetic writer B\n"
        print(f"B check before A: {'match' if b_check_before_a else 'mismatch'}")
        print(f"Observer check after A: {'match' if observer_check_after_a else 'mismatch'}")
        print(f"Final target contains B: {'yes' if final_is_b else 'no'}")
        print("No conditional replacement or concurrent host app was tested.")

        # A separate ordered example: an already-open handle may still refer to
        # the original object after the path is replaced. Some platforms or
        # sharing modes may reject the replacement instead.
        target.write_text("synthetic open original\n", encoding="utf-8")
        replacement = root / "replacement.tmp"
        replacement.write_text("synthetic new path\n", encoding="utf-8")
        with target.open("r+b") as earlier_handle:
            try:
                os.replace(replacement, target)
            except OSError as exc:
                print(f"Replace with old handle open: unavailable ({type(exc).__name__})")
            else:
                earlier_handle.seek(0)
                earlier_handle.write(b"synthetic late write\n")
                earlier_handle.flush()
                earlier_handle.seek(0)
                old_has_write = earlier_handle.read().startswith(b"synthetic late write\n")
                target_is_new = target.read_text(encoding="utf-8") == "synthetic new path\n"
                print(f"Old handle contains late write: {'yes' if old_has_write else 'no'}")
                print(f"Old handle write left new path content: {'yes' if target_is_new else 'no'}")


if __name__ == "__main__":
    main()
