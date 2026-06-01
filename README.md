# FundTrail Analysis Tool

A web-based tool for **cybercrime investigators** to trace stolen-money trails.
Officers upload bank-transaction Excel files; the app reconstructs how funds
moved account-to-account, draws an interactive flow graph, flags suspect /
repeater accounts, and auto-generates official letters to banks.

> This is the **clean, upload-ready copy** of the project. It contains source
> code only — no databases, no case files, no large datasets, no secrets.
> See [`docs/FILES_TO_UPLOAD.md`](docs/FILES_TO_UPLOAD.md) for what was removed and why.

---

## 1. What you need first

- **Python 3.10+**
- **MySQL 8+** (the project target) — or skip it and use the built-in SQLite fallback for quick dev.
- The IFSC reference dataset (`IFSC_CODES.pkl`) — too large for Git; copy it into `main/`
  from the original project folder or your shared drive (see `docs/FILES_TO_UPLOAD.md`).

## 2. Set up (macOS / Linux)

```bash
cd "new files"

# 1) virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2) dependencies
pip install -r main/requirements.txt

# 3) configuration
cp .env.example .env
# then edit .env and set a real SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 3. Choose your database

**Option A — SQLite (zero setup, good for development).**
Leave `DATABASE_URL` unset in `.env`. The app creates `data/fundtrail.db` automatically.

**Option B — MySQL (project target).**
```bash
mysql -u root -p < main/setup.sql          # creates DB + 'fundtrail' user
# then in .env, set:
# DATABASE_URL=mysql+pymysql://fundtrail:YOUR_PASSWORD@localhost:3306/fundtrail
```

## 4. Create the first users and run

```bash
cd main
python scripts/create_user.py     # creates admin / officer / viewer
python app.py                     # starts http://127.0.0.1:5000
```

Open <http://127.0.0.1:5000> and log in.

> **Local-login gotcha:** the app sets `SESSION_COOKIE_SECURE = True`, which tells
> some browsers to send the session cookie only over HTTPS. If login "succeeds but
> bounces back" on `http://127.0.0.1`, that's why. The fix (planned) is to make this
> flag depend on an environment variable so it is `False` in local dev and `True` in
> production. See `docs/PROJECT_BRIEFING.md`.

## 5. Project layout

```
new files/
├── .env.example          # copy to .env, fill in secrets
├── .gitignore            # keeps data/secrets out of Git
├── README.md             # this file
├── docs/                 # briefing, security tracker, upload guide
└── main/
    ├── app.py            # the running application (monolith — refactor planned)
    ├── app/              # half-finished modular version (target architecture)
    ├── models.py         # database models
    ├── templates/        # HTML
    ├── static/           # CSS / JS / images (D3 graph lives here)
    ├── migrations/       # Alembic DB migrations
    ├── scripts/          # admin & security-verification scripts
    └── setup.sql         # MySQL database + user creation
```

## 6. Roles

| Role | Can do |
|------|--------|
| **Admin** | Manage users, view all cases, system analytics, logs |
| **Investigative Officer** | Upload data, trace funds, put accounts on hold, generate letters |
| **Viewer** | Read-only view of fund flows and reports |

---
See [`docs/PROJECT_BRIEFING.md`](docs/PROJECT_BRIEFING.md) for the full architecture,
known issues, security status, the 60-day plan, and questions for your mentor.
