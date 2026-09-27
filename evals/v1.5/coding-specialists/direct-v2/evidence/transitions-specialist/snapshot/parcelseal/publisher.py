"""Legacy sending and durable publication with uncertain-outcome recovery."""

import json
import os
import sqlite3
import threading
import weakref

from .transport import LookupUnavailable, NotAccepted


class _DatabaseLock:
    def __init__(self):
        self.lock = threading.RLock()


_database_locks_guard = threading.Lock()
_database_locks = {}


def _shared_database_lock(state_path):
    """Return a process-local lock shared by publishers for this file."""
    path = os.path.realpath(os.path.abspath(os.fsdecode(os.fspath(state_path))))
    with _database_locks_guard:
        reference = _database_locks.get(path)
        shared = reference() if reference is not None else None
        if shared is None:
            shared = _DatabaseLock()
            _database_locks[path] = weakref.ref(shared)
        return shared


class PublishConflict(ValueError):
    """An identity has already been recorded with different content."""


class LegacySender:
    def __init__(self, transport):
        self.transport = transport

    def send(self, name, payload):
        return self.transport.send("legacy", name, payload)


class Publisher:
    """Persist publish identity and outcome, reconciling uncertain sends.

    A pending row is committed before contacting the transport. SQLite's write
    transaction then serializes lookup/send/outcome handling for callers that
    share the state file. The transaction cannot include the transport's file
    write, so a timeout or interrupted call remains pending and is reconciled
    with ``lookup`` on a later call.
    """

    def __init__(self, state_path, transport):
        self.state_path = state_path
        self.transport = transport
        self._lock = threading.RLock()
        self._coordination = _shared_database_lock(state_path)
        self._closed = False
        self._db = sqlite3.connect(
            state_path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            self._db.execute("PRAGMA busy_timeout = 30000")
            self._db.execute("PRAGMA journal_mode = WAL")
            self._db.execute("PRAGMA synchronous = FULL")
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS publications (
                    tenant TEXT NOT NULL,
                    key TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    status TEXT NOT NULL
                        CHECK (status IN ('pending', 'delivered', 'rejected')),
                    receipt TEXT,
                    PRIMARY KEY (tenant, key),
                    CHECK (
                        (status = 'delivered' AND receipt IS NOT NULL)
                        OR (status <> 'delivered' AND receipt IS NULL)
                    )
                )
                """
            )
        except BaseException:
            self._db.close()
            self._closed = True
            raise

    @staticmethod
    def _validate(tenant, key, payload):
        if not isinstance(tenant, str) or not tenant or len(tenant) > 80:
            raise ValueError("tenant must be a nonempty string of at most 80 characters")
        if not isinstance(key, str) or not key or len(key) > 80:
            raise ValueError("key must be a nonempty string of at most 80 characters")
        if not isinstance(payload, bytes):
            raise ValueError("payload must be bytes")

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError("Publisher is closed")

    def _rollback(self):
        if self._db.in_transaction:
            self._db.rollback()

    @staticmethod
    def _response(status, receipt=None):
        # Every call gets a fresh, JSON-compatible object. In particular, a
        # caller cannot mutate the receipt that will be replayed from storage.
        if status == "delivered":
            return {"status": status, "receipt": receipt}
        return {"status": status, "receipt": None}

    @staticmethod
    def _receipt_json(receipt):
        return json.dumps(receipt, allow_nan=False, separators=(",", ":"))

    def _read(self, tenant, key):
        return self._db.execute(
            "SELECT payload, status, receipt FROM publications "
            "WHERE tenant = ? AND key = ?",
            (tenant, key),
        ).fetchone()

    def publish(self, tenant, key, payload):
        # Validate before touching the database or transport.
        self._validate(tenant, key, payload)

        # SQLite serializes the operation transaction, while this shared lock
        # also closes the small gap between durably inserting a new pending
        # row and starting that transaction across separate Publisher objects.
        with self._lock, self._coordination.lock:
            self._ensure_open()
            try:
                # Durably establish the identity and content before the
                # external effect. This row is the recovery point if the
                # process stops during a send.
                self._db.execute("BEGIN IMMEDIATE")
                row = self._read(tenant, key)
                inserted = row is None
                if inserted:
                    self._db.execute(
                        "INSERT INTO publications "
                        "(tenant, key, payload, status, receipt) "
                        "VALUES (?, ?, ?, 'pending', NULL)",
                        (tenant, key, sqlite3.Binary(payload)),
                    )
                elif bytes(row[0]) != payload:
                    raise PublishConflict(
                        "this tenant/key identity was recorded with different payload bytes"
                    )
                self._db.commit()
            except BaseException:
                self._rollback()
                raise

            try:
                # Keep the same-identity decision and resulting state change
                # serialized across Publisher instances. The pending row above
                # is already committed, so a crash rolls this transaction back
                # to a recoverable state.
                self._db.execute("BEGIN IMMEDIATE")
                row = self._read(tenant, key)
                if row is None:
                    raise RuntimeError("publication row disappeared")
                if bytes(row[0]) != payload:
                    raise PublishConflict(
                        "this tenant/key identity was recorded with different payload bytes"
                    )

                status, receipt_json = row[1], row[2]
                if status == "delivered":
                    self._db.commit()
                    return self._response("delivered", json.loads(receipt_json))
                if status == "rejected":
                    self._db.commit()
                    return self._response("rejected")

                # A newly created row has not had an attempt. Existing pending
                # rows must be reconciled before another send is allowed.
                if not inserted:
                    try:
                        receipt = self.transport.lookup(tenant, key)
                    except LookupUnavailable:
                        self._db.commit()
                        return self._response("pending")
                    if receipt is not None:
                        encoded = self._receipt_json(receipt)
                        self._db.execute(
                            "UPDATE publications SET status = 'delivered', receipt = ? "
                            "WHERE tenant = ? AND key = ?",
                            (encoded, tenant, key),
                        )
                        self._db.commit()
                        return self._response("delivered", json.loads(encoded))

                try:
                    receipt = self.transport.send(tenant, key, payload)
                except NotAccepted:
                    self._db.execute(
                        "UPDATE publications SET status = 'rejected', receipt = NULL "
                        "WHERE tenant = ? AND key = ?",
                        (tenant, key),
                    )
                    self._db.commit()
                    return self._response("rejected")
                except TimeoutError:
                    # A timeout says nothing about whether the provider wrote
                    # the file. Preserve pending for lookup on the next call.
                    self._db.commit()
                    return self._response("pending")

                encoded = self._receipt_json(receipt)
                self._db.execute(
                    "UPDATE publications SET status = 'delivered', receipt = ? "
                    "WHERE tenant = ? AND key = ?",
                    (encoded, tenant, key),
                )
                self._db.commit()
                return self._response("delivered", json.loads(encoded))
            except BaseException:
                self._rollback()
                raise

    def close(self):
        """Close only this Publisher's database connection."""
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True
