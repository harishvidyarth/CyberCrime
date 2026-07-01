"""Standalone launcher for the FundTrail .exe (single local laptop, offline).

PyInstaller entry point. It pins a STABLE per-user data directory (so the SQLite
database — and the login — persist across EXE rebuilds/moves), provides a stable
per-machine SECRET_KEY, shows the first-login credentials in a dialog, and opens the
app in a native standalone window (no browser tab, no console).

NOT for shared / networked use — embedded SQLite is single-machine only.
"""

import os
import sys
import secrets
import shutil
import threading
import time
import webbrowser

# PyInstaller *windowed* builds (FundTrail.spec console=False) start the process with
# sys.stdout / sys.stderr == None. Reattach them to a null sink HERE — before `import app`
# (below) configures logging and runs import-time prints — so the frozen exe can never
# crash with "AttributeError: 'NoneType' object has no attribute 'flush'" on startup.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

_PORT = int(os.environ.get("PORT", "5050"))
_URL = f"http://127.0.0.1:{_PORT}"


def _default_data_dir():
    """Stable per-user data dir, identical to app.py's resolver, so the EXE always
    finds the same database regardless of where the executable lives."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "FundTrail")


def _msgbox(text, title="FundTrail"):
    """Show a native dialog on Windows (the EXE has no console); print elsewhere."""
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)  # MB_ICONINFORMATION
            return
        except Exception:
            pass
    print(f"{title}: {text}")


_DATA_DIR = os.environ.get("FUNDTRAIL_DATA_DIR") or _default_data_dir()
try:
    os.makedirs(_DATA_DIR, exist_ok=True)
except PermissionError:
    _DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FundTrail")
    os.makedirs(_DATA_DIR, exist_ok=True)

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

_LEGACY_DATA_DIR = os.path.join(_APP_DIR, "FundTrail_data")
_PRIMARY_DB = os.path.join(_DATA_DIR, "fundtrail.db")
if not os.path.exists(_PRIMARY_DB) and os.path.isdir(_LEGACY_DATA_DIR) and os.path.abspath(_LEGACY_DATA_DIR) != os.path.abspath(_DATA_DIR):
    try:
        for _name in os.listdir(_LEGACY_DATA_DIR):
            _src = os.path.join(_LEGACY_DATA_DIR, _name)
            _dst = os.path.join(_DATA_DIR, _name)
            if os.path.exists(_dst):
                continue
            if os.path.isdir(_src):
                shutil.copytree(_src, _dst)
            else:
                shutil.copy2(_src, _dst)
    except OSError as exc:
        _msgbox(
            f"FundTrail could not migrate old data from:\n{_LEGACY_DATA_DIR}\n\n"
            f"The app will continue using:\n{_DATA_DIR}\n\n{exc}",
            "FundTrail — data migration warning",
        )
os.environ["FUNDTRAIL_DATA_DIR"] = _DATA_DIR

if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "main"))

if not os.environ.get("SECRET_KEY"):
    _key_file = os.path.join(_DATA_DIR, "secret.key")
    if os.path.exists(_key_file):
        with open(_key_file, "r", encoding="utf-8") as _f:
            os.environ["SECRET_KEY"] = _f.read().strip()
    else:
        _k = secrets.token_hex(32)
        with open(_key_file, "w", encoding="utf-8") as _f:
            _f.write(_k)
        os.environ["SECRET_KEY"] = _k

os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")
os.environ.setdefault("PORT", str(_PORT))

import app as _app  # noqa: E402  builds the Flask app + seeds the DB at import time


def _show_initial_credentials():
    """Show the first-login credentials while they exist. The file is removed when the
    user changes their password (app.py), so this stops appearing after first login."""
    cred_file = os.path.join(_DATA_DIR, "INITIAL_CREDENTIALS.txt")
    if not os.path.exists(cred_file):
        return
    try:
        with open(cred_file, "r", encoding="utf-8") as f:
            body = f.read().strip()
    except OSError:
        return
    _msgbox(body, "FundTrail — first-login credentials (change them on first login)")


def _run_server():
    try:
        _app.app.run(host="127.0.0.1", port=_PORT, debug=False, use_reloader=False)
    except OSError as exc:
        _msgbox(f"FundTrail could not start on port {_PORT}.\nIt may already be running.\n\n{exc}",
                "FundTrail — startup error")
        os._exit(1)


if __name__ == "__main__":
    _show_initial_credentials()
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)
    try:
        import webview  # pywebview — native standalone window

        webview.create_window("FundTrail", _URL, width=1280, height=820)
        webview.start()
    except Exception:
        try:
            webbrowser.open(_URL)
        except Exception:
            pass
        server_thread.join()  # keep process + server alive (no console to wait on)
