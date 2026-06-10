# Changelog

All notable changes to FundTrail are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

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
