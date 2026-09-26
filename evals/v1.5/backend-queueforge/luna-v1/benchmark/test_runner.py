import importlib.util, pathlib, subprocess, sys, tempfile, unittest, os, threading, time, http.server
spec=importlib.util.spec_from_file_location('runner',pathlib.Path(__file__).with_name('runner.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Controls(unittest.TestCase):
    def test_payload_size(self): self.assertEqual(len(r.json.dumps(r.PAYLOAD,separators=(',',':')).encode()),256)
    def test_owned_process_resources(self):
        p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);v=r.stop(p)
        self.assertIsNotNone(v['cpu_seconds']);self.assertGreater(v['peak_rss_bytes'],0);self.assertEqual(p.returncode,-15)
    def test_public_total_deadline_trickle(self):
        class Trickle(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Length','1000');self.end_headers()
                try:
                    for _ in range(1000):self.wfile.write(b' ');self.wfile.flush();time.sleep(.01)
                except (OSError,ConnectionError):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Trickle);server.daemon_threads=True
        t=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True);t.start();start=time.monotonic()
        try:
            with self.assertRaises(Exception):r.public(f'http://127.0.0.1:{server.server_port}','t','/',deadline=start+.15)
            self.assertLess(time.monotonic()-start,.5)
        finally:server.shutdown();server.server_close();t.join()
    def test_size_and_cap_predicate(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);(p/'a.sqlite').write_bytes(b'abc');(p/'b.sqlite-wal').write_bytes(b'xyz');(p/'refs.json').write_bytes(b'not database')
            self.assertEqual(r.size_tree(p),6);old=r.MAX_DATA;r.MAX_DATA=5
            try:
                with self.assertRaises(RuntimeError):r.check_cap(p)
            finally:r.MAX_DATA=old
if __name__=='__main__':unittest.main()
