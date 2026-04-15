#!/usr/bin/env python3
"""
Streamer Tablet Helper — PC Server  v3.0
Receives commands from your tablet over local Wi-Fi and executes them.

Supports: keyboard shortcuts · sounds · OBS WebSocket · Twitch markers
"""

import json, os, sys, socket, subprocess, time, threading, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = 7878

# ─── TOKEN STORAGE ────────────────────────────────────────────────────────────
# Tokens are saved next to this script so they survive restarts
_TOKEN_FILE = Path(__file__).parent / ".twitch_tokens.json"

# ─── OBS CONFIG ───────────────────────────────────────────────────────────────
OBS_HOST     = "localhost"
OBS_PORT     = 4455
OBS_PASSWORD = ""

# ─── TWITCH CONFIG ────────────────────────────────────────────────────────────
# Register a free app at https://dev.twitch.tv/console → set type "Public",
# redirect URI "http://localhost", and copy the Client ID here.
TWITCH_CLIENT_ID = ""   # set via --twitch-client-id or edit here

_twitch_access_token  = ""
_twitch_refresh_token = ""
_twitch_user_id       = ""
_twitch_lock          = threading.Lock()

# ─── NETWORK ──────────────────────────────────────────────────────────────────
def get_local_ip() -> str:
    candidates = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        candidates.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = addr[4][0]
            if not ip.startswith("127."):
                candidates.append(ip)
    except Exception:
        pass
    for ip in candidates:
        if ip.startswith("192.168."): return ip
    for ip in candidates:
        if ip.startswith("10."):      return ip
    return candidates[0] if candidates else "127.0.0.1"

# ─── KEYBOARD ─────────────────────────────────────────────────────────────────
def simulate_keys(keys: list) -> tuple:
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        return True, "OK"
    except ImportError:
        return False, "pyautogui not installed — run: pip install pyautogui"
    except Exception as e:
        return False, str(e)

# ─── SOUND ────────────────────────────────────────────────────────────────────
def play_sound(path: str) -> tuple:
    if not path:        return False, "No path given"
    if not os.path.isfile(path): return False, f"File not found: {path}"
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", path])
        else:
            subprocess.Popen(["aplay", path])
        return True, "Playing"
    except Exception as e:
        return False, str(e)

# ─── OBS WEBSOCKET ────────────────────────────────────────────────────────────
_obs_ws   = None
_obs_lock = threading.Lock()

def obs_connect():
    global _obs_ws
    try:
        import websocket, hashlib, base64
    except ImportError:
        return None, "websocket-client not installed — run: pip install websocket-client"
    with _obs_lock:
        if _obs_ws is not None:
            try:
                _obs_ws.ping()
                return _obs_ws, None
            except Exception:
                _obs_ws = None
        try:
            ws = websocket.WebSocket()
            ws.settimeout(4)
            ws.connect(f"ws://{OBS_HOST}:{OBS_PORT}")
            hello = json.loads(ws.recv())
            auth_data = hello.get("d", {}).get("authentication")
            if auth_data and OBS_PASSWORD:
                secret = base64.b64encode(
                    hashlib.sha256((OBS_PASSWORD + auth_data["salt"]).encode()).digest()
                ).decode()
                auth_resp = base64.b64encode(
                    hashlib.sha256((secret + auth_data["challenge"]).encode()).digest()
                ).decode()
                ws.send(json.dumps({"op": 1, "d": {"rpcVersion": 1, "authentication": auth_resp, "eventSubscriptions": 0}}))
            else:
                ws.send(json.dumps({"op": 1, "d": {"rpcVersion": 1, "eventSubscriptions": 0}}))
            ws.recv()
            _obs_ws = ws
            return ws, None
        except Exception as e:
            return None, str(e)

def obs_request(request_type: str, data: dict = None) -> tuple:
    ws, err = obs_connect()
    if err: return False, err
    try:
        import uuid
        rid = str(uuid.uuid4())[:8]
        payload = {"op": 6, "d": {"requestType": request_type, "requestId": rid, "requestData": data or {}}}
        with _obs_lock:
            ws.send(json.dumps(payload))
            resp = json.loads(ws.recv())
        result = resp.get("d", {}).get("requestStatus", {})
        if result.get("result", False):
            return True, resp.get("d", {}).get("responseData", {})
        else:
            return False, result.get("comment", "OBS error")
    except Exception as e:
        global _obs_ws
        _obs_ws = None
        return False, str(e)

