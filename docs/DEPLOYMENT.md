# FundTrail — Deployment & Build Guide

**Tasks #23 (deployment) & #34 (Mac/Linux build requirements).**

Deployment model (confirmed): **offline `.exe` / binary per machine.** Each officer
runs a self-contained app locally with embedded SQLite — no server, no network.

## Prerequisites on the target machine
- The binary (built per OS, see below), or Python 3.10+ for a source run.
- `IFSC_CODES.pkl` placed next to the app (not shipped in Git; from shared drive).
- A `.env` with a real `SECRET_KEY` (`python3 -c "import secrets;print(secrets.token_hex(32))"`).
- For local http login: `SESSION_COOKIE_INSECURE=true` in `.env`.

## Run from source (any OS)
```bash
python3 -m venv .venv && source .venv/bin/activate   # Win: .venv\Scripts\activate
pip install -r main/requirements.txt
cp .env.example .env      # then set SECRET_KEY
cd main && python scripts/create_user.py && python app.py
```

## One-click Docker deployment (recommended)

The repo ships `fundtrail.sh` (Mac/Linux) and `fundtrail.bat` (Windows) that
handle everything: install Docker if missing, generate `.env` with a fresh
`SECRET_KEY` on first run, build the container image, wait for the health-check,
and print the LAN access URL.

```bash
# Mac / Linux
chmod +x fundtrail.sh
./fundtrail.sh          # start
./fundtrail.sh stop     # stop

# Windows — double-click fundtrail.bat, or from Command Prompt:
fundtrail.bat           # start
fundtrail.bat stop      # stop
```

The SQLite database persists in a named Docker volume (`fundtrail-data`) and
survives container restarts and image rebuilds.

## Building a single-file app (PyInstaller) — DEPRECATED

> ⚠️ `main/FundTrail.spec` has been removed from the repository. The Docker
> deployment model above is the supported path. The notes below are kept for
> historical reference only.

PyInstaller **cannot cross-compile** — you must build on each target OS.

| Target | Build on | Output | Command (from `main/`) |
|--------|----------|--------|------------------------|
| **Windows .exe** | Windows | `dist/FundTrail.exe` | `pyinstaller FundTrail.spec` |
| **macOS** | macOS | `dist/FundTrail` / `.app` | `pyinstaller FundTrail.spec` |
| **Linux** | Linux | `dist/FundTrail` | `pyinstaller FundTrail.spec` |

## Post-build checklist
- Launch the binary on a clean machine (no Python) → app starts, login works.
- First run creates the SQLite DBs in the secured data dir (perms 600).
- Upload a sample Excel → graph renders → letter generates.
- Confirm `SECRET_KEY` is required (app refuses to start without it).

## Server deployment (only if the mentor later wants central hosting)
Use the provided `docker-compose.yml` (app + MySQL behind a reverse proxy with
HTTPS), set `DATABASE_URL` to MySQL, and set `SESSION_COOKIE_INSECURE=false`. This
is **not** needed for the offline model — keep it as a documented option.
