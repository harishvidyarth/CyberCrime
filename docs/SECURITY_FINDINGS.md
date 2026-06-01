# FundTrail — Security Findings Tracker

**Authoritative source:** *Security Vulnerability Retest Report v2.0* (Sandeep V,
Tamil Nadu Cyber Crime Wing). Initial pentest **3 Feb 2026**, retest **19 Feb 2026**,
ref `PENTEST-FUNDTRAIL-2026-001`. Original PDFs in `old files/reports/`.

## Headline
- Initial assessment: **14 findings** — 4 Critical, 4 High, 3 Medium, 3 Low.
- Retest result: **14/14 remediated** (1 accepted-risk). 0 open at retest time. ✅
- **⚠️ BUT the code was edited AFTER the retest (app.py dated May 13) and some
  verified fixes have REGRESSED.** "Maintaining integrity" = restoring these.

Status legend: ✅ fixed & still holds · 🟡 fix weakened / partial regression · 🔴 regressed (re-introduced)

## The 14 official findings vs. current code

| ID | Finding | Severity (CVSS) | Retest | **Current code** | Action |
|----|---------|-----------------|--------|------------------|--------|
| FT-001 | IDOR — mass financial data exposure | Critical (9.8) | ✅ FIXED | ✅ `check_case_access()` used ×8 in app.py | keep |
| FT-002 | Hardcoded admin credentials | Critical (9.8) | ✅ FIXED | 🟡 app generates strong random pw, **but** `reset_admin_password.py`/`reset_officer_password.py` set `admin123`/`officer123`, bypassing the policy | don't ship weak creds; force change |
| FT-003 | Viewer authentication bypass | Critical (9.1) | ✅ FIXED | ✅ all roles require password | keep |
| FT-004 | Unauthenticated API endpoints | Critical (9.1) | ✅ FIXED | ✅ `@login_required` / `@admin_required` | keep |
| FT-005 | Database files world-readable | High (8.6) | ✅ FIXED | 🟡 **partial regression** — `_ensure_secure_file()` only secures the `data/` copies; **stray 755 (world-readable) DB copies** with password hashes exist in `main/` and `main/instance/` | delete strays (DB consolidation), enforce 600 |
| FT-006 | Weak / hardcoded secret key | High (8.1) | ✅ FIXED (fallback removed, `RuntimeError` if unset) | 🔴 **REGRESSED** — hardcoded fallback re-added at `app.py:408` (`"fallback-fundtrail-secret-key-12345!@#"`) | restore RuntimeError, remove fallback |
| FT-007 | Weak password hashing | High (7.5) | ✅ FIXED | ✅ scrypt + lockout(5) + 5/min rate limit | keep |
| FT-008 | Verbose errors / info disclosure | Medium (5.3) | ✅ FIXED | ✅ generic errors, `FLASK_DEBUG` defaults False | keep |
| FT-009 | Missing SRI on CDN resources | Medium (5.0) | ✅ FIXED | ✅ CSP set; ⏳ spot-check `integrity=` still in templates | verify in templates |
| FT-010 | Insecure session cookie config | Medium (4.8) | ✅ FIXED | 🟡 flags set, but `SESSION_COOKIE_SECURE=True` **blocks login over local http** (your offline/dev case) | make env-conditional |
| FT-011 | Server version disclosure | Low (3.7) | ✅ FIXED | ✅ `StripServerHeaderMiddleware` + `server_version=""` | keep |
| FT-012 | Missing Cache-Control headers | Low (3.1) | ✅ FIXED | ✅ `after_request` sets `no-store` | keep |
| FT-013 | Password autocomplete enabled | Info | ✅ ACCEPTED RISK | n/a (modern browsers ignore it) | none |
| FT-014 | Stored XSS via officer creation | High (7.5) | ✅ FIXED | ✅ Jinja2 auto-escape + nonce CSP | keep |

## Defence-in-depth controls confirmed present (from retest §4, verified in code)
Rate limiting (`flask_limiter`, 5/min login), account lockout (15 min after 5 fails),
password complexity (12+), forced password change, nonce-based CSP, security headers
(X-Frame-Options, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy),
timing-attack prevention (dummy-hash compare), centralized logging, open-redirect
prevention (`is_safe_url`).

## Additional findings from our own review (not in the original 14)

| ID | Finding | Severity | Action |
|----|---------|----------|--------|
| R-01 | **Real victim PII + case `.db` files committed to Git** | High (privacy) | clean repo (`docs/FILES_TO_UPLOAD.md`) |
| R-02 | **~5 scattered DB copies** at different paths (monolith vs package) | High | consolidate to one store (fixes FT-005 strays + Excel bug) |
| R-03 | Placeholder `SECRET_KEY` shipped in `.env` | Medium | ship only `.env.example`; generate real key |
| R-04 | Excel upload validation depth (real `.xlsx`? size cap? formula injection?) | Medium | verify/harden `upload_excel()` |

## How to verify a fix (your regression net)
```bash
cd main
python scripts/verify_secret_key.py        # etc. — one per finding
```
A finding is only ✅ when its verify script passes. Re-run them after every change
so we never silently regress a fix again (which is exactly what happened to FT-006).
