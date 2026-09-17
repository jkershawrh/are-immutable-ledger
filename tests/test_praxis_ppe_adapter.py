"""Contract tests for the Praxis PPE preview adapter."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "praxis_ppe"))

from ppe_to_ledger import (  # noqa: E402
    ContractError,
    canonicalize_ocsf,
    ledger_fields,
    map_to_ocsf,
    process_line,
    validate_event,
)


def make_event(**overrides):
    event = {
        "schema_version": "praxis.ppe.audit.v1",
        "event_id": "ppe-event-001",
        "occurred_at": "2026-09-17T14:00:00Z",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "decision": "allow",
        "policy_id": "model-access",
        "policy_version": "sha256:policy-digest",
        "subject_id": "tenant-a-workload",
        "resource": "model/demo-chat",
        "reason_code": "policy_allow",
        "duration_ms": 2.4,
        "input_hash": "a" * 64,
    }
    event.update(overrides)
    return event


def make_stats():
    return {
        "written": 0,
        "parse_errors": 0,
        "contract_errors": 0,
        "write_errors": 0,
    }


def test_fixture_contains_allow_and_deny_contract_events():
    fixture = ROOT / "adapters/praxis_ppe/fixtures/ppe-audit-v1.jsonl"
    events = [
        json.loads(line) for line in fixture.read_text().splitlines() if line.strip()
    ]

    assert [event["decision"] for event in events] == ["allow", "deny"]
    for event in events:
        assert validate_event(event) is event


def test_unknown_schema_version_is_rejected():
    with pytest.raises(ContractError, match="unsupported schema_version"):
        validate_event(make_event(schema_version="praxis.ppe.audit.v2"))


def test_missing_required_field_is_rejected():
    event = make_event()
    del event["trace_id"]
    with pytest.raises(ContractError, match="trace_id"):
        validate_event(event)


def test_malformed_input_hash_is_rejected():
    with pytest.raises(ContractError, match="SHA-256"):
        validate_event(make_event(input_hash="not-a-digest"))


@pytest.mark.parametrize(
    "occurred_at", ["not-a-time", "2026-09-17T14:00:00"]
)
def test_timestamp_must_be_rfc3339_with_timezone(occurred_at):
    with pytest.raises(ContractError, match="RFC 3339"):
        validate_event(make_event(occurred_at=occurred_at))


@pytest.mark.parametrize("field", ["prompt", "completion", "authorization", "api_key"])
def test_sensitive_content_fields_are_rejected(field):
    event = make_event()
    event[field] = "DO-NOT-PERSIST-CANARY"
    with pytest.raises(ContractError, match="sensitive-content"):
        validate_event(event)


def test_transform_requires_transform_identifier():
    with pytest.raises(ContractError, match="transform_id"):
        validate_event(make_event(decision="transform"))


def test_mapping_uses_exact_trace_and_contains_no_model_content():
    event = make_event()
    ocsf = map_to_ocsf(event)
    serialized = canonicalize_ocsf(ocsf).decode()

    assert ocsf["metadata"]["correlation_uid"] == event["trace_id"]
    assert ocsf["metadata"]["uid"] == event["event_id"]
    assert ocsf["unmapped"]["praxis.ppe.decision"] == "allow"
    assert "prompt" not in serialized.lower()
    assert "completion" not in serialized.lower()
    assert "credential" not in serialized.lower()


@pytest.mark.parametrize("decision", ["allow", "deny", "transform"])
def test_decisions_use_separate_versioned_entry_types(decision):
    overrides = {"decision": decision}
    if decision == "transform":
        overrides["transform_id"] = "redact-email-v1"
    fields = ledger_fields(make_event(**overrides), source_id="praxis-lab-dev")

    assert fields["entry_type"] == f"praxis.ppe.policy.{decision}.v1"
    assert fields["source_id"] == "praxis-lab-dev"


def test_event_id_is_the_retry_stable_idempotency_key():
    event = make_event()
    first = ledger_fields(event)
    second = ledger_fields(event)

    assert first["idempotency_key"] == event["event_id"]
    assert second["idempotency_key"] == first["idempotency_key"]
    assert second["content"] == first["content"]


def test_process_line_submits_receipt_without_changing_decision():
    client = MagicMock()
    client.issue_receipt.return_value = SimpleNamespace(chain_position=7)
    stats = make_stats()
    event = make_event(decision="deny", reason_code="model_not_allowed")

    receipt = process_line(
        client, json.dumps(event), stats, source_id="praxis-lab-dev"
    )

    assert receipt.chain_position == 7
    assert stats["written"] == 1
    kwargs = client.issue_receipt.call_args.kwargs
    assert kwargs["entry_type"] == "praxis.ppe.policy.deny.v1"
    assert kwargs["correlation_id"] == event["trace_id"]
    assert kwargs["idempotency_key"] == event["event_id"]
    assert json.loads(kwargs["content"])["unmapped"]["praxis.ppe.decision"] == "deny"


def test_contract_violation_is_not_submitted():
    client = MagicMock()
    stats = make_stats()
    event = make_event(schema_version="unsupported")

    assert process_line(client, json.dumps(event), stats) is None
    assert stats["contract_errors"] == 1
    client.issue_receipt.assert_not_called()
