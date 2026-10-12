"""Exercise the real loopback HTTP boundary with synthetic credentials only."""
import contextlib
import http.client
import io
import json
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import setup_ui


class SetupServerTests(unittest.TestCase):
    def setUp(self):
        self.saved = []
        def save(account, settings, values, **kwargs):
            self.saved.append((settings.copy(), values.copy(), kwargs.copy()))
        self.server = setup_ui.SetupServer(object(), save)
        self.token = self.server.token
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method="POST", path="/action", payload=None, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        if raw is None and method == "POST":
            raw = json.dumps(payload or {"action": "save", "credentials": {"AGENTMAIL_API_KEY": "synthetic-secret"}})
        actual = {"Origin": self.server.origin, "Content-Type": "application/json", "X-Setup-Token": self.token}
        actual.update(headers or {})
        actual = {key: value for key, value in actual.items() if value is not None}
        try:
            connection.request(method, path, body=raw, headers=actual)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_loopback_only_and_html_has_no_token_or_saved_values(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertNotIn(self.token.encode(), body)
        self.assertNotIn(b"synthetic-secret", body)
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_assets_are_local_and_arbitrary_files_are_not_served(self):
        for path in ("/setup.css", "/setup.js", "/logo.png"):
            self.assertEqual(self.request("GET", path)[0], 200)
        for path in ("/../scripts/credential_store.py", "/status", "/?key=synthetic-secret", "/config.json"):
            status, _, body = self.request("GET", path)
            self.assertEqual(status, 404)
            self.assertNotIn(b"synthetic-secret", body)

    def test_save_only_updates_supplied_credentials_and_consumes_token(self):
        status, _, body = self.request(payload={"action": "save", "credentials": {"AGENTMAIL_API_KEY": "synthetic-secret", "TEXTVERIFIED_API_KEY": ""}})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "saved"})
        self.assertEqual(self.saved, [({}, {"AGENTMAIL_API_KEY": "synthetic-secret"}, {"replace_credentials": True})])
        self.assertTrue(self.server.finished)
        self.assertEqual(self.server.token, "")
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def test_configure_later_performs_no_write(self):
        self.assertEqual(self.request(payload={"action": "later"})[0], 200)
        self.assertFalse(self.saved)
        self.assertTrue(self.server.finished)

    def test_wrong_missing_or_cross_origin_requests_do_not_save(self):
        for headers in ({"Origin": "https://untrusted.example"}, {"Origin": None},
                        {"Host": "untrusted.example"}, {"X-Setup-Token": None},
                        {"X-Setup-Token": "incorrect"}, {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 403)
        self.assertFalse(self.saved)
        self.assertFalse(self.server.finished)

    def test_cors_preflight_and_form_posts_are_rejected(self):
        status, headers, _ = self.request("OPTIONS")
        self.assertEqual(status, 403)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.request(headers={"Content-Type": "application/x-www-form-urlencoded"})[0], 400)
        self.assertFalse(self.saved)

    def test_invalid_or_excessive_payloads_never_save(self):
        for payload in ([], {"action": "save", "credentials": {"AMAZON_PASSWORD": "no"}},
                        {"action": "save", "credentials": {"AGENTMAIL_API_KEY": ["no"]}},
                        {"action": "save", "credentials": {"AGENTMAIL_API_KEY": "bad\nvalue"}},
                        {"action": "save", "credentials": {}, "sms_max_total_usd": "100"},
                        {"action": "later", "credentials": {}}):
            self.assertEqual(self.request(raw=json.dumps(payload))[0], 400)
        self.assertEqual(self.request(raw="not-json")[0], 400)
        self.assertEqual(self.request(raw="x" * (setup_ui.MAX_BODY + 1))[0], 413)
        self.assertEqual(self.request(headers={"Transfer-Encoding": "chunked"})[0], 400)
        self.assertFalse(self.saved)

    def test_expired_session_cannot_load_or_save(self):
        self.server.deadline = time.monotonic() - 1
        self.assertEqual(self.request()[0], 410)
        self.assertEqual(self.request("GET", "/")[0], 410)
        self.assertFalse(self.saved)

    def test_save_failure_is_sanitized_and_can_retry(self):
        original = self.server.saver
        def fail(*args, **kwargs):
            raise RuntimeError("synthetic-secret-in-exception")
        self.server.saver = fail
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            status, _, body = self.request()
        self.assertEqual(status, 503)
        self.assertEqual(body, b'{"status":"save_failed"}')
        self.assertNotIn("synthetic-secret", out.getvalue() + err.getvalue())
        self.assertFalse(self.server.finished)
        self.server.saver = original
        self.assertEqual(self.request()[0], 200)

    def test_duplicate_host_origin_or_token_headers_are_rejected(self):
        for header, value in (("Host", self.server.host), ("Origin", self.server.origin), ("X-Setup-Token", self.token)):
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
            body = b'{"action":"later"}'
            try:
                connection.putrequest("POST", "/action", skip_host=True)
                for key, item in (("Host", self.server.host), ("Origin", self.server.origin),
                                  ("X-Setup-Token", self.token), ("Content-Type", "application/json"),
                                  ("Content-Length", str(len(body))), (header, value)):
                    connection.putheader(key, item)
                connection.endheaders(body)
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
            finally:
                connection.close()
        self.assertFalse(self.saved)

    def test_replayed_post_is_rejected_even_before_listener_stops(self):
        with patch.object(self.server, "shutdown"):
            self.assertEqual(self.request()[0], 200)
            self.assertEqual(self.request()[0], 410)
        self.assertEqual(len(self.saved), 1)

    def test_request_paths_and_payloads_are_not_logged(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            self.request("GET", "/synthetic-secret")
            self.request(raw="synthetic-secret-invalid-json")
        self.assertEqual(out.getvalue() + err.getvalue(), "")

    def test_timeout_stops_listener(self):
        with setup_ui.running_server(object(), lambda *a, **k: None, ttl=0.05) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertTrue(server.finished)


if __name__ == "__main__":
    unittest.main()
