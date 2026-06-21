#!/usr/bin/env python3
"""
FundTrail MRM 7-step workflow tests — dependency-free (no pytest needed).

Run:  cd main && python tests/test_mrm_workflow.py
Exits non-zero on any failure.

Covers the sequential/set-once rules of /save_mrm_status, the refund-step
mirroring into Transaction/POHRefundDetails, the read-only /mrm_timeline gate,
the MRM payload in /put_on_hold_transactions, and the startup backfill of
pre-existing refund/court data. Uses a throwaway temp DB and synthetic data only.
"""

import os, re, sys, json, secrets, tempfile, contextlib

MAIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MAIN)

os.environ["FUNDTRAIL_DATA_DIR"] = tempfile.mkdtemp(prefix="ft_mrm_")
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")

with contextlib.redirect_stdout(open(os.devnull, "w")):
    from app import app, ensure_mrm_backfill, MRM_STEPS, MRM_REFUND_STEP
    from models import db, User, UploadedFile, Transaction, Complaint, POHRefundDetails, MRMTracking, MRMStatusLog

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
    return client.post(
        "/login", data={"role": role, "username": username, "password": password, "csrf_token": tok}
    )


# ── seed: admin + two officers + a case with a put-on-hold txn owned by A ──
with app.app_context():
    db.create_all()

    def mkuser(uname, role, pw):
        u = User.query.filter_by(username=uname).first() or User(username=uname, role=role)
        if u.id is None:
            db.session.add(u)
        u.role = role
        if not u.password_hash or not u.check_password(pw):
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

    uf = UploadedFile(filename="mrm.xlsx", uploader="off_a")
    db.session.add(uf)
    db.session.commit()
    db.session.add(
        Transaction(
            ack_no="CASE-MRM",
            layer=3,
            from_account="111111111",
            to_account="222222222",
            amount=5000.0,
            put_on_hold_amount=5000.0,
            put_on_hold_txn_id="HOLD-1",
            put_on_hold_date="2026-06-01",
            txn_id="TX-MRM",
            upload_id=uf.id,
        )
    )
    if not Complaint.query.filter_by(ack_no="CASE-MRM").first():
        db.session.add(Complaint(ack_no="CASE-MRM", file_name="mrm.xlsx", uploaded_by=A_ID, assigned_to=A_ID))
    db.session.commit()

admin_c, a_c, b_c = app.test_client(), app.test_client(), app.test_client()
login(admin_c, "Admin", "admin", "AdminPass@2026!")
login(a_c, "Investigative Officer", "off_a", "OffaPass@2026!")
login(b_c, "Investigative Officer", "off_b", "OffbPass@2026!")


def save(client, step, date="2026-06-18", **extra):
    body = {"ack_no": "CASE-MRM", "hold_txn_id": "HOLD-1", "step": step, "date": date}
    body.update(extra)
    return client.post("/save_mrm_status", json=body)


print("\n── Sequential + set-once enforcement ──")
check("non-owner B save step1 -> 403", save(b_c, 1).status_code == 403)
check("owner A save step1 -> 200", save(a_c, 1).status_code == 200)
check("step3 before step2 -> 409 (sequential)", save(a_c, 3).status_code == 409)
check("re-saving dated step1 -> 409 (set-once)", save(a_c, 1).status_code == 409)
check("step2 -> 200", save(a_c, 2).status_code == 200)
check("bad date rejected -> 400", save(a_c, 3, date="soon").status_code == 400)
check("step out of range (9) -> 400", save(a_c, 9).status_code == 400)

print("\n── Refund step (6) requires type + positive amount ──")
check("steps 3,4,5 saved", all(save(a_c, s).status_code == 200 for s in (3, 4, 5)))
check("step6 without type/amount -> 400", save(a_c, MRM_REFUND_STEP).status_code == 400)
check("step6 with zero amount -> 400", save(a_c, MRM_REFUND_STEP, refund_type="FULL", refund_amount=0).status_code == 400)
r6 = save(a_c, MRM_REFUND_STEP, refund_type="FULL", refund_amount=5000)
check("step6 with FULL + amount -> 200", r6.status_code == 200)

