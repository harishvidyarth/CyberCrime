#!/usr/bin/env python3
"""
FundTrail access-control & validation tests — dependency-free (no pytest needed).

Run:  cd main && python tests/test_access_control.py
Exits non-zero on any failure.

Covers the per-officer isolation feature (a case belongs to its uploader / an
admin-assigned officer only), admin-only route gating, the new input validators,
and the legacy-data backfill. Uses a throwaway temp DB and synthetic data only.
"""

import os, re, sys, json, secrets, tempfile, contextlib

MAIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MAIN)

# Self-contained: isolated DB + a secret key, so the suite runs without a real .env.
os.environ["FUNDTRAIL_DATA_DIR"] = tempfile.mkdtemp(prefix="ft_acl_")
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")

with contextlib.redirect_stdout(open(os.devnull, "w")):
    from app import (
        app,
        validate_aadhar,
        validate_mobile,
        validate_court_order_date,
        ALLOWED_REFUND_STATUSES,
        backfill_complaints,
        migrate_split_dbs_into_main,
        secure_base,
    )
    from models import db, User, UploadedFile, Transaction, Complaint, POHRefundDetails

# Focus on authz/validation logic; CSRF itself is covered by smoke_test.py.
app.config["WTF_CSRF_ENABLED"] = False
app.config["SESSION_COOKIE_SECURE"] = False

FAILS = []


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)
    return cond


def csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


def login(client, role, username, password):
    tok = csrf(client.get("/login").get_data(as_text=True))
    return client.post("/login", data={"role": role, "username": username, "password": password, "csrf_token": tok})


def loc(r):
    return r.headers.get("Location", "")


# ── seed users + one case owned by officer A ──────────────────────────
with app.app_context():
    db.create_all()

    def mkuser(uname, role, pw):
        u = User.query.filter_by(username=uname).first() or User(username=uname, role=role)
        if u.id is None:
            db.session.add(u)
        u.role = role
        u.set_password(pw)
        u.must_change_password = False
        u.failed_login_attempts = 0
        u.account_locked_until = None
        return u

    mkuser("admin", "Admin", "AdminPass@2026!")
    a = mkuser("off_a", "Investigative Officer", "OffaPass@2026!")
    b = mkuser("off_b", "Investigative Officer", "OffbPass@2026!")
    db.session.commit()
    A_ID, B_ID = a.id, b.id

    # A case uploaded by officer A: UploadedFile + Transaction + Complaint(owner=A).
    uf = UploadedFile(filename="caseA.xlsx", uploader="off_a")
    db.session.add(uf)
    db.session.commit()
    db.session.add(
        Transaction(
            ack_no="CASE-A",
            layer=1,
            from_account="111111111",
            to_account="222222222",
            amount=100.0,
            txn_id="TX1",
            upload_id=uf.id,
        )
    )
    if not Complaint.query.filter_by(ack_no="CASE-A").first():
        db.session.add(Complaint(ack_no="CASE-A", file_name="caseA.xlsx", uploaded_by=A_ID, assigned_to=A_ID))
    db.session.commit()

admin_c, a_c, b_c = app.test_client(), app.test_client(), app.test_client()
login(admin_c, "Admin", "admin", "AdminPass@2026!")
login(a_c, "Investigative Officer", "off_a", "OffaPass@2026!")
login(b_c, "Investigative Officer", "off_b", "OffbPass@2026!")

print("\n── Per-officer isolation ──")
check("owner A can read own case", a_c.get("/graph_data/CASE-A").status_code == 200)
check("non-owner B is DENIED (403)", b_c.get("/graph_data/CASE-A").status_code == 403)
check("admin can read any case", admin_c.get("/graph_data/CASE-A").status_code == 200)

a_list = json.loads(a_c.get("/available_ack_nos").get_data(as_text=True))["available_ack_nos"]
b_list = json.loads(b_c.get("/available_ack_nos").get_data(as_text=True))["available_ack_nos"]
check("A sees CASE-A in their list", "CASE-A" in a_list)
check("B does NOT see CASE-A in their list", "CASE-A" not in b_list)

