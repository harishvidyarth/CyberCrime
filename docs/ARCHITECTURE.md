# FundTrail — System Architecture

**Task #22.** How the pieces fit together.

## High-level flow
```
 Officer browser
      │  (HTTPS in prod / http on local offline machine)
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Flask app (main/app.py — monolith today; main/app/ = target) │
│                                                               │
│  Auth          → Flask-Login + scrypt + lockout + rate limit  │
│  CSRF/headers  → Flask-WTF + CSP/HSTS/X-Frame via after_request│
│  Ingestion     → pandas/openpyxl parse Excel → Transaction rows│
│  Analysis      → build layered fund-flow graph (D3.js)         │
│  Letters       → python-docx / reportlab → .docx & .pdf        │
│  IFSC lookup   → in-memory cache from IFSC_CODES.pkl           │
└───────────────┬───────────────────────────────┬───────────────┘
                ▼                                 ▼
        SQLite (default)                  Static assets
   fundtrail.db / kyc.db / poh.db         templates/ static/
   (or MySQL via DATABASE_URL)            (D3 graph, CSS)
```

## Components
| Layer | Where | Notes |
|-------|-------|-------|
| **Web/routes** | 37 routes (`app.py`) / blueprints (`app/routes/`) | auth, ingestion, analysis, letters, admin, main |
| **Auth & access** | `app/utils/security.py`, login route | `@login_required`, `@admin_required`, `check_case_access()` |
| **Data models** | `models.py` | `Transaction`, `User`, `Complaint`, `UploadedFile`, `UsageLog`, `KYCDetails`, `POHRefundDetails` |
| **Storage** | 3 SQLite binds | main + `kyc_store` + `poh_store` (separate so re-uploads don't wipe KYC/refund data) |
| **Reference data** | `IFSC_CODES.pkl` (~30 MB) | bank/branch/state lookup, cached in memory |
| **Documents** | `templates/*.docx` | letter templates filled per case |

## Trust boundaries
- **Browser ↔ app:** all state-changing routes need a valid session + CSRF token.
  Role checks are server-side (never UI-only) — see retest FT-003/FT-004.
- **App ↔ DB:** parameterised via SQLAlchemy ORM (no raw SQL string-building).
- **Excel upload:** untrusted input → validated extension, size cap (`MAX_ROWS`),
  cell sanitisation against formula injection (`sanitize_cell`).

## Request lifecycle (example: view a case graph)
1. `GET /graph/<ack_no>` → `@login_required` → `check_case_access(ack_no)` (IDOR guard)
2. `GET /graph_data/<ack_no>` returns JSON nodes/links
3. D3.js (`static/graph.js`) renders the interactive tree in `graph_tree1.html`
4. `after_request` stamps CSP / no-cache / security headers on the response

## Why it's structured for offline use
Single Flask process + embedded SQLite + bundled IFSC dataset → packageable as a
self-contained `.exe` per machine (no server, no network). This is why **SQLite,
not MySQL**, is the right default (see `PROJECT_BRIEFING.md`).

## Target architecture (the refactor, task #12)
Collapse the monolith into the existing `app/` package (blueprints already exist for
auth/ingestion/analysis/letters/admin/main) with a clean app factory, one config
module, and one models module — then delete `app.py`. This removes the duplication
and makes the 8-person team's branches stop colliding in one giant file.
