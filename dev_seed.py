#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  FundTrail dev_seed.py — FOR DEVELOPMENT ONLY                     ║
║                                                                   ║
║  Resets every user account to a KNOWN, PUBLICLY DOCUMENTED        ║
║  password so developers are never locked out of a fresh clone.   ║
║                                                                   ║
║  NEVER run this against a production database. Real deployments  ║
║  must use main/scripts/create_user.py, which generates random    ║
║  per-machine passwords (pentest finding FT-002).                 ║
╚══════════════════════════════════════════════════════════════════╝

Usage:  python dev_seed.py          (from the project root)
"""

import os
import sys
import secrets

ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(ROOT, "main")
sys.path.insert(0, MAIN)
os.chdir(MAIN)

# The app refuses to start without a SECRET_KEY. Use the real .env when present;
# otherwise a throwaway key is fine — we only need DB access, not sessions.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(MAIN, ".env"))
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")

# Guardrail: a configured DATABASE_URL means a real (possibly shared/production)
# database. Known passwords there would recreate pentest finding FT-002.
if os.environ.get("DATABASE_URL"):
    print("ERROR: DATABASE_URL is set — this looks like a real deployment, not a dev clone.")
    print("       dev_seed.py only runs against the local SQLite dev database.")
    print("       For real deployments use: python scripts/create_user.py")
    sys.exit(1)

import contextlib  # noqa: E402

with contextlib.redirect_stdout(open(os.devnull, "w")):
    from app import app  # noqa: E402
from models import db, User  # noqa: E402

# NOTE: passwords must satisfy the app's own policy (12+ chars, upper/lower/digit/
# special) — the policy is never weakened, even for dev accounts.
DEV_ACCOUNTS = [
    ("Admin", "admin", "Admin@123456"),
    ("Investigative Officer", "officer1", "Officer@123456"),
]


def reset_account(role, username, password):
    """Create-or-reset one dev account; returns a status string for the table."""
    user = User.query.filter_by(username=username).first()
    created = user is None
    if created:
        user = User(username=username, role=role)
        db.session.add(user)
    user.role = role
    try:
        user.set_password(password)
        status = "created" if created else "reset"
    except ValueError as exc:
        if "recent passwords" in str(exc):
            status = "unchanged"  # already on this dev password
        else:
            raise
    # Dev convenience: no forced change, no lockout, no 2FA on seeded accounts.
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.totp_secret = None
    return status


def main():
    print(__doc__.split("Usage:")[0])
    with app.app_context():
        db.create_all()
        rows = []
        for role, username, password in DEV_ACCOUNTS:
            status = reset_account(role, username, password)
            rows.append((role, username, password, status))
        db.session.commit()

    w_role, w_user, w_pass = 10, 14, 18
    line = f"╠{'═' * w_role}╬{'═' * w_user}╬{'═' * w_pass}╣"
    print(f"╔{'═' * (w_role + w_user + w_pass + 2)}╗")
    print(f"║{'FundTrail — Dev Credentials'.center(w_role + w_user + w_pass + 2)}║")
    print(f"╠{'═' * w_role}╦{'═' * w_user}╦{'═' * w_pass}╣")
    print(f"║{'Role'.center(w_role)}║{'Username'.center(w_user)}║{'Password'.center(w_pass)}║")
    print(line)
    for role, username, password, _status in rows:
        short_role = "Admin" if role == "Admin" else "Officer"
        print(f"║{short_role.center(w_role)}║{username.center(w_user)}║{password.center(w_pass)}║")
    print(f"╚{'═' * w_role}╩{'═' * w_user}╩{'═' * w_pass}╝")
    for _role, username, _password, status in rows:
        print(f"  - {username}: {status}")
    print("\nLog in at http://127.0.0.1:5050 — see CREDENTIALS.md for details.")
    print("REMINDER: development only. Production setups use scripts/create_user.py.")


if __name__ == "__main__":
    main()
