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


def _parse_credentials(body):
    """Pull username/password out of INITIAL_CREDENTIALS.txt ('Username: x' lines).
    Returns (username, password) or (None, None) when the format is unexpected."""
    username = password = None
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        if "user" in key.lower():
            username = val.strip()
        elif "pass" in key.lower():
            password = val.strip()
    return username, password


def _show_initial_credentials():
    """Show the first-login credentials while they exist. The file is removed when the
    user changes their password (app.py), so this stops appearing after first login.

    Fix: Issue 8 — MessageBoxW text cannot be selected/copied, so officers had to
    retype a random password by hand. Use a tkinter dialog with readonly (still
    selectable) Entry fields and a Copy button; keep the old msgbox as a fallback."""
    cred_file = os.path.join(_DATA_DIR, "INITIAL_CREDENTIALS.txt")
    if not os.path.exists(cred_file):
        return
    try:
        with open(cred_file, "r", encoding="utf-8") as f:
            body = f.read().strip()
    except OSError:
        return

    try:
        import tkinter as tk

        username, password = _parse_credentials(body)

        root = tk.Tk()
        root.title("FundTrail — First-Run Credentials")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        frame = tk.Frame(root, padx=18, pady=14)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="First-run login credentials", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        def _readonly_row(r, label, value):
            tk.Label(frame, text=label, font=("Segoe UI", 10)).grid(row=r, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=value)
            ent = tk.Entry(frame, textvariable=var, width=34, font=("Consolas", 10),
                           state="readonly", readonlybackground="white",
                           selectbackground="#2451d6", selectforeground="white")
            ent.grid(row=r, column=1, sticky="we", padx=(8, 8), pady=3)
            return ent

        if username and password:
            _readonly_row(1, "Username", username)
            _readonly_row(2, "Password", password)

            feedback = tk.Label(frame, text="", fg="#047857", font=("Segoe UI", 9))
            feedback.grid(row=3, column=1, sticky="w", padx=(8, 0))

            def _copy_password():
                root.clipboard_clear()
                root.clipboard_append(password)
                feedback.config(text="Copied")
                root.after(2000, lambda: feedback.config(text=""))

            tk.Button(frame, text="Copy password", command=_copy_password).grid(
                row=2, column=2, sticky="w", pady=3
            )
        else:
            # Unexpected file format: show the raw text, still selectable/copyable.
            txt = tk.Text(frame, width=46, height=6, font=("Consolas", 10))
            txt.insert("1.0", body)
            txt.configure(state="disabled")
            txt.grid(row=1, column=0, columnspan=3, pady=3)

        def _open_location():
            try:
                if os.name == "nt":
                    os.startfile(_DATA_DIR)
            except OSError:
                pass

        tk.Button(frame, text="Open credentials file location", command=_open_location).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        tk.Label(frame, text="Change your password immediately after first login.",
                 font=("Segoe UI", 10, "bold"), fg="#b91c1c").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        tk.Button(frame, text="OK", width=12, command=root.destroy).grid(
            row=6, column=0, columnspan=3, pady=(12, 0)
        )

        root.eval("tk::PlaceWindow . center")
        root.mainloop()
        return
    except Exception:
        pass  # tkinter unavailable/broken -> last-resort native msgbox below

    _msgbox(body, "FundTrail — first-login credentials (change them on first login)")


def _run_server():
    try:
        # Fix: Issue 9b — threaded=True: the single-threaded dev server serializes
        # requests, so one slow request froze every other page inside the exe.
        # use_reloader MUST stay False (the forked reloader breaks pywebview) and
        # debug MUST stay False in the frozen build.
        _app.app.run(host="127.0.0.1", port=_PORT, debug=False, use_reloader=False, threaded=True)
    except OSError as exc:
        _msgbox(f"FundTrail could not start on port {_PORT}.\nIt may already be running.\n\n{exc}",
                "FundTrail — startup error")
        os._exit(1)


class _SaveApi:
    """Exposed to the web page as window.pywebview.api. The embedded webview has no
    "Downloads" folder, so exports can't fall through to a browser download. The page
    fetches the export bytes (carrying its session cookie), base64-encodes them, and
    calls save_file() — which opens a NATIVE Save-As dialog and writes the chosen path."""

    window = None  # set to the created window below

    def save_file(self, b64, suggested_name="export.xlsx"):
        import base64
        import webview as _wv
        try:
            win = _SaveApi.window
            result = win.create_file_dialog(_wv.SAVE_DIALOG, save_filename=suggested_name)
            if not result:
                return ""  # user cancelled
            path = result[0] if isinstance(result, (list, tuple)) else result
            payload = b64.split(",", 1)[-1]  # tolerate a data: URL prefix
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(payload))
            return path
        except Exception as exc:  # pragma: no cover - desktop only
            try:
                _msgbox(f"Could not save the file:\n{exc}", "FundTrail — save error")
            except Exception:
                pass
            return ""


def _wait_for_server(timeout=45.0):
    """Block until the Flask thread answers on the local port (or timeout)."""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(_URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def _startup_splash():
    """Fix: Issue 9i — on low-end machines Flask + the 182k-record IFSC pickle take
    several seconds to come up, during which the exe shows nothing and looks frozen.
    Show a tiny tkinter splash immediately, destroy it once the server responds."""
    try:
        import tkinter as tk

        splash = tk.Tk()
        splash.overrideredirect(True)
        splash.attributes("-topmost", True)
        w, h = 340, 110
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        splash.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        frame = tk.Frame(splash, bg="#0a2e63", padx=2, pady=2)
        frame.pack(fill="both", expand=True)
        inner = tk.Frame(frame, bg="white")
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text="FundTrail", bg="white", fg="#0a2e63",
                 font=("Segoe UI", 14, "bold")).pack(pady=(18, 2))
        tk.Label(inner, text="Starting, please wait…", bg="white", fg="#475569",
                 font=("Segoe UI", 10)).pack()

        done = threading.Event()

        def _poll():
            if done.is_set():
                splash.destroy()
            else:
                splash.after(150, _poll)

        def _waiter():
            _wait_for_server()
            done.set()

        threading.Thread(target=_waiter, daemon=True).start()
        splash.after(150, _poll)
        splash.mainloop()
    except Exception:
        _wait_for_server()  # no tkinter: just wait quietly


if __name__ == "__main__":
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    # Splash while Flask warms up (also replaces the old fixed 1.5 s sleep),
    # then the copyable credentials dialog — both on the main thread, before
    # pywebview takes it over (pywebview MUST own the main thread on Windows).
    _startup_splash()
    _show_initial_credentials()
    try:
        import webview  # pywebview — native standalone window

        # Fix: Issue 6 — safety net: any navigation download the JS interceptor
        # misses still gets a native download dialog (pywebview >= 4.3).
        webview.settings["ALLOW_DOWNLOADS"] = True
        # Fix: Issue 9c — never auto-open devtools in the shipped build.
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False

        # NOTE (Issue 5): pywebview has no window-icon API on Windows — the
        # taskbar/title-bar icon comes from the exe's embedded resource
        # (FundTrail.spec icon=...), so nothing to set here.
        _SaveApi.window = webview.create_window(
            "FundTrail", _URL, width=1280, height=820,
            # Fix: Issue 9c — floor the window size (layout thrash on tiny sizes)
            # and enable native text selection (officers copy account numbers).
            min_size=(800, 600), text_select=True,
            js_api=_SaveApi(),
        )
        webview.start()
    except Exception:
        try:
            webbrowser.open(_URL)
        except Exception:
            pass
        server_thread.join()  # keep process + server alive (no console to wait on)
