import json
import logging
import os
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .db import Database
from .service import APIError, authenticate, authorize, bad, canonical, login, mutate, read

STATIC = Path(__file__).resolve().parent / 'static'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'DepotFlow/1'
    protocol_version = 'HTTP/1.1'
    disable_nagle_algorithm = True

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(raw)

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, fmt, *args):
        if os.environ.get('ACCESS_LOG') == '1':
            logging.info('%s %s', self.address_string(), fmt % args)

    def payload(self):
        if self.headers.get('Transfer-Encoding'):
            self.close_connection = True
            bad('Use a Content-Length JSON request; chunked requests are not supported.')
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            self.close_connection = True
            bad('A valid Content-Length is required.')
        size = int(lengths[0])
        if size > 65536:
            self.close_connection = True
            raise APIError(413, 'payload_too_large', 'JSON body must be at most 64 KiB.')
        raw = self.rfile.read(size)
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            bad('Content-Type must be application/json.')
        try:
            payload = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
            # Reject lone Unicode surrogates that SQLite cannot persist.
            json.dumps(payload, ensure_ascii=False).encode('utf-8')
        except (ValueError, UnicodeError, RecursionError):
            bad('Body must be valid JSON with unique object fields.')
        if not isinstance(payload, dict):
            bad('JSON body must be an object.')
        return payload

    def dispatch(self, method):
        try:
            url = urlsplit(self.path)
            path = url.path
            if method == 'GET' and path == '/api/health':
                self.send(200, '{"status":"ok"}')
                return
            if not path.startswith('/api'):
                files = {'/': ('index.html', 'text/html; charset=utf-8'),
                         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                         '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if method != 'GET' or path not in files:
                    raise APIError(404, 'not_found', 'Page not found.')
                name, mime = files[path]
                self.send(200, (STATIC / name).read_bytes(), mime)
                return
            if len(self.path) > 12000:
                bad('Request URL is too long.')
            if method == 'POST' and path != '/api/session':
                # Check identity/role before accepting the payload, without holding a write lock.
                # Authentication is checked again inside the transaction before any replay.
                try:
                    with closing(self.server.db.connect()) as preflight:
                        user = authenticate(preflight, self.headers.get('Authorization', ''))
                        authorize(user, path)
                except APIError:
                    self.close_connection = True
                    raise
            if method not in ('GET', 'POST'):
                self.close_connection = True
            # Consume JSON before opening a database transaction so slow clients do not hold locks.
            payload = self.payload() if method == 'POST' else None
            with closing(self.server.db.connect()) as conn:
                try:
                    conn.execute('BEGIN IMMEDIATE' if method == 'POST' else 'BEGIN')
                    if method == 'POST' and path == '/api/session':
                        result = login(conn, payload)
                        status, body = 200, canonical(result)
                    else:
                        user = authenticate(conn, self.headers.get('Authorization', ''))
                        if method == 'GET':
                            result = read(conn, user, path, parse_qs(url.query, keep_blank_values=True))
                            status, body = 200, canonical(result)
                        elif method == 'POST':
                            if url.query:
                                bad('Mutation endpoints do not accept query parameters.')
                            status, body = mutate(conn, user, path, payload, self.headers.get('Idempotency-Key'))
                        else:
                            raise APIError(405, 'method_not_allowed', 'Use GET for reads and POST for mutations.')
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
            self.send(status, body)
        except APIError as exc:
            self.send(exc.status, canonical({'error': {'code': exc.code, 'message': exc.message}}))
        except sqlite3.OperationalError as exc:
            logging.exception('Database operation failed')
            if 'locked' in str(exc).lower():
                self.send(503, canonical({'error': {'code': 'busy', 'message': 'Store is busy. Retry the same request with the same Idempotency-Key.'}}))
            else:
                self.send(500, canonical({'error': {'code': 'internal_error', 'message': 'The request could not be completed.'}}))
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            logging.exception('Unexpected request failure')
            self.send(500, canonical({'error': {'code': 'internal_error', 'message': 'The request could not be completed. Retry with the same Idempotency-Key.'}}))

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def do_PUT(self):
        self.dispatch('PUT')

    do_DELETE = do_PATCH = do_PUT


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    os.umask(0o077)
    db = Database(os.environ.get('DATA_DIR', 'data'), os.environ.get('SEED_DEMO') == '1')
    port = int(os.environ.get('PORT', '8000'))
    server = Server(('127.0.0.1', port), Handler)
    server.db = db
    print(f'DepotFlow listening on http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
