# FundTrail — Database Schema & Design Notes

**Tasks #9 (review) & #21 (improve).**

## Stores (3 SQLite binds)
| Bind | File | Holds | Why separate |
|------|------|-------|--------------|
| default | `fundtrail.db` | transactions, users, complaints, uploads, logs | core |
| `kyc_store` | `kyc_details.db` | KYC details per txn | survives Excel re-upload |
| `poh_store` | `poh_refund_details.db` | put-on-hold refund details | survives Excel re-upload |

## Tables (from `models.py`)
**Transaction** (the core fund-flow record): `id`, `layer`, `from_account`,
`to_account`, `ack_no`, `bank_name`, `ifsc_code`, `txn_date`, `txn_id`, `amount`,
`disputed_amount`, `action_taken`, `account_number`, `state`, ATM fields
(`atm_id`, `atm_withdraw_amount/date`, `atm_location`), cheque fields, put-on-hold
fields, court/refund fields, KYC mirror fields, `upload_id` (FK→UploadedFile).
Indexes: `idx_transaction_ack_no`, `idx_transaction_put_on_hold`.

**User:** `username` (unique), `password_hash` (scrypt), `role`, `name`, `rank`,
`email`, `failed_login_attempts`, `account_locked_until`, `must_change_password`.

**Complaint:** `ack_no` (unique), `file_name`, `uploaded_by` (FK), `assigned_to` (FK),
`upload_time`. **UploadedFile:** `filename`, `data` (BLOB), `uploader`, `mimetype`,
`upload_time`, `transaction_count`. **UsageLog:** audit trail of actions.
**KYCDetails / POHRefundDetails:** keyed by `txn_id` / (`ack_no`,`txn_id`).

## Findings
1. **Storing the uploaded `.xlsx` as a BLOB** (`UploadedFile.data`) inside the DB bloats
   it (multi-MB rows). Consider storing files on disk (secured dir) + a path/hash in DB.
2. **Dates stored as `String(100)`** (`txn_date`, `atm_withdraw_date`, …) — prevents
   real date filtering/sorting. Migrate to `Date`/`DateTime` with a parse step.
3. **`amount` as `Float`** — money should be `Numeric`/`Decimal` to avoid rounding
   errors in totals. (Code already uses `Decimal` in places — make the column match.)
4. **KYC fields duplicated** on both `Transaction` and `KYCDetails` — pick one source
   of truth to avoid drift.
5. **No `withdrawal_type`** — needed for the Excel fix (POS/AEPS/ATM in one model).
6. **Indexes:** add on `Transaction.txn_id`, `Transaction.account_number`,
   `Complaint.assigned_to` (queried on every case-access check).

## Recommendation (incremental, additive migrations only)
Keep the schema shape; do **small Alembic migrations**: add `withdrawal_type` +
indexes now (needed for the Excel fix), then schedule the `Float→Numeric` and
`String→Date` migrations with a data-backfill script. Don't redesign wholesale —
the app is verified and in use; evolve it safely.