# Bug #2 (letter routes had no auth) and Bug #7 (KYC/refund had no case check).
# Run BEFORE the assignment test below, so officer B is still a non-owner here.
print("\n── Letters & KYC enforce login + case access (Bug #2 & #7) ──")
anon = app.test_client()
check(
    "anon POST /generate_letter -> not 200 (login required)",
    anon.post("/generate_letter", json={"ack_no": "CASE-A", "letter_type": "suspect"}).status_code != 200,
)
check(
    "non-owner B POST /generate_letter CASE-A -> 403",
    b_c.post("/generate_letter", json={"ack_no": "CASE-A", "letter_type": "suspect"}).status_code == 403,
)
check(
    "owner A POST /generate_letter CASE-A -> 200",
    a_c.post("/generate_letter", json={"ack_no": "CASE-A", "letter_type": "suspect"}).status_code == 200,
)
check(
    "non-owner B POST /generate_letter_docx CASE-A -> 403",
    b_c.post(
        "/generate_letter_docx", json={"ack_no": "CASE-A", "account_number": "222222222", "letter_type": "suspect"}
    ).status_code
    == 403,
)
check(
    "non-owner B POST /save_kyc for A's txn -> 403",
    b_c.post("/save_kyc", json={"txn_id": "TX1", "aadhar": "123412341234", "mobile": "9876543210"}).status_code == 403,
)
check(
    "non-owner B POST /save_hold_refund CASE-A -> 403",
    b_c.post(
        "/save_hold_refund", json={"ack_no": "CASE-A", "hold_txn_id": "X", "refund_status": "Refunded"}
    ).status_code
    == 403,
)

print("\n── Admin-only gating ──")
check("officer GET /view_officers -> 403", a_c.get("/view_officers").status_code == 403)
check(
    "officer POST /assign_case -> 403",
    a_c.post("/assign_case", data={"ack_no": "CASE-A", "officer_id": str(B_ID)}).status_code == 403,
)
check("officer GET /download_logs -> 403 (admin only, Bug #3)", a_c.get("/download_logs").status_code == 403)
check("admin GET /download_logs -> 200", admin_c.get("/download_logs").status_code == 200)
check(
    "state_transactions tolerates junk pagination, no 500 (Bug #10)",
    admin_c.get("/state_transactions/CASE-A/Kerala?page=abc&per_page=xyz").status_code == 200,
)

print("\n── Assignment grants access ──")
r = admin_c.post("/assign_case", data={"ack_no": "CASE-A", "officer_id": str(B_ID)})
check("admin assign CASE-A -> redirect", r.status_code in (301, 302))
check("assigned officer B can now read CASE-A", b_c.get("/graph_data/CASE-A").status_code == 200)
check("uploader A still retains access", a_c.get("/graph_data/CASE-A").status_code == 200)

print("\n── Input validators ──")
check("aadhaar 12 digits ok", validate_aadhar("123412341234"))
check("aadhaar with spaces ok", validate_aadhar("1234 1234 1234"))
check("aadhaar 11 digits rejected", not validate_aadhar("12341234123"))
check("aadhaar blank allowed", validate_aadhar(""))
check("mobile 10-digit ok", validate_mobile("9876543210"))
check("mobile +91 prefix ok", validate_mobile("+919876543210"))
check("mobile 9 digits rejected", not validate_mobile("987654321"))
check("court date yyyy-mm-dd ok", validate_court_order_date("2026-06-09"))
check("court date dd-mm-yyyy ok", validate_court_order_date("09-06-2026"))
check("court date junk rejected", not validate_court_order_date("soon"))
check(
    "refund status whitelist enforced",
    "Refunded" in ALLOWED_REFUND_STATUSES and "Hacked" not in ALLOWED_REFUND_STATUSES,
)

print("\n── KYC endpoint enforces validation ──")
r = a_c.post("/save_kyc", json={"txn_id": "TX1", "aadhar": "123", "mobile": "9876543210"})
check("save_kyc rejects bad aadhaar (400)", r.status_code == 400)
r = a_c.post(
    "/save_kyc",
    json={"txn_id": "TX1", "aadhar": "123412341234", "mobile": "9876543210", "name": "Synthetic", "address": "Test"},
)
check("save_kyc accepts valid KYC (200)", r.status_code == 200)

print("\n── Backfill for legacy (pre-feature) uploads ──")
with app.app_context():
    uf2 = UploadedFile(filename="legacy.xlsx", uploader="off_b")
    db.session.add(uf2)
    db.session.commit()
    db.session.add(
        Transaction(ack_no="LEGACY-1", layer=1, from_account="1", to_account="2", amount=5.0, upload_id=uf2.id)
    )
    db.session.commit()
    backfill_complaints()
    post = Complaint.query.filter_by(ack_no="LEGACY-1").first()
    check("backfill creates a complaint for the legacy upload", post is not None)
    check("backfill maps uploader off_b -> uploaded_by", bool(post) and post.uploaded_by == B_ID)

print("\n── DB consolidation: legacy split-file migration ──")
import sqlite3 as _sqlite