def handle_obs(data: dict) -> tuple:
    cmd = data.get("command", "")
    if cmd == "SetCurrentProgramScene":
        return obs_request("SetCurrentProgramScene", {"sceneName": data.get("scene", "")})
    elif cmd == "StartStream":    return obs_request("StartStream")
    elif cmd == "StopStream":     return obs_request("StopStream")
    elif cmd == "StartRecord":    return obs_request("StartRecord")
    elif cmd == "StopRecord":     return obs_request("StopRecord")
    elif cmd == "ToggleMute":
        return obs_request("ToggleInputMute", {"inputName": data.get("source", "")})
    elif cmd == "SetVolume":
        vol = float(data.get("volume", 1.0))
        return obs_request("SetInputVolume", {"inputName": data.get("source", ""), "inputVolumeMul": max(0.0, min(1.0, vol))})
    elif cmd == "GetSceneList":
        ok, resp = obs_request("GetSceneList")
        if ok:
            return True, {"scenes": [s["sceneName"] for s in resp.get("scenes", [])]}
        return False, resp
    else:
        return False, f"Unknown OBS command: {cmd}"

# ─── TWITCH AUTH ──────────────────────────────────────────────────────────────

def _twitch_api(method: str, path: str, body: dict = None) -> tuple:
    """Make a Twitch Helix API call. Returns (ok, response_dict)."""
    global _twitch_access_token
    if not _twitch_access_token:
        return False, "Not logged in — run: python streamer_helper_server.py --twitch-login"

    url = f"https://api.twitch.tv/helix{path}"
    headers = {
        "Authorization": f"Bearer {_twitch_access_token}",
        "Client-Id":     TWITCH_CLIENT_ID,
        "Content-Type":  "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        # 401 → try token refresh once, then retry
        if e.code == 401:
            ok = _twitch_refresh()
            if ok:
                headers["Authorization"] = f"Bearer {_twitch_access_token}"
                req2 = urllib.request.Request(url, data=data, headers=headers, method=method)
                try:
                    with urllib.request.urlopen(req2, timeout=8) as r2:
                        return True, json.loads(r2.read())
                except Exception as e2:
                    return False, str(e2)
            return False, "Token expired and refresh failed — run --twitch-login again"
        try:
            err_body = json.loads(e.read())
            return False, err_body.get("message", str(e))
        except Exception:
            return False, str(e)
    except Exception as e:
        return False, str(e)

def _twitch_refresh() -> bool:
    """Use the stored refresh token to get a new access token. Returns True on success."""
    global _twitch_access_token, _twitch_refresh_token
    if not _twitch_refresh_token:
        return False
    try:
        params = urllib.parse.urlencode({
            "grant_type":    "refresh_token",
            "refresh_token": _twitch_refresh_token,
            "client_id":     TWITCH_CLIENT_ID,
        }).encode()
        req = urllib.request.Request(
            "https://id.twitch.tv/oauth2/token",
            data=params,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        _twitch_access_token  = data["access_token"]
        _twitch_refresh_token = data["refresh_token"]
        _save_tokens()
        print(f"  ✅ Twitch token refreshed automatically")
        return True
    except Exception as e:
        print(f"  ⚠️  Token refresh failed: {e}")
        return False

def _save_tokens():
    try:
        _TOKEN_FILE.write_text(json.dumps({
            "access_token":  _twitch_access_token,
            "refresh_token": _twitch_refresh_token,
            "user_id":       _twitch_user_id,
        }))
    except Exception as e:
        print(f"  ⚠️  Could not save tokens: {e}")

def _load_tokens() -> bool:
    global _twitch_access_token, _twitch_refresh_token, _twitch_user_id
    if not _TOKEN_FILE.exists():
        return False
    try:
        data = json.loads(_TOKEN_FILE.read_text())
        _twitch_access_token  = data.get("access_token",  "")
        _twitch_refresh_token = data.get("refresh_token", "")
        _twitch_user_id       = data.get("user_id",       "")
        return bool(_twitch_access_token)
    except Exception:
        return False

def _fetch_user_id() -> bool:
    """Get and store the broadcaster's user_id from the token."""
    global _twitch_user_id
    ok, resp = _twitch_api("GET", "/users")
    if ok and resp.get("data"):
        _twitch_user_id = resp["data"][0]["id"]
        _save_tokens()
        return True
    return False

def twitch_login_device_flow():
    """
    Run the Device Code Flow interactively in the terminal.
    The user visits a URL and enters a code — no redirect server needed.
    Call this when --twitch-login is passed.
    """
    global _twitch_access_token, _twitch_refresh_token

    if not TWITCH_CLIENT_ID:
        print()
        print("  ❌  No Twitch Client ID configured!")
        print()
        print("  How to get one (free, takes 2 minutes):")
        print("  1. Go to https://dev.twitch.tv/console")
        print("  2. Click 'Register Your Application'")
        print("  3. Name: anything  |  OAuth Redirect URL: http://localhost")
        print("  4. Category: Other  |  Client Type: Public")
        print("  5. Click Create, then copy the Client ID")
        print()
        print("  Then run:")
        print("  python streamer_helper_server.py --twitch-client-id YOUR_ID --twitch-login")
        print()
        return False

    scope = "channel:manage:broadcast"
    print()
    print("  ── Twitch Login ──────────────────────────────────────────")

    # Step 1: Request device code
    try:
        params = urllib.parse.urlencode({
            "client_id": TWITCH_CLIENT_ID,
            "scopes":    scope,
        }).encode()
        req = urllib.request.Request(
            "https://id.twitch.tv/oauth2/device",
            data=params, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            device_resp = json.loads(r.read())
    except Exception as e:
        print(f"  ❌  Failed to start login: {e}")
        return False

    user_code        = device_resp["user_code"]
    verification_uri = device_resp["verification_uri"]
    device_code      = device_resp["device_code"]
    expires_in       = device_resp.get("expires_in", 300)
    interval         = device_resp.get("interval", 5)

    print()
    print(f"  1. Open this URL in your browser:")
    print(f"     👉  {verification_uri}")
    print()
    print(f"  2. Enter this code when prompted:")
    print(f"     🔑  {user_code}")
    print()
    print("  Waiting for you to authorize… (press Ctrl+C to cancel)")
    print()

    # Try to open the browser automatically
    try:
        import webbrowser
        webbrowser.open(verification_uri)
    except Exception:
        pass

    # Step 2: Poll for the token
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        try:
            poll_params = urllib.parse.urlencode({
                "client_id":   TWITCH_CLIENT_ID,
                "device_code": device_code,
                "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
            }).encode()
            poll_req = urllib.request.Request(
                "https://id.twitch.tv/oauth2/token",
                data=poll_params, method="POST"
            )
            with urllib.request.urlopen(poll_req, timeout=10) as r:
                token_resp = json.loads(r.read())

            _twitch_access_token  = token_resp["access_token"]
            _twitch_refresh_token = token_resp.get("refresh_token", "")

            # Get user ID
            if _fetch_user_id():
                print(f"  ✅  Logged in! User ID: {_twitch_user_id}")
                print(f"  ✅  Token saved to {_TOKEN_FILE.name}")
                print()
                return True
            else:
                print("  ⚠️  Got token but could not fetch user ID — markers may fail")
                _save_tokens()
                return True

        except urllib.error.HTTPError as e:
            # 400 = still waiting, anything else = real error
            if e.code != 400:
                print(f"  ❌  Auth error: {e.code}")
                return False
        except Exception as e:
            print(f"  ❌  Polling error: {e}")
            return False

    print("  ❌  Login timed out — please try again")
    return False


def handle_twitch(data: dict) -> tuple:
    """Handle all Twitch commands from the tablet."""
    cmd = data.get("command", "")

    if cmd == "marker":
        description = data.get("description", "")
        if not _twitch_user_id:
            # Try to fetch user id if we have a token but no id
            if _twitch_access_token:
                _fetch_user_id()
            if not _twitch_user_id:
                return False, "Not logged in to Twitch — run --twitch-login"

        body = {"user_id": _twitch_user_id}
        if description:
            body["description"] = description[:140]  # Twitch max is 140 chars

        ok, resp = _twitch_api("POST", "/streams/markers", body)
        if ok:
            marker = resp.get("data", [{}])[0]
            pos = marker.get("position_seconds", "?")
            desc_echo = marker.get("description", "")
            msg = f"Marker at {pos}s"
            if desc_echo:
                msg += f" — {desc_echo}"
            return True, msg
        else:
            return False, str(resp)

    else:
        return False, f"Unknown Twitch command: {cmd}"

# ─── HTTP HANDLER ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"  {ts}  [{self.address_string()}]  {fmt % args}")

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "http://localhost")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            self.send_json(200, {
                "status":  "ok",
                "server":  "Streamer Tablet Helper",
                "version": "3.0",
                "obs":     bool(OBS_PASSWORD),
                "twitch":  bool(_twitch_access_token),
            })
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
        except Exception:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        action = data.get("action")
        ts = time.strftime("%H:%M:%S")
        print(f"\n  {ts}  → {action}  {json.dumps({k:v for k,v in data.items() if k != 'action'})}")

        if action == "keys":
            keys = [k.strip() for k in data.get("keys", []) if k.strip()]
            if not keys:
                self.send_json(400, {"error": "No keys provided"}); return
            ok, msg = simulate_keys(keys)
            self.send_json(200 if ok else 500, {"ok": ok, "message": msg})

        elif action == "sound":
            ok, msg = play_sound(data.get("path", ""))
            self.send_json(200 if ok else 500, {"ok": ok, "message": msg})

        elif action == "obs":
            ok, msg = handle_obs(data)
            resp = {"ok": ok}
            if isinstance(msg, dict): resp.update(msg)
            else:                     resp["message"] = str(msg)
            self.send_json(200 if ok else 500, resp)

        elif action == "twitch":
            ok, msg = handle_twitch(data)
            self.send_json(200 if ok else 500, {"ok": ok, "message": str(msg)})

        else:
            self.send_json(400, {"error": f"Unknown action: {action}"})

# ─── STARTUP ──────────────────────────────────────────────────────────────────
def print_banner(ip: str):
    W = 62
    print("═" * W)
    print("  🎮  Streamer Tablet Helper — PC Server  v3.0")
    print("═" * W)
    print()
    print("  ┌─ YOUR PC ────────────────────────────────────────────┐")
    print(f"  │  IP Address :  {ip:<38}│")
    print(f"  │  Port       :  {PORT:<38}│")
    print("  └──────────────────────────────────────────────────────┘")
    print()
    print("  Enter this IP in the Streamer Tablet Helper app")
    print("  on your device, then tap CONNECT.")
    print()

def main():
    global OBS_PASSWORD, OBS_HOST, OBS_PORT, TWITCH_CLIENT_ID

    args = sys.argv[1:]
    do_twitch_login = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--obs-password"     and i+1 < len(args): OBS_PASSWORD      = args[i+1]; i += 2
        elif a == "--obs-host"       and i+1 < len(args): OBS_HOST          = args[i+1]; i += 2
        elif a == "--obs-port"       and i+1 < len(args): OBS_PORT          = int(args[i+1]); i += 2
        elif a == "--twitch-client-id" and i+1 < len(args): TWITCH_CLIENT_ID = args[i+1]; i += 2
        elif a == "--twitch-login":                        do_twitch_login   = True; i += 1
        else: i += 1

    # Twitch login flow (interactive, runs before the server starts)
    if do_twitch_login:
        twitch_login_device_flow()
        print("  Starting server…\n")

    ip = get_local_ip()
    print_banner(ip)

    # ── Dependency status ──
    try:
        import pyautogui
        print("  ✅ pyautogui            — keyboard simulation ready")
    except ImportError:
        print("  ⚠️  pyautogui missing    — run: pip install pyautogui")

    if OBS_PASSWORD:
        print(f"  ✅ OBS WebSocket        — {OBS_HOST}:{OBS_PORT}")
    else:
        print("  ℹ️  OBS disabled         — use --obs-password to enable")

    # ── Twitch status ──
    _load_tokens()          # always try to load saved tokens on startup

    if _twitch_access_token:
        # Validate the loaded token silently; refresh if needed
        try:
            req = urllib.request.Request(
                "https://id.twitch.tv/oauth2/validate",
                headers={"Authorization": f"OAuth {_twitch_access_token}"}
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                vdata = json.loads(r.read())
            if not _twitch_user_id:
                global _twitch_user_id
                _twitch_user_id = vdata.get("user_id", "")
                _save_tokens()
            print(f"  ✅ Twitch              — logged in as {vdata.get('login', '?')} (markers ready)")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("  🔄 Twitch token expired, refreshing…")
                if _twitch_refresh():
                    print("  ✅ Twitch              — token refreshed OK")
                else:
                    print("  ⚠️  Twitch token invalid — run: python streamer_helper_server.py --twitch-login")
            else:
                print(f"  ⚠️  Twitch validate error {e.code}")
        except Exception as e:
            print(f"  ⚠️  Twitch validate error: {e}")
    else:
        if TWITCH_CLIENT_ID:
            print("  ℹ️  Twitch not logged in")
            print("       Run: python streamer_helper_server.py --twitch-login")
        else:
            print("  ℹ️  Twitch disabled     — see README for setup")

    print()
    print("  Listening for device button presses…")
    print("  (Press Ctrl+C to stop)")
    print()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  ✋  Server stopped.")

if __name__ == "__main__":
    main()
