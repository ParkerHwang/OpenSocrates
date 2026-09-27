#!/usr/bin/env python3
"""DepotFlow local same-origin HTTP application. Python 3.10+; no packages."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import sys
import traceback
from urllib.parse import parse_qs, urlsplit

from database import connect, initialize
from service import APIError, authenticate, authorize_mutation, login, mutate, read_route

ROOT = Path(__file__).resolve().parent
MAX_BODY = 1_048_576


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'DepotFlow/1'
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, fmt, *args):
        if os.environ.get('QUIET') != '1':
            super().log_message(fmt, *args)

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=True, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def body(self):
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isdigit():
            raise APIError(400, 'invalid_payload', 'Supply one Content-Length and a JSON body.')
        length = int(lengths[0])
        if length > MAX_BODY:
            raise APIError(413, 'payload_too_large', 'Request body exceeds 1 MiB.')
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise APIError(400, 'invalid_payload', 'Content-Type must be application/json.')
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(data, dict):
                raise ValueError()
            # Reject unpaired surrogates anywhere, including ignored client fields.
            json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            return data
        except (ValueError, UnicodeError, RecursionError):
            raise APIError(400, 'invalid_payload', 'Body must be a valid JSON object, without duplicate keys or nonfinite numbers.') from None

    def handle_request(self):
        db = None
        try:
            split = urlsplit(self.path)
            path = split.path
            if self.command == 'GET' and path == '/api/health':
                return self.send(200, {'status': 'ok'})
            if self.command == 'GET' and path in ('/', '/app.js', '/styles.css', '/favicon.svg'):
                filename, content_type = {'/': ('index.html', 'text/html; charset=utf-8'),
                    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                    '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
                    '/favicon.svg': ('favicon.svg', 'image/svg+xml')}[path]
                return self.send(200, (ROOT / 'static' / filename).read_bytes(), content_type)
            db = connect(self.server.db_path)
            if self.command == 'POST' and path == '/api/session':
                data = self.body()
                # Hashing is outside a write transaction; session insertion is atomic.
                return self.send(200, login(db, data))
            user = authenticate(db, self.headers.get('Authorization'))
            if self.command == 'GET':
                db.execute('BEGIN')
                result = read_route(db, user, path, parse_qs(split.query, keep_blank_values=True))
                db.commit()
                return self.send(200, result)
            if self.command != 'POST':
                raise APIError(405, 'method_not_allowed', 'Use GET or POST for this API.')
            authorize_mutation(user, path)
            if split.query:
                raise APIError(400, 'invalid_payload', 'Mutation URLs do not accept query parameters.')
            data = self.body()
            # Writer lock acquired before checking retry records or reading versions.
            db.execute('BEGIN IMMEDIATE')
            user = authenticate(db, self.headers.get('Authorization'))
            status, result = mutate(db, user, self.command, path, data, self.headers.get('Idempotency-Key'))
            db.commit()
            self.send(status, result)
        except APIError as error:
            if db:
                db.rollback()
            self.close_connection = True
            self.send(error.status, {'error': {'code': error.code, 'message': error.message}})
        except sqlite3.OperationalError as error:
            if db:
                db.rollback()
            self.close_connection = True
            if 'locked' in str(error).lower():
                self.send(503, {'error': {'code': 'busy', 'message': 'The store is busy. Retry with the same Idempotency-Key.'}})
            else:
                traceback.print_exc()
                self.send(500, {'error': {'code': 'internal_error', 'message': 'The request could not be completed.'}})
        except (BrokenPipeError, ConnectionResetError):
            if db:
                db.rollback()
        except Exception:
            if db:
                db.rollback()
            self.close_connection = True
            traceback.print_exc()
            self.send(500, {'error': {'code': 'internal_error', 'message': 'The request could not be completed.'}})
        finally:
            if db:
                db.close()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = handle_request


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


if __name__ == '__main__':
    os.umask(0o077)
    port = int(os.environ.get('PORT', '8000'))
    path = initialize(os.environ.get('DATA_DIR', str(ROOT / '.data')), os.environ.get('SEED_DEMO') == '1')
    with Server(('127.0.0.1', port), Handler) as server:
        server.db_path = path
        print(f'DepotFlow listening on http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
