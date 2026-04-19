#!/usr/bin/env python3
"""
Streamer Tablet Helper - PC Server
Double-click to run. No terminal needed.

Features: keyboard shortcuts / sounds / OBS WebSocket / Twitch markers
GUI:      system tray / status window / settings panel / auto-start
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import socket
import subprocess
import time
import threading
import urllib.request
import urllib.parse
import webbrowser
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from pathlib import Path

# ── CustomTkinter setup
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── When packaged with PyInstaller, __file__ lives inside a temp folder.
# We store config next to the .exe / .py instead.
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent

_CONFIG_FILE = _BASE / "config.json"

PORT = 7878

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  (loaded from config.json, saved on change)
# ─────────────────────────────────────────────────────────────────────────────
_cfg = {
    "obs_password":      "",
    "obs_host":          "localhost",
    "obs_port":          4455,
    "twitch_client_id":  "",
    "twitch_access_token": "",
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
_log_lines = []
_log_lock = threading.Lock()
_log_cb = None   # set by GUI once window is up


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
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


def mask_ip(ip: str) -> str:
    """Masks an IP address for privacy (e.g. 192.168.0.1 -> 192.168.x.x)"""
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.x.x"
    return "x.x.x.x"

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
        if ip.startswith("192.168."):
            return ip
    for ip in candidates:
        if ip.startswith("10."):
            return ip
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
    if not path:
        return False, "No path given"
    if not os.path.isfile(path):
        return False, f"File not found: {path}"
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME |
                               winsound.SND_ASYNC)
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
_obs_ws = None
_obs_lock = threading.Lock()
_obs_connected = False   # Track actual connection state


def obs_connect():
    global _obs_ws, _obs_connected
    try:
        import websocket
        import hashlib
        import base64
    except ImportError:
        _obs_connected = False
        return None, "websocket-client not installed"
    with _obs_lock:
        if _obs_ws is not None:
            try:
                _obs_ws.ping()
                _obs_connected = True
                return _obs_ws, None
            except Exception:
                _obs_ws = None
        try:
            ws = websocket.WebSocket()
            ws.settimeout(4)
            ws.connect(f"ws://{_cfg['obs_host']}:{_cfg['obs_port']}")

            # 1. Receive Hello (op 0)
            hello_raw = ws.recv()
            if not hello_raw:
                return None, "Connection closed by OBS immediately."
            hello = json.loads(hello_raw)

            if hello.get("op") != 0:
                return None, f"Expected Hello (op 0), got {hello.get('op')}. Are you using OBS WebSocket 4.x? This app requires 5.x."

            auth_data = hello.get("d", {}).get("authentication")
            pwd = _cfg["obs_password"]

            # 2. Identify (op 1)
            identify_d = {
                "rpcVersion": hello.get("d", {}).get("rpcVersion", 1),
                "eventSubscriptions": 0
            }

            if auth_data:
                if not pwd:
                    return None, "OBS requires a password, but none is set in Settings."

                secret = base64.b64encode(
                    hashlib.sha256((pwd + auth_data["salt"]).encode()).digest()
                ).decode()
                auth_resp = base64.b64encode(
                    hashlib.sha256(
                        (secret + auth_data["challenge"]).encode()).digest()
                ).decode()
                identify_d["authentication"] = auth_resp

            ws.send(json.dumps({"op": 1, "d": identify_d}))

            # 3. Receive IdentifyResponse (op 2)
            resp_raw = ws.recv()
            if not resp_raw:
                return None, "Authentication failed: OBS closed the connection. Check your password."

            resp = json.loads(resp_raw)
            if resp.get("op") != 2:
                return None, f"Auth failed or unexpected response: {resp}"

            _obs_ws = ws
            _obs_connected = True
            return ws, None
        except Exception as e:
            _obs_connected = False
            err_msg = str(e)
            if "10053" in err_msg:
                err_msg = "Connection aborted (WinError 10053). This usually means OBS rejected the connection (wrong password or version)."
            return None, err_msg


def obs_request(request_type, data=None):
    global _obs_ws, _obs_connected

    # Try twice: once with potentially cached connection, once with a fresh one
    for attempt in range(2):
        ws, err = obs_connect()
        if err:
            _obs_connected = False
            return False, err
        try:
            import uuid
            rid = str(uuid.uuid4())[:8]
            payload = {"op": 6, "d": {"requestType": request_type,
                                      "requestId": rid, "requestData": data or {}}}
            with _obs_lock:
                ws.send(json.dumps(payload))
                resp = json.loads(ws.recv())
            res = resp.get("d", {}).get("requestStatus", {})
            if res.get("result"):
                _obs_connected = True
                return True, resp.get("d", {}).get("responseData", {})
            return False, res.get("comment", "OBS error")
        except Exception as e:
            _obs_ws = None  # Clear cached connection on failure
            _obs_connected = False
            if attempt == 1:  # If second attempt also fails, return error
                return False, str(e)
            log(f"OBS request failed, retrying with fresh connection... ({e})")
            continue
    return False, "Failed after retry"


def handle_obs(data):
    cmd = str(data.get("command", "")).strip()
    scene = data.get("scene", "") or data.get("sceneName", "")
    source = data.get("source", "") or data.get("sourceName", "")

    if cmd.lower() == "setcurrentprogramscene":
        return obs_request("SetCurrentProgramScene", {"sceneName": scene})
    elif cmd.lower() == "startstream":
        return obs_request("StartStream")
    elif cmd.lower() == "stopstream":
        return obs_request("StopStream")
    elif cmd.lower() == "startrecord":
        return obs_request("StartRecord")
    elif cmd.lower() == "stoprecord":
        return obs_request("StopRecord")
    elif cmd.lower() == "togglemute":
        return obs_request("ToggleInputMute", {"inputName": source})
    elif cmd.lower() == "togglesource":
        if not source:
            return False, "No source name provided"

        if scene:
            # Scene specified, toggle only in that scene
            # 2. Get scene item ID
            ok, resp = obs_request(
                "GetSceneItemId", {"sceneName": scene, "sourceName": source})
            if not ok:
                return False, f"Could not find source '{source}' in scene '{scene}'"
            item_id = resp.get("sceneItemId")

            # 3. Get current enabled state
            ok, resp = obs_request("GetSceneItemEnabled", {
                                   "sceneName": scene, "sceneItemId": item_id})
            if not ok:
                return False, f"Could not get visibility for '{source}'"
            is_enabled = resp.get("sceneItemEnabled")

            # 4. Toggle
            return obs_request("SetSceneItemEnabled", {
                "sceneName": scene,
                "sceneItemId": item_id,
                "sceneItemEnabled": not is_enabled
            })
        else:
            # No scene specified, toggle in all scenes where the source exists
            ok, resp = obs_request("GetSceneList")
            if not ok:
                return False, f"Could not get scene list: {resp}"
            scenes = resp.get("scenes", [])
            toggled = False
            for sc in scenes:
                scene_name = sc.get("sceneName")
                # Check if source exists in this scene
                ok2, resp2 = obs_request(
                    "GetSceneItemId", {"sceneName": scene_name, "sourceName": source})
                if ok2:
                    item_id = resp2.get("sceneItemId")
                    # Get current enabled state
                    ok3, resp3 = obs_request("GetSceneItemEnabled", {
                                             "sceneName": scene_name, "sceneItemId": item_id})
                    if ok3:
                        is_enabled = resp3.get("sceneItemEnabled")
                        # Toggle
                        obs_request("SetSceneItemEnabled", {
                            "sceneName": scene_name,
                            "sceneItemId": item_id,
                            "sceneItemEnabled": not is_enabled
                        })
                        toggled = True
            if toggled:
                return True, f"Toggled source '{source}' in applicable scenes"
            else:
                return False, f"Source '{source}' not found in any scene"
    elif cmd.lower() == "setvolume":
        vol = max(0.0, min(1.0, float(data.get("volume", 1.0))))
        return obs_request("SetInputVolume", {"inputName": source, "inputVolumeMul": vol})
    return False, f"Unknown OBS command: {cmd}"


# ─────────────────────────────────────────────────────────────────────────────
# TWITCH
# ─────────────────────────────────────────────────────────────────────────────
_twitch_user_id = ""
_twitch_username = ""


def _twitch_api(method, path, body=None):
    token = _cfg.get("twitch_access_token", "")
    if not token:
        return False, "No Twitch token set in Settings"

    url = f"https://api.twitch.tv/helix{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id":     _cfg["twitch_client_id"],
        "Content-Type":  "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        # We won't auto-refresh for manual tokens as we don't have a secret/refresh token usually
        try:
            return False, json.loads(e.read()).get("message", str(e))
        except:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def _fetch_twitch_user():
    global _twitch_user_id, _twitch_username
    ok, resp = _twitch_api("GET", "/users")
    if ok and resp.get("data"):
        _twitch_user_id = resp["data"][0]["id"]
        _twitch_username = resp["data"][0]["login"]
        return True
    return False


def handle_twitch(data):
    cmd = data.get("command", "")
    token = _cfg.get("twitch_access_token", "")
    if not token:
        return False, "No Twitch token set in Settings"

    if not _twitch_user_id:
        _fetch_twitch_user()
        if not _twitch_user_id:
            return False, "Could not fetch Twitch user ID - check your token"

    if cmd == "marker":
        desc = data.get("description", "")
        ok, resp = _twitch_api(
            "POST", f"/streams/markers?user_id={_twitch_user_id}&description={urllib.parse.quote(desc)}")
        if ok:
            pos = resp.get("data", [{}])[0].get("position_seconds", 0)
            return True, f"Marker at {pos}s" + (f" - {desc}" if desc else "")
        return False, resp

    elif cmd == "ad":
        length = int(data.get("length", 30))
        ok, resp = _twitch_api("POST", "/channels/commercial", {
            "broadcaster_id": _twitch_user_id,
            "length": length
        })
        if ok:
            msg = resp.get("data", [{}])[0].get("message", "")
            if not msg:
                msg = f"Running {length}s ad"
            return True, msg
        return False, resp

    elif cmd == "clip":
        title = data.get("description", "")
        duration = float(data.get("duration", 30))
        # Clamp duration between 5 and 60 seconds
        duration = max(5.0, min(60.0, duration))
        ok, resp = _twitch_api("POST", f"/clips?broadcaster_id={_twitch_user_id}" +
                               (f"&title={urllib.parse.quote(title)}" if title else "") +
                               (f"&duration={duration}" if duration != 30 else ""))
        if ok:
            clip_data = resp.get("data", [{}])[0]
            clip_id = clip_data.get("id", "")
            edit_url = clip_data.get("edit_url", "")
            return True, f"Clip created: https://clips.twitch.tv/{clip_id}"
        # Provide helpful error message for common issues
        err_msg = resp if isinstance(
            resp, str) else resp.get("message", str(resp))
        if "clips:edit" in err_msg.lower() or "scope" in err_msg.lower():
            return False, "MISSING SCOPE: Your token needs 'clips:edit' permission. See Settings → Twitch for instructions."
        if "not live" in err_msg.lower() or "404" in err_msg:
            return False, "Cannot clip: Channel is not currently live"
        return False, err_msg

    return False, f"Unknown Twitch command: {cmd}"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP SERVER
# ─────────────────────────────────────────────────────────────────────────────
_connected_clients = {}  # IP -> last_seen_timestamp
_clients_lock = threading.Lock()


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
            _connected_clients[ip] = time.time()
        if self.path == "/ping":
            self.send_json(200, {
                "status":  "ok",
                "server":  "Streamer Tablet Helper",
                "obs":     bool(_cfg["obs_password"]),
                "twitch":  bool(_cfg.get("twitch_access_token")),
            })
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        ip = self.client_address[0]
        with _clients_lock:
            _connected_clients[ip] = time.time()

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
        except Exception:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        action = data.get("action", "")
        extras = {k: v for k, v in data.items() if k != "action"}
        log(f"← [{mask_ip(ip)}]  {action}  {json.dumps(extras) if extras else ''}")

        if action == "keys":
            keys = [k.strip() for k in data.get("keys", []) if k.strip()]
            if not keys:
                self.send_json(400, {"error": "No keys"})
                return
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
            if isinstance(msg, dict):
                resp.update(msg)
            else:
                resp["message"] = str(msg)
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
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "StreamerTabletHelper"


def set_autostart(enable: bool):
    if sys.platform != "win32":
        return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             _REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            exe = sys.executable if getattr(sys, "frozen", False) else \
                f'pythonw "{Path(__file__).resolve()}"'
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, exe)
            log("Auto-start enabled")
        else:
            try:
                winreg.DeleteValue(key, _REG_NAME)
            except:
                pass
            log("Auto-start disabled")
        winreg.CloseKey(key)
        _cfg["start_with_windows"] = enable
        save_config()
    except Exception as e:
        log(f"Auto-start error: {e}")


def get_autostart() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             _REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _REG_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────
# Colours
C_BG = "#0a0c10"
C_SURFACE = "#111520"
C_BORDER = "#1e2535"
C_ACCENT = "#00e5ff"
C_GREEN = "#00ff99"
C_RED = "#ff3c6e"
C_MUTED = "#555e7a"
C_TEXT = "#cdd6f4"
C_TWITCH = "#9146ff"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Streamer Tablet Helper")
        self.geometry("560x680")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set a taskbar/title-bar icon
        try:
            icon_png = _BASE / "Streamer Tablet Helper.png"
            if icon_png.exists():
                from PIL import Image, ImageTk
                img = Image.open(str(icon_png))
                photo = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, photo)
            else:
                # Fallback to icon.ico if present
                icon_path = _BASE / "icon.ico"
                if icon_path.exists():
                    self.iconbitmap(str(icon_path))
        except Exception as e:
            print(f"Could not set icon: {e}")

        self._server_thread = None
        self._httpd = None
        self._ip = get_local_ip()
        self._tray = None
        self._ip_hidden = True

        self._build_ui()
        self._start_server()
        self._validate_twitch_token()
        self._validate_obs_connection()
        self._tick()   # periodic UI refresh

        # Minimise to tray on start if autostart is set
        if _cfg.get("start_with_windows") and get_autostart():
            self.after(200, self._minimise_to_tray)

    # ── UI BUILD ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──
        hdr = ctk.CTkFrame(self, height=60, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🎮  Streamer Tablet Helper", font=("Segoe UI", 20, "bold"),
                     text_color=C_ACCENT).pack(side="left", padx=16, pady=14)

        # ── Status cards ──
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=12, pady=10)

        # IP card
        ip_card = self._card(cards, "YOUR PC IP - enter this in the app")

        self._lbl_ip_warning = ctk.CTkLabel(ip_card, text="⚠️  WARNING: Do NOT show this on stream!",
                                            font=("Segoe UI", 12, "bold"), text_color=C_RED)
        self._lbl_ip_warning.pack(pady=(0, 6))

        self._lbl_ip = ctk.CTkLabel(ip_card, text="• • • • • • • • •", font=("Courier New", 28, "bold"),
                                    text_color=C_MUTED)
        self._lbl_ip.pack(pady=(0, 4))

        btn_row = ctk.CTkFrame(ip_card, fg_color="transparent")
        btn_row.pack()

        self._btn_ip_toggle = ctk.CTkButton(btn_row, text="👁️ Show IP", font=("Segoe UI", 12),
                                            fg_color=C_BORDER, text_color=C_TEXT,
                                            hover_color=C_SURFACE, height=28, width=100,
                                            command=self._toggle_ip)
        self._btn_ip_toggle.pack(side="left", padx=4)

        ctk.CTkButton(btn_row, text="📋 Copy", font=("Segoe UI", 12),
                      fg_color=C_BORDER, text_color=C_TEXT,
                      hover_color=C_SURFACE, height=28, width=100,
                      command=lambda: self._copy(self._ip)).pack(side="left", padx=4)

        ctk.CTkButton(btn_row, text="🔄 Refresh", font=("Segoe UI", 12),
                      fg_color=C_BORDER, text_color=C_TEXT,
                      hover_color=C_SURFACE, height=28, width=100,
                      command=self._refresh_ip).pack(side="left", padx=4)

        # Feature status row
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=12)

        self._dot_server = self._status_dot(status_row, "Server",  C_MUTED)
        self._dot_obs = self._status_dot(status_row, "OBS",     C_MUTED)
        self._dot_twitch = self._status_dot(status_row, "Twitch",  C_MUTED)
        self._dot_keys = self._status_dot(status_row, "Keys",    C_MUTED)

        # Devices connected
        self._lbl_devices = ctk.CTkLabel(status_row, text="0 devices",
                                         font=("Segoe UI", 11), text_color=C_MUTED)
        self._lbl_devices.pack(side="right", padx=4)

        # ── Notebook tabs ──
        self.nb = ctk.CTkTabview(self, anchor="nw")
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tab_log = self.nb.add("Activity Log")
        self.tab_settings = self.nb.add("Settings")

        self._build_log_tab(self.tab_log)
        self._build_settings_tab(self.tab_settings)

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(wrapper, text=title.upper(), font=("Segoe UI", 10, "bold"),
                     text_color=C_MUTED, anchor="w").pack(fill="x", pady=(0, 4))
        inner = ctk.CTkFrame(wrapper, corner_radius=10, fg_color=C_SURFACE)
        inner.pack(fill="x", padx=2, pady=2)
        return inner

    def _status_dot(self, parent, label: str, color: str) -> ctk.CTkLabel:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(side="left", padx=(0, 12))
        dot = ctk.CTkLabel(f, text="⬤", font=(
            "Segoe UI", 12), text_color=color)
        dot.pack(side="left")
        ctk.CTkLabel(f, text=label, font=("Segoe UI", 11),
                     text_color=C_MUTED).pack(side="left", padx=(3, 0))
        return dot

    # ── LOG TAB ──────────────────────────────────────────────────────────────
    def _build_log_tab(self, frame):
        global _log_cb
        self._log_box = ctk.CTkTextbox(
            frame, fg_color=C_SURFACE, text_color=C_TEXT,
            font=("Courier New", 12), corner_radius=8,
            wrap="word",
        )
        self._log_box.pack(fill="both", expand=True, padx=0, pady=(0, 6))

        # ScrolledText tags equivalent for CustomTkinter Textbox is tricky as it doesn't support them directly.
        # We will simplify by using normal text for now.

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=6)
        ctk.CTkButton(btn_row, text="Clear log", font=("Segoe UI", 12),
                      fg_color=C_BORDER, text_color=C_TEXT,
                      hover_color=C_SURFACE, height=32, width=120,
                      command=self._clear_log).pack(side="right")

        _log_cb = self._append_log

        # Replay buffered lines from before the window was ready
        with _log_lock:
            for line in _log_lines:
                self._append_log(line)

    def _append_log(self, line: str):
        def _do():
            # For CTkTextbox, we just insert. It doesn't have a disabled/enabled state like tk.Text.
            self._log_box.insert("end", line + "\n")
            self._log_box.see("end")
        self.after(0, _do)

    def _clear_log(self):
        with _log_lock:
            _log_lines.clear()
        self._log_box.delete("1.0", "end")

    # ── SETTINGS TAB ─────────────────────────────────────────────────────────
    def _build_settings_tab(self, frame):
        # We can use CTkScrollableFrame for settings
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        def _section(text):
            ctk.CTkLabel(scroll_frame, text=text, font=("Segoe UI", 12, "bold"),
                         text_color=C_ACCENT).pack(anchor="w", pady=(18, 4), padx=2)
            # Divider
            ctk.CTkFrame(scroll_frame, height=2, fg_color=C_BORDER).pack(
                fill="x", pady=(0, 8))

        def _row(label, widget_fn):
            r = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            r.pack(fill="x", pady=5)
            ctk.CTkLabel(r, text=label, font=("Segoe UI", 12), text_color=C_TEXT,
                         width=140, anchor="w").pack(side="left")
            widget_fn(r)
            return r

        def _entry(parent, value="", **kw):
            e = ctk.CTkEntry(parent, fg_color=C_SURFACE, text_color=C_TEXT,
                             border_color=C_BORDER, font=("Segoe UI", 12), **kw)
            e.pack(side="left", fill="x", expand=True, padx=(0, 4))
            return e

        # ── OBS ──────────────────────────────────────────────────────────────
        _section("OBS WEBSOCKET")

        self._obs_pw_var = tk.StringVar(value=_cfg["obs_password"])
        _row("Password", lambda p: _entry(p, _cfg["obs_password"],
                                          textvariable=self._obs_pw_var, show="●"))

        self._obs_host_var = tk.StringVar(value=_cfg["obs_host"])
        _row("Host", lambda p: _entry(
            p, _cfg["obs_host"], textvariable=self._obs_host_var))

        self._obs_port_var = tk.StringVar(value=str(_cfg["obs_port"]))
        _row("Port", lambda p: _entry(
            p, str(_cfg["obs_port"]), textvariable=self._obs_port_var, width=80))

        ctk.CTkLabel(scroll_frame, text="Enable in OBS → Tools → WebSocket Server Settings",
                     font=("Segoe UI", 11), text_color=C_MUTED).pack(anchor="w", padx=2, pady=(0, 4))

        obs_btn_row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        obs_btn_row.pack(anchor="w", pady=(0, 4))
        ctk.CTkButton(obs_btn_row, text="Save OBS Connection Settings", font=("Segoe UI", 12, "bold"),
                      fg_color=C_ACCENT, text_color="#000", hover_color="#00b8cc",
                      height=36, command=self._save_obs).pack(side="left", padx=(0, 8))
        ctk.CTkButton(obs_btn_row, text="💾 Save & Test Connection", font=("Segoe UI", 12),
                      fg_color=C_BORDER, text_color=C_TEXT, hover_color=C_SURFACE,
                      height=36, command=self._test_obs).pack(side="left")

        # ── TWITCH ───────────────────────────────────────────────────────────
        _section("TWITCH - STREAM MARKERS")

        self._twitch_id_var = tk.StringVar(value=_cfg["twitch_client_id"])
        _row("Client ID", lambda p: _entry(p, _cfg["twitch_client_id"],
                                           textvariable=self._twitch_id_var))

        self._twitch_token_var = tk.StringVar(
            value=_cfg["twitch_access_token"])
        _row("OAuth Token", lambda p: _entry(p, _cfg["twitch_access_token"],
                                             textvariable=self._twitch_token_var, show="●"))

        # Detailed OAuth instructions with required scopes
        ctk.CTkLabel(scroll_frame,
                     text="""SETUP INSTRUCTIONS:

