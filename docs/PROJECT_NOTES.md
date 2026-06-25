# FundTrail — Project Notes

Single home for the working notes that used to live in many small docs
(checklists, audits, mentor questions, tooling/SonarCloud reports, the Excel-import
write-up). Durable reference docs stay in their own files (see **Docs map** below).

## Docs map (what to read)
| Topic | File |
|---|---|
| What the app is / how it works | `HOW_IT_WORKS.md`, `../README.md` |
| Architecture & data flow | `ARCHITECTURE.md` |
| Database schema & models | `DATABASE.md` |
| HTTP routes | `ROUTES.md` |
| Deployment / installers / .exe | `DEPLOYMENT.md`, `INSTALLERS.md` |
| Security review findings | `SECURITY_FINDINGS.md` |
| Coding standards | `CODING_STANDARDS.md` |
| Release history | `../CHANGELOG.md` |
| Dev credentials | `../CREDENTIALS.md` |
| Agent/session working rules | `../CLAUDE.md` |

## Upload integrity (Excel import)
- Dedup is keyed on **Acknowledgement No** (canonicalized via `_canon_ack`, drops
  whitespace/trailing `.0`), not filename. A 2nd upload of an ACK that already has
  transactions is rejected with 409; same `filename`+uploader is also rejected.
- `UploadedFile` is flushed (not committed) and persisted **atomically** with its
  transactions, so a parse failure can never leave an orphaned file row.
- `_dedupe_uploads()` runs at startup (and in the .exe) as a self-heal: collapses any
  legacy duplicate-ACK uploads (keep newest) and removes 0-transaction orphan files.
- Analytics/upload counts only include files that have transactions.

## SonarCloud / quality
- Run locally: `ruff check main/app.py`. Cognitive-complexity refactors keep helpers
  **above** the `@app.route` line (a helper inserted between the decorator and the
  function silently rebinds the route — verify with `smoke_test.py`).
- Accessibility: tables need a `<th>`; JS-populated tables keep a static placeholder
  `<th>` in markup so the linter sees a header.

## MRM (Money Restoration Module)
- 7 sequential steps; each step's date must be `>=` the previous step and `<=` the next.
- Set-once for officers; an **Admin may edit** a saved step's date (re-logged in the
  audit trail). Admin can never create the first save for a step.

## Testing
Maintained suites (run with the project venv):
`main/tests/test_mrm_workflow.py`, `smoke_test.py`, `test_access_control.py`,
`test_integration_probes.py`, `test_sentry_scrubber.py`.
