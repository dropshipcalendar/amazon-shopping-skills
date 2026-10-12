"""Short-lived loopback credential form. No Tk, external assets, or secret logging."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
import webbrowser

from credential_store import NAMES
from workflow import WorkflowError

ASSETS = Path(__file__).resolve().parents[1] / "assets"
FILES = {"/": ("setup.html", "text/html; charset=utf-8"),
         "/setup.css": ("setup.css", "text/css; charset=utf-8"),
         "/setup.js": ("setup.js", "text/javascript; charset=utf-8"),
         "/logo.png": ("dropship-calendar.png", "image/png")}
MAX_BODY = 32768
SESSION_SECONDS = 900


def credential_values(fields):
    if not isinstance(fields, dict) or set(fields) - set(NAMES):
        raise ValueError("Invalid fields")
    if any(not isinstance(value, str) or len(value) > 4096 or
           any(char in value for char in "\r\n\0") for value in fields.values()):
        raise ValueError("Invalid fields")
    return {name: value for name, value in fields.items() if value}


def save_credentials(account, fields, saver):
    values = credential_values(fields)
    try:
        return saver(account, {}, values, replace_credentials=True)
    finally:
        values.clear()


class SetupServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False

    def __init__(self, account, saver, ttl=SESSION_SECONDS):
        self.account, self.saver = account, saver
        self.token = secrets.token_urlsafe(32)
        self.deadline = time.monotonic() + ttl
        self.finished = False
        self.session_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), SetupHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"
        self.url = self.origin + "/#" + self.token

    def handle_error(self, request, client_address):
        # Default tracebacks could include application exception diagnostics.
        pass

    def finish(self):
        self.finished = True
        self.token = ""


class SetupHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LocalSetup"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        pass

    def respond(self, status, body=b"", content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        # Never reflect request paths, headers, or supplied diagnostics.
        self.respond(code, b'{"status":"rejected"}')

    def valid_host(self):
        return self.headers.get_all("Host", []) == [self.server.host]

    def expired(self):
        return self.server.finished or time.monotonic() >= self.server.deadline

    def do_GET(self):
        if not self.valid_host():
            return self.send_error(403)
        if self.expired():
            return self.send_error(410)
        asset = FILES.get(self.path)
        if asset is None:
            return self.send_error(404)
        try:
            data = (ASSETS / asset[0]).read_bytes()
        except OSError:
            return self.send_error(503)
        self.respond(200, data, asset[1])

    def do_OPTIONS(self):
        self.send_error(403)

    def do_POST(self):
        if not self.valid_host() or self.headers.get_all("Origin", []) != [self.server.origin]:
            return self.send_error(403)
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin"):
            return self.send_error(403)
        tokens = self.headers.get_all("X-Setup-Token", [])
        if len(tokens) != 1 or not tokens[0].isascii():
            return self.send_error(403)
        if self.path != "/action" or self.headers.get_all("Content-Type", []) != ["application/json"]:
            return self.send_error(400)
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            return self.send_error(400)
        length = int(lengths[0])
        if not 0 < length <= MAX_BODY:
            return self.send_error(413)
        with self.server.session_lock:
            if self.expired():
                return self.send_error(410)
            if not secrets.compare_digest(tokens[0], self.server.token):
                return self.send_error(403)
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("Incomplete request")
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError("Invalid action")
                action = payload.get("action")
                if action == "later" and set(payload) == {"action"}:
                    response = b'{"status":"later"}'
                elif action == "save" and set(payload) == {"action", "credentials"}:
                    credential_values(payload["credentials"])
                    try:
                        save_credentials(self.server.account, payload["credentials"], self.server.saver)
                    except Exception:
                        return self.respond(503, b'{"status":"save_failed"}')
                    response = b'{"status":"saved"}'
                else:
                    raise ValueError("Invalid action")
            except (ValueError, UnicodeError):
                return self.send_error(400)
            finally:
                # Best-effort reference release; Python strings cannot be zeroized.
                if "payload" in locals() and isinstance(payload, dict):
                    credentials = payload.get("credentials")
                    if isinstance(credentials, dict):
                        credentials.clear()
                raw = b""
            self.server.finish()
            try:
                self.respond(200, response)
            finally:
                threading.Thread(target=self.server.shutdown, daemon=True).start()


@contextmanager
def running_server(account, saver, ttl=SESSION_SECONDS):
    server = SetupServer(account, saver, ttl)
    def expire():
        with server.session_lock:
            server.finish()
        server.shutdown()
    timer = threading.Timer(ttl, expire)
    timer.daemon = True
    timer.start()
    try:
        yield server
    finally:
        timer.cancel()
        server.finish()
        server.server_close()


def show_setup(account, save_settings, *, open_browser=True, ready=None):
    try:
        with running_server(account, save_settings) as server:
            if ready:
                ready({"setup_url": server.url, "expires_in_seconds": SESSION_SECONDS})
            if open_browser:
                webbrowser.open(server.url, new=1)
            server.serve_forever(poll_interval=0.1)
    except OSError:
        raise WorkflowError("Local setup unavailable; run setup.py configure ACCOUNT_ID --prompt in your own terminal") from None
