import json
import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.environ.get("YT_SYNC_HOST", "127.0.0.1")
PORT = int(os.environ.get("YT_SYNC_PORT", "8765"))
TOKEN = os.environ.get("YT_SYNC_TOKEN", secrets.token_urlsafe(18))
PUBLIC_URL = os.environ.get("YT_SYNC_PUBLIC_URL", "").strip()
STATE_FILE = os.environ.get(
    "YT_SYNC_STATE_FILE",
    os.path.join(os.path.dirname(__file__), "yt_sync_remote_state.json"),
)

state_store = {
    "revision": 0,
    "updated_at": 0,
    "type": "INIT",
    "sender": None,
    "timestamp": 0,
    "state": None,
    "jam_control_enabled": False,
}


def load_state_from_disk():
    global state_store
    if not os.path.exists(STATE_FILE):
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            state_store.update(data)
    except Exception:
        pass


def save_state_to_disk():
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state_store, file, ensure_ascii=True, indent=2)


def is_authorized(handler):
    expected = f"Bearer {TOKEN}"
    return handler.headers.get("Authorization", "") == expected


def is_local_request(handler):
    address = getattr(handler, "client_address", ("", 0))[0]
    return address in ("127.0.0.1", "::1", "localhost")


class SyncHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[yt-sync-server] {self.address_string()} - {fmt % args}")

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "revision": state_store.get("revision", 0),
                    "updated_at": state_store.get("updated_at", 0),
                },
            )
            return

        if self.path == "/state":
            if not is_authorized(self):
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return

            self._send_json(200, state_store)
            return

        if self.path == "/runtime":
            if not is_local_request(self):
                self._send_json(403, {"ok": False, "error": "local_only"})
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "public_url": PUBLIC_URL,
                    "token": TOKEN,
                },
            )
            return

        if self.path == "/config":
            if not is_authorized(self):
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "jam_control_enabled": bool(state_store.get("jam_control_enabled", False)),
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path == "/config":
            if not is_authorized(self):
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self._send_json(400, {"ok": False, "error": "invalid_json"})
                return

            state_store["jam_control_enabled"] = bool(payload.get("jam_control_enabled", False))
            save_state_to_disk()
            self._send_json(
                200,
                {
                    "ok": True,
                    "jam_control_enabled": state_store["jam_control_enabled"],
                },
            )
            return

        if self.path != "/publish":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        if not is_authorized(self):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

        packet_state = payload.get("state")
        if not isinstance(packet_state, dict) or not packet_state.get("video_id"):
            self._send_json(400, {"ok": False, "error": "invalid_state"})
            return

        sender_role = payload.get("sender_role", "client")
        jam_control_enabled = bool(state_store.get("jam_control_enabled", False))
        if sender_role != "host" and not jam_control_enabled:
            self._send_json(403, {"ok": False, "error": "jam_control_disabled"})
            return

        state_store["revision"] = int(state_store.get("revision", 0)) + 1
        state_store["updated_at"] = int(time.time() * 1000)
        state_store["type"] = payload.get("type", "STATE_SNAPSHOT")
        state_store["sender"] = payload.get("sender")
        state_store["timestamp"] = int(payload.get("timestamp") or state_store["updated_at"])
        state_store["state"] = packet_state
        save_state_to_disk()

        self._send_json(200, {"ok": True, "revision": state_store["revision"]})


def main():
    load_state_from_disk()

    print("[yt-sync-server] starting")
    print(f"[yt-sync-server] host={HOST}")
    print(f"[yt-sync-server] port={PORT}")
    print(f"[yt-sync-server] token={TOKEN}")
    print(f"[yt-sync-server] state_file={STATE_FILE}")

    server = ThreadingHTTPServer((HOST, PORT), SyncHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[yt-sync-server] stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
