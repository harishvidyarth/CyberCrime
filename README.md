# FundTrail Analysis Tool

A web-based tool for **cybercrime investigators** to trace stolen-money trails.
Officers upload bank-transaction Excel files; the app reconstructs how funds
moved account-to-account, draws an interactive flow graph, flags suspect /
repeater accounts, and auto-generates official letters to banks.

> New to the project? Read [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) first —
> it explains the whole thing from the basics.

---

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
├── .env.example          # template; your real .env is git-ignored
├── README.md             # this file
├── docs/                 # HOW_IT_WORKS, architecture, security, deployment…
└── main/
    ├── app.py            # the running application (being refactored into app/)
    ├── app/              # modular version (target architecture)
    ├── models.py         # database tables (Transaction, User, Complaint…)
    ├── ifsc_utils.py     # local IFSC -> bank/branch/state lookup
    ├── IFSC_CODES.pkl    # the 176k-entry IFSC dataset (ships with the repo)
    ├── templates/        # HTML pages
    ├── static/           # CSS / JS / images (D3 fund-flow graph)
    ├── migrations/       # Alembic database migrations
    └── scripts/          # admin + security-verification scripts
```

## 5. Roles

| Role | Can do |
|------|--------|
| **Admin** | Manage officers, view all cases, analytics, audit logs |
| **Investigative Officer** | Upload data, trace funds, put accounts on hold, generate letters |
| **Viewer** | Read-only view of fund flows and reports |

---
More: [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) (workflow & mental model) ·
[`docs/PROJECT_BRIEFING.md`](docs/PROJECT_BRIEFING.md) (architecture, security, plan) ·
[`docs/SECURITY_FINDINGS.md`](docs/SECURITY_FINDINGS.md).
