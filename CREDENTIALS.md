# FundTrail — Development Credentials

> **⚠️ NEVER COMMIT REAL PASSWORDS.** The accounts below exist **only on your local
> dev machine** after you run the seed script. Production deployments must use
> `main/scripts/create_user.py`, which generates random per-machine passwords
> (this is a hard requirement from pentest finding FT-002 — do not work around it).

This is the first file to read after cloning. If you can't log in, you almost
certainly just need to run the seed script.

## Default dev accounts

| Role                  | Username   | Password          |
|-----------------------|------------|-------------------|
| Admin                 | `admin`    | `Admin@123456`    |
| Investigative Officer | `officer1` | `Officer@123456`  |

Passwords are 12+ characters because the app's password policy applies to dev
accounts too (the policy is never weakened).

## Locked out? Reset everything

From the project root:

```bash
python dev_seed.py
```

This creates the accounts if missing, resets their passwords to the table above,
clears any lockouts, disables 2FA on them, and prints the credential table again.
Run it as often as you like — it is idempotent.

## Safety guardrails built into the script

- Refuses to run when `DATABASE_URL` is set (i.e. against a real/shared database).
- Only ever touches the local SQLite dev database under `data/`.
- The login page shows a reminder hint about this script **in debug mode only** —
  production builds never reveal it.
