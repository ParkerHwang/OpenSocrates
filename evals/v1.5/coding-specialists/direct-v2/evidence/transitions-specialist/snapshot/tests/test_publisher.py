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
        self.addCleanup(self.tempdir.cleanup)
        self.database = self.tempdir.name + "/state.sqlite"
        self.transport = FileTransport(self.tempdir.name + "/provider")
        self.publisher = Publisher(self.database, self.transport)
        self.addCleanup(self.publisher.close)

    def stored_row(self, tenant, key):
        with sqlite3.connect(self.database) as connection:
            return connection.execute(
                "SELECT payload, status, receipt FROM publications "
                "WHERE tenant = ? AND key = ?",
                (tenant, key),
            ).fetchone()

    def test_delivered_replay_is_durable_detached_and_identity_scoped(self):
        first = self.publisher.publish("tenant", "one", b"same")
        self.assertEqual(first["status"], "delivered")
        self.assertEqual(set(first), {"status", "receipt"})
        first["receipt"]["meta"]["bytes"] = -1

        replay = self.publisher.publish("tenant", "one", b"same")
        self.assertEqual(replay["status"], "delivered")
        self.assertEqual(replay["receipt"]["meta"]["bytes"], 4)
        second_identity = self.publisher.publish("tenant", "two", b"same")
        self.assertEqual(second_identity["status"], "delivered")
        self.assertEqual(self.transport.effect_count(), 2)
        self.assertEqual(len(self.transport.calls), 2)

        row = self.stored_row("tenant", "one")
        self.assertEqual(bytes(row[0]), b"same")
        self.assertEqual(row[1], "delivered")
        self.assertEqual(json.loads(row[2]), replay["receipt"])

    def test_timeout_after_acceptance_recovers_after_recreation(self):
        self.transport.fault = "timeout-after"
        response = self.publisher.publish("acme", "invoice-7", b"document")
        self.assertEqual(response, {"status": "pending", "receipt": None})
        self.assertEqual(self.stored_row("acme", "invoice-7")[:2], (b"document", "pending"))
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.effect_count(), 1)

        self.publisher.close()
        self.publisher = Publisher(self.database, self.transport)
        response = self.publisher.publish("acme", "invoice-7", b"document")
        self.assertEqual(response["status"], "delivered")
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.effect_count(), 1)
        self.assertEqual(self.stored_row("acme", "invoice-7")[1], "delivered")

    def test_unavailable_lookup_stays_pending_then_absence_allows_send(self):
        self.transport.fault = "timeout-before"
        self.assertEqual(
            self.publisher.publish("acme", "invoice-8", b"document"),
            {"status": "pending", "receipt": None},
        )
        self.assertEqual(self.transport.effect_count(), 0)
        self.transport.lookup_unavailable = True
        self.assertEqual(
            self.publisher.publish("acme", "invoice-8", b"document"),
            {"status": "pending", "receipt": None},
        )
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.effect_count(), 0)
        self.assertEqual(self.stored_row("acme", "invoice-8")[:2], (b"document", "pending"))

        self.transport.lookup_unavailable = False
        self.assertEqual(
            self.publisher.publish("acme", "invoice-8", b"document")["status"],
            "delivered",
        )
        self.assertEqual(len(self.transport.calls), 2)
        self.assertEqual(self.transport.effect_count(), 1)

    def test_rejection_replays_and_conflict_changes_neither_record_nor_effects(self):
        self.transport.fault = "reject"
        response = self.publisher.publish("acme", "invoice-9", b"document")
        self.assertEqual(response, {"status": "rejected", "receipt": None})
        row_before = self.stored_row("acme", "invoice-9")
        call_count = len(self.transport.calls)
        effect_count = self.transport.effect_count()

        self.publisher.close()
        self.publisher = Publisher(self.database, self.transport)
        self.assertFalse(self.transport.closed)
        self.assertEqual(
            self.publisher.publish("acme", "invoice-9", b"document"), response
        )
        with self.assertRaises(PublishConflict):
            self.publisher.publish("acme", "invoice-9", b"different")
        self.assertEqual(self.stored_row("acme", "invoice-9"), row_before)
        self.assertEqual(len(self.transport.calls), call_count)
        self.assertEqual(self.transport.effect_count(), effect_count)

    def test_two_publishers_keep_concurrent_distinct_identities(self):
        second_publisher = Publisher(self.database, self.transport)
        self.addCleanup(second_publisher.close)
        start = threading.Barrier(3)
        results = {}
        errors = []

        def publish(label, publisher):
            try:
                start.wait(5)
                results[label] = publisher.publish("tenant", label, b"same payload")
            except BaseException as error:
                errors.append(error)

        threads = [
            threading.Thread(target=publish, args=("first", self.publisher)),
            threading.Thread(target=publish, args=("second", second_publisher)),
        ]
        for thread in threads:
            thread.start()
        start.wait(5)
        for thread in threads:
            thread.join(5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual({key: value["status"] for key, value in results.items()},
                         {"first": "delivered", "second": "delivered"})
        self.assertEqual(self.transport.effect_count(), 2)
        self.assertEqual(self.stored_row("tenant", "first")[:2],
                         (b"same payload", "delivered"))
        self.assertEqual(self.stored_row("tenant", "second")[:2],
                         (b"same payload", "delivered"))

    def test_concurrent_conflicting_content_has_one_recorded_winner(self):
        second_publisher = Publisher(self.database, self.transport)
        self.addCleanup(second_publisher.close)
        start = threading.Barrier(3)
        outcomes = []

        def publish(publisher, payload):
            try:
                start.wait(5)
                outcomes.append((payload, publisher.publish("tenant", "same", payload)))
            except BaseException as error:
                outcomes.append((payload, error))

        threads = [
            threading.Thread(target=publish, args=(self.publisher, b"left")),
            threading.Thread(target=publish, args=(second_publisher, b"right")),
        ]
        for thread in threads:
            thread.start()
        start.wait(5)
        for thread in threads:
            thread.join(5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        winners = [(payload, value) for payload, value in outcomes
                   if isinstance(value, dict)]
        conflicts = [value for _, value in outcomes if isinstance(value, PublishConflict)]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(winners[0][1]["status"], "delivered")
        self.assertEqual(bytes(self.stored_row("tenant", "same")[0]), winners[0][0])
        self.assertEqual(self.transport.effect_count(), 1)
        self.assertEqual(len(self.transport.calls), 1)

    def test_conflict_does_not_change_pending_attempt(self):
        self.transport.fault = "timeout-before"
        self.assertEqual(
            self.publisher.publish("acme", "invoice-10", b"document")["status"],
            "pending",
        )
        row_before = self.stored_row("acme", "invoice-10")
        call_count = len(self.transport.calls)
        with self.assertRaises(PublishConflict):
            self.publisher.publish("acme", "invoice-10", b"different")
        self.assertEqual(self.stored_row("acme", "invoice-10"), row_before)
        self.assertEqual(len(self.transport.calls), call_count)

    def test_invalid_arguments_have_no_database_or_transport_effect(self):
        invalid = [
            ("", "key", b"x"),
            ("t" * 81, "key", b"x"),
            ("tenant", "", b"x"),
            ("tenant", "k" * 81, b"x"),
            ("tenant", "key", bytearray(b"x")),
        ]
        for args in invalid:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    self.publisher.publish(*args)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM publications").fetchone()[0], 0
            )
        self.assertEqual(self.transport.calls, [])

    def test_two_publishers_serialize_same_identity_during_uncertain_send(self):
        entered_send = threading.Event()
        release_send = threading.Event()
        second_started = threading.Event()

        class BlockingTransport:
            def send(inner_self, tenant, key, payload):
                entered_send.set()
                if not release_send.wait(5):
                    raise AssertionError("test did not release the controlled send")
                self.transport.fault = "timeout-after"
                return self.transport.send(tenant, key, payload)

            def lookup(inner_self, tenant, key):
                return self.transport.lookup(tenant, key)

        second_publisher = Publisher(self.database, BlockingTransport())
        self.addCleanup(second_publisher.close)
        results = {}
        errors = []

        def first_call():
            try:
                results["first"] = second_publisher.publish("shared", "key", b"payload")
            except BaseException as error:
                errors.append(error)

        def second_call():
            second_started.set()
            try:
                results["second"] = self.publisher.publish("shared", "key", b"payload")
            except BaseException as error:
                errors.append(error)

        first_thread = threading.Thread(target=first_call)
        first_thread.start()
        self.assertTrue(entered_send.wait(5), "first send did not reach the controlled point")
        second_thread = threading.Thread(target=second_call)
        second_thread.start()
        self.assertTrue(second_started.wait(5), "second call did not start")
        release_send.set()
        first_thread.join(5)
        second_thread.join(5)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertCountEqual(
            [results["first"]["status"], results["second"]["status"]],
            ["pending", "delivered"],
        )
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.effect_count(), 1)
        self.assertEqual(self.stored_row("shared", "key")[:2], (b"payload", "delivered"))


if __name__ == "__main__":
    unittest.main()
