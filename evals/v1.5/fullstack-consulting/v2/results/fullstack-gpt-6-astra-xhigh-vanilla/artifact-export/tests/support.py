"""Real HTTP process fixture shared by integration and load exercises."""
import http.client
import json
import os
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class App:
    def __init__(self):
        (ROOT / '.test-data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='depot-', dir=ROOT / '.test-data')
        self.data = Path(self.temp.name)
        self.log = open(self.data / 'server.log', 'a+')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.process = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'

    def start(self, seed=True):
        env = os.environ | {'PORT': str(self.port), 'DATA_DIR': str(self.data), 'SEED_DEMO': '1' if seed else '0'}
        self.process = subprocess.Popen([str(ROOT / 'run.sh')], cwd=ROOT, env=env, stdout=self.log, stderr=self.log)
        for _ in range(200):
            if self.process.poll() is not None:
                raise RuntimeError((self.data / 'server.log').read_text())
            try:
                if self.request('GET', '/api/health')[0] == 200:
                    return self
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(.05)
        raise RuntimeError('Server did not start')

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)

    def close(self):
        self.stop()
        self.log.close()
        self.temp.cleanup()

    def request(self, method, path, data=None, token=None, key=None, headers=None, raw=None):
        outgoing = dict(headers or {})
        if token:
            outgoing['Authorization'] = f'Bearer {token}'
        if key is not None:
            outgoing['Idempotency-Key'] = key
        body = raw if raw is not None else json.dumps(data) if data is not None else None
        if body is not None:
            outgoing.setdefault('Content-Type', 'application/json')
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=40)
        try:
            connection.request(method, path, body=body, headers=outgoing)
            response = connection.getresponse()
            content = response.read()
            return response.status, json.loads(content) if response.getheader('Content-Type', '').startswith('application/json') else content.decode()
        finally:
            connection.close()

    def login(self, role='operator', tenant='north'):
        status, data = self.request('POST', '/api/session', {'email': f'{role}@{tenant}.example', 'password': 'DepotDemo!2026'})
        assert status == 200, (status, data)
        return data['token']


def new_key():
    return uuid.uuid4().hex
