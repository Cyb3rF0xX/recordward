"""Server security tests: the guards that make a localhost server safe.

These start a real server on an ephemeral port bound to 127.0.0.1 and make
HTTP requests against it. Each test uses an isolated RECORDWARD_HOME.

Covers:
  * Host-header allowlist (DNS-rebinding defense)
  * strict Content-Security-Policy + nonce, and other security headers
  * POST requires application/json
  * oversized / missing Content-Length rejected
  * note log-injection resistance end to end
  * unknown source and bad reset scope rejected
"""

from __future__ import annotations

import http.client
import importlib
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path


class ServerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bgtest-srv-")
        os.environ["RECORDWARD_HOME"] = self.tmp
        os.environ["RECORDWARD_QUIET"] = "1"

        import recordward.paths as paths
        import recordward.core as core
        import recordward.settings as settings
        import recordward.server as server

        importlib.reload(paths)
        self.core = importlib.reload(core)
        importlib.reload(settings)
        self.server_mod = importlib.reload(server)
        self.core.bootstrap()

        # Bind to an ephemeral port on loopback.
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.server_mod.Handler)
        self.port = self.httpd.server_address[1]
        self.host = f"127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("RECORDWARD_HOME", None)
        os.environ.pop("RECORDWARD_QUIET", None)
        for root, _, files in os.walk(self.tmp, topdown=False):
            for f in files:
                Path(root, f).unlink()
            Path(root).rmdir()

    def req(self, method, path, body=None, headers=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or self.host}
        if headers:
            h.update(headers)
        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=payload, headers=h)
        resp = conn.getresponse()
        data = resp.read()
        status = resp.status
        rheaders = dict(resp.getheaders())
        conn.close()
        return status, data, rheaders


class TestSecurityHeaders(ServerBase):
    def test_csp_and_nonce_present(self):
        status, data, headers = self.req("GET", "/")
        self.assertEqual(status, 200)
        csp = headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'none'", csp)
        self.assertIn("nonce-", csp)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        # the nonce in the header must match the one on the <script> tag
        nonce = csp.split("nonce-")[1].split("'")[0]
        self.assertIn(f'nonce="{nonce}"'.encode(), data)


class TestHostGuard(ServerBase):
    def test_bad_host_rejected(self):
        status, _, _ = self.req("GET", "/", host="evil.com")
        self.assertEqual(status, 421)

    def test_localhost_names_allowed(self):
        for h in (f"127.0.0.1:{self.port}", f"localhost:{self.port}"):
            status, _, _ = self.req("GET", "/", host=h)
            self.assertEqual(status, 200)


class TestEmbeddedCSP(ServerBase):
    def test_browser_mode_has_no_unsafe_eval(self):
        self.server_mod.EMBEDDED = False
        _, _, headers = self.req("GET", "/")
        self.assertNotIn("unsafe-eval", headers.get("Content-Security-Policy", ""))

    def test_embedded_mode_allows_eval_for_webview_bridge(self):
        self.server_mod.EMBEDDED = True
        try:
            _, _, headers = self.req("GET", "/")
            self.assertIn("unsafe-eval", headers.get("Content-Security-Policy", ""))
        finally:
            self.server_mod.EMBEDDED = False  # don't leak into other tests


class TestInputHardening(ServerBase):
    def test_post_requires_json_content_type(self):
        status, _, _ = self.req(
            "POST", "/api/done",
            headers={"Content-Type": "text/plain"},
            body={"name": "x"},
        )
        self.assertEqual(status, 400)

    def test_oversized_content_length_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(
            "POST", "/api/done",
            headers={
                "Host": self.host,
                "Content-Type": "application/json",
                "Content-Length": str(10 * 1024 * 1024),
            },
        )
        # We don't actually send the body; server must reject on the declared
        # length before reading it.
        # (Some stacks need a tiny body to flush headers.)
        try:
            conn.send(b"{}")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
        finally:
            conn.close()

    def test_unknown_source_rejected(self):
        status, data, _ = self.req("POST", "/api/done", body={"name": "nope"})
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(data)["ok"])

    def test_bad_reset_scope_rejected(self):
        status, _, _ = self.req("POST", "/api/reset", body={"what": "lol"})
        self.assertEqual(status, 400)


class TestEndToEnd(ServerBase):
    def test_done_then_status_reflects_it(self):
        name = "Equifax (AnnualCreditReport)"
        status, _, _ = self.req("POST", "/api/done", body={"name": name})
        self.assertEqual(status, 200)
        _, data, _ = self.req("GET", "/api/status")
        statuses = json.loads(data)["statuses"]
        eq = next(s for s in statuses if s["name"] == name)
        self.assertFalse(eq["due"])  # no longer due after recording

    def test_note_injection_stays_one_line(self):
        name = "Equifax (AnnualCreditReport)"
        self.req("POST", "/api/done",
                 body={"name": name, "note": "ok\n2020-01-01 FAKE"})
        history = self.core.HISTORY.read_text(encoding="utf-8")
        # exactly one non-empty line -> no forged second entry
        lines = [ln for ln in history.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
