#!/usr/bin/env python3
"""
Streamer Tablet Helper — PC Server
Receives commands from your tablet over local Wi-Fi and executes them.
"""

import json
import os
import sys
import socket
import subprocess
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 7878

# ─── OBS WEBSOCKET ────────────────────────────────────────────────────────────
# Filled in once when the user runs: python server.py --obs-password yourpassword
OBS_HOST     = "localhost"
OBS_PORT     = 4455
OBS_PASSWORD = ""   # set via --obs-password or edit here

# ─── NETWORK ──────────────────────────────────────────────────────────────────
def get_local_ip() -> str:
    """Best-effort local LAN IP (no packets actually sent)."""
    candidates = []
    # Method 1: UDP trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        candidates.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    # Method 2: hostname resolution
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = addr[4][0]
            if not ip.startswith("127."):
                candidates.append(ip)
    except Exception:
        pass
    # Prefer 192.168.x.x, then 10.x.x.x, else first found
    for ip in candidates:
        if ip.startswith("192.168."):
            return ip
    for ip in candidates:
        if ip.startswith("10."):
            return ip
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
    if not path:
        return False, "No path given"
    if not os.path.isfile(path):
        return False, f"File not found: {path}"
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
_obs_ws   = None          # persistent websocket connection
_obs_lock = threading.Lock()

def obs_connect():
    """Open (or reuse) a websocket connection to OBS."""
    global _obs_ws
    try:
        import websocket, hashlib, base64, secrets
    except ImportError:
        return None, "websocket-client not installed — run: pip install websocket-client"

    with _obs_lock:
        # Reuse if still open
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

            # Read Hello
            hello = json.loads(ws.recv())
            auth_data = hello.get("d", {}).get("authentication")

            if auth_data and OBS_PASSWORD:
                # OBS auth: SHA256(password + salt) → base64 → SHA256(that + challenge) → base64
                secret = base64.b64encode(
                    hashlib.sha256((OBS_PASSWORD + auth_data["salt"]).encode()).digest()
                ).decode()
                auth_response = base64.b64encode(
                    hashlib.sha256((secret + auth_data["challenge"]).encode()).digest()
                ).decode()
                ws.send(json.dumps({
                    "op": 1,
                    "d": {"rpcVersion": 1, "authentication": auth_response, "eventSubscriptions": 0}
                }))
            else:
                ws.send(json.dumps({"op": 1, "d": {"rpcVersion": 1, "eventSubscriptions": 0}}))

            ws.recv()   # Identified response
            _obs_ws = ws
            return ws, None
        except Exception as e:
            return None, str(e)

def obs_request(request_type: str, data: dict = None) -> tuple:
    """Send one OBS WebSocket request and return (ok, response_dict | error_str)."""
    ws, err = obs_connect()
    if err:
        return False, err
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
        _obs_ws = None   # force reconnect next time
        return False, str(e)

def handle_obs(data: dict) -> tuple:
    cmd = data.get("command", "")

    if cmd == "SetCurrentProgramScene":
        return obs_request("SetCurrentProgramScene", {"sceneName": data.get("scene", "")})

    elif cmd == "StartStream":
        return obs_request("StartStream")

    elif cmd == "StopStream":
        return obs_request("StopStream")

    elif cmd == "StartRecord":
        return obs_request("StartRecord")

    elif cmd == "StopRecord":
        return obs_request("StopRecord")

    elif cmd == "ToggleMute":
        return obs_request("ToggleInputMute", {"inputName": data.get("source", "")})

    elif cmd == "SetVolume":
        vol = float(data.get("volume", 1.0))   # 0.0–1.0 multiplier
        return obs_request("SetInputVolume", {
            "inputName": data.get("source", ""),
            "inputVolumeMul": max(0.0, min(1.0, vol))
        })

    elif cmd == "GetSceneList":
        ok, resp = obs_request("GetSceneList")
        if ok:
            scenes = [s["sceneName"] for s in resp.get("scenes", [])]
            return True, {"scenes": scenes}
        return False, resp

    else:
        return False, f"Unknown OBS command: {cmd}"

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
        # Local-only CORS: only needed if you ever test from a browser on the same machine
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
                "status": "ok",
                "server": "Streamer Tablet Helper",
                "version": "2.0",
                "obs": OBS_PASSWORD != "" or OBS_HOST != "localhost"
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
                self.send_json(400, {"error": "No keys provided"})
                return
            ok, msg = simulate_keys(keys)
            self.send_json(200 if ok else 500, {"ok": ok, "message": msg})

        elif action == "sound":
            ok, msg = play_sound(data.get("path", ""))
            self.send_json(200 if ok else 500, {"ok": ok, "message": msg})

        elif action == "obs":
            ok, msg = handle_obs(data)
            resp = {"ok": ok}
            if isinstance(msg, dict):
                resp.update(msg)
            else:
                resp["message"] = str(msg)
            self.send_json(200 if ok else 500, resp)

        else:
            self.send_json(400, {"error": f"Unknown action: {action}"})

# ─── STARTUP ──────────────────────────────────────────────────────────────────
def check_deps():
    missing = []
    try:
        import pyautogui
    except ImportError:
        missing.append("pyautogui")
    return missing

def print_banner(ip: str):
    W = 60
    print("═" * W)
    print("  🎮  Streamer Tablet Helper — PC Server  v2.0")
    print("═" * W)
    print()
    print("  ┌─ YOUR PC ──────────────────────────────────────┐")
    print(f"  │  IP Address :  {ip:<34}│")
    print(f"  │  Port       :  {PORT:<34}│")
    print("  └────────────────────────────────────────────────┘")
    print()
    print("  Enter this IP in the Streamer Tablet Helper app")
    print(f"  on your tablet, then tap CONNECT.")
    print()

def main():
    global OBS_PASSWORD, OBS_HOST, OBS_PORT

    # Simple CLI args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--obs-password" and i + 1 < len(args):
            OBS_PASSWORD = args[i + 1]; i += 2
        elif args[i] == "--obs-host" and i + 1 < len(args):
            OBS_HOST = args[i + 1]; i += 2
        elif args[i] == "--obs-port" and i + 1 < len(args):
            OBS_PORT = int(args[i + 1]); i += 2
        else:
            i += 1

    ip = get_local_ip()
    print_banner(ip)

    # Dependency check
    missing = check_deps()
    if missing:
        print(f"  ⚠️  Missing packages: {', '.join(missing)}")
        print(f"     Run: pip install {' '.join(missing)}")
        print()
    else:
        print("  ✅ pyautogui ready — keyboard simulation active")

    # OBS status
    if OBS_PASSWORD:
        print(f"  ✅ OBS WebSocket configured  ({OBS_HOST}:{OBS_PORT})")
    else:
        print("  ℹ️  OBS integration: disabled")
        print("     To enable: python server.py --obs-password YOUR_OBS_PASSWORD")

    print()
    print("  Listening for tablet button presses…")
    print("  (Press Ctrl+C to stop)")
    print()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  ✋  Server stopped.")

if __name__ == "__main__":
    main()
