#!/usr/bin/env python3
"""
Streamer Tablet Helper - PC Server  v4.0
Double-click to run. No terminal needed.

Features: keyboard shortcuts / sounds / OBS WebSocket / Twitch markers
GUI:      system tray / status window / settings panel / auto-start
"""

import json, os, sys, socket, subprocess, time, threading, urllib.request, urllib.parse
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path

# ── When packaged with PyInstaller, __file__ lives inside a temp folder.
# We store config next to the .exe / .py instead.
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent

_TOKEN_FILE   = _BASE / ".twitch_tokens.json"
_CONFIG_FILE  = _BASE / "config.json"

PORT = 7878

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  (loaded from config.json, saved on change)
# ─────────────────────────────────────────────────────────────────────────────
_cfg = {
    "obs_password":      "",
    "obs_host":          "localhost",
    "obs_port":          4455,
    "twitch_client_id":  "",
    "start_with_windows": False,
}

def load_config():
    if _CONFIG_FILE.exists():
        try:
            _cfg.update(json.loads(_CONFIG_FILE.read_text()))
        except Exception:
            pass

def save_config():
    try:
        _CONFIG_FILE.write_text(json.dumps(_cfg, indent=2))
    except Exception as e:
        log(f"Could not save config: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING  (thread-safe, fed to the GUI log box)
# ─────────────────────────────────────────────────────────────────────────────
_log_lines   = []
_log_lock    = threading.Lock()
_log_cb      = None   # set by GUI once window is up

def log(msg: str):
    ts  = time.strftime("%H:%M:%S")
    line = f"[{ts}]  {msg}"
    with _log_lock:
        _log_lines.append(line)
        if len(_log_lines) > 500:
            _log_lines.pop(0)
    if _log_cb:
        try:
            _log_cb(line)
        except Exception:
            pass
    else:
        print(line)

# ─────────────────────────────────────────────────────────────────────────────
# NETWORK
# ─────────────────────────────────────────────────────────────────────────────
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
        for addr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
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

# ─────────────────────────────────────────────────────────────────────────────
# KEYBOARD
# ─────────────────────────────────────────────────────────────────────────────
def simulate_keys(keys: list) -> tuple:
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        return True, "OK"
    except ImportError:
        return False, "pyautogui not installed"
    except Exception as e:
        return False, str(e)

# ─────────────────────────────────────────────────────────────────────────────
# SOUND
# ─────────────────────────────────────────────────────────────────────────────
def play_sound(path: str) -> tuple:
    if not path:             return False, "No path given"
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

# ─────────────────────────────────────────────────────────────────────────────
# OBS WEBSOCKET
# ─────────────────────────────────────────────────────────────────────────────
_obs_ws   = None
_obs_lock = threading.Lock()

def obs_connect():
    global _obs_ws
    try:
        import websocket, hashlib, base64
    except ImportError:
        return None, "websocket-client not installed"
    with _obs_lock:
        if _obs_ws is not None:
            try:
                _obs_ws.ping(); return _obs_ws, None
            except Exception:
                _obs_ws = None
        try:
            ws = websocket.WebSocket()
            ws.settimeout(4)
            ws.connect(f"ws://{_cfg['obs_host']}:{_cfg['obs_port']}")
            hello    = json.loads(ws.recv())
            auth_data = hello.get("d", {}).get("authentication")
            pwd = _cfg["obs_password"]
            if auth_data and pwd:
                import base64, hashlib
                secret = base64.b64encode(
                    hashlib.sha256((pwd + auth_data["salt"]).encode()).digest()
                ).decode()
                auth_resp = base64.b64encode(
                    hashlib.sha256((secret + auth_data["challenge"]).encode()).digest()
                ).decode()
                ws.send(json.dumps({"op":1,"d":{"rpcVersion":1,"authentication":auth_resp,"eventSubscriptions":0}}))
            else:
                ws.send(json.dumps({"op":1,"d":{"rpcVersion":1,"eventSubscriptions":0}}))
            ws.recv()
            _obs_ws = ws
            return ws, None
        except Exception as e:
            return None, str(e)

def obs_request(request_type, data=None):
    ws, err = obs_connect()
    if err: return False, err
    try:
        import uuid
        rid = str(uuid.uuid4())[:8]
        payload = {"op":6,"d":{"requestType":request_type,"requestId":rid,"requestData":data or {}}}
        with _obs_lock:
            ws.send(json.dumps(payload))
            resp = json.loads(ws.recv())
        res = resp.get("d",{}).get("requestStatus",{})
        if res.get("result"): return True, resp.get("d",{}).get("responseData",{})
        return False, res.get("comment","OBS error")
    except Exception as e:
        global _obs_ws; _obs_ws = None; return False, str(e)

def handle_obs(data):
    cmd = data.get("command","")
    if   cmd == "SetCurrentProgramScene": return obs_request("SetCurrentProgramScene",{"sceneName":data.get("scene","")})
    elif cmd == "StartStream":   return obs_request("StartStream")
    elif cmd == "StopStream":    return obs_request("StopStream")
    elif cmd == "StartRecord":   return obs_request("StartRecord")
    elif cmd == "StopRecord":    return obs_request("StopRecord")
    elif cmd == "ToggleMute":    return obs_request("ToggleInputMute",{"inputName":data.get("source","")})
    elif cmd == "SetVolume":
        vol = max(0.0, min(1.0, float(data.get("volume",1.0))))
        return obs_request("SetInputVolume",{"inputName":data.get("source",""),"inputVolumeMul":vol})
    return False, f"Unknown OBS command: {cmd}"

# ─────────────────────────────────────────────────────────────────────────────
# TWITCH
# ─────────────────────────────────────────────────────────────────────────────
_twitch_access_token  = ""
_twitch_refresh_token = ""
_twitch_user_id       = ""
_twitch_username      = ""

def _twitch_api(method, path, body=None):
    global _twitch_access_token
    if not _twitch_access_token:
        return False, "Not logged in to Twitch"
    url     = f"https://api.twitch.tv/helix{path}"
    headers = {
        "Authorization": f"Bearer {_twitch_access_token}",
        "Client-Id":     _cfg["twitch_client_id"],
        "Content-Type":  "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            if _twitch_refresh():
                headers["Authorization"] = f"Bearer {_twitch_access_token}"
                req2 = urllib.request.Request(url, data=data, headers=headers, method=method)
                try:
                    with urllib.request.urlopen(req2, timeout=8) as r2:
                        return True, json.loads(r2.read())
                except Exception as e2:
                    return False, str(e2)
            return False, "Token expired - please log in again from Settings"
        try:   return False, json.loads(e.read()).get("message", str(e))
        except: return False, str(e)
    except Exception as e:
        return False, str(e)

def _twitch_refresh():
    global _twitch_access_token, _twitch_refresh_token
    if not _twitch_refresh_token: return False
    try:
        params = urllib.parse.urlencode({
            "grant_type":    "refresh_token",
            "refresh_token": _twitch_refresh_token,
            "client_id":     _cfg["twitch_client_id"],
        }).encode()
        req = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=params, method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        _twitch_access_token  = d["access_token"]
        _twitch_refresh_token = d["refresh_token"]
        _save_twitch_tokens()
        log("Twitch token refreshed automatically")
        return True
    except Exception as e:
        log(f"Twitch token refresh failed: {e}")
        return False

def _save_twitch_tokens():
    try:
        _TOKEN_FILE.write_text(json.dumps({
            "access_token":  _twitch_access_token,
            "refresh_token": _twitch_refresh_token,
            "user_id":       _twitch_user_id,
            "username":      _twitch_username,
        }))
    except Exception as e:
        log(f"Could not save Twitch tokens: {e}")

def _load_twitch_tokens():
    global _twitch_access_token, _twitch_refresh_token, _twitch_user_id, _twitch_username
    if not _TOKEN_FILE.exists(): return False
    try:
        d = json.loads(_TOKEN_FILE.read_text())
        _twitch_access_token  = d.get("access_token",  "")
        _twitch_refresh_token = d.get("refresh_token", "")
        _twitch_user_id       = d.get("user_id",       "")
        _twitch_username      = d.get("username",       "")
        return bool(_twitch_access_token)
    except Exception:
        return False

def _fetch_twitch_user():
    global _twitch_user_id, _twitch_username
    ok, resp = _twitch_api("GET", "/users")
    if ok and resp.get("data"):
        _twitch_user_id  = resp["data"][0]["id"]
        _twitch_username = resp["data"][0]["login"]
        _save_twitch_tokens()
        return True
    return False

def handle_twitch(data):
    cmd  = data.get("command", "")
    if cmd == "marker":
        if not _twitch_user_id:
            if _twitch_access_token: _fetch_twitch_user()
            if not _twitch_user_id:
                return False, "Not logged in to Twitch - open Settings to log in"
        
        desc = data.get("description", "")
        ok, resp = _twitch_api("POST", f"/streams/markers?user_id={_twitch_user_id}&description={urllib.parse.quote(desc)}")
        if ok:
            pos = resp.get("data", [{}])[0].get("position_seconds", 0)
            return True, f"Marker at {pos}s" + (f" - {desc}" if desc else "")
        return False, resp
    return False, f"Unknown Twitch command: {cmd}"

# Twitch Device Code Flow - called from Settings GUI
def twitch_login(on_done):
    """
    1. Get device code
    2. Show URL + Code to user
    3. Poll for token
    """
    def _run():
        if not _cfg["twitch_client_id"]:
            on_done(False, "No Client ID - fill in the Twitch Client ID field first")
            return

        try:
            # Step 1: Request Device Code
            params = urllib.parse.urlencode({
                "client_id": _cfg["twitch_client_id"],
                "scopes":    "channel:manage:broadcast",
            }).encode()
            req = urllib.request.Request("https://id.twitch.tv/oauth2/device", data=params, method="POST")
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read())
            
            # Step 2: Inform user
            # We open the URL automatically for them, but they still need the code
            import webbrowser
            webbrowser.open(d["verification_uri"])
            
            # Use a message box that doesn't block polling
            messagebox.showinfo("Twitch Login", f"A browser window has opened.\n\nPlease enter this code to authorize:\n\n {d['user_code']}")

            # Step 3: Poll
            interval = d.get("interval", 5)
            expires  = time.time() + d.get("expires_in", 300)
            device_code = d["device_code"]

            while time.time() < expires:
                time.sleep(interval)
                poll_params = urllib.parse.urlencode({
                    "client_id":   _cfg["twitch_client_id"],
                    "scopes":      "channel:manage:broadcast",
                    "device_code": device_code,
                    "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
                }).encode()
                
                try:
                    req_poll = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=poll_params, method="POST")
                    with urllib.request.urlopen(req_poll, timeout=8) as r_poll:
                        token_data = json.loads(r_poll.read())
                    
                    global _twitch_access_token, _twitch_refresh_token
                    _twitch_access_token  = token_data["access_token"]
                    _twitch_refresh_token = token_data["refresh_token"]
                    _fetch_twitch_user()
                    on_done(True, f"Logged in as {_twitch_username}")
                    return
                except urllib.error.HTTPError as e_poll:
                    err_body = json.loads(e_poll.read())
                    if err_body.get("message") == "authorization_pending":
                        continue
                    else:
                        on_done(False, err_body.get("message", "Login failed"))
                        return

            on_done(False, "Login timed out - please try again")
        except Exception as e:
            on_done(False, str(e))

    threading.Thread(target=_run, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# HTTP SERVER
# ─────────────────────────────────────────────────────────────────────────────
_connected_clients = set()
_clients_lock      = threading.Lock()

from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default HTTPServer stderr output

    def send_json(self, code, data):
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
        ip = self.client_address[0]
        with _clients_lock:
            _connected_clients.add(ip)
        if self.path == "/ping":
            self.send_json(200, {
                "status":  "ok",
                "server":  "Streamer Tablet Helper",
                "version": "4.0",
                "obs":     bool(_cfg["obs_password"]),
                "twitch":  bool(_twitch_access_token),
            })
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        ip = self.client_address[0]
        with _clients_lock:
            _connected_clients.add(ip)

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
        except Exception:
            self.send_json(400, {"error": "Invalid JSON"}); return

        action = data.get("action", "")
        extras = {k: v for k, v in data.items() if k != "action"}
        log(f"← [{ip}]  {action}  {json.dumps(extras) if extras else ''}")

        if action == "keys":
            keys = [k.strip() for k in data.get("keys", []) if k.strip()]
            if not keys: self.send_json(400, {"error": "No keys"}); return
            ok, msg = simulate_keys(keys)
            log(f"  keys {'✓' if ok else '✗'}  {msg}")
            self.send_json(200 if ok else 500, {"ok": ok, "message": msg})

        elif action == "sound":
            ok, msg = play_sound(data.get("path", ""))
            log(f"  sound {'✓' if ok else '✗'}  {msg}")
            self.send_json(200 if ok else 500, {"ok": ok, "message": msg})

        elif action == "obs":
            ok, msg = handle_obs(data)
            log(f"  OBS {'✓' if ok else '✗'}  {msg}")
            resp = {"ok": ok}
            if isinstance(msg, dict): resp.update(msg)
            else:                     resp["message"] = str(msg)
            self.send_json(200 if ok else 500, resp)

        elif action == "twitch":
            ok, msg = handle_twitch(data)
            log(f"  Twitch {'✓' if ok else '✗'}  {msg}")
            self.send_json(200 if ok else 500, {"ok": ok, "message": str(msg)})

        else:
            self.send_json(400, {"error": f"Unknown action: {action}"})

# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS AUTOSTART  (registry)
# ─────────────────────────────────────────────────────────────────────────────
_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "StreamerTabletHelper"

def set_autostart(enable: bool):
    if sys.platform != "win32": return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            exe = sys.executable if getattr(sys, "frozen", False) else \
                  f'pythonw "{Path(__file__).resolve()}"'
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, exe)
            log("Auto-start enabled")
        else:
            try:    winreg.DeleteValue(key, _REG_NAME)
            except: pass
            log("Auto-start disabled")
        winreg.CloseKey(key)
        _cfg["start_with_windows"] = enable
        save_config()
    except Exception as e:
        log(f"Auto-start error: {e}")

