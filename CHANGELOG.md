# Changelog

All notable changes to FundTrail are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [3.0.0] — 2026-06-13

### Added
- **2FA QR code** rendered as inline SVG — no Pillow/PNG dependency, identical
  rendering on every platform. White background `<rect>` injected so the code
  is visible in dark mode; `mm` units replaced with integer `px` to prevent
  Windows browsers from collapsing the SVG.
- **One-click Docker scripts** `fundtrail.sh` (Mac/Linux) and `fundtrail.bat`
  (Windows) — single file per OS replaces the former four-file start/stop split.
  Both accept `start` (default) and `stop` sub-commands, auto-install Docker on
  first run, and wait for `/healthz` before printing the access URL.

### Changed
- **Codebase organization pass** (no behavior change):
  - `ruff format` applied to all 8 Python files; lint remains clean.
  - `app.py` now opens with a module docstring and a 14-section index;
    matching banner comments mark each section in the file.
  - Letter templates renamed to remove spaces:
    `Template for letter generation_suspect accounts.docx` → `letter_template_suspect_accounts.docx`,
    `Template for letter generation_victim account.docx` → `letter_template_victim_account.docx`
    (references updated in `app.py`).
- **Dark mode — analytics page**: `td`, `.kpi-val`, `.section-head h2`,
  `.amt-cell`, `.hold-pill`, `.bar-wrap`, `.dl-link`, and hover rows now use
  readable dark-palette colours under `[data-theme="dark"]`.
- **Dark mode — table alternating rows**: `style.css` base rule
  `table tr:nth-child(even) { background: #f2f2f2 }` overridden for dark mode
  with `#1e2d42` so near-white text stays readable across all pages.
- `fundtrail.sh` / `fundtrail.bat` replace `start.sh`, `stop.sh`, `start.bat`,
  `stop.bat` (4 files → 2; no functional change to the Docker workflow).
- Removed `main/FundTrail.spec` (obsolete PyInstaller build config, superseded
  by the Docker-first deployment model).

### Security (post-v2.0 fixes — 9 additional vulnerabilities)
- **IDOR — edit_officer**: officer lookup scoped to `_officers_q()`, blocking
  cross-group officer edits.
- **Group isolation — delete_complaint**: non-SuperAdmin Admins get 403 for
  complaints in another group.
- **Privilege escalation — available_ack_nos**: Admin path replaced with
  `_cases_q()`-scoped query, eliminating cross-group ACK leakage.
- **Missing auth — download_fundtrail_pdf**: `check_case_access()` called before
  PDF generation.
- **HSTS mis-fire on HTTP LAN**: `Strict-Transport-Security` header only sent
  when `SESSION_COOKIE_INSECURE=false`.
- **Login timing side-channel**: random 50–150 ms sleep equalises success/failure
  response times.
- **IDOR — delete_by_ack**: non-SuperAdmin Admins blocked from deleting another
  group's cases.
- **IDOR — assign_case**: complaint lookup changed to `_cases_q().filter_by()`,
  scoping the reassignment to the requesting admin's own cases.
- **IDOR — view_complaint**: non-SuperAdmin Admins blocked from viewing complaints
  with a different `owner_admin_id`.

## [2.0.0] — 2026-06-10

### Added
- **Case workflow**: Open / Under Investigation / Closed status on every case.
- **Global search** across ACK numbers, accounts, transaction IDs, and banks (scoped to the user's cases).
- **Repeat-account (mule) detection** across cases (admin).
- **Case notes & chronological timeline** per case.
- **Bulk letter download** — all generated letters for a case as one ZIP.
- **Excel export** of analytics (admin-wide and per-officer).
- **Refund recovery dashboard** (held vs refunded, per case and overall).
- **Two-factor authentication** (TOTP, authenticator-app based, per user).
- **In-app audit log viewer** with filters and pagination (admin).
- **Idle-session warning** with auto-logout; **last-login** display.
- **Password expiry (90 days, configurable)** and reuse prevention (last 5).
- **Admin metrics dashboard** (uploads/week, status mix, recovery rate).
- **Health-check endpoint** `/healthz`; **request-ID structured logging** (`LOG_FORMAT=json`);
  **alerts.log** for 500s.
- **Developer seed script** `dev_seed.py` + `CREDENTIALS.md` (dev only; production
  still uses random per-machine passwords).
- **Design system** (`static/css/design-system.css`): tokens, dark mode, components;
  sidebar layout; redesigned pages; accessibility pass (ARIA, contrast, keyboard).
- GitHub Actions CI (tests + dependency audit), ruff lint config, pytest wrapper.
- Gzip response compression; static-asset caching; debounced table filters.

### Changed
- Runtime upgraded to **Python 3.11** (3.9 is EOL); all dependency CVEs patched
  (`requests`, `python-dotenv`, `urllib3`, `pillow`) — `pip-audit` clean.
- Login failures now show one generic message (anti user-enumeration); session is
  rotated at login (fixation hygiene).
- Internal error details are no longer returned to clients (server log only).
- Deprecated `X-XSS-Protection` sniffer disabled (`0`); CSP remains the control.
- `datetime.utcnow` replaced with timezone-aware UTC timestamps.

### Removed
- Dead `/upload` endpoint (unused, contradictory size limits).
- Stale `graph_test.html` scratch artifact; dead commented code blocks.

### Security
- 10 known CVEs across 4 packages remediated; `pip-audit` reports none.

## [1.x] — Feb–Jun 2026
- Phases 1–9: pentest remediation (14/14 findings fixed), per-officer case isolation,
  CSRF, nonce CSP, rate limiting, account lockout, scrypt hashing, offline vendored
  JS, DB consolidation, test suites. See `docs/SECURITY_FINDINGS.md`.
