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


# --- page_size honoring and clamping --------------------------------------
#
# Production incident (October 2026): consumers passing page_size=100 to
# GET /api/entries received up to 10,000 full-content entries, and the
# request outran every consumer's HTTP timeout against the 14.5M-row
# ledger. The REST contract these tests pin: an explicit page_size bounds
# both the response body and the gateway's backend work, clamped to
# [1, 10000]. When page_size is absent the historical defaults (100 for
# /api/entries, 10000 for the capped read endpoints) must be preserved so
# existing consumers see no change.


class _FakeRunawayPageClient:
    """Backend page that ignores the requested page_size.

    Stand-in for the deployed incident: the ledger handed back far more
    entries than the gateway asked for, so a page_size=100 request carried
    up to 10,000 entries. The gateway must enforce the cap itself rather
    than trust the backend page.
    """

    def __init__(self, entries):
        self.entries = entries
        self.query_kwargs = None

    def query_page(self, **kwargs):
        self.query_kwargs = kwargs
        return list(self.entries), "next-page", len(self.entries)


class _FakeBoundedLedger:
    """Serves a large result set one backend page at a time, honouring the
    requested page_size like the gRPC service does."""

    def __init__(self, total):
        self.total = total
        self.requested_page_sizes = []

    def query_page(self, *, page_size, page_token="", **kwargs):
        self.requested_page_sizes.append(page_size)
        start = int(page_token) if page_token else 0
        count = max(0, min(page_size, self.total - start))
        next_token = str(start + count) if start + count < self.total else ""
        return [_entry() for _ in range(count)], next_token, self.total


def _entries(n):
    entries = [_entry() for _ in range(n)]
    for i, e in enumerate(entries):
        e.entry_id = f"entry-{i}"
    return entries


def test_entries_honors_explicit_page_size(monkeypatch):
    ledger = _FakeRunawayPageClient(_entries(5))
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).get("/api/entries?page_size=2")

    assert response.status_code == 200
    assert ledger.query_kwargs["page_size"] == 2  # forwarded to the ledger
    body = response.json()
    assert len(body["entries"]) <= 2  # and enforced in the response
    assert [e["entry_id"] for e in body["entries"]] == ["entry-0", "entry-1"]
    assert body["next_page_token"] == "next-page"


def test_entries_default_page_size_is_unchanged_when_absent(monkeypatch):
    ledger = _FakeRunawayPageClient(_entries(3))
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).get("/api/entries")

    assert response.status_code == 200
    # No page_size requested: the historical default is forwarded unchanged
    # and the single-page response shape is preserved.
    assert ledger.query_kwargs["page_size"] == 100
    assert len(response.json()["entries"]) == 3


def test_entries_clamps_explicit_page_size_into_supported_range(monkeypatch):
    ledger = _FakeRunawayPageClient(_entries(1))
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)
    client = TestClient(gateway.app)

    assert client.get("/api/entries?page_size=0").status_code == 200
    assert ledger.query_kwargs["page_size"] == 1

    assert client.get("/api/entries?page_size=-5").status_code == 200
    assert ledger.query_kwargs["page_size"] == 1

    assert client.get("/api/entries?page_size=999999").status_code == 200
    assert ledger.query_kwargs["page_size"] == 10000


def test_capped_read_endpoints_clamp_runaway_page_size(monkeypatch):
    ledger = _FakeBoundedLedger(total=12000)
    monkeypatch.setattr(gateway, "get_client", lambda: ledger)

    response = TestClient(gateway.app).get("/api/summary?page_size=999999")

    assert response.status_code == 200
    body = response.json()
    # A runaway page_size must not turn a capped read into a full-ledger
    # scan: gateway work stops at the maximum supported page size.
    assert body["total_entries"] == 10000
    assert body["truncated"] is True
    # The internal 500-entry backend page is preserved.
    assert max(ledger.requested_page_sizes) <= 500
