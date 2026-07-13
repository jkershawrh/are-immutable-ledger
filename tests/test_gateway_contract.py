"""Focused REST compatibility tests for fleet ecosystem queries."""

from types import SimpleNamespace

import pytest

gateway = pytest.importorskip(
    "api.gateway",
    reason="optional REST gateway dependencies are not installed",
)


def _entry():
    return SimpleNamespace(
        entry_id="entry-1",
        entry_type="fleet.operation.verified",
        agent_id="fleet-controller",
        content=b'{"phase":"VERIFIED"}',
        content_type="application/json",
        source_id="urn:fleet-llm-d:controller",
        correlation_id="corr-1",
        entry_hash="a" * 64,
        previous_hash="b" * 64,
        chain_position=3,
        written_ts=150,
        input_hash="c" * 64,
        writer_signature=b"",
        signer_key_reference="",
        attestation_report=b"",
    )


class _FakeClient:
    def __init__(self):
        self.query_kwargs = None
        self.closed = False

    def query(self, **kwargs):
        self.query_kwargs = kwargs
        return [_entry()]

    def close(self):
        self.closed = True


def test_entries_query_forwards_unix_millisecond_window_and_input_hash(monkeypatch):
    ledger = _FakeClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = gateway.app.test_client().get(
        "/api/entries?correlation_id=corr-1&from_ts=100&to_ts=200"
    )

    assert response.status_code == 200
    assert ledger.query_kwargs == {
        "correlation_id": "corr-1",
        "from_ts": 100,
        "to_ts": 200,
    }
    assert ledger.closed is True
    assert response.get_json()[0]["input_hash"] == "c" * 64


def test_entries_query_rejects_non_integer_time_window(monkeypatch):
    ledger = _FakeClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = gateway.app.test_client().get("/api/entries?from_ts=not-a-number")

    assert response.status_code == 400
    assert ledger.query_kwargs is None
    assert ledger.closed is True
