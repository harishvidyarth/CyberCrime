# Sentry — error tracking with PII scrubbing

FundTrail handles financial-crime case data, so the Sentry integration is built to
**fail closed**: it is inactive until a `SENTRY_DSN` is set, and even when active a
`before_send` hook strips case PII before any event leaves the process.

Status: **inactive** (no `SENTRY_DSN` set). The SDK is wired in `app.py` and the
scrubber is tested, but nothing is transmitted until you opt in.

## What is scrubbed

The `before_send` hook (`_sentry_before_send` in `app.py`) replaces values under
sensitive keys with `[Filtered]`, recursively, across the whole event: request
params/data, headers, `extra`, `contexts`, breadcrumbs, and **exception-frame local
variables**. Key matching is case-insensitive substring, derived from the actual
column names in `models.py`.

| Scrubbed (value → `[Filtered]`) | Source field(s) |
|---|---|
| `account` (any key containing it) | `from_account`, `to_account`, `account_number` |
| `ack_no` | `ack_no` (case identifier) |
| `aadhar`, `aadhaar` | `kyc_aadhar`, `aadhar` |
| `kyc` (any) | `kyc_name`, `kyc_aadhar`, `kyc_mobile`, `kyc_address` |
| `mobile`, `phone` | `kyc_mobile`, `mobile` |
| `address` | `kyc_address`, `address` |
| `ifsc` | `ifsc_code`, `cheque_ifsc` |
| `txn_id` | `txn_id`, `put_on_hold_txn_id` |
| `pan_number`, `pancard` | defensive (not a current column) |
| `name` (exact key) | `KYCDetails.name` / `kyc_name` — suspect/victim names |
| URL query string | dropped whole + query stripped from `request.url` (can carry `ack_no`) |

## What is NOT scrubbed (and why)

| Kept | Why |
|---|---|
| `username`, `filename`, `file_name`, `bank_name`, `hostname`, `step_label`, frame metadata (`classname`, `funcname`, `modulename`, `pathname`) | Debugging value, not case PII. Without `username` you cannot tell which officer hit an error |
| `amount`, `disputed_amount`, `refund_amount` | Numeric amounts alone are not identifying; kept for triage |
| Exception type, message, stack frames (file/line) | Core of what makes an error report useful |

If you decide any kept field is too sensitive for your threat model, add its key
substring to `SENTRY_SENSITIVE_KEY_PARTS` in `app.py` (and a test case).

## Privacy defaults (already set)

| Option | Value | Effect |
|---|---|---|
| `send_default_pii` | `False` | No cookies / auth headers / client IP / request body attached by the SDK |
| `enable_logs` | `False` | Log lines are **not** forwarded (they can contain case data). Opt in with `SENTRY_ENABLE_LOGS=true` only after reviewing log content |
| `before_send` | `_sentry_before_send` | The scrubbing described above |
| `traces_sample_rate` | `0.1` | 10% performance traces |

## How to enable later (production only)

1. Create a project at sentry.io and copy its DSN.
2. Set it in the **production** environment (never commit it):
   - `.env`: `SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<project>`
   - or container/host env var of the same name.
3. Optional: `SENTRY_ENVIRONMENT=production`, `SENTRY_RELEASE=<version>`.
4. Restart the app. Confirm a deliberate test error appears in Sentry with all
   sensitive fields showing `[Filtered]`.
5. Leave `SENTRY_SEND_DEFAULT_PII` and `SENTRY_ENABLE_LOGS` **unset/false** unless
   you have a specific, reviewed reason.

> Do not set `SENTRY_DSN` in shared/dev `.env` files — that would start sending
> events from every developer machine.

## Tested

`main/tests/test_sentry_scrubber.py` feeds a synthetic event (fake account numbers,
Aadhaar, names, KYC fields, exception-frame vars, breadcrumbs) through the real
`before_send` and asserts every sensitive field becomes `[Filtered]` while
debug-useful fields survive — and that `SENTRY_DSN` is unset this session.