def get_autostart() -> bool:
    if sys.platform != "win32": return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _REG_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────
# Colours
C_BG      = "#0a0c10"
C_SURFACE = "#111520"
C_BORDER  = "#1e2535"
C_ACCENT  = "#00e5ff"
C_GREEN   = "#00ff99"
C_RED     = "#ff3c6e"
C_MUTED   = "#555e7a"
C_TEXT    = "#cdd6f4"
C_TWITCH  = "#9146ff"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Streamer Tablet Helper")
        self.configure(bg=C_BG)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set a taskbar/title-bar icon from the bundled icon if present
        icon_path = _BASE / "icon.ico"
        if icon_path.exists():
            try: self.iconbitmap(str(icon_path))
            except Exception: pass

        self._server_thread = None
        self._httpd         = None
        self._ip            = get_local_ip()
        self._tray          = None

        self._build_ui()
        self._start_server()
        self._validate_twitch_token()
        self._tick()   # periodic UI refresh

        # Minimise to tray on start if autostart is set
        if _cfg.get("start_with_windows") and get_autostart():
            self.after(200, self._minimise_to_tray)

    # ── UI BUILD ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.geometry("560x640")

        # ── Header ──
        hdr = tk.Frame(self, bg=C_SURFACE, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🎮  Streamer Tablet Helper", font=("Segoe UI", 14, "bold"),
                 bg=C_SURFACE, fg=C_ACCENT).pack(side="left", padx=16, pady=14)
        tk.Label(hdr, text="v4.0", font=("Segoe UI", 9),
                 bg=C_SURFACE, fg=C_MUTED).pack(side="left", pady=14)

        sep = tk.Frame(self, bg=C_BORDER, height=1); sep.pack(fill="x")

        # ── Status cards ──
        cards = tk.Frame(self, bg=C_BG, padx=12, pady=10)
        cards.pack(fill="x")

        # IP card
        ip_card = self._card(cards, "YOUR PC IP - enter this in the app")
        self._lbl_ip = tk.Label(ip_card, text=self._ip, font=("Courier New", 22, "bold"),
                                bg=C_SURFACE, fg=C_ACCENT)
        self._lbl_ip.pack(pady=(0, 4))
        btn_row = tk.Frame(ip_card, bg=C_SURFACE)
        btn_row.pack()
        tk.Button(btn_row, text="📋 Copy", font=("Segoe UI", 9), bg=C_BORDER, fg=C_TEXT,
                  relief="flat", cursor="hand2", padx=8, pady=3,
                  command=lambda: self._copy(self._ip)).pack(side="left", padx=4)
        tk.Button(btn_row, text="🔄 Refresh", font=("Segoe UI", 9), bg=C_BORDER, fg=C_TEXT,
                  relief="flat", cursor="hand2", padx=8, pady=3,
                  command=self._refresh_ip).pack(side="left", padx=4)
        ip_card.pack(fill="x", padx=0, pady=(0, 8))

        # Feature status row
        status_row = tk.Frame(self, bg=C_BG, padx=12)
        status_row.pack(fill="x")

        self._dot_server = self._status_dot(status_row, "Server",  C_MUTED)
        self._dot_obs    = self._status_dot(status_row, "OBS",     C_MUTED)
        self._dot_twitch = self._status_dot(status_row, "Twitch",  C_MUTED)
        self._dot_keys   = self._status_dot(status_row, "Keys",    C_MUTED)

        # Devices connected
        self._lbl_devices = tk.Label(status_row, text="0 devices",
                                     font=("Segoe UI", 9), bg=C_BG, fg=C_MUTED)
        self._lbl_devices.pack(side="right", padx=4)

        sep2 = tk.Frame(self, bg=C_BORDER, height=1)
        sep2.pack(fill="x", pady=8)

        # ── Notebook tabs ──
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook",           background=C_BG,      borderwidth=0)
        style.configure("TNotebook.Tab",       background=C_SURFACE, foreground=C_MUTED,
                        padding=[14, 6], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", C_BG)],
                  foreground=[("selected", C_ACCENT)])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._build_log_tab(nb)
        self._build_settings_tab(nb)

    def _card(self, parent, title: str) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=C_BG)
        tk.Label(wrapper, text=title.upper(), font=("Segoe UI", 8), bg=C_BG,
                 fg=C_MUTED, anchor="w").pack(fill="x", pady=(0, 4))
        inner = tk.Frame(wrapper, bg=C_SURFACE, padx=16, pady=12)
        inner.pack(fill="x")
        return inner

    def _status_dot(self, parent, label: str, color: str) -> tk.Label:
        f = tk.Frame(parent, bg=C_BG)
        f.pack(side="left", padx=(0, 12))
        dot = tk.Label(f, text="⬤", font=("Segoe UI", 10), bg=C_BG, fg=color)
        dot.pack(side="left")
        tk.Label(f, text=label, font=("Segoe UI", 9), bg=C_BG, fg=C_MUTED).pack(side="left", padx=(3,0))
        return dot

    # ── LOG TAB ──────────────────────────────────────────────────────────────
    def _build_log_tab(self, nb):
        frame = tk.Frame(nb, bg=C_BG)
        nb.add(frame, text="  Activity Log  ")

        self._log_box = scrolledtext.ScrolledText(
            frame, bg=C_SURFACE, fg=C_TEXT,
            font=("Courier New", 9), relief="flat",
            state="disabled", wrap="word", height=18,
            insertbackground=C_TEXT,
        )
        self._log_box.pack(fill="both", expand=True, padx=0, pady=0)
        self._log_box.tag_config("ok",  foreground=C_GREEN)
        self._log_box.tag_config("err", foreground=C_RED)
        self._log_box.tag_config("dim", foreground=C_MUTED)

        btn_row = tk.Frame(frame, bg=C_BG)
        btn_row.pack(fill="x", pady=6)
        tk.Button(btn_row, text="Clear log", font=("Segoe UI", 9), bg=C_BORDER, fg=C_TEXT,
                  relief="flat", cursor="hand2", padx=8, pady=3,
                  command=self._clear_log).pack(side="right")

        global _log_cb
        _log_cb = self._append_log

        # Replay buffered lines from before the window was ready
        with _log_lock:
            for line in _log_lines:
                self._append_log(line)

    def _append_log(self, line: str):
        def _do():
            self._log_box.configure(state="normal")
            tag = "ok" if "✓" in line else ("err" if "✗" in line else "dim")
            self._log_box.insert("end", line + "\n", tag)
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _clear_log(self):
        with _log_lock:
            _log_lines.clear()
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ── SETTINGS TAB ─────────────────────────────────────────────────────────
    def _build_settings_tab(self, nb):
        outer = tk.Frame(nb, bg=C_BG)
        nb.add(outer, text="  Settings  ")

        canvas = tk.Canvas(outer, bg=C_BG, highlightthickness=0)
        sb     = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        frame  = tk.Frame(canvas, bg=C_BG)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _section(text):
            tk.Label(frame, text=text, font=("Segoe UI", 9, "bold"),
                     bg=C_BG, fg=C_ACCENT).pack(anchor="w", pady=(18, 4), padx=2)
            tk.Frame(frame, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 8))

        def _row(label, widget_fn):
            r = tk.Frame(frame, bg=C_BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=label, font=("Segoe UI", 10), bg=C_BG, fg=C_TEXT,
                     width=20, anchor="w").pack(side="left")
            widget_fn(r)
            return r

        def _entry(parent, value="", **kw):
            e = tk.Entry(parent, bg=C_SURFACE, fg=C_TEXT, insertbackground=C_TEXT,
                         relief="flat", font=("Segoe UI", 10), **kw)
            e.insert(0, value)
            e.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 4))
            return e

        # ── OBS ──────────────────────────────────────────────────────────────
        _section("OBS WEBSOCKET")

        self._obs_pw_var = tk.StringVar(value=_cfg["obs_password"])
        _row("Password", lambda p: _entry(p, _cfg["obs_password"],
                                          textvariable=self._obs_pw_var, show="●"))

        self._obs_host_var = tk.StringVar(value=_cfg["obs_host"])
        _row("Host", lambda p: _entry(p, _cfg["obs_host"], textvariable=self._obs_host_var))

        self._obs_port_var = tk.StringVar(value=str(_cfg["obs_port"]))
        _row("Port", lambda p: _entry(p, str(_cfg["obs_port"]), textvariable=self._obs_port_var, width=8))

        tk.Label(frame, text="Enable in OBS → Tools → WebSocket Server Settings",
                 font=("Segoe UI", 8), bg=C_BG, fg=C_MUTED).pack(anchor="w", padx=2, pady=(0, 4))

        obs_btn_row = tk.Frame(frame, bg=C_BG)
        obs_btn_row.pack(anchor="w", pady=(0, 4))
        tk.Button(obs_btn_row, text="Save OBS Settings", font=("Segoe UI", 9),
                  bg=C_ACCENT, fg="#000", relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._save_obs).pack(side="left", padx=(0, 8))
        tk.Button(obs_btn_row, text="Test Connection", font=("Segoe UI", 9),
                  bg=C_BORDER, fg=C_TEXT, relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._test_obs).pack(side="left")

        # ── TWITCH ───────────────────────────────────────────────────────────
        _section("TWITCH - STREAM MARKERS")

        self._twitch_id_var = tk.StringVar(value=_cfg["twitch_client_id"])
        _row("Client ID", lambda p: _entry(p, _cfg["twitch_client_id"],
                                           textvariable=self._twitch_id_var))

        tk.Label(frame,
                 text="Get a free Client ID at dev.twitch.tv/console\n"
                      "Create app → type Public → redirect http://localhost → copy Client ID",
                 font=("Segoe UI", 8), bg=C_BG, fg=C_MUTED, justify="left"
                 ).pack(anchor="w", padx=2, pady=(0, 6))

        self._lbl_twitch_status = tk.Label(frame, text="Not logged in",
                                           font=("Segoe UI", 9), bg=C_BG, fg=C_MUTED)
        self._lbl_twitch_status.pack(anchor="w", padx=2, pady=(0, 6))
        self._update_twitch_label()

        twitch_btn_row = tk.Frame(frame, bg=C_BG)
        twitch_btn_row.pack(anchor="w", pady=(0, 4))
        self._btn_twitch_login = tk.Button(
            twitch_btn_row, text="🟣 Log in with Twitch", font=("Segoe UI", 9),
            bg=C_TWITCH, fg="#fff", relief="flat", cursor="hand2",
            padx=10, pady=4, command=self._twitch_login_flow)
        self._btn_twitch_login.pack(side="left", padx=(0, 8))
        tk.Button(twitch_btn_row, text="Log out", font=("Segoe UI", 9),
                  bg=C_BORDER, fg=C_TEXT, relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._twitch_logout).pack(side="left")

        # Twitch login status label (shown during auth)
        self._lbl_twitch_auth = tk.Label(frame, text="", font=("Segoe UI", 9),
                                         bg=C_BG, fg=C_MUTED, wraplength=480, justify="left")
        self._lbl_twitch_auth.pack(anchor="w", padx=2, pady=(0, 4))

        # ── GENERAL ──────────────────────────────────────────────────────────
        _section("GENERAL")

        self._autostart_var = tk.BooleanVar(value=get_autostart())
        autostart_row = tk.Frame(frame, bg=C_BG)
        autostart_row.pack(anchor="w", pady=3)
        tk.Checkbutton(autostart_row, text="Start with Windows",
                       variable=self._autostart_var,
                       bg=C_BG, fg=C_TEXT, selectcolor=C_SURFACE,
                       activebackground=C_BG, activeforeground=C_TEXT,
                       font=("Segoe UI", 10), cursor="hand2",
                       command=lambda: set_autostart(self._autostart_var.get())
                       ).pack(side="left")
        if sys.platform != "win32":
            tk.Label(autostart_row, text="(Windows only)", font=("Segoe UI", 8),
                     bg=C_BG, fg=C_MUTED).pack(side="left", padx=6)

        tk.Button(frame, text="Minimise to Tray", font=("Segoe UI", 9),
                  bg=C_BORDER, fg=C_TEXT, relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._minimise_to_tray
                  ).pack(anchor="w", pady=(8, 0))

    # ── OBS ACTIONS ──────────────────────────────────────────────────────────
    def _save_obs(self):
        _cfg["obs_password"] = self._obs_pw_var.get().strip()
        _cfg["obs_host"]     = self._obs_host_var.get().strip() or "localhost"
        try:   _cfg["obs_port"] = int(self._obs_port_var.get().strip())
        except: _cfg["obs_port"] = 4455
        global _obs_ws; _obs_ws = None   # force reconnect
        save_config()
        log("OBS settings saved")
        messagebox.showinfo("Saved", "OBS settings saved.", parent=self)

    def _test_obs(self):
        def _run():
            ok, resp = obs_request("GetVersion")
            if ok:
                ver = resp.get("obsVersion", "?")
                log(f"OBS connected  ✓  version {ver}")
                self.after(0, lambda: messagebox.showinfo("OBS", f"Connected!\nOBS version: {ver}", parent=self))
            else:
                log(f"OBS test failed: {resp}")
                self.after(0, lambda: messagebox.showerror("OBS", f"Could not connect:\n{resp}", parent=self))
        threading.Thread(target=_run, daemon=True).start()

    # ── TWITCH ACTIONS ───────────────────────────────────────────────────────
    def _update_twitch_label(self):
        if _twitch_username:
            self._lbl_twitch_status.config(
                text=f"✓  Logged in as  {_twitch_username}", fg=C_TWITCH)
        elif _twitch_access_token:
            self._lbl_twitch_status.config(text="✓  Logged in", fg=C_TWITCH)
        else:
            self._lbl_twitch_status.config(text="Not logged in", fg=C_MUTED)

    def _twitch_login_flow(self):
        # Save client ID first
        _cfg["twitch_client_id"] = self._twitch_id_var.get().strip()
        save_config()

        self._btn_twitch_login.config(state="disabled")
        self._lbl_twitch_auth.config(text="Starting login…", fg=C_MUTED)

        def on_url(url, code):
            self.after(0, lambda: self._lbl_twitch_auth.config(
                text=f"1. Your browser should open automatically.\n"
                     f"2. If not, visit: {url}\n"
                     f"3. Enter code: {code}\n"
                     f"4. Waiting for you to approve…",
                fg=C_TEXT))

        def on_done(ok, msg):
            def _ui():
                self._btn_twitch_login.config(state="normal")
                self._lbl_twitch_auth.config(text="")
                self._update_twitch_label()
                if ok:
                    log(f"Twitch login successful: {msg}")
                    messagebox.showinfo("Twitch", f"✓  {msg}", parent=self)
                else:
                    log(f"Twitch login failed: {msg}")
                    messagebox.showerror("Twitch", f"Login failed:\n{msg}", parent=self)
            self.after(0, _ui)

        twitch_login_device_flow(on_url, on_done)

    def _twitch_logout(self):
        global _twitch_access_token, _twitch_refresh_token, _twitch_user_id, _twitch_username
        _twitch_access_token = _twitch_refresh_token = _twitch_user_id = _twitch_username = ""
        try: _TOKEN_FILE.unlink()
        except Exception: pass
        self._update_twitch_label()
        log("Twitch logged out")

    # ── SERVER ───────────────────────────────────────────────────────────────
    def _start_server(self):
        def _run():
            try:
                self._httpd = HTTPServer(("0.0.0.0", PORT), Handler)
                log(f"Server started - listening on port {PORT}")
                self._httpd.serve_forever()
            except Exception as e:
                log(f"Server failed to start: {e}")
        self._server_thread = threading.Thread(target=_run, daemon=True)
        self._server_thread.start()

    # ── TWITCH TOKEN VALIDATION on startup ───────────────────────────────────
    def _validate_twitch_token(self):
        if not _twitch_access_token: return
        def _run():
            try:
                req = urllib.request.Request(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": f"OAuth {_twitch_access_token}"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    vdata = json.loads(r.read())
                global _twitch_user_id, _twitch_username
                _twitch_user_id  = vdata.get("user_id",  _twitch_user_id)
                _twitch_username = vdata.get("login",    _twitch_username)
                _save_twitch_tokens()
                log(f"Twitch ready - logged in as {_twitch_username}")
                self.after(0, self._update_twitch_label)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    log("Twitch token expired, refreshing...")
                    if _twitch_refresh():
                        log("Twitch token refreshed")
                        self.after(0, self._update_twitch_label)
                    else:
                        log("Twitch token invalid - please log in again from Settings")
        threading.Thread(target=_run, daemon=True).start()

    # ── PERIODIC TICK ────────────────────────────────────────────────────────
    def _tick(self):
        # Update status dots
        server_ok = self._httpd is not None
        self._dot_server.config(fg=C_GREEN if server_ok else C_RED)

        obs_ok = _cfg.get("obs_password", "") != ""
        self._dot_obs.config(fg=C_GREEN if obs_ok else C_MUTED)

        twitch_ok = bool(_twitch_access_token)
        self._dot_twitch.config(fg=C_TWITCH if twitch_ok else C_MUTED)

        try:
            import pyautogui
            self._dot_keys.config(fg=C_GREEN)
        except ImportError:
            self._dot_keys.config(fg=C_MUTED)

        with _clients_lock:
            n = len(_connected_clients)
        self._lbl_devices.config(
            text=f"{n} device{'s' if n != 1 else ''} seen",
            fg=C_GREEN if n > 0 else C_MUTED)

        self.after(2000, self._tick)

    # ── HELPERS ──────────────────────────────────────────────────────────────
    def _copy(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        log(f"Copied to clipboard: {text}")

    def _refresh_ip(self):
        self._ip = get_local_ip()
        self._lbl_ip.config(text=self._ip)
        log(f"IP refreshed: {self._ip}")

    def _on_close(self):
        if messagebox.askokcancel("Quit",
            "Stop the server?\n\nThe tablet app will lose connection.", parent=self):
            if self._httpd:
                threading.Thread(target=self._httpd.shutdown, daemon=True).start()
            self.destroy()

    def _minimise_to_tray(self):
        """Hide the window. Show a system tray icon if pystray is available."""
        self.withdraw()
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Build a simple icon image if no icon.ico is present
            ico_path = _BASE / "icon.ico"
            if ico_path.exists():
                img = Image.open(str(ico_path))
            else:
                img = Image.new("RGB", (64, 64), "#0a0c10")
                d   = ImageDraw.Draw(img)
                d.ellipse([8, 8, 56, 56], fill="#00e5ff")
                d.text((22, 20), "S", fill="#000000")

            def _show(icon, item):
                icon.stop()
                self._tray = None
                self.after(0, self.deiconify)

            def _quit(icon, item):
                icon.stop()
                if self._httpd:
                    threading.Thread(target=self._httpd.shutdown, daemon=True).start()
                self.after(0, self.destroy)

            menu = pystray.Menu(
                pystray.MenuItem("Open", _show, default=True),
                pystray.MenuItem("Quit", _quit),
            )
            self._tray = pystray.Icon("StreamerTabletHelper", img, "Streamer Tablet Helper", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()

        except ImportError:
            # pystray not installed - just minimise to taskbar normally
            self.iconify()

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    load_config()
    _load_twitch_tokens()

    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
