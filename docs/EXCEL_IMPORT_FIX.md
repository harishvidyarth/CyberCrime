# Excel "partial data" bug — root cause & fix plan

**Task #10/#25. Status: investigation COMPLETE.** This documents exactly why "some
Excel data shows up and some doesn't," with evidence, and the precise fix.

## What officers see
Upload a bank trail file → the graph/analytics show the main transfers and ATM
withdrawals, but **POS withdrawals, AEPS withdrawals and several other transaction
types are missing** — silently, with no error.

## Root cause (confirmed against 33 real files)
The importer in `upload_excel()` (`main/app.py:878`) only reads **four** sheets:

| Read by the app | Ignored by the app (but present in real files) |
|-----------------|------------------------------------------------|
| `Money Transfer to` | `Withdrawal through POS` — cash-out at POS terminals |
| `Withdrawal through ATM` | `AEPS` — Aadhaar-Enabled Payment System cash-outs |
| `Cash Withdrawal through Cheque` | `Others Less Then 500` |
| `Transaction put on hold` | `Other`, `Refund Completed`, `Old Transaction` |

POS and AEPS are **real money-exit channels** fraudsters use, exactly like ATM/cheque.
Because the importer never opens those sheets, those transactions never reach the
database or the fund-flow graph → "missing data."

### Evidence
Sheet inventory across the sample files (e.g. `BankAction_CompleteTrail11_07_2025_18_06_50.xlsx`):
`Money Transfer to`, `Cash Withdrawal through Cheque`, `Transaction put on hold`,
`Withdrawal through ATM`, **`Other`**, **`AEPS`**, **`Others Less Then 500`**,
**`Withdrawal through POS`**, **`Old Transaction`**.

The ignored sheets share the same key columns as the handled ones
(`S No.`, `Acknowledgement No.`, `Account No./ (Wallet /PG/PA) Id`,
`Transaction Id / UTR Number`, `Withdrawal Amount`, `Withdrawal Date & Time`, …),
so they are fully ingestible.

## Three sub-issues
1. **Incomplete sheet coverage (primary).** POS/AEPS/other sheets are never read.
2. **Fragile matching (secondary).** The main sheet uses a robust `find_sheet_name()`
   (`app.py:939`), but the ATM/Cheque/Hold lookups (`app.py:1011-1013`) use brittle
   exact matching — a renamed sheet in a future export would be dropped silently too.
3. **Silent failure (UX).** Officers get no feedback about which sheets were imported
   vs. skipped, so missing data is invisible.

## The fix (scoped — implement as `feature/excel-import-coverage`)
1. **Add a withdrawal-sheet pipeline.** POS and AEPS map cleanly onto the existing
   ATM withdrawal model (account, amount, date, location/merchant, reference). Add
   them (and treat `Other`/`Others Less Then 500` as generic withdrawals) so every
   fund movement is captured. May need a few new `Transaction` columns
   (`withdrawal_type`, `merchant_name`/`mid` for POS) — small, additive migration.
2. **Use `find_sheet_name()` everywhere** — replace the exact checks at
   `app.py:1011-1013` so naming variations never silently drop a sheet.
3. **Add an import summary.** After upload, flash/log per sheet: rows found, rows
   imported, and **"present but not ingested"** sheets. Converts silent loss into
   visible feedback. (Quick win — do this first.)

## Verification
After the fix, add a test (task #25→#40): for each sample file, assert
`rows imported == sum(data rows across recognised sheets)` and that no recognised
sheet is silently skipped.

> ⚠️ This is an additive change to a pentest-verified app. Keep the cell sanitiser
> (`sanitize_cell`, `app.py:924`) on every new sheet to preserve the FT-014/formula-
> injection protection, and re-run `verify_*` after.
