# FundTrail — Route & API Inventory

**Task #8.** All 37 routes, grouped, with access level. (L = `@login_required`,
A = `@admin_required`/Admin-only, P = public.)

## Auth & session
| Route | Method | Acc | Purpose |
|-------|--------|-----|---------|
| `/` | GET | P | landing → redirect to login/index |
| `/login` | GET/POST | P | login (rate-limited 5/min, lockout) |
| `/logout` | GET | L | end session |
| `/change_password` | GET/POST | L | forced/voluntary password change |

## Ingestion
| `/upload` | POST | L | save raw file |
| `/upload_excel` | POST | L | **parse Excel → transactions** (see EXCEL_IMPORT_FIX.md) |
| `/download/<filename>` | GET | L | download stored upload |

## Analysis & visualisation
| `/index` | GET | L | main dashboard |
| `/view_graph`, `/graph/<ack_no>` | GET | L+case | fund-flow graph view |
| `/graph_data/<ack_no>` | GET | L+case | graph JSON (nodes/links) |
| `/available_ack_nos`, `/complaints` | GET | L | case lists |
| `/atm_data/<ack_no>` | GET | L+case | ATM withdrawals |
| `/statewise_summary/<ack_no>` | GET | L+case | state totals |
| `/put_on_hold_transactions/<ack_no>` | GET | L+case | held txns |
| `/state_transactions/<ack_no>/<state>` | GET | L+case | per-state drilldown |
| `/ifsc_info/<ifsc>` | GET | L | bank/branch lookup |

## Case actions
| `/save_kyc` | POST | L+case | save KYC for a txn |
| `/save_hold_refund` | POST | L+case | save refund/court details |
| `/generate_letter[_pdf|_docx]` | POST | L+case | bank letters |
| `/download_fundtrail_pdf` | POST | L+case | export trail PDF |

## Admin
| `/admin_dashboard`, `/view_analytics`, `/download_logs` | GET | A | admin views/logs |
| `/view_all_complaints`, `/view_complaint/<id>` | GET | A | all cases |
| `/view_officers`, `/admin/add_officer`, `/submit_officer`, `/update_officer`, `/edit_officer/<id>`, `/delete_officer` | GET/POST | A | officer management |
| `/delete_complaint/<id>` (DELETE), `/delete_by_ack` (POST) | — | A | delete cases |

## Review notes (business logic)
- **Case access** is enforced by `check_case_access(ack_no)` on every `<ack_no>`
  route (IDOR guard, retest FT-001). Verify it wraps *all* analysis routes after the
  refactor — easy to miss one when moving code.
- **`/upload_excel`** holds the most logic (~500 lines) and the Excel bug — first
  candidate to extract into a service class during the SOLID refactor (#12).
- **Letter generation** has 3 near-duplicate routes (`/generate_letter`,
  `_pdf`, `_docx`) — consolidate into one with a `format` param (redundancy, #13).
