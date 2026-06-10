# FundTrail — Project Briefing & 60-Day Plan

*Audience: the intern team. This is the map of the project: what it is, what's
broken, what's secure, and how 8 beginners can finish it without stepping on
each other. Paste straight into Notion if you like.*

---

## 1. What the app actually does

FundTrail is a **Flask** web app used by police cybercrime investigators.

1. An officer uploads a **bank-transaction Excel file** for a complaint
   (identified by an *Acknowledgement Number*, `ack_no`).
2. The app parses several sheets — main money-transfer trail, ATM withdrawals,
   cheque withdrawals, and "transaction put on hold" — into a `Transaction` table.
3. It builds an **interactive fund-flow graph** (D3.js): each account is a node,
   each transfer an arrow, organised in *layers* (layer 1 = first hop from victim).
4. It enriches accounts with **bank/branch/state** from a 51 MB **IFSC dataset**.
5. Officers mark suspect accounts **"on hold"** and **auto-generate official .docx/PDF
   letters** to banks requesting KYC or asking to freeze funds.
6. **Roles:** Admin (manage everything), Investigative Officer (investigate).
   *(The read-only Viewer role was removed.)*

**Tech:** Python/Flask, SQLAlchemy ORM, SQLite *or* MySQL, Flask-Login (auth),
Flask-WTF (CSRF), Flask-Limiter (rate limiting), pandas/openpyxl (Excel),
python-docx + reportlab/xhtml2pdf (letters), D3.js (graph).

---

## 2. The four structural problems (fix these first)

### 2.1 The app exists twice (redundancy)
There is a **3,577-line monolith** `main/app.py` *and* a **half-finished modular
package** `main/app/` (`routes/`, `utils/`, its own `models.py`). There are even
two `models.py`. This is the main reason the code feels unreadable and is a
**merge-conflict magnet** for a team.
→ **Plan:** pick the modular package as the target, migrate the monolith's logic
into it route-by-route, then delete the monolith. (Several weeks; do it last.)

### 2.2 The database exists ~5 times (very likely your "Excel partial data" bug)
Copies of `fundtrail.db` live in `data/`, `main/`, `main/data/`, `main/instance/`.
The monolith and the modular package compute **different** database paths, so you
can **upload into one database and read from another** → "some data shows, some
doesn't."
→ **Plan:** decide one canonical location (`FUNDTRAIL_DATA_DIR` or MySQL), delete
the rest, confirm by uploading a file and counting rows.

### 2.3 Real victim data is in Git (security/privacy incident)
The repo tracks `.db` files and real victim Excel uploads (e.g.
`victim_dinesh_kumar_..._complaint_excel.xlsx`). For a police tool this is serious.
→ **Plan:** see `docs/FILES_TO_UPLOAD.md`. Start a clean repo from `new_files/`.

### 2.4 Hardcoded fallback secret key
`app.py` falls back to `"fallback-fundtrail-secret-key-12345!@#"` if `SECRET_KEY`
is unset. Anyone who knows it can forge login sessions.
→ **Plan:** remove the fallback; make the app refuse to start in production without
a real key.

---

## 3. The "Excel data partially shows up" bug — how we'll diagnose

Two likely causes (probably both):

1. **Wrong database** (see 2.2) — reading a different DB than you wrote to.
2. **Silent sheet/column skips** — the importer matches sheet names *exactly*
   (`if 'Withdrawal through ATM' in xls.sheet_names`). If a bank's export has a
   slightly different sheet name, extra spaces, a shifted header row, or merged
   cells, that whole sheet (or rows) is **dropped without warning**.

**Diagnostic plan:** run the app, upload one real file, and log per sheet:
*rows in Excel* vs *rows written to DB*, plus every skipped row and the reason.
That turns "some data is missing" into an exact list of what and why.

---

## 4. Security status (from the SAST / DAST / retest cycle)

The `scripts/verify_*.py` and `reproduce_*.py` files show what the pentest found
and what's been fixed. Full tracker: `docs/SECURITY_FINDINGS.md`. Headline:

