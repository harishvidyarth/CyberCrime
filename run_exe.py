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


def _open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open("http://127.0.0.1:5050")
    except Exception:
        pass


if __name__ == "__main__":
    print("FundTrail is starting — open http://127.0.0.1:5050 in your browser.")
    print(f"All data is stored locally in: {_DATA_DIR}")
    threading.Thread(target=_open_browser, daemon=True).start()
    _app.app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
