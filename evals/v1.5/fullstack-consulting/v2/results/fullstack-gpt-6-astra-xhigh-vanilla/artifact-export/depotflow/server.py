import json
import logging
import os
import signal
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import db, service

STATIC = Path(__file__).resolve().parent.parent / 'static'
MAX_BODY = 128 * 1024


def reject_constant(value):
    raise ValueError('Non-finite JSON number')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


class Handler(BaseHTTPRequestHandler):
    server_version = 'DepotFlow/1.0'
    protocol_version = 'HTTP/1.1'
    disable_nagle_algorithm = True

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, fmt, *args):
        if os.environ.get('ACCESS_LOG') == '1':
            logging.info('%s %s', self.address_string(), fmt % args)

    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body, separators=(',', ':'), ensure_ascii=True)
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def json_body(self):
        if self.headers.get('Transfer-Encoding'):
            service.fail(400, 'invalid_payload', 'Chunked request bodies are not supported.')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            service.fail(400, 'invalid_payload', 'Invalid Content-Length.')
        if not 0 < length <= MAX_BODY:
            service.fail(400, 'invalid_payload', 'A JSON object body of at most 128 KiB is required.')
        if self.headers.get_content_type() != 'application/json':
            service.fail(400, 'invalid_payload', 'Content-Type must be application/json.')
        try:
            data = json.loads(self.rfile.read(length), parse_constant=reject_constant, object_pairs_hook=unique_object)
            # Also reject deeply nested input and non-UTF8 surrogate text before persistence.
            json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, UnicodeError, RecursionError):
            service.fail(400, 'invalid_json', 'Body must be valid JSON without duplicate keys or non-finite numbers.')
        if not isinstance(data, dict):
            service.fail(400, 'invalid_payload', 'Body must be a JSON object.')
        return data

    def handle_request(self):
        connection = None
        try:
            parsed = urlsplit(self.path)
            path = parsed.path
            if self.command == 'GET' and path == '/api/health':
                self.respond(200, {'status': 'ok'})
                return
            if not path.startswith('/api'):
                assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/mobile.css': ('mobile.css', 'text/css; charset=utf-8'),
                          '/styles.css': ('styles.css', 'text/css; charset=utf-8')}
                if self.command != 'GET' or path not in assets:
                    service.fail(404, 'not_found', 'Route not found.')
                filename, content_type = assets[path]
                self.respond(200, (STATIC / filename).read_bytes(), content_type)
                return
            connection = db.connect(self.server.db_path)
            if self.command == 'POST' and path == '/api/session':
                self.respond(200, service.login(connection, self.json_body()))
                return
            user = service.authenticate(connection, self.headers.get('Authorization'))
            if self.command == 'GET':
                connection.execute('BEGIN')
                result = service.read(connection, user, path, parse_qs(parsed.query, keep_blank_values=True))
                connection.commit()
                self.respond(200, result)
            elif self.command == 'POST':
                service.authorize(user, path)
                if parsed.query:
                    service.fail(400, 'invalid_filter', 'Mutation routes do not accept query parameters.')
                status, body = service.mutation(connection, user, path, self.headers.get('Idempotency-Key'), self.json_body())
                self.respond(status, body)
            else:
                service.fail(405, 'method_not_allowed', 'Use GET or POST for this API.')
        except service.APIError as exc:
            self.close_connection = True  # Invalid/unauthorized bodies may be unread.
            if connection:
                connection.rollback()
            self.respond(exc.status, {'error': {'code': exc.code, 'message': exc.message}})
        except sqlite3.OperationalError:
            if connection:
                connection.rollback()
            logging.exception('Database operation failed')
            self.respond(503, {'error': {'code': 'database_busy', 'message': 'Storage is busy. Retry with the same Idempotency-Key.'}})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            if connection:
                connection.rollback()
            logging.exception('Unhandled request error')
            self.respond(500, {'error': {'code': 'internal_error', 'message': 'Unexpected server error. Retry with the same Idempotency-Key.'}})
        finally:
            if connection:
                connection.close()

    do_GET = handle_request
    do_POST = handle_request
    do_PUT = handle_request
    do_PATCH = handle_request
    do_DELETE = handle_request
    do_OPTIONS = handle_request
    do_HEAD = handle_request


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    data_dir = Path(os.environ.get('DATA_DIR', '.data')).resolve()
    database = data_dir / 'depotflow.sqlite3'
    db.initialize(database, os.environ.get('SEED_DEMO') == '1')
    server = Server(('127.0.0.1', int(os.environ.get('PORT', '8000'))), Handler)
    server.db_path = database
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    logging.info('DepotFlow listening on http://127.0.0.1:%s (data: %s)', server.server_port, data_dir)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
