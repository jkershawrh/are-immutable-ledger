"""Authentication behaviour for the ledger REST gateway.

The gateway fronts an append-only evidence store: POST /api/entries and
POST /api/receipts write records the rest of the platform treats as
authoritative. It previously skipped authentication entirely when
GATEWAY_API_TOKEN was unset, and no deployment manifest set it, so the
running gateway accepted anonymous writes.

These tests pin the fail-closed behaviour and the probe exemption.
"""

import importlib
import sys

import pytest

fastapi = pytest.importorskip(
    "fastapi", reason="gateway dependencies not installed"
)
from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "ledger-gateway-test-token-not-a-real-secret"


def _load_gateway(monkeypatch, *, token, allow_unauth=None):
    monkeypatch.setenv("LEDGER_ENDPOINT", "localhost:19292")
    if token is None:
        monkeypatch.delenv("GATEWAY_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GATEWAY_API_TOKEN", token)
    if allow_unauth is None:
        monkeypatch.delenv("GATEWAY_ALLOW_UNAUTHENTICATED", raising=False)
    else:
        monkeypatch.setenv("GATEWAY_ALLOW_UNAUTHENTICATED", allow_unauth)

    sys.modules.pop("api.gateway", None)
    return importlib.import_module("api.gateway")


def test_refuses_to_start_without_a_token(monkeypatch):
    """The regression guard: no token used to mean no authentication."""
    with pytest.raises(SystemExit) as excinfo:
        _load_gateway(monkeypatch, token=None)
    assert "GATEWAY_API_TOKEN" in str(excinfo.value)


def test_explicit_opt_in_allows_unauthenticated_local_use(monkeypatch):
    gateway = _load_gateway(monkeypatch, token=None, allow_unauth="true")
    assert gateway.ALLOW_UNAUTHENTICATED is True


def test_write_endpoint_rejects_missing_token(monkeypatch):
    gateway = _load_gateway(monkeypatch, token=TOKEN)
    response = TestClient(gateway.app).post("/api/entries", json={})
    assert response.status_code == 401, response.text


def test_write_endpoint_rejects_wrong_token(monkeypatch):
    gateway = _load_gateway(monkeypatch, token=TOKEN)
    response = TestClient(gateway.app).post(
        "/api/entries", json={}, headers={"Authorization": "Bearer not-the-token"}
    )
    assert response.status_code == 401, response.text


def test_read_endpoint_also_requires_a_token(monkeypatch):
    gateway = _load_gateway(monkeypatch, token=TOKEN)
    response = TestClient(gateway.app).get("/api/summary")
    assert response.status_code == 401, response.text


def test_healthz_never_requires_credentials(monkeypatch):
    """Container probes must not need the token."""
    gateway = _load_gateway(monkeypatch, token=TOKEN)
    response = TestClient(gateway.app).get("/healthz")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"