**Already remediated (keep them working — don't regress):** IDOR / case-access
control, Viewer privilege escalation, CSRF protection, session-cookie hardening,
server-header disclosure, SRI on CDN assets, several unauthenticated-access holes.

**Still worth fixing:** hardcoded fallback secret key; placeholder secret in `.env`;
`SESSION_COOKIE_SECURE` breaking local login; confirm upload validation (real
`.xlsx`, size cap, formula-injection); PII-in-Git.

**Prevention habits going forward:**
- Every case lookup goes through one access-check function.
- `@login_required` and role checks on the server, never UI-only.
- Secrets only from environment; app fails fast if missing.
- Never commit data; CSRF stays on; keep SRI hashes updated.

---

## 5. Reality check on the "extra tech" ideas

Honest senior advice — several requested tools would **cost you weeks for no benefit**:

| Idea | Verdict | Why |
|------|---------|-----|
| MetaGPT (auto-codegen) | ❌ Skip | Generating code over a *pentest-verified* app invites regressions. Wrong tool for "maintain integrity." |
| External knowledge-graph repo | ❌ Skip | The app *is* a graph tool. A one-page architecture diagram beats installing a random repo. |
| Kafka / RabbitMQ message queues | ❌ Skip | One internal tool, a few officers. Solves a scale problem you don't have. |
| Redis / heavy caching | ❌ Skip | The only hot path (IFSC lookup) is **already cached** via `.pkl` + JSON. |
| Microservices | ❌ Skip | Over-engineering. Keep one clean Flask app. |
| **SOLID / design patterns / clean DB design** | ✅ Yes | Apply them *as the lens* for the monolith→modular refactor (§2.1). |
| **Docker (one compose: app + MySQL)** | ✅ Modest yes | Gives 8 people one identical environment + reproducible Linux builds. |
| Notion for docs/specs/TODO | ✅ Yes | Paste these docs in; track tasks there. |

**Packaging note:** PyInstaller **cannot cross-compile.** Your Mac builds a *Mac*
binary; a Windows `.exe` must be built **on Windows**; a Linux single-file **on
Linux** (a second good reason for Docker). One universal build from one machine is
not possible with this toolchain.

---

## 6. Git workflow for a team of 8 (avoiding merge hell)

1. **`main` is protected.** Nobody pushes straight to it.
2. **One short-lived branch per task:** `feature/excel-import-fix`,
   `fix/secret-key`, etc. Branch from latest `main`.
3. **Small PRs, merged daily.** Big branches that live for a week are what cause
   merge hell.
4. **Never commit `.db`, `uploads/`, datasets, or build artifacts** — binaries
   cannot be merged and will conflict constantly.
5. **`git pull --rebase origin main` before you push.** Keeps history linear.
6. **Own your files.** Assign each person a *module* (auth, ingestion, analysis,
   letters, admin) so two people rarely edit the same file. The biggest single
   conflict source is the 3,577-line `app.py` — finishing the modular split (§2.1)
   is itself the best anti-conflict move.
7. **If a conflict happens:** open the file, keep both intents, test, commit. Ask
   for a 5-minute pair session rather than guessing.

---

## 7. The 60-day plan (≈ 8 people, 2 with some experience)

| Weeks | Goal | Who |
|-------|------|-----|
| 1–2 | Stabilize: everyone runs it; pick ONE database; clean repo; security tracker filled from the PDFs | Whole team learns the codebase together |
| 3–5 | Close open security findings + fix the Excel import bug + add the row-count diagnostic | Pairs: 1 experienced + 1 beginner |
| 5–7 | Refactor monolith → clean modular package; comment every function; delete dead scripts | Each person owns one module |
| 7–8 | UI/UX redesign + Docker/packaging + final docs + retest | Split: 2 UI, 2 infra, rest docs/QA |

**Teaching the beginners:** give each beginner **one route module** end-to-end —
small enough to learn, isolated enough to avoid conflicts. Daily 15-min standup:
"what I did / what's blocking me." Pair the 2 experienced members across the
weaker ones rather than letting them do all the work.

---

## 8. Questions for your mentor

1. Is production **SQLite or MySQL**? (Decides the whole DB task.)
2. Is this meant to run **offline as an .exe on one machine**, or **hosted on a
   server** for many officers? (Decides Docker / HTTPS / packaging.)
3. **Are the committed victim Excel files real case data?** If yes, the PII-in-Git
   issue needs to be reported.
4. Which is the **canonical codebase** — `app.py` or the modular `app/`?
5. What is the **definition of done** for the retest — zero highs, or a signed-off
   report?
6. Do they want the **password policy** strictly enforced even for the default
   `admin`/`officer` accounts (the reset scripts currently bypass it)?

---

## 9. Things only a human can do
- Get clarity from the mentor on the questions above.
- Confirm whether the sample data is real (and report it if so).
- Decide deployment model (offline exe vs server).
- Be added as a collaborator on the GitHub repo / set up your SSH key.
- Rotate any credentials that were shared in plain text.
