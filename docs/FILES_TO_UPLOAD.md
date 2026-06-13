# What goes to GitHub — and what must NEVER

> The original repo committed **real victim data and 100 MB+ of binaries**.
> This guide prevents that from happening again. Read it before any `git push`.

## ✅ Safe to commit (source code & config templates)

| Item | Why |
|------|-----|
| `main/app.py`, `main/app/`, `main/models.py`, `main/ifsc_utils.py` | Application source |
| `main/templates/`, `main/static/` | UI (HTML/CSS/JS, logos) |
| `main/migrations/` | Database schema history |
| `main/scripts/` | Admin & security-verification scripts |
| `main/requirements.txt` | Dependency list |
| `main/setup.sql` | DB/user creation (with placeholder password only) |
| `main/build_configs/*.spec` | PyInstaller build configs (if re-added) |
| `.env.example`, `.gitignore`, `README.md`, `docs/` | Project hygiene & docs |

## ⛔ NEVER commit (data, secrets, bloat)

| Item | Why it's dangerous |
|------|--------------------|
| `*.db` (`fundtrail.db`, `kyc_details.db`, `poh_refund_details.db`) | **Real case data / victim PII** |
| `uploads/`, `main/uploads/` | **Real victim/suspect bank Excel files** |
| `generated_letters/` | **Official letters naming real people** |
| `.env` | Contains the real `SECRET_KEY` / DB password |
| `IFSC_CODES.json` / `.pkl` / `.xlsx` | 30–51 MB each; bloats history forever |
| `*.exe`, `*.msi`, `*.zip`, `dist/`, `build/`, `.venv/` | Build artifacts, not source |

## 📦 The large IFSC dataset (needed to run, too big for Git)

`IFSC_CODES.pkl` (~30 MB) is required at runtime but should not live in Git.
Options, best first:
1. **Shared drive / OneDrive / Google Drive** — teammates download it into `main/`.
2. **Git LFS** — `git lfs track "IFSC_CODES.pkl"` if you must keep it in the repo.
3. **Regenerate it** from the source `IFSC_CODES.xlsx` with a small script (cleanest long-term).

## ⚠️ The existing repo history already contains PII

The current `.git` history (9 commits ahead of `origin`) already has committed
`.db` files and victim Excel uploads. A normal `.gitignore` does **not** remove
what is already in history. Two safe paths:

- **Recommended — start a clean repo from `new_files/`** (fresh history, zero PII):
  ```bash
  cd "new_files"
  git init
  git add .
  git commit -m "Clean FundTrail source (no data, no secrets)"
  git branch -M main
  # create a new EMPTY private repo on GitHub, then:
  git remote add origin git@github.com:<your-org>/<new-repo>.git
  git push -u origin main
  ```
- **Or scrub the old history** with `git filter-repo` / BFG before pushing again
  (more error-prone; do it with your mentor).

> **Important:** because the old repo `Lubhika/fundtrail-updated-` may already be
> shared, treat any data in it as exposed. Tell your mentor — for a police tool,
> committed victim PII is a data-handling incident, not just untidy.
