import json
import sqlite3
import tempfile
import threading
import unittest

from parcelseal.publisher import PublishConflict, Publisher
from parcelseal.transport import FileTransport


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = self.tempdir.name + "/state.sqlite"
        self.transport = FileTransport(self.tempdir.name + "/provider")

    def tearDown(self):
        self.tempdir.cleanup()

    def rows(self):
        with sqlite3.connect(self.database) as connection:
            return connection.execute(
                """SELECT tenant_id, key_id, payload, status, receipt_json
                     FROM publish_operations ORDER BY tenant_id, key_id"""
            ).fetchall()

    def test_delivery_replays_detached_receipt_after_recreation(self):
        publisher = Publisher(self.database, self.transport)
        first = publisher.publish("acme", "one", b"same bytes")
        self.assertEqual(first["status"], "delivered")
        original_receipt = json.loads(json.dumps(first["receipt"]))
        first["receipt"]["meta"]["bytes"] = -1
        first["receipt"]["id"] = "caller mutation"
        publisher.close()

        recreated = Publisher(self.database, self.transport)
        replay = recreated.publish("acme", "one", b"same bytes")
        independent = recreated.publish("acme", "two", b"same bytes")
        self.assertEqual(replay, {"status": "delivered", "receipt": original_receipt})
        self.assertEqual(independent["status"], "delivered")
        self.assertNotEqual(replay["receipt"]["id"], independent["receipt"]["id"])
        self.assertEqual(self.transport.calls, [("acme", "one"), ("acme", "two")])
        self.assertEqual(self.transport.effect_count(), 2)

        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[2] for row in rows}, {b"same bytes"})
        self.assertEqual({row[3] for row in rows}, {"delivered"})
        self.assertTrue(all(row[4] is not None for row in rows))
        recreated.close()
        self.assertFalse(self.transport.closed)

    def test_validation_happens_before_any_publication_effect(self):
        publisher = Publisher(self.database, self.transport)
        invalid_calls = [
            ("", "key", b"payload"),
            ("x" * 81, "key", b"payload"),
            ("tenant", "", b"payload"),
            ("tenant", "x" * 81, b"payload"),
            ("tenant", "key", bytearray(b"payload")),
            (None, "key", b"payload"),
        ]
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                publisher.publish(*arguments)
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(self.transport.effect_count(), 0)
        publisher.close()
        self.assertEqual(self.rows(), [])

    def test_conflicting_payload_does_not_change_pending_record(self):
        publisher = Publisher(self.database, self.transport)
        self.transport.fault = "timeout-before"
        self.assertEqual(
            publisher.publish("acme", "uncertain", b"original"),
            {"status": "pending", "receipt": None},
        )
        before = self.rows()
        self.assertEqual(len(before), 1)
        self.assertEqual((before[0][2], before[0][3], before[0][4]), (b"original", "pending", None))

        with self.assertRaises(PublishConflict):
            publisher.publish("acme", "uncertain", b"different")
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.transport.calls, [("acme", "uncertain")])
        self.assertEqual(self.transport.effect_count(), 0)
        publisher.close()

    def test_pending_lookup_unavailable_then_absence_allows_retry(self):
        publisher = Publisher(self.database, self.transport)
        self.transport.fault = "timeout-before"
        self.assertEqual(publisher.publish("acme", "retry", b"body")["status"], "pending")
        self.transport.lookup_unavailable = True
        self.assertEqual(publisher.publish("acme", "retry", b"body"), {"status": "pending", "receipt": None})
        self.assertEqual(self.transport.calls, [("acme", "retry")])
        self.assertEqual(self.transport.effect_count(), 0)
        self.assertEqual((self.rows()[0][2], self.rows()[0][3]), (b"body", "pending"))

        self.transport.lookup_unavailable = False
        result = publisher.publish("acme", "retry", b"body")
        self.assertEqual(result["status"], "delivered")
        self.assertEqual(self.transport.calls, [("acme", "retry"), ("acme", "retry")])
        self.assertEqual(self.transport.effect_count(), 1)
        row = self.rows()[0]
        self.assertEqual((row[2], row[3]), (b"body", "delivered"))
        publisher.close()

    def test_timeout_after_acceptance_is_reconciled_after_restart(self):
        publisher = Publisher(self.database, self.transport)
        self.transport.fault = "timeout-after"
        pending = publisher.publish("acme", "maybe", b"accepted")
        self.assertEqual(pending, {"status": "pending", "receipt": None})
        self.assertEqual((self.rows()[0][2], self.rows()[0][3]), (b"accepted", "pending"))
        self.assertEqual(self.transport.effect_count(), 1)
        publisher.close()

        recreated = Publisher(self.database, self.transport)
        delivered = recreated.publish("acme", "maybe", b"accepted")
        self.assertEqual(delivered["status"], "delivered")
        self.assertEqual(self.transport.calls, [("acme", "maybe")])
        self.assertEqual(self.transport.effect_count(), 1)
        row = self.rows()[0]
        self.assertEqual((row[2], row[3]), (b"accepted", "delivered"))
        self.assertEqual(row[4], json.dumps(delivered["receipt"], separators=(",", ":")))
        recreated.close()

    def test_rejection_is_terminal_and_keeps_payload(self):
        publisher = Publisher(self.database, self.transport)
        self.transport.fault = "reject"
        rejected = publisher.publish("acme", "denied", b"keep me")
        self.assertEqual(rejected, {"status": "rejected", "receipt": None})
        publisher.close()

        recreated = Publisher(self.database, self.transport)
        replay = recreated.publish("acme", "denied", b"keep me")
        self.assertEqual(replay, rejected)
        with self.assertRaises(PublishConflict):
            recreated.publish("acme", "denied", b"different")
        row = self.rows()[0]
        self.assertEqual((row[2], row[3], row[4]), (b"keep me", "rejected", None))
        self.assertEqual(self.transport.calls, [("acme", "denied")])
        self.assertEqual(self.transport.effect_count(), 0)
        recreated.close()

    def test_two_publishers_serialize_same_identity_and_keep_distinct_rows(self):
        entered_send = threading.Event()
        allow_send_to_finish = threading.Event()

        class ControlledTransport(FileTransport):
            def send(controlled, tenant, key, payload):
                entered_send.set()
                if not allow_send_to_finish.wait(5):
                    raise AssertionError("test did not release controlled send")
                return super(ControlledTransport, controlled).send(tenant, key, payload)

        self.transport = ControlledTransport(self.tempdir.name + "/provider")
        first = Publisher(self.database, self.transport)
        second = Publisher(self.database, self.transport)
        outcomes = {}
        failures = []

        def publish_into(name, publisher, tenant, key, payload):
            try:
                outcomes[name] = publisher.publish(tenant, key, payload)
            except BaseException as error:
                failures.append(error)

        first_thread = threading.Thread(
            target=publish_into,
            args=("first", first, "acme", "shared", b"shared body"),
        )
        first_thread.start()
        self.assertTrue(entered_send.wait(5), "first send did not reach the controlled point")

        second_started = threading.Event()

        def second_publish():
            second_started.set()
            publish_into("second", second, "acme", "shared", b"shared body")

        second_thread = threading.Thread(target=second_publish)
        second_thread.start()
        self.assertTrue(second_started.wait(5))
        allow_send_to_finish.set()
        first_thread.join(5)
        second_thread.join(5)
        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(outcomes["first"]["status"], "delivered")
        self.assertEqual(outcomes["second"]["status"], "delivered")
        self.assertEqual(self.transport.calls, [("acme", "shared")])
        self.assertEqual(self.transport.effect_count(), 1)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0][2], rows[0][3]), (b"shared body", "delivered"))

        # Simultaneous writes for different identities must both survive too.
        barrier = threading.Barrier(3)
        other_threads = []
        for name, key in (("third", "other-1"), ("fourth", "other-2")):
            publisher = first if name == "third" else second
            thread = threading.Thread(
                target=lambda result_name=name, identity=key, owner=publisher: (
                    barrier.wait(),
                    publish_into(result_name, owner, "acme", identity, b"same"),
                )
            )
            other_threads.append(thread)
            thread.start()
        barrier.wait()
        for thread in other_threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(self.rows()), 3)
        self.assertEqual(self.transport.effect_count(), 3)
        self.assertEqual({row[3] for row in self.rows()}, {"delivered"})

        conflict_barrier = threading.Barrier(3)
        conflict_results = []
        conflicts = []

        def conflicting_publish(publisher, payload):
            conflict_barrier.wait()
            try:
                conflict_results.append(
                    publisher.publish("acme", "race", payload)
                )
            except PublishConflict as error:
                conflicts.append(error)
            except BaseException as error:
                failures.append(error)

        conflict_threads = [
            threading.Thread(target=conflicting_publish, args=(first, b"left")),
            threading.Thread(target=conflicting_publish, args=(second, b"right")),
        ]
        for thread in conflict_threads:
            thread.start()
        conflict_barrier.wait()
        for thread in conflict_threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(conflict_results), 1)
        self.assertEqual(len(conflicts), 1)
        race_row = next(row for row in self.rows() if row[1] == b"race")
        self.assertIn(race_row[2], (b"left", b"right"))
        self.assertEqual(race_row[3], "delivered")
        self.assertEqual(len(self.rows()), 4)
        self.assertEqual(self.transport.calls.count(("acme", "race")), 1)
        self.assertEqual(self.transport.effect_count(), 4)
        first.close()
        second.close()


if __name__ == "__main__":
    unittest.main()
