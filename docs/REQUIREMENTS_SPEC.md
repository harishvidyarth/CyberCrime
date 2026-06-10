# FundTrail — Requirements & Specification

**Task #30 (Notion content).** Paste this into Notion as the project spec. It pairs
with `TASK_CHECKLIST.md` (the task board) and `PROJECT_BRIEFING.md` (the deep dive).

## 1. Purpose
A tool for Tamil Nadu Cyber Crime Wing investigators to trace stolen-money trails
from bank transaction data, visualise fund flow, and generate official bank letters.

## 2. Users & roles
| Role | Capabilities |
|------|--------------|
| Admin | Manage officers, view all cases, analytics, audit logs |
| Investigative Officer | Upload data, trace funds, hold accounts, generate letters |
| Viewer | Read-only access to fund flows and reports |

## 3. Functional requirements
- **FR-1** Authenticate users with strong hashing, lockout, forced password change.
- **FR-2** Upload bank trail `.xlsx`; parse **all** money-movement sheets
  (transfers, ATM, POS, AEPS, cheque, put-on-hold) into transactions. *(Gap: POS/AEPS
  not yet ingested — see EXCEL_IMPORT_FIX.md.)*
- **FR-3** Visualise fund flow as an interactive, layered graph.
- **FR-4** Enrich accounts with bank/branch/state via IFSC lookup.
- **FR-5** Mark suspect accounts "on hold"; record court/refund details.
- **FR-6** Generate suspect/victim bank letters as `.docx` and `.pdf`.
- **FR-7** State-wise summaries, repeater/split/burst detection, analytics.
- **FR-8** Per-case access control; full audit logging of actions.

## 4. Non-functional requirements
- **Security:** OWASP-aligned; all 14 retest findings remain remediated.
- **Deployment:** offline, self-contained per machine (SQLite, no network).
- **Portability:** runs on Windows/macOS/Linux; built per OS.
- **Maintainability:** modular, documented, ≤ ~50-line functions, tests for core flows.
- **Privacy:** no case data or PII ever leaves the machine or enters Git.

## 5. Constraints & assumptions
- Bank export format = "BankAction_CompleteTrail" multi-sheet `.xlsx`.
- IFSC dataset (~30 MB) distributed out-of-band (shared drive), not in Git.
- Single-machine usage; concurrency is low (one officer per instance).

## 6. Out of scope (decided — see TOOLING_EVALUATION.md)
MetaGPT codegen, Graphify knowledge graph, Redis caching, message queues,
microservices. These don't fit an offline single-machine tool.

## 7. Open questions for the mentor
SQLite vs MySQL in production · offline vs hosted · is the sample data real (PII) ·
canonical codebase · definition of "done" for retest · password policy for defaults.
(See `PROJECT_BRIEFING.md` §8.)