print("\n── Refund step mirrors into Transaction / POHRefundDetails ──")
with app.app_context():
    t = Transaction.query.filter_by(ack_no="CASE-MRM", put_on_hold_txn_id="HOLD-1").first()
    check("Transaction.refund_amount mirrored", t.refund_amount == 5000.0)
    check("Transaction.refund_status = Refunded", t.refund_status == "Refunded")
    check("Transaction.refund_type = FULL", t.refund_type == "FULL")
    poh = POHRefundDetails.query.filter_by(ack_no="CASE-MRM", txn_id="HOLD-1").first()
    check("POHRefundDetails refund persisted", bool(poh) and poh.refund_amount == 5000.0)
    m = MRMTracking.query.filter_by(ack_no="CASE-MRM", txn_id="HOLD-1").first()
    check("MRM step6 dated + amount", bool(m) and bool(m.step6) and m.refund_amount == 5000.0)

print("\n── Audit trail (who / what / when) ──")
with app.app_context():
    logs = MRMStatusLog.query.filter_by(ack_no="CASE-MRM", txn_id="HOLD-1").all()
    check("one audit row per completed stage (6)", len(logs) == 6)
    check("audit records who performed each stage", all(g.performed_by == "off_a" for g in logs))
    refund_log = MRMStatusLog.query.filter_by(ack_no="CASE-MRM", txn_id="HOLD-1", step=MRM_REFUND_STEP).first()
    check("refund audit row carries type + amount", bool(refund_log) and refund_log.refund_type == "FULL" and refund_log.refund_amount == 5000.0)

print("\n── Read-only timeline + hold payload ──")
tl = admin_c.get("/mrm_timeline/CASE-MRM/HOLD-1")
check("admin GET /mrm_timeline -> 200", tl.status_code == 200)
tldata = json.loads(tl.get_data(as_text=True))
check("timeline reports latest_step 6", tldata.get("latest_step") == MRM_REFUND_STEP)
check("timeline has 7 steps", len(tldata.get("steps", [])) == len(MRM_STEPS))
check("timeline includes audit trail", len(tldata.get("audit", [])) == 6)
check("non-owner B GET /mrm_timeline -> 403", b_c.get("/mrm_timeline/CASE-MRM/HOLD-1").status_code == 403)

poh_resp = a_c.get("/put_on_hold_transactions/CASE-MRM")
check("put_on_hold_transactions -> 200", poh_resp.status_code == 200)
rows = json.loads(poh_resp.get_data(as_text=True))
check("hold row carries hold_txn_id + mrm payload", bool(rows) and rows[0].get("hold_txn_id") == "HOLD-1" and "mrm" in rows[0])

print("\n── Startup backfill of pre-existing refund/court data ──")
with app.app_context():
    uf2 = UploadedFile(filename="legacy_mrm.xlsx", uploader="off_a")
    db.session.add(uf2)
    db.session.commit()
    db.session.add(
        Transaction(
            ack_no="CASE-MRM",
            layer=4,
            from_account="3",
            to_account="444444444",
            amount=2000.0,
            put_on_hold_amount=2000.0,
            put_on_hold_txn_id="HOLD-LEGACY",
            put_on_hold_date="2026-05-01",
            court_order_date="2026-05-20",
            refund_status="Partially Refunded",
            refund_amount=1200.0,
            txn_id="TX-LEG",
            upload_id=uf2.id,
        )
    )
    db.session.commit()
    ensure_mrm_backfill()
    m = MRMTracking.query.filter_by(ack_no="CASE-MRM", txn_id="HOLD-LEGACY").first()
    check("backfill created an MRM row", m is not None)
    check("backfill step1 = hold date", bool(m) and m.step1 == "2026-05-01")
    check("backfill Partially Refunded -> step6 PARTIAL", bool(m) and bool(m.step6) and m.refund_type == "PARTIAL")
    check("backfill carried refund amount", bool(m) and m.refund_amount == 1200.0)
    # Idempotent: a second pass must not duplicate or overwrite.
    before = MRMTracking.query.count()
    ensure_mrm_backfill()
    check("backfill is idempotent (no new rows)", MRMTracking.query.count() == before)

print()
if FAILS:
    print(f"❌ {len(FAILS)} MRM TEST(S) FAILED")
    sys.exit(1)
print("✅ ALL MRM WORKFLOW TESTS PASSED")
