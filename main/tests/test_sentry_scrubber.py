"""Verify the Sentry before_send scrubber actually strips case PII.

An untested scrubber is worse than none (false confidence), so this exercises the
real _sentry_before_send / _sentry_scrub functions against a representative event:
request query string, request data, exception-frame local variables, extra, and
breadcrumbs — covering the sensitive field names taken from models.py.
"""

import os
import secrets
import sys
import tempfile

MAIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MAIN)

os.environ.setdefault("FUNDTRAIL_DATA_DIR", tempfile.mkdtemp(prefix="ft_sentry_"))
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")

import app as app_module  # noqa: E402

FILTERED = app_module._SENTRY_FILTERED


def _fake_event():
    return {
        "request": {
            "url": "https://host/graph_data/ACK123?ack_no=ACK123&q=x",
            "query_string": "ack_no=ACK123",
            "data": {"account_number": "50100123456789", "note": "ok"},
            "headers": {"Host": "host"},
        },
        "extra": {
            "kyc_name": "John Doe",
            "kyc_aadhar": "1234-5678-9012",
            "kyc_mobile": "9876543210",
            "to_account": "919010001",
            "ifsc_code": "HDFC0001234",
            "txn_id": "UTR99999",
            "username": "officer_42",
            "bank_name": "HDFC Bank",
        },
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "vars": {
                                    "ack_no": "ACK123",
                                    "from_account": "919010001",
                                    "aadhar": "1111-2222-3333",
                                    "address": "12 MG Road",
                                    "name": "Jane Suspect",
                                    "amount": "50000",
                                    "filename": "case.xlsx",
                                }
                            }
                        ]
                    }
                }
            ]
        },
        "breadcrumbs": {"values": [{"data": {"account_number": "50100999", "step_label": "refund"}}]},
    }


def test_before_send_scrubs_known_sensitive_fields():
    out = app_module._sentry_before_send(_fake_event(), None)

    # URL query string dropped entirely; query params gone from url.
    assert "query_string" not in out["request"]
    assert "?" not in out["request"]["url"]

    # request.data + extra
    assert out["request"]["data"]["account_number"] == FILTERED
    assert out["request"]["data"]["note"] == "ok"  # non-sensitive preserved
    extra = out["extra"]
    for key in ("kyc_name", "kyc_aadhar", "kyc_mobile", "to_account", "ifsc_code", "txn_id"):
        assert extra[key] == FILTERED, f"{key} not scrubbed"
    # Debug-useful, non-PII name-like keys are deliberately kept.
    assert extra["username"] == "officer_42"
    assert extra["bank_name"] == "HDFC Bank"

    # Exception-frame local variables.
    frame_vars = out["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    for key in ("ack_no", "from_account", "aadhar", "address", "name"):
        assert frame_vars[key] == FILTERED, f"frame var {key} not scrubbed"
    assert frame_vars["amount"] == "50000"  # amount kept (not an identity field)
    assert frame_vars["filename"] == "case.xlsx"  # kept

    # Breadcrumbs nested data.
    crumb = out["breadcrumbs"]["values"][0]["data"]
    assert crumb["account_number"] == FILTERED
    assert crumb["step_label"] == "refund"


def test_before_send_returns_event_so_reporting_still_works():
    # Must return the (scrubbed) event, never None, or error reporting is dropped.
    assert app_module._sentry_before_send({"message": "boom"}, None) == {"message": "boom"}


def test_sentry_dsn_unset_keeps_sentry_inactive():
    # Guard: this session must not enable Sentry with a live DSN.
    assert not os.environ.get("SENTRY_DSN")
