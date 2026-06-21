#!/usr/bin/env python3
"""
FundTrail smoke tests — a dependency-free safety net.

Run:  cd main && python tests/smoke_test.py
Exits non-zero if anything fails. Run it before AND after each refactor step:
if a route disappears or a template's url_for() breaks, a check here turns red.
"""

import os, re, sys, tempfile, contextlib

MAIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MAIN)
os.environ["FUNDTRAIL_DATA_DIR"] = tempfile.mkdtemp(prefix="ft_smoke_")

with contextlib.redirect_stdout(open(os.devnull, "w")):
    import app as app_module
    from app import app, sanitize_text
    from models import db, User

app.config["WTF_CSRF_ENABLED"] = True  # keep CSRF real
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


# ── seed users ────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    for uname, role, pw in [
        ("admin", "Admin", "AdminPass@2026!"),
        ("officer", "Investigative Officer", "OfficerPass@2026!"),
        ("reset_user", "Investigative Officer", "ResetPass@2026!"),
    ]:
        u = User.query.filter_by(username=uname).first() or User(username=uname, role=role)
        if u.id is None:
            db.session.add(u)
        u.role = role
        if uname == "reset_user":
            u.email = "reset@example.gov"
            u.totp_secret = "JBSWY3DPEHPK3PXP"
        u.set_password(pw)
        u.must_change_password = False
        u.failed_login_attempts = 0
        u.account_locked_until = None
    db.session.commit()

print("\n── Routes ──")
ROUTE_BASELINE = 43
n = len(list(app.url_map.iter_rules()))
check(f"route count >= {ROUTE_BASELINE} (got {n})", n >= ROUTE_BASELINE)

print("\n── Auth & role routing ──")
admin = app.test_client()
officer = app.test_client()
check("admin login -> /admin_dashboard", "admin_dashboard" in loc(login(admin, "Admin", "admin", "AdminPass@2026!")))
check(
    "officer login -> /index", "/index" in loc(login(officer, "Investigative Officer", "officer", "OfficerPass@2026!"))
)
check("/home anon -> /login", "/login" in loc(app.test_client().get("/home")))
check("/home admin -> /admin_dashboard", "/admin_dashboard" in loc(admin.get("/home")))
check("/home officer -> /index", "/index" in loc(officer.get("/home")))
check("admin /index -> /admin_dashboard (separation)", "/admin_dashboard" in loc(admin.get("/index")))
check("officer /admin_dashboard -> redirect (blocked)", officer.get("/admin_dashboard").status_code in (301, 302))

print("\n── Pages render (catches url_for breakage in refactor) ──")
for p in [
    "/admin_dashboard",
    "/view_officers",
    "/manage_files",
    "/admin/add_officer",
    "/view_analytics",
    "/view_all_complaints",
]:
    check(f"admin GET {p}", admin.get(p).status_code == 200)
_gr = admin.get("/graph/SMOKE-ACK")
check("admin GET /graph/<ack> renders", _gr.status_code == 200)
check(
    "graph page is offline (no d3js.org / cdnjs)",
    "d3js.org" not in _gr.get_data(as_text=True) and "cdnjs" not in _gr.get_data(as_text=True),
)
for p in ["/index", "/my_analytics", "/change_password"]:
    check(f"officer GET {p}", officer.get(p).status_code == 200)

print("\n── Add Officer flow ──")
tok = csrf(admin.get("/admin/add_officer").get_data(as_text=True))
r = admin.post(
    "/submit_officer",
    data={
        "name": "T",
        "rank": "SI",
        "email": "t@x.gov",
        "username": "smoke_off",
        "password": "weak",
        "csrf_token": tok,
    },
)
check("weak pw is NOT 404", r.status_code != 404)
check("weak pw shows the rule", "at least 12 characters" in r.get_data(as_text=True))
r = admin.post(
    "/submit_officer",
    data={
        "name": "T",
        "rank": "SI",
        "email": "t@x.gov",
        "username": "smoke_off",
        "password": "TempPass@2026!",
        "csrf_token": tok,
    },
)
check("strong pw -> /view_officers", "view_officers" in loc(r))
with app.app_context():
    o = User.query.filter_by(username="smoke_off").first()
    check(
        "officer saved, temp pw, must_change", bool(o) and o.must_change_password and o.check_password("TempPass@2026!")
    )

print("\n── CSRF & errors ──")
r = admin.post(
    "/submit_officer",
    data={"name": "X", "rank": "SI", "email": "x@x.gov", "username": "x2", "password": "TempPass@2026!"},
)
check("missing CSRF -> 400", r.status_code == 400)
check("missing CSRF -> friendly page", "Session Expired" in r.get_data(as_text=True))
r = admin.get("/no-such-route-xyz")
check("404 page renders", r.status_code == 404 and "Return to Home" in r.get_data(as_text=True))
check("logout -> /login", "/login" in loc(admin.get("/logout")))

print("\n── Password reset email fallback ──")
sent_links = []


def fake_send_password_reset(_to_email, reset_link):
    sent_links.append(reset_link)


app_module.send_password_reset = fake_send_password_reset
reset_client = app.test_client()
tok = csrf(reset_client.get("/forgot_password").get_data(as_text=True))
r = reset_client.post("/forgot_password", data={"username": "reset_user", "csrf_token": tok})
check("reset user with TOTP reaches verify step", r.status_code == 200 and "Authentication code" in r.get_data(as_text=True))
r = reset_client.post("/forgot_password", data={"code": "000000", "csrf_token": tok})
check("bad TOTP keeps email fallback available", r.status_code == 200 and "Email reset" in r.get_data(as_text=True))
r = reset_client.post(
    "/forgot_password",
    data={"reset_method": "email", "email": "wrong@example.gov", "csrf_token": tok},
)
check("wrong reset email does not send", r.status_code == 200 and not sent_links)
r = reset_client.post(
    "/forgot_password",
    data={"reset_method": "email", "email": "reset@example.gov", "csrf_token": tok},
)
check("matching reset email sends link", r.status_code == 200 and len(sent_links) == 1)
reset_path = sent_links[0].split("http://localhost", 1)[-1]
r = reset_client.get(reset_path)
reset_tok = csrf(r.get_data(as_text=True))
check("valid reset token renders password form", r.status_code == 200 and reset_tok)
r = reset_client.post(
    reset_path,
    data={"password": "ResetPass@2027!", "confirm_password": "ResetPass@2027!", "csrf_token": reset_tok},
)
check("valid reset token changes password", "/login" in loc(r))
check("reset token cannot be reused", reset_client.get(reset_path).status_code in (301, 302))
check("invalid reset token redirects", reset_client.get("/reset_password/not-a-token").status_code in (301, 302))
with app.app_context():
    reset_user = User.query.filter_by(username="reset_user").first()
    check("new reset password works", reset_user.check_password("ResetPass@2027!"))

print("\n── Security hardening (Phase 5) ──")
check("MAX_CONTENT_LENGTH set (request-size cap)", bool(app.config.get("MAX_CONTENT_LENGTH")))
check("sanitize_text strips control/null chars + trims", sanitize_text("  ab\x00c\x01d  ") == "abcd")
check("sanitize_text caps length", len(sanitize_text("x" * 500, 100)) == 100)
check("sanitize_text(None) -> ''", sanitize_text(None) == "")

print()
if FAILS:
    print(f"❌ {len(FAILS)} CHECK(S) FAILED: {FAILS}")
    sys.exit(1)
print("✅ ALL SMOKE TESTS PASSED")
