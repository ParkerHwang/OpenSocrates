"""Legacy sending and durable local publication state."""

import json
import os
import sqlite3
import threading

from .transport import LookupUnavailable, NotAccepted


class PublishConflict(ValueError):
    """Raised when one logical identity is reused for different content."""


class LegacySender:
    def __init__(self, transport):
        self.transport = transport

    def send(self, name, payload):
        return self.transport.send("legacy", name, payload)


_identity_locks_guard = threading.Lock()
_identity_locks = {}


def _lock_for_identity(database_key, tenant, key):
    identity = (database_key, tenant, key)
    with _identity_locks_guard:
        lock = _identity_locks.get(identity)
        if lock is None:
            lock = threading.Lock()
            _identity_locks[identity] = lock
        return lock


class Publisher:
    """A durable local record of calls to the supplied transport.

    The SQLite row is committed before a transport call. Transport operations
    are deliberately outside SQLite transactions because the local database
    and the transport do not share an atomic commit boundary.
    """

    def __init__(self, state_path, transport):
        self.state_path = state_path
        self.transport = transport
        raw_path = os.fspath(state_path)
        decoded_path = os.fsdecode(raw_path)
        if decoded_path == ":memory:":
            # Each in-memory connection has a separate database.
            self._database_key = ":memory:" + str(id(self))
        else:
            self._database_key = os.fsdecode(os.path.realpath(raw_path))

        self._db_lock = threading.Lock()
        self._lifecycle = threading.Condition()
        self._active_calls = 0
        self._closing = False
        self._closed = False

        self._connection = sqlite3.connect(
            state_path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            self._connection.execute("PRAGMA busy_timeout = 30000")
            with self._db_lock:
                self._connection.execute(
                    """CREATE TABLE IF NOT EXISTS publish_operations (
                           tenant_id BLOB NOT NULL,
                           key_id BLOB NOT NULL,
                           payload BLOB NOT NULL,
                           status TEXT NOT NULL
                               CHECK (status IN ('pending', 'delivered', 'rejected')),
                           receipt_json TEXT,
                           PRIMARY KEY (tenant_id, key_id),
                           CHECK (
                               (status = 'delivered' AND receipt_json IS NOT NULL)
                               OR (status != 'delivered' AND receipt_json IS NULL)
                           )
                       )"""
                )
        except BaseException:
            self._connection.close()
            raise

    @staticmethod
    def _validate(tenant, key, payload):
        if not isinstance(tenant, str) or not tenant or len(tenant) > 80:
            raise ValueError("tenant must be a nonempty string of at most 80 characters")
        if not isinstance(key, str) or not key or len(key) > 80:
            raise ValueError("key must be a nonempty string of at most 80 characters")
        if not isinstance(payload, bytes):
            raise ValueError("payload must be bytes")

    @staticmethod
    def _identity_bytes(value):
        # surrogatepass covers every Python str, including strings containing
        # lone surrogate code points that SQLite's TEXT binding cannot encode.
        return value.encode("utf-8", "surrogatepass")

    def _enter_call(self):
        with self._lifecycle:
            if self._closing or self._closed:
                raise RuntimeError("Publisher is closed")
            self._active_calls += 1

    def _leave_call(self):
        with self._lifecycle:
            self._active_calls -= 1
            if self._active_calls == 0:
                self._lifecycle.notify_all()

    def _get_or_create(self, tenant_id, key_id, payload):
        with self._db_lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """SELECT payload, status, receipt_json
                         FROM publish_operations
                        WHERE tenant_id = ? AND key_id = ?""",
                    (tenant_id, key_id),
                ).fetchone()
                created = row is None
                if created:
                    connection.execute(
                        """INSERT INTO publish_operations
                               (tenant_id, key_id, payload, status, receipt_json)
                           VALUES (?, ?, ?, 'pending', NULL)""",
                        (tenant_id, key_id, payload),
                    )
                    status, receipt_json = "pending", None
                else:
                    if row[0] != payload:
                        raise PublishConflict("identity is already recorded with different payload bytes")
                    status, receipt_json = row[1], row[2]
                connection.execute("COMMIT")
                return created, status, receipt_json
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def _record(self, tenant_id, key_id, payload, status, receipt_json=None):
        with self._db_lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """UPDATE publish_operations
                          SET status = ?, receipt_json = ?
                        WHERE tenant_id = ? AND key_id = ? AND payload = ?""",
                    (status, receipt_json, tenant_id, key_id, payload),
                )
                if cursor.rowcount != 1:
                    raise PublishConflict("recorded identity or payload changed during publication")
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _encode_receipt(receipt):
        # JSON round-tripping both constrains the public result to JSON values
        # and detaches it from any mutable object returned by the transport.
        return json.dumps(receipt, allow_nan=False, separators=(",", ":"))

    @staticmethod
    def _result(status, receipt_json=None):
        receipt = json.loads(receipt_json) if status == "delivered" else None
        return {"status": status, "receipt": receipt}

    def publish(self, tenant, key, payload):
        self._validate(tenant, key, payload)
        self._enter_call()
        try:
            tenant_id = self._identity_bytes(tenant)
            key_id = self._identity_bytes(key)
            identity_lock = _lock_for_identity(self._database_key, tenant, key)
            with identity_lock:
                created, status, receipt_json = self._get_or_create(
                    tenant_id, key_id, payload
                )
                if status == "delivered" or status == "rejected":
                    return self._result(status, receipt_json)

                if not created:
                    try:
                        receipt = self.transport.lookup(tenant, key)
                    except LookupUnavailable:
                        return self._result("pending")
                    if receipt is not None:
                        receipt_json = self._encode_receipt(receipt)
                        self._record(
                            tenant_id, key_id, payload, "delivered", receipt_json
                        )
                        return self._result("delivered", receipt_json)

                try:
                    receipt = self.transport.send(tenant, key, payload)
                except NotAccepted:
                    self._record(tenant_id, key_id, payload, "rejected")
                    return self._result("rejected")
                except TimeoutError:
                    # A timeout says nothing about whether the transport acted.
                    return self._result("pending")

                receipt_json = self._encode_receipt(receipt)
                self._record(tenant_id, key_id, payload, "delivered", receipt_json)
                return self._result("delivered", receipt_json)
        finally:
            self._leave_call()

    def close(self):
        with self._lifecycle:
            if self._closed:
                return
            if self._closing:
                while not self._closed:
                    self._lifecycle.wait()
                return
            self._closing = True
            while self._active_calls:
                self._lifecycle.wait()
        try:
            with self._db_lock:
                self._connection.close()
        finally:
            with self._lifecycle:
                self._closed = True
                self._lifecycle.notify_all()
