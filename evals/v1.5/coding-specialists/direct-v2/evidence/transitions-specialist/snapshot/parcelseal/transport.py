"""Explicit synthetic provider semantics; no real network service."""
import hashlib
import json
from pathlib import Path
import threading


class NotAccepted(Exception):
    pass


class LookupUnavailable(Exception):
    pass


class FileTransport:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.fault = None
        self.lookup_unavailable = False
        self.calls = []
        self.closed = False

    def _path(self, tenant, key):
        identity = json.dumps([tenant, key], separators=(",", ":")).encode()
        return self.root / (hashlib.sha256(identity).hexdigest() + ".json")

    def send(self, tenant, key, payload):
        with self.lock:
            self.calls.append((tenant, key))
            fault, self.fault = self.fault, None
            if fault == "reject":
                raise NotAccepted("provider rejected before acceptance")
            if fault == "timeout-before":
                raise TimeoutError("outcome is unknown to caller")
            path = self._path(tenant, key)
            digest = hashlib.sha256(payload).hexdigest()
            if path.exists():
                receipt = json.loads(path.read_text())
                if receipt["digest"] != digest:
                    raise ValueError("provider identity conflict")
            else:
                receipt = {"id": path.stem, "digest": digest, "meta": {"bytes": len(payload)}}
                path.write_text(json.dumps(receipt))
            if fault == "timeout-after":
                raise TimeoutError("outcome is unknown to caller")
            return receipt

    def lookup(self, tenant, key):
        with self.lock:
            if self.lookup_unavailable:
                raise LookupUnavailable("provider lookup unavailable")
            path = self._path(tenant, key)
            return json.loads(path.read_text()) if path.exists() else None

    def effect_count(self):
        return len(list(self.root.glob("*.json")))

    def close(self):
        self.closed = True
