"""Real HTTP/subprocess harness shared by integration tests and load exercises."""
import json
import os
import select
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
LOCAL.mkdir(exist_ok=True)


class RunningServer:
    def __init__(self, directory=None, seed=True):
        self.temporary = tempfile.TemporaryDirectory(prefix='depotflow-', dir=LOCAL) if directory is None else None
        self.directory = Path(directory or self.temporary.name)
        self.seed = seed
        self.process = None
        self.start()

    def start(self):
        env = dict(os.environ, PORT='0', DATA_DIR=str(self.directory), SEED_DEMO='1' if self.seed else '0', PYTHON=sys.executable)
        self.log = open(self.directory / 'server.log', 'a')
        self.process = subprocess.Popen([str(ROOT / 'run.sh')], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                        stderr=self.log, text=True)
        ready, _, _ = select.select([self.process.stdout], [], [], 20)
        if not ready:
            self.stop()
            raise RuntimeError('Server did not announce readiness within 20 seconds')
        line = self.process.stdout.readline().strip()
        if not line.startswith('DepotFlow listening on '):
            raise RuntimeError(f'Server startup failed: {line}; see {self.directory / "server.log"}')
        self.base = line.split(' on ', 1)[1]

    def stop(self, kill=False):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill() if kill else self.process.terminate()
                self.process.wait(timeout=10)
            self.process.stdout.close()
            self.log.close()
            self.process = None

    def restart(self, kill=False):
        self.stop(kill=kill)
        self.start()

    def close(self):
        self.stop()
        if self.temporary:
            self.temporary.cleanup()

    def request(self, method, path, payload=None, token=None, key=None, raw=None, headers=None):
        headers = dict(headers or {})
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if key is not None:
            headers['Idempotency-Key'] = key
        if payload is not None:
            raw = json.dumps(payload).encode()
        if raw is not None:
            headers.setdefault('Content-Type', 'application/json')
        req = urllib.request.Request(self.base + path, data=raw, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as response:
            return response.code, json.loads(response.read())

    def login(self, role='operator', tenant='north'):
        status, body = self.request('POST', '/api/session', {'email': f'{role}@{tenant}.example', 'password': 'DepotDemo!2026'})
        assert status == 200, (status, body)
        return body['token']


def new_key():
    return str(uuid.uuid4())
