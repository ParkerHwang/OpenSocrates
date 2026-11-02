"""Explore a synthetic SQLite epoch/revision guard, not 2.0 learning behavior.

Only invented values are stored in a temporary database. Ordered operations model
stop, restart, resume and delayed results; no AI app, real user data or external
message delivery is involved.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory


def apply_candidate(conn: sqlite3.Connection, *, epoch: int, revision: int, candidate: str) -> int:
    with conn:
        cursor = conn.execute(
            "UPDATE learning SET candidate = ?, revision = revision + 1 "
            "WHERE id = 1 AND enabled = 1 AND epoch = ? AND revision = ?",
            (candidate, epoch, revision),
        )
        return cursor.rowcount


def main() -> None:
    print(f"SQLite {sqlite3.sqlite_version}")
    with TemporaryDirectory(prefix="opensocrates-learning-probe-") as temp:
        db_path = Path(temp) / "synthetic.sqlite3"
        with closing(sqlite3.connect(db_path)) as init:
            with init:
                init.execute(
                    "CREATE TABLE learning (id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL, "
                    "epoch INTEGER NOT NULL, revision INTEGER NOT NULL, candidate TEXT)"
                )
                init.execute("INSERT INTO learning VALUES (1, 1, 1, 0, NULL)")
            with init:
                # Simulated user stop advances the authorization generation.
                init.execute("UPDATE learning SET enabled = 0, epoch = 2 WHERE id = 1")

        # Reopen the database in the same process; this is only a restart model.
        with (
            closing(sqlite3.connect(db_path)) as controller,
            closing(sqlite3.connect(db_path)) as worker,
        ):
            stopped = controller.execute(
                "SELECT enabled, epoch, revision FROM learning WHERE id = 1"
            ).fetchone()
            old_while_stopped = apply_candidate(worker, epoch=1, revision=0, candidate="old")
            with controller:
                # Simulated explicit resume has its own generation.
                controller.execute("UPDATE learning SET enabled = 1, epoch = 3 WHERE id = 1")
            old_after_resume = apply_candidate(worker, epoch=1, revision=0, candidate="old")
            new_result = apply_candidate(worker, epoch=3, revision=0, candidate="new")
            duplicate = apply_candidate(worker, epoch=3, revision=0, candidate="new")
            final = controller.execute(
                "SELECT enabled, epoch, revision, candidate FROM learning WHERE id = 1"
            ).fetchone()

        print(f"After reopen: enabled={stopped[0]} epoch={stopped[1]} revision={stopped[2]}")
        print(f"Old result rows updated while stopped: {old_while_stopped}")
        print(f"Old result rows updated after resume: {old_after_resume}")
        print(f"New result rows updated: {new_result}; duplicate rows updated: {duplicate}")
        print(
            f"Final: enabled={final[0]} epoch={final[1]} revision={final[2]} candidate={final[3]}"
        )
        print("External delivery, data-retention permission and model behavior were not tested.")


if __name__ == "__main__":
    main()