_poh_old = os.path.join(secure_base, "poh_refund_details.db")
_c = _sqlite.connect(_poh_old)
_c.execute(
    "CREATE TABLE poh_refund_details (id INTEGER PRIMARY KEY, ack_no TEXT, "
    "txn_id TEXT, court_order_date TEXT, refund_status TEXT, refund_amount REAL, updated_at TEXT)"
)
_c.execute("INSERT INTO poh_refund_details (ack_no, txn_id, refund_status) VALUES ('CASE-A', 'POH9', 'Refunded')")
_c.commit()
_c.close()
with app.app_context():
    migrate_split_dbs_into_main()
    _m = POHRefundDetails.query.filter_by(ack_no="CASE-A", txn_id="POH9").first()
    check("legacy POH row imported into main DB", bool(_m) and _m.refund_status == "Refunded")
    check(
        "old split file renamed to .migrated", os.path.exists(_poh_old + ".migrated") and not os.path.exists(_poh_old)
    )

print("\n── Refund status survives a bank re-upload (bug-guard) ──")
with app.app_context():
    ufr = UploadedFile(filename="reup.xlsx", uploader="off_a")
    db.session.add(ufr)
    db.session.commit()
    db.session.add(
        Transaction(
            ack_no="REUP-1", layer=1, from_account="111111111", to_account="900000001",
            amount=5000.0, txn_id="TXR1", put_on_hold_txn_id="UTR-REUP-1", put_on_hold_amount=5000.0,
            upload_id=ufr.id,
        )
    )
    if not Complaint.query.filter_by(ack_no="REUP-1").first():
        db.session.add(Complaint(ack_no="REUP-1", file_name="reup.xlsx", uploaded_by=A_ID, assigned_to=A_ID))
    db.session.commit()

# Officer A records a refund through the real route (persists to POHRefundDetails).
r = a_c.post(
    "/save_hold_refund",
    json={"ack_no": "REUP-1", "hold_txn_id": "UTR-REUP-1",
          "refund_status": "Refunded", "refund_amount": 5000.0, "court_order_date": "2026-06-01"},
)
check("officer can save refund status (200)", r.status_code == 200)
with app.app_context():
    _p = POHRefundDetails.query.filter_by(ack_no="REUP-1", txn_id="UTR-REUP-1").first()
    check("refund status persisted to POHRefundDetails", bool(_p) and _p.refund_status == "Refunded")

# Simulate the bank re-uploading a new Excel for the same ACK: the upload purges and
# re-creates the Transaction rows with blank refund fields. The persistent store must
# NOT be touched, so the previous refund status must survive and re-appear on reload.
with app.app_context():
    Transaction.query.filter_by(ack_no="REUP-1").delete()
    db.session.commit()
    ufr2 = UploadedFile(filename="reup_v2.xlsx", uploader="off_a")
    db.session.add(ufr2)
    db.session.commit()
    db.session.add(
        Transaction(
            ack_no="REUP-1", layer=1, from_account="111111111", to_account="900000001",
            amount=5000.0, txn_id="TXR1", put_on_hold_txn_id="UTR-REUP-1", put_on_hold_amount=5000.0,
            refund_status=None, refund_amount=None, court_order_date=None, upload_id=ufr2.id,
        )
    )
    db.session.commit()
    _p2 = POHRefundDetails.query.filter_by(ack_no="REUP-1", txn_id="UTR-REUP-1").first()
    check("POHRefundDetails survives the Transaction purge", bool(_p2) and _p2.refund_status == "Refunded")

# End-to-end: reloading the graph restores the refund status onto the fresh rows.
gd = a_c.get("/graph_data/REUP-1").get_data(as_text=True)
check("re-uploaded case still reports 'Refunded' in graph data", "Refunded" in gd)

print("\n── Unsupported upload leaves no orphaned file (security) ──")
import io as _io, zipfile as _zip

_UPLOAD = app.config["UPLOAD_FOLDER"]
os.makedirs(_UPLOAD, exist_ok=True)
# A real ZIP (passes the .xlsx extension + 'PK' magic-byte gate) but NOT a workbook,
# so parsing fails. The saved working copy must be deleted, not left in UPLOAD_FOLDER.
_buf = _io.BytesIO()
with _zip.ZipFile(_buf, "w") as _z:
    _z.writestr("hello.txt", "not a workbook")
_buf.seek(0)
_before = set(os.listdir(_UPLOAD))
_r = a_c.post(
    "/upload_excel",
    data={"excel_file": (_buf, "not_real.xlsx")},
    content_type="multipart/form-data",
)
_added = [f for f in (set(os.listdir(_UPLOAD)) - _before) if "not_real" in f]
check("bad upload is rejected (redirect, not 200 OK page)", _r.status_code in (301, 302))
check("no orphaned file left in UPLOAD_FOLDER", not _added)
with app.app_context():
    check("no UploadedFile row for the rejected file", UploadedFile.query.filter_by(filename="not_real.xlsx").first() is None)

print()
if FAILS:
    print(f"❌ {len(FAILS)} CHECK(S) FAILED: {FAILS}")
    sys.exit(1)
print("✅ ALL ACCESS-CONTROL TESTS PASSED")
