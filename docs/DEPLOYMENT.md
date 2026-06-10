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

## Building the single-file app (PyInstaller)
> **PyInstaller cannot cross-compile.** You must build on each target OS (or via a
> VM/Docker for Linux). One machine cannot produce binaries for all three OSes.

| Target | Build on | Output | Command (from `main/`) |
|--------|----------|--------|------------------------|
| **Windows .exe** | Windows | `dist/FundTrail.exe` | `pyinstaller FundTrail.spec` |
| **macOS** | macOS (this Mac) | `dist/FundTrail` / `.app` | `pyinstaller FundTrail.spec` |
| **Linux** | Linux (or Docker) | `dist/FundTrail` | `pyinstaller FundTrail.spec` |

The existing `FundTrail.spec` / `build_configs/*.spec` already bundle data files
(templates, IFSC dataset). Verify the spec includes `IFSC_CODES.pkl`, the `.docx`
templates, and `templates/` + `static/` via its `datas=[...]`.

### Linux build via Docker (no Linux machine needed)
```bash
docker run --rm -v "$PWD":/src -w /src/main python:3.11-slim bash -lc \
  "pip install -r requirements.txt pyinstaller && pyinstaller FundTrail.spec"
# dist/FundTrail (Linux) appears in main/dist/
```

## Post-build checklist
- Launch the binary on a clean machine (no Python) → app starts, login works.
- First run creates the SQLite DBs in the secured data dir (perms 600).
- Upload a sample Excel → graph renders → letter generates.
- Confirm `SECRET_KEY` is required (app refuses to start without it).

## Server deployment (only if the mentor later wants central hosting)
Use the provided `docker-compose.yml` (app + MySQL behind a reverse proxy with
HTTPS), set `DATABASE_URL` to MySQL, and set `SESSION_COOKIE_INSECURE=false`. This
is **not** needed for the offline model — keep it as a documented option.
