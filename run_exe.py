"""Standalone launcher for the FundTrail .exe (single local laptop, offline).

This is the PyInstaller entry point. It:
  * pins a PERSISTENT data directory NEXT TO the .exe so the SQLite database
    survives restarts (the bundled _MEIPASS temp dir is wiped when the app exits),
  * provides a stable per-machine SECRET_KEY (the app refuses to start without one),
  * starts the Flask app and opens the browser.

NOT for shared / networked use — embedded SQLite is single-machine only.
"""

import os
import sys
import secrets
import threading
import time
import webbrowser

# Folder the app runs from: the .exe's own directory when frozen, else this file's dir.
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
    # Bundled python modules (app.py, models.py, ifsc_utils.py, ...) live under _MEIPASS.
    sys.path.insert(0, sys._MEIPASS)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(_APP_DIR, "main"))

# Persistent data dir beside the exe (DB, INITIAL_CREDENTIALS.txt, logs, secret key).
_DATA_DIR = os.path.join(_APP_DIR, "FundTrail_data")
os.makedirs(_DATA_DIR, exist_ok=True)
os.environ.setdefault("FUNDTRAIL_DATA_DIR", _DATA_DIR)

# Stable per-machine SECRET_KEY, persisted alongside the data.
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

# Local HTTP on a single laptop (no HTTPS reverse proxy in front).
os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")
os.environ.setdefault("PORT", "5050")

import app as _app  # noqa: E402  builds the Flask app + seeds the DB at import time

_PORT = int(os.environ.get("PORT", "5050"))
_URL = f"http://127.0.0.1:{_PORT}"


def _show_initial_credentials():
    """Print the first-login credentials prominently so they're never a mystery.
    They exist (in INITIAL_CREDENTIALS.txt) only until the password is changed."""
    cred_file = os.path.join(_DATA_DIR, "INITIAL_CREDENTIALS.txt")
    if os.path.exists(cred_file):
        try:
            with open(cred_file, "r", encoding="utf-8") as f:
                body = f.read().strip()
            print("\n" + "=" * 64)
            print("  FIRST-LOGIN CREDENTIALS  (you must change them on first login)")
            print("=" * 64)
            print(body)
            print("=" * 64 + "\n")
        except Exception:
            pass


def _run_server():
    _app.app.run(host="127.0.0.1", port=_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    print(f"FundTrail is starting at {_URL}")
    print(f"All data is stored locally in: {_DATA_DIR}")
    _show_initial_credentials()

    # Serve Flask in the background; the main thread drives the desktop window.
    threading.Thread(target=_run_server, daemon=True).start()
    time.sleep(1.5)  # let the server bind before the window loads

    # Prefer a real STANDALONE desktop window (no browser tab) via pywebview's native
    # OS webview. Fall back to the browser if pywebview / a system webview is missing.
    try:
        import webview  # pywebview
        webview.create_window("FundTrail", _URL, width=1280, height=820)
        webview.start()
    except Exception as exc:
        print(f"Desktop window unavailable ({exc}); opening in your browser instead.")
        try:
            webbrowser.open(_URL)
        except Exception:
            pass
        try:
            while True:
                time.sleep(3600)  # keep the process (and server) alive
        except KeyboardInterrupt:
            pass
