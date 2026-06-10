# FundTrail Analysis Tool

![CI](https://github.com/harishvidyarth/CyberCrime/actions/workflows/ci.yml/badge.svg)
**Version 2.0** · Python 3.10+ · Flask · fully offline-capable

A web-based tool for **cybercrime investigators** to trace stolen-money trails.
Officers upload bank-transaction Excel files; the app reconstructs how funds
moved account-to-account, draws an interactive flow graph, flags suspect /
repeater accounts, and auto-generates official letters to banks.

> New to the project? Read [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) first —
> it explains the whole thing from the basics.

## What's new in v2.0 (June 2026)

- **Case workflow** — Open / Under Investigation / Closed status on every case
- **Global search** across ACK numbers, accounts, transaction IDs and banks
- **Repeat-account (mule) detection** across cases · **case notes & timeline**
- **Refund recovery dashboard** and **admin metrics** (uploads/week, recovery rate)
- **Two-factor authentication (TOTP)**, audit-log viewer, idle auto-logout,
  password expiry + reuse prevention, last-login display
- **Bulk letter ZIP download**, Excel exports, multi-file batch upload
- **New design system UI** — sidebar navigation, dark mode, accessibility pass
- All dependency CVEs patched (`pip-audit` clean), GitHub Actions CI, `/healthz`

Full details in [`CHANGELOG.md`](CHANGELOG.md). Dev login credentials:
[`CREDENTIALS.md`](CREDENTIALS.md).

---

## 0. First Time Setup (developers — fastest path)

Foolproof, four steps, no passwords to lose:

```bash
# Step 1 — clone
git clone git@github.com:harishvidyarth/CyberCrime.git && cd CyberCrime

# Step 2 — install requirements (Python 3.10+)
python3 -m venv .venv && source .venv/bin/activate
pip install -r main/requirements.txt

# Step 3 — seed the DEV accounts (known passwords, dev machines only)
python dev_seed.py

# Step 4 — run, then log in with the credentials the script printed
cd main && python app.py        # -> http://127.0.0.1:5050
```

The dev accounts and reset instructions live in [`CREDENTIALS.md`](CREDENTIALS.md).
**Deploying for real?** Skip `dev_seed.py` and use `scripts/create_user.py`
(random per-machine passwords) as described in section 2 below.

## 1. What you need first

- **Python 3.10+** and **git**
- Nothing else — the IFSC dataset (`main/IFSC_CODES.pkl`) and everything needed to
  run now **come with the repo**. The app uses **embedded SQLite**, so there is no
  database server to install.

## 2. Get it running — copy & paste (macOS / Linux)

```bash
# 1) Clone (you must be a collaborator on the repo + have your SSH key set up)
git clone git@github.com:harishvidyarth/CyberCrime.git
cd CyberCrime

# 2) Create & activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 3) Install dependencies
pip install --upgrade pip
pip install -r main/requirements.txt

# 4) One-command setup: creates .env (with a fresh secret key) AND the first users
cd main
python scripts/create_user.py

# 5) Run
python app.py                        # -> http://127.0.0.1:5050
```

`create_user.py` **prints the admin & officer passwords** in the terminal and also
saves them to **`data/INITIAL_CREDENTIALS.txt`** (git-ignored) so you never lose
them. The passwords are **random and unique to your machine** — there is no shared
default. Run the script again any time you're locked out; it safely resets both
accounts (your `.env` is never overwritten).

Then open **<http://127.0.0.1:5050>**, log in (**role = Admin**, username `admin`,
password from the terminal). You'll be **required to set a new password on first
login**, after which you can delete `INITIAL_CREDENTIALS.txt`.

> ### ❓ "What is the default password when I clone?"
> **There isn't one — and that's on purpose.** A fixed password committed to the repo
> would be a security hole. Instead, `python scripts/create_user.py` generates a
> **fresh, random password** for `admin` and `officer` on *your* machine and:
> - **prints them in the terminal**, and
> - **saves them to `data/INITIAL_CREDENTIALS.txt`** (git-ignored).
>
> So your password = whatever the script printed/saved for your clone. **Lost it?**
> Just run `python scripts/create_user.py` again — it safely resets both accounts and
> writes the new passwords to the same file. You're forced to set your own password on
> first login anyway.

> **Port note:** on macOS, port **5000 is used by AirPlay Receiver**, so we default
> to **5050** via the `PORT` variable in `.env`. Set it to any free port.

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

## 6. Running the tests

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
