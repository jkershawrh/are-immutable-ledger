"""Focused REST compatibility tests for fleet ecosystem queries."""

import os
from types import SimpleNamespace

import pytest

# The gateway refuses to start without GATEWAY_API_TOKEN. These tests cover
# query forwarding rather than authentication, so they opt into unauthenticated
# mode explicitly; tests/test_gateway_auth.py covers the auth behaviour itself.
os.environ.setdefault("GATEWAY_ALLOW_UNAUTHENTICATED", "true")

from fastapi.testclient import TestClient  # noqa: E402

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
        hash_version="ARE_LEDGER_ENTRY_HASH_V3",
    )


class _FakeClient:
    def __init__(self):
        self.query_kwargs = None
        self.closed = False

    def query_page(self, **kwargs):
        self.query_kwargs = kwargs
        return [_entry()], "next-page", 1

    def close(self):
        self.closed = True


class _FakeWriteClient:
    def __init__(self):
        self.write_kwargs = None

    def write(self, **kwargs):
        self.write_kwargs = kwargs
        return SimpleNamespace(
            entry_id="entry-1",
            entry_hash="a" * 64,
            chain_position=1,
            written_ts=150,
            hash_version="ARE_LEDGER_ENTRY_HASH_V3",
        )


class _FakeAuditClient:
    def __init__(self):
        first = _entry()
        second = _entry()
        second.entry_id = "entry-2"
        second.entry_type = "kagenti.policy.denied"
        second.source_id = "urn:kagenti:gateway"
        second.chain_position = 4
        self.entries = [first, second]
        self.query_kwargs = None

    def query_page(self, **kwargs):
        self.query_kwargs = kwargs
        return self.entries, "", len(self.entries)


def test_entries_query_forwards_unix_millisecond_window_and_input_hash(monkeypatch):
    ledger = _FakeClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).get(
        "/api/entries?correlation_id=corr-1&from_ts=100&to_ts=200"
    )

    assert response.status_code == 200
    assert ledger.query_kwargs == {
        "page_size": 100,
        "page_token": "",
        "correlation_id": "corr-1",
        "from_ts": 100,
        "to_ts": 200,
    }
    assert ledger.closed is False  # singleton client is reused, not closed per-request
    body = response.json()
    assert body["entries"][0]["input_hash"] == "c" * 64
    assert body["entries"][0]["hash_version"] == "ARE_LEDGER_ENTRY_HASH_V3"
    assert body["next_page_token"] == "next-page"
    assert body["total_count"] == 1


def test_entries_query_rejects_non_integer_time_window(monkeypatch):
    ledger = _FakeClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).get("/api/entries?from_ts=not-a-number")

    assert response.status_code == 400
    assert ledger.query_kwargs is None
    assert ledger.closed is False  # singleton client is reused, not closed per-request


def test_write_serializes_structured_json_content(monkeypatch):
    ledger = _FakeWriteClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).post(
        "/api/entries",
        json={
            "entry_type": "release.validation.v1",
            "agent_id": "certifier",
            "content": {"check": "contract", "passed": True},
        },
    )

    assert response.status_code == 201
    assert ledger.write_kwargs["content"] == '{"check":"contract","passed":true}'


def test_summary_preserves_filters_and_truncation_contract(monkeypatch):
    ledger = _FakeAuditClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).get(
        "/api/summary?entry_type=fleet.operation.verified&from_ts=100&page_size=2"
    )

    assert response.status_code == 200
    assert ledger.query_kwargs == {
        "page_size": 2,
        "page_token": "",
        "entry_type": "fleet.operation.verified",
        "from_ts": 100,
    }
    assert response.json()["truncated"] is True


def test_chains_and_timeline_keep_legacy_response_shapes(monkeypatch):
    ledger = _FakeAuditClient()
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)
    client = TestClient(gateway.app)

    chains = client.get("/api/chains").json()
    assert isinstance(chains, dict)
    assert chains["chains"][0]["source"] == "unknown"
    assert chains["chains"][1]["source"] == "kagenti"

    timeline = client.get("/api/timeline").json()
    assert timeline["cross_links"] == {
        "corr-1": ["entry-1", "entry-2"],
    }


import grpc


def _fake_rpc_error(code, details):
    """A grpc.RpcError stand-in the endpoint's except clause can catch."""

    class _FakeRpcError(grpc.RpcError):
        def __init__(self):
            super().__init__(details)
            self._code = code
            self._details = details

        def code(self):
            return self._code

        def details(self):
            return self._details

    return _FakeRpcError()


class TestGrpcErrorMapping:
    """gRPC errors must map to honest HTTP statuses.

    Production incident (2026-11-12): an unhandled RpcError surfaced as a
    generic 500, so permanently rejected content (INVALID_ARGUMENT, e.g.
    oversized) was indistinguishable from transient failure — a client
    receipt spool retried undeliverable entries for two weeks. Permanent
    rejections must answer 4xx.
    """

    def test_invalid_argument_maps_to_400(self):
        import grpc

        resp = gateway._grpc_error_response(
            _fake_rpc_error(grpc.StatusCode.INVALID_ARGUMENT,
                          "content exceeds max 1048576 bytes"))
        assert resp.status_code == 400
        assert "exceeds max" in resp.body.decode()

    def test_unavailable_maps_to_503(self):
        import grpc

        resp = gateway._grpc_error_response(
            _fake_rpc_error(grpc.StatusCode.UNAVAILABLE, "starting"))
        assert resp.status_code == 503

    def test_internal_maps_to_500(self):
        import grpc

        resp = gateway._grpc_error_response(
            _fake_rpc_error(grpc.StatusCode.INTERNAL, "boom"))
        assert resp.status_code == 500

    def test_write_endpoint_maps_oversized_rejection(self, monkeypatch):
        """POST /api/receipts answers 400, not 500, for oversized content."""
        import grpc

        def raise_invalid(**kwargs):
            raise _fake_rpc_error(grpc.StatusCode.INVALID_ARGUMENT,
                                  "content exceeds max 1048576 bytes")

        monkeypatch.setattr(gateway, "get_client",
                            lambda: SimpleNamespace(issue_receipt=raise_invalid))
        with TestClient(gateway.app) as client:
            response = client.post("/api/receipts", json={
                "entry_type": "decision.record", "agent_id": "probe",
                "content": "x", "content_type": "application/json",
                "source_id": "probe", "correlation_id": "c",
                "idempotency_key": "k", "input_hash": "h",
            })
        assert response.status_code == 400
        assert "exceeds max" in response.json()["error"]