1. Visit twitchtokengenerator.com
2. Enable these SCOPES (check the boxes):
   ✓ channel:manage:broadcast  (Stream markers)
   ✓ channel:edit:commercial    (Run ads)
   ✓ clips:edit                 (Create clips)
3. Click 'Generate Token' and authorize with Twitch
4. Copy 'Access Token' and 'Client ID' above

SCOPES EXPLAINED:
• channel:manage:broadcast = Mark moments in your VOD
• channel:edit:commercial   = Run commercials/ads
• clips:edit                = Instant clips with one tap""",
                     font=("Segoe UI", 11), text_color="#ffffff", justify="left"
                     ).pack(anchor="w", padx=2, pady=(0, 6))

        self._lbl_twitch_status = ctk.CTkLabel(scroll_frame, text="Checking status...",
                                               font=("Segoe UI", 12), text_color=C_MUTED)
        self._lbl_twitch_status.pack(anchor="w", padx=2, pady=(0, 6))

        twitch_btn_row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        twitch_btn_row.pack(anchor="w", pady=(0, 4))

        ctk.CTkButton(twitch_btn_row, text="🌐 Open Token Generator", font=("Segoe UI", 12, "bold"),
                      fg_color=C_TWITCH, text_color="#fff", hover_color="#772ce8",
                      height=36, command=lambda: webbrowser.open("https://twitchtokengenerator.com/")).pack(side="left", padx=(0, 8))

        ctk.CTkButton(twitch_btn_row, text="💾 Save & Test Twitch", font=("Segoe UI", 12),
                      fg_color=C_ACCENT, text_color="#000", hover_color="#00b8cc",
                      height=36, command=self._save_twitch_manual).pack(side="left")

        # Twitch login status label (shown during auth)
        self._lbl_twitch_auth = ctk.CTkLabel(scroll_frame, text="", font=("Segoe UI", 11),
                                             text_color=C_MUTED, wraplength=480, justify="left")
        self._lbl_twitch_auth.pack(anchor="w", padx=2, pady=(0, 4))
        self._update_twitch_label()

        # ── GENERAL ──────────────────────────────────────────────────────────
        _section("GENERAL")

        self._autostart_var = tk.BooleanVar(value=get_autostart())
        autostart_row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        autostart_row.pack(anchor="w", pady=3)
        ctk.CTkCheckBox(autostart_row, text="Start with Windows",
                        variable=self._autostart_var,
                        font=("Segoe UI", 13),
                        command=lambda: set_autostart(
                            self._autostart_var.get())
                        ).pack(side="left")
        if sys.platform != "win32":
            ctk.CTkLabel(autostart_row, text="(Windows only)", font=("Segoe UI", 11),
                         text_color=C_MUTED).pack(side="left", padx=6)

        ctk.CTkButton(scroll_frame, text="Minimise to Tray", font=("Segoe UI", 12),
                      fg_color=C_BORDER, text_color=C_TEXT, hover_color=C_SURFACE,
                      height=36, command=self._minimise_to_tray
                      ).pack(anchor="w", pady=(12, 0))

    # ── OBS ACTIONS ──────────────────────────────────────────────────────────
    def _apply_obs_settings(self, silent=False):
        global _obs_ws
        pwd = self._obs_pw_var.get().strip()

        # Validation: check for newlines or if it looks like the log buffer
        if "\n" in pwd or "Server started" in pwd or "IP refreshed" in pwd:
            if not messagebox.askyesno("Warning",
                                       "The password contains newlines or looks like log messages.\n\n"
                                       "Are you sure you want to save this as your password?"):
                return False

        _cfg["obs_password"] = pwd
        _cfg["obs_host"] = self._obs_host_var.get().strip() or "localhost"
        try:
            _cfg["obs_port"] = int(self._obs_port_var.get().strip())
        except:
            _cfg["obs_port"] = 4455

        _obs_ws = None   # force reconnect
        save_config()
        log("OBS connection settings saved")
        if not silent:
            messagebox.showinfo(
                "Saved", "OBS connection settings saved.", parent=self)
        return True

    def _save_obs(self):
        self._apply_obs_settings(silent=False)

    def _test_obs(self):
        if not self._apply_obs_settings(silent=True):
            return

        def _run():
            ok, resp = obs_request("GetVersion")
            if ok:
                ver = resp.get("obsVersion", "?")
                log(f"OBS connected  ✓  version {ver}")
                self.after(0, lambda: messagebox.showinfo(
                    "OBS", f"Connected!\nOBS version: {ver}", parent=self))
            else:
                msg = str(resp)
                if "10061" in msg:
                    msg = "Connection Refused.\n\nPossible causes:\n1. OBS is not open.\n2. WebSocket Server is not enabled in OBS (Tools -> WebSocket Server Settings).\n3. Port 4455 is blocked or wrong."
                log(f"OBS test failed: {resp}")
                self.after(0, lambda: messagebox.showerror(
                    "OBS", f"Could not connect:\n{msg}", parent=self))
        threading.Thread(target=_run, daemon=True).start()

    # ── TWITCH ACTIONS ───────────────────────────────────────────────────────
    def _save_twitch_manual(self):
        _cfg["twitch_client_id"] = self._twitch_id_var.get().strip()
        _cfg["twitch_access_token"] = self._twitch_token_var.get().strip()
        save_config()
        log("Twitch settings saved")
        self._lbl_twitch_status.configure(
            text="Validating...", text_color=C_MUTED)
        self._validate_twitch_token()

    def _update_twitch_label(self):
        token = _cfg.get("twitch_access_token", "")
        if _twitch_username:
            self._lbl_twitch_status.configure(
                text=f"✓  Logged in as  {_twitch_username}", text_color=C_TWITCH)
        elif token:
            self._lbl_twitch_status.configure(
                text="✓  Token set", text_color=C_TWITCH)
        else:
            self._lbl_twitch_status.configure(
                text="Not logged in", text_color=C_MUTED)

    # ── TWITCH ACTIONS (DEPRECATED) ──────────────────────────────────────────
    def _twitch_login_flow(self):
        pass

    def _twitch_logout(self):
        global _twitch_username, _twitch_user_id
        _cfg["twitch_access_token"] = ""
        save_config()
        _twitch_username = _twitch_user_id = ""
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
        token = _cfg.get("twitch_access_token", "")
        cid = _cfg.get("twitch_client_id", "")
        if not token:
            return

        def _run():
            global _twitch_user_id, _twitch_username
            try:
                req = urllib.request.Request(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": f"OAuth {token}"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    vdata = json.loads(r.read())

                _twitch_user_id = vdata.get("user_id",  "")
                _twitch_username = vdata.get("login",    "")
                actual_cid = vdata.get("client_id", "")

                if cid and actual_cid and cid != actual_cid:
                    log(
                        f"Twitch Error: Client ID mismatch! Config has {cid}, but token belongs to {actual_cid}")
                    self.after(0, lambda: self._lbl_twitch_status.configure(
                        text="✗ Client ID mismatch - check your settings", text_color=C_RED))
                else:
                    log(f"Twitch ready - logged in as {_twitch_username}")
                    self.after(0, self._update_twitch_label)
            except Exception as e:
                log(f"Twitch token validation failed: {e}")
                _twitch_username = ""
                _twitch_user_id = ""
                self.after(0, self._update_twitch_label)
        threading.Thread(target=_run, daemon=True).start()

    # ── OBS CONNECTION VALIDATION on startup ─────────────────────────────────
    def _validate_obs_connection(self):
        if not (_cfg.get("obs_host") and _cfg.get("obs_port")):
            return

        def _run():
            ok, msg = obs_connect()
            if ok:
                log("OBS auto-connect successful")
            else:
                log(f"OBS auto-connect failed: {msg}")

        threading.Thread(target=_run, daemon=True).start()

    # ── PERIODIC TICK ────────────────────────────────────────────────────────
    def _tick(self):
        # Update status dots
        server_ok = self._httpd is not None
        self._dot_server.configure(text_color=C_GREEN if server_ok else C_RED)

        # OBS status - use the tracked connection state
        self._dot_obs.configure(
            text_color=C_GREEN if _obs_connected else C_MUTED)

        twitch_ok = bool(_cfg.get("twitch_access_token"))
        self._dot_twitch.configure(
            text_color=C_TWITCH if twitch_ok else C_MUTED)

        try:
            import pyautogui
            self._dot_keys.configure(text_color=C_GREEN)
        except ImportError:
            self._dot_keys.configure(text_color=C_MUTED)

        # Cleanup inactive clients (not seen for >15s)
        now = time.time()
        with _clients_lock:
            inactive = [ip for ip, last in _connected_clients.items()
                        if now - last > 15]
            for ip in inactive:
                del _connected_clients[ip]
            n = len(_connected_clients)

        self._lbl_devices.configure(
            text=f"{n} device{'s' if n != 1 else ''} seen",
            text_color=C_GREEN if n > 0 else C_MUTED)

        self.after(2000, self._tick)

    # ── HELPERS ──────────────────────────────────────────────────────────────
    def _copy(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        log("IP copied to clipboard")

    def _toggle_ip(self):
        self._ip_hidden = not self._ip_hidden
        if self._ip_hidden:
            self._lbl_ip.configure(
                text="• • • • • • • • •", text_color=C_MUTED)
            self._btn_ip_toggle.configure(text="👁️ Show IP")
        else:
            self._lbl_ip.configure(text=self._ip, text_color=C_ACCENT)
            self._btn_ip_toggle.configure(text="🙈 Hide IP")

    def _refresh_ip(self):
        self._ip = get_local_ip()
        if not self._ip_hidden:
            self._lbl_ip.configure(text=self._ip)
        log(f"IP refreshed: {mask_ip(self._ip)}")

    def _on_close(self):
        if messagebox.askokcancel("Quit",
                                  "Stop the server?\n\nThe tablet app will lose connection.", parent=self):
            if self._httpd:
                threading.Thread(target=self._httpd.shutdown,
                                 daemon=True).start()
            self.destroy()

    def _minimise_to_tray(self):
        """Hide the window. Show a system tray icon if pystray is available."""
        self.withdraw()
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Use the main PNG icon for the tray
            ico_png = _BASE / "Streamer Tablet Helper.png"
            if ico_png.exists():
                img = Image.open(str(ico_png))
            else:
                # Fallback to icon.ico if present
                ico_path = _BASE / "icon.ico"
                if ico_path.exists():
                    img = Image.open(str(ico_path))
                else:
                    img = Image.new("RGB", (64, 64), "#0a0c10")
                    d = ImageDraw.Draw(img)
                    d.ellipse([8, 8, 56, 56], fill="#00e5ff")
                    d.text((22, 20), "S", fill="#000000")

            def _show(icon, item):
                icon.stop()
                self._tray = None
                self.after(0, self.deiconify)

            def _quit(icon, item):
                icon.stop()
                if self._httpd:
                    threading.Thread(
                        target=self._httpd.shutdown, daemon=True).start()
                self.after(0, self.destroy)

            menu = pystray.Menu(
                pystray.MenuItem("Open", _show, default=True),
                pystray.MenuItem("Quit", _quit),
            )
            self._tray = pystray.Icon(
                "StreamerTabletHelper", img, "Streamer Tablet Helper", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()

        except ImportError:
            # pystray not installed - just minimise to taskbar normally
            self.iconify()

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────


def main():
    load_config()

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
