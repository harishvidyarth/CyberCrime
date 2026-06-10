# FundTrail — How It Works (the mental model)

Read this first. It explains the whole app in plain language — what it does, how a
request flows, and which file does what — so you can start working on it confidently.

---

## 1. The 30-second picture
A victim is cheated online. The money doesn't stay in one place — the fraudster
**moves it through many bank accounts** (layer by layer) and finally pulls it out
(ATM, POS, cheque, AEPS). The police get a bank-transaction export for the case.

**FundTrail turns that messy Excel into a picture**: a tree showing the victim's
account at the top and the chain of accounts the money flowed into, with bank/state
info, so the officer can see where the money went, freeze suspect accounts, and send
official letters to banks.

## 2. What an officer actually does (the real workflow)
1. **Log in** (Admin / Investigative Officer).
2. **Upload** the bank Excel file for a complaint (identified by an *Acknowledgement
   Number*, `ack_no`).
3. The app **reads the Excel**, splits out money transfers, ATM/POS/cheque/AEPS
   withdrawals, and "put on hold" entries, and saves each as a **transaction**.
4. **Search the `ack_no`** → the app draws the **fund-flow graph** (D3.js): victim
   account → layer-1 accounts → layer-2 … Colours mean things (see §6).
5. Click nodes to see details, **mark suspect accounts "on hold"**, add KYC, and
   **generate letters** (.docx / PDF) to the banks.
6. **Analytics**: totals, state-wise summary, repeater accounts, etc.

## 3. How it's built (the pieces)
```
Browser  ──HTTP──►  Flask app (Python)  ──►  SQLite database (case data)
                         │                    IFSC_CODES.pkl (bank/state lookup)
                         └──► HTML templates + D3.js (draws the graph)
```
- **Flask** = the web server written in Python. It receives URLs ("routes") and
  returns HTML or JSON.
- **Templates** (`main/templates/*.html`) = the pages the browser shows.
- **SQLite** (`data/fundtrail.db`) = a single-file database holding cases,
  transactions, users, logs.
- **D3.js** (`static/`, `graph_tree1.html`) = the JavaScript that draws the
  interactive graph in the browser.
- **IFSC lookup** (`ifsc_utils.py` + `IFSC_CODES.pkl`) = turns a bank IFSC code into
  bank name / branch / **state** (used for the state-wise features).

## 4. The data model (the main tables, in `models.py`)
| Table | What it holds |
|-------|---------------|
| **User** | login accounts (username, hashed password, role, lockout fields) |
| **Complaint** | one case (`ack_no`, who uploaded/was assigned) |
| **UploadedFile** | the uploaded Excel + metadata |
| **Transaction** | the core record — one money movement: from/to account, amount, layer, IFSC, **state**, ATM/cheque/hold fields |
| **KYCDetails / POHRefundDetails** | KYC + "put on hold" refund info, kept separately so re-uploading the Excel doesn't wipe them |
| **UsageLog** | audit trail of who did what |

The **graph is built from `Transaction` rows**: each `from_account → to_account` is a
link; `layer` decides the depth.

## 5. What happens when you… (request lifecycle)
- **Log in** → `POST /login` → checks username **+ role + password**, applies lockout,
  starts a session → redirects Admin to `/admin_dashboard`, others to `/index`.
- **Upload Excel** → `POST /upload_excel` (`app.py`) → reads the sheets with pandas →
  cleans each cell (anti-injection) → creates `Transaction` rows.
- **View graph** → `GET /graph/<ack_no>` checks you're allowed to see this case
  (`check_case_access`), then `GET /graph_data/<ack_no>` returns JSON nodes/links →
  D3 draws the tree.
- **Statewise summary** → `GET /statewise_summary/<ack_no>` → looks up each account's
  **state from `IFSC_CODES.pkl`** (instant, local) → groups by state/region.
- **Generate letter** → `POST /generate_letter(_pdf|_docx)` → fills a Word template
  with the account's details → returns the file.
- **Every response** passes through `after_request`, which stamps security headers
  (CSP, no-cache, etc.).

## 6. Reading the graph (what the colours/shapes mean)
- **Green box (top)** = the Acknowledgement (case) node.
- **Orange box** = the **victim** account.
- **Green boxes** = suspect/destination accounts in the trail.
- **Red outline** = flagged / special status; **lock icon** = put on hold.
> ⚠️ These colours are set by the D3 code and **carry investigative meaning** — don't
> change them when restyling.

## 7. Roles & access
- **Admin** → everything: manage officers, all cases, analytics, logs.
- **Investigative Officer** → upload, trace, hold, letters — but only **their own /
  unassigned** cases (`check_case_access` enforces this).

*(The read-only Viewer role was removed — only Admin and Investigative Officer remain.)*

## 8. Security model (short version)
Login lockout + strong hashing (scrypt), CSRF on every form, role checks on every
route, per-case access control (no peeking at others' cases), strict security headers
+ CSP, secret key from the environment (never hardcoded). Full status:
[`SECURITY_FINDINGS.md`](SECURITY_FINDINGS.md).

## 9. Where to be careful (so you don't break things)
- `main/app.py` is **one big file (~3,500 lines)** — we're slowly splitting it into the
  `main/app/` package. Change one route at a time and test.
- The **graph page** (`graph_tree1.html`, ~2,000 lines of D3) is delicate — restyle
  the frame, not the graph logic or node colours.
- **Never commit** real `.db` files, `uploads/`, or `.env` (secrets/PII) — see
  [`FILES_TO_UPLOAD.md`](FILES_TO_UPLOAD.md).
- The Excel importer currently **ignores POS/AEPS sheets** (a known bug, task #56).

## 10. How to start working on it
1. Get it running (README §2).
2. Log in, upload a sample Excel from the project's `uploads/` folder, view the graph.
3. Pick one small task (see [`TASK_CHECKLIST.md`](TASK_CHECKLIST.md)), make a branch,
   change it, test, open a PR. Follow [`GIT_WORKFLOW.md`](GIT_WORKFLOW.md) and
   [`CODING_STANDARDS.md`](CODING_STANDARDS.md).

That's the whole mental model. When in doubt, search the route name in `app.py` and
follow what it does — every feature is one route.
