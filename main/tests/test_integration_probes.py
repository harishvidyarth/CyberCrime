import os
import secrets
import sys
import tempfile

MAIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MAIN)

os.environ.setdefault("FUNDTRAIL_DATA_DIR", tempfile.mkdtemp(prefix="ft_integrations_"))
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("SESSION_COOKIE_INSECURE", "true")

import app as app_module  # noqa: E402


def _client(monkeypatch, enabled="false", token="probe-token"):
    monkeypatch.setenv("ENABLE_INTEGRATION_TEST_ROUTES", enabled)
    monkeypatch.setenv("INTEGRATION_TEST_TOKEN", token)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_integration_probes_are_disabled_by_default(monkeypatch):
    client = _client(monkeypatch, enabled="false")

    assert client.post("/__integration_test/sentry").status_code == 404
    assert client.post("/__integration_test/resend").status_code == 404


def test_integration_probes_require_bearer_token(monkeypatch):
    client = _client(monkeypatch, enabled="true", token="expected-token")

    assert client.post("/__integration_test/resend").status_code == 404
    assert client.post(
        "/__integration_test/resend",
        headers={"Authorization": "Bearer wrong-token"},
    ).status_code == 404


def test_resend_probe_uses_environment_recipient(monkeypatch):
    sent = []

    def fake_send(to_email):
        sent.append(to_email)
        return {"id": "email_test_123"}

    client = _client(monkeypatch, enabled="true", token="expected-token")
    monkeypatch.setenv("RESEND_TEST_TO", "qa@example.gov")
    monkeypatch.setattr(app_module, "send_integration_test_email", fake_send)

    response = client.post(
        "/__integration_test/resend",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "sent"
    assert sent == ["qa@example.gov"]
