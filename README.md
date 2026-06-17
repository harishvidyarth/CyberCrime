# FundTrail Analysis Tool

![CI](https://github.com/harishvidyarth/CyberCrime/actions/workflows/ci.yml/badge.svg)
**Version 3.0** · Python 3.11+ · Flask · fully offline-capable

A web-based tool for **cybercrime investigators** to trace stolen-money trails.
Officers upload bank-transaction Excel files; the app reconstructs how funds
moved account-to-account, draws an interactive flow graph, flags suspect /
repeater accounts, and auto-generates official letters to banks.

> New to the project? Read [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) first —
> it explains the whole thing from the basics.

## What's new in v3.0 (June 2026)

- **9 additional security fixes** — IDOR and group-isolation bugs found and patched
  in post-v2.0 internal audit (routes: `edit_officer`, `delete_complaint`,
  `available_ack_nos`, `download_fundtrail_pdf`, `delete_by_ack`, `assign_case`,
  `view_complaint`; plus HSTS mis-fire and login timing side-channel)
- **2FA QR code** rendered as inline SVG — no Pillow/PNG dependency, works on all
  platforms, visible in dark mode
- **One-click Docker scripts** consolidated: `fundtrail.sh` (Mac/Linux) +
  `fundtrail.bat` (Windows) replace the former four-file start/stop split
- **Dark mode fixes** — analytics contrast + table alternating-row legibility

v2.0 highlights: case workflow, global search, mule detection, 2FA, audit log,
idle auto-logout, password expiry, bulk ZIP download, design system UI.

Full details in [`CHANGELOG.md`](CHANGELOG.md). Dev login credentials:
[`CREDENTIALS.md`](CREDENTIALS.md).

---

## 0. Running FundTrail — first time & every time

Two ways to run it: **Docker** (one command, recommended) or **plain Python** (no
Docker). Both serve the app at **<http://127.0.0.1:5050>** and keep all data **on
your own machine**. In both modes the database persists between runs, so **your
login stays the same every time** — it is never reset on restart.

You only need **git** (and either Docker *or* Python 3.11+). The IFSC dataset and
everything else needed to run ships with the repo; the database is embedded SQLite,
so there is no database server to install.

---

### A) With Docker  *(recommended — one command)*

`fundtrail.sh` (Mac/Linux) and `fundtrail.bat` (Windows) auto-install Docker if
missing, generate `.env` with a fresh secret key on first run, build the image, and
wait until the app is ready. The database lives in a Docker volume (`fundtrail-data`)
that **survives every stop / start / rebuild**.

**First time (after cloning):**

```bash
# Mac / Linux
git clone git@github.com:harishvidyarth/CyberCrime.git && cd CyberCrime
chmod +x fundtrail.sh
./fundtrail.sh                         # builds + starts -> http://127.0.0.1:5050
```

```bat
:: Windows  (double-click fundtrail.bat, or from Command Prompt)
git clone git@github.com:harishvidyarth/CyberCrime.git && cd CyberCrime
fundtrail.bat                          :: builds + starts -> http://127.0.0.1:5050
```

First login — the **same on every machine**, and you're forced to change it
immediately: **`admin` / `Admin@123456`** (and **`officer` / `Officer@123456`**).
The exact values are also saved here:

```bash
docker compose exec fundtrail cat /data/INITIAL_CREDENTIALS.txt
```

**Every time after that (nth time):**

```bash
# Mac / Linux                          # Windows
./fundtrail.sh          # start        fundtrail.bat
./fundtrail.sh stop     # stop         fundtrail.bat stop
```

Same data, same login. ⚠️ Don't run `docker compose down -v` — the `-v` deletes the
data volume (that is the only thing that wipes your DB and forces a new password).

---

### B) Without Docker  *(plain Python 3.11+)*

Runs the app directly with embedded SQLite. The database is a local file at
`data/fundtrail.db` and persists between runs.

**First time (after cloning):**

```bash
# Mac / Linux
git clone git@github.com:harishvidyarth/CyberCrime.git && cd CyberCrime
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r main/requirements.txt
cd main && python scripts/create_user.py   # creates .env + first users (prints passwords)
python app.py                              # -> http://127.0.0.1:5050
```

```bat
:: Windows  (Command Prompt)
git clone git@github.com:harishvidyarth/CyberCrime.git && cd CyberCrime
python -m venv .venv && .venv\Scripts\activate
pip install --upgrade pip && pip install -r main\requirements.txt
cd main && python scripts\create_user.py
python app.py                              :: -> http://127.0.0.1:5050
```

First login is the **same known default on every machine** — **`admin` / `Admin@123456`**
(and **`officer` / `Officer@123456`**) — and you're **forced to change it on first
login**. The values are also saved to `data/INITIAL_CREDENTIALS.txt`. **Locked out?**
Run `create_user.py` again to reset both accounts (your `.env` is never overwritten).

**Every time after that (nth time):**

```bash
# Mac / Linux                          :: Windows
source .venv/bin/activate              .venv\Scripts\activate
cd main && python app.py               cd main && python app.py
```

Same data, same login. *(Dev shortcut: `python dev_seed.py` from the repo root seeds
known dev passwords — dev machines only; see [`CREDENTIALS.md`](CREDENTIALS.md).)*

> **Port note:** on macOS, port **5000** is used by AirPlay Receiver, so we default to
> **5050** via the `PORT` variable in `.env`. Set it to any free port.
>
> **First-login password:** the same known default (`admin` / `Admin@123456`,
> `officer` / `Officer@123456`) is used on every fresh install so you're never locked
> out after a clone — and you're **forced to change it on first login**. To use a
> different seed, set `SEED_ADMIN_PASSWORD` / `SEED_OFFICER_PASSWORD` before first run.

## 3. Database — SQLite (no setup)

FundTrail uses **embedded SQLite**: a single file (`data/fundtrail.db`), created
automatically on first run. No server, no configuration — ideal for the offline,
per-machine deployment. (It can also run on MySQL via `DATABASE_URL` if ever hosted
centrally — see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) and "Hosting securely".)

