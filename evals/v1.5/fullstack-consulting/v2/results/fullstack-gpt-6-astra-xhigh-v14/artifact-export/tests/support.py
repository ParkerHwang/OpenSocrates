"""Real subprocess and HTTP helpers shared by integration tests and benchmarks."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


class RunningApp:
    def __init__(self, seed=True):
        (ROOT / '.test-data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='store-', dir=ROOT / '.test-data')
        self.directory = Path(self.temp.name)
        self.log = open(self.directory / 'server.log', 'w+')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.process = None
        self.seed = seed
        self.start()

    @property
    def db_path(self):
        return self.directory / 'depotflow.sqlite3'

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'

    def start(self):
        self.process = subprocess.Popen([str(ROOT / 'run.sh')], cwd=ROOT,
            env={**os.environ, 'PORT': str(self.port), 'DATA_DIR': str(self.directory),
                 'SEED_DEMO': '1' if self.seed else '0', 'QUIET': '1'}, stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.log.seek(0)
                raise RuntimeError(self.log.read())
            try:
                if self.request('GET', '/api/health')[0] == 200:
                    return
            except OSError:
                time.sleep(.03)
        raise RuntimeError('Server did not become ready.')

    def stop(self, hard=False):
        if self.process and self.process.poll() is None:
            self.process.kill() if hard else self.process.terminate()
            self.process.wait(timeout=10)

    def restart(self, hard=False):
        self.stop(hard)
        self.start()

    def close(self):
        self.stop()
        self.log.close()
        self.temp.cleanup()

    def request(self, method, path, data=None, token=None, key=None, headers=None, raw=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=25)
        request_headers = {'Content-Type': 'application/json'}
        if token:
            request_headers['Authorization'] = f'Bearer {token}'
        if key is not None:
            request_headers['Idempotency-Key'] = key
        request_headers.update(headers or {})
        body = raw if raw is not None else json.dumps(data) if data is not None else None
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            payload = response.read()
            content = json.loads(payload) if 'application/json' in response.getheader('Content-Type', '') else payload.decode()
            return response.status, content
        finally:
            connection.close()

    def login(self, role='admin', tenant='north'):
        status, body = self.request('POST', '/api/session', {'email': f'{role}@{tenant}.example', 'password': 'DepotDemo!2026'})
        assert status == 200, body
        return body['token']


def key():
    return str(uuid.uuid4())