## 4. Project layout

```
CyberCrime/
├── README.md             # this file
├── CHANGELOG.md          # version history (v2.0 = enterprise upgrade)
├── CREDENTIALS.md        # DEV-ONLY default accounts + reset instructions
├── dev_seed.py           # DEV-ONLY: reset accounts to known passwords
├── LICENSE               # proprietary — internal TN Police use
├── pyproject.toml        # ruff lint + pytest configuration
├── fundtrail.sh          # one-click start/stop for Mac/Linux  (./fundtrail.sh [start|stop])
├── fundtrail.bat         # one-click start/stop for Windows    (fundtrail.bat [start|stop])
├── .github/workflows/    # CI: tests + dependency audit + lint on every push
├── docs/                 # HOW_IT_WORKS, architecture, security, deployment…
└── main/
    ├── app.py            # the running application (all routes)
    ├── models.py         # database tables (Transaction, User, Complaint…)
    ├── ifsc_utils.py     # local IFSC -> bank/branch/state lookup
    ├── IFSC_CODES.pkl    # the 176k-entry IFSC dataset (ships with the repo)
    ├── .env.example      # template; your real .env is git-ignored
    ├── templates/        # HTML pages (_layout.html = sidebar base layout)
    ├── static/           # css/design-system.css, app.js, vendored D3 graph libs
    ├── migrations/       # Alembic database migrations
    ├── tests/            # smoke + access-control suites (run before/after changes)
    └── scripts/          # admin + security-verification scripts
```

## 5. Roles

| Role | Can do |
|------|--------|
| **Admin** | Manage/assign officers & cases, all analytics, metrics, audit logs, repeat-account detection |
| **Investigative Officer** | Upload data, trace funds, put accounts on hold, generate letters, case notes & status |

(The old read-only *Viewer* role was removed — every account authenticates with a password.)

## 6. Docker (optional — one-command container)

Docker is **not required** (the tool runs fine as a plain Python app), but the
repo ships convenience scripts that auto-install Docker if missing:

```bash
# Mac / Linux
./fundtrail.sh          # start  (builds image + waits for ready)
./fundtrail.sh stop     # stop

# Windows — double-click fundtrail.bat, or from Command Prompt:
fundtrail.bat           # start
fundtrail.bat stop      # stop
```

Or use Docker directly:

```bash
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") docker compose up -d
# -> http://127.0.0.1:5050   (DB persists in the fundtrail-data volume)
```

Gunicorn (2 workers, --preload), non-root user, /healthz healthcheck. The
image contains **no secrets and no case data** (.dockerignore excludes .env,
databases, uploads and generated letters). For any non-localhost deployment put
an HTTPS reverse proxy in front and set `SESSION_COOKIE_INSECURE=false`.

## 7. Running the tests

```bash
cd main
python tests/smoke_test.py            # routes, auth, pages render, CSRF
python tests/test_access_control.py   # per-officer isolation, validators
```

Both suites are dependency-free, use a throwaway temp database, and run in CI on
every push. Run them **before and after every change**.

---
More: [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) (workflow & mental model) ·
[`docs/PROJECT_BRIEFING.md`](docs/PROJECT_BRIEFING.md) (architecture, security, plan) ·
[`docs/SECURITY_FINDINGS.md`](docs/SECURITY_FINDINGS.md).
