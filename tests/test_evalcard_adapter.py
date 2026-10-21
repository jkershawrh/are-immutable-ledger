"""Contract tests for the fabric evaluation-card adapter."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "evalcard"))

from evalcard_to_ledger import (  # noqa: E402
    ContractError,
    DEFAULT_AGENT_ID,
    DEFAULT_SOURCE_ID,
    ENTRY_TYPE,
    digest,
    ledger_fields,
    notarize,
    validate_card,
    verify,
)


def make_card(**overrides):
    value = {
        "schema_version": "fabric.evaluation-card/v1",
        "issued_at": "2026-10-21T00:00:00+00:00",
        "mode": "workload-pipeline",
        "construct": {
            "statement": "Whether a candidate interprets one bounded snapshot correctly.",
            "metric": "Exact-output GREEN grade per case against frozen references.",
            "gaming_analysis": "A digest-keyed replay table could pass without capability.",
            "construct_sha256": "0" * 64,
        },
        "evaluation": {
            "source_schema_version": "folsom.workload-pipeline/v1",
            "source_id": "card-test-suite",
            "binding_sha256": "1" * 64,
            "measured_sha256": "2" * 64,
            "split": "development",
        },
        "systems": [
            {
                "system_id": "c1",
                "scaffold": {"adapter": "replay", "procedure_revision": "p1"},
                "model_binding": {"candidate_kind": "recorded-model", "profile_sha256": "3" * 64},
                "evidence_label": "REHEARSAL",
                "repetition": {"trials_per_case": 2, "case_count": 2, "total_trials": 4, "incomplete_trials": 0},
                "single_attempt_rate": {"value": 0.5, "passed": 2, "total": 4, "wilson_95": [0.15, 0.85]},
                "pass_at_k": {"value": 0.5, "passed": 1, "total": 2, "wilson_95": [0.09, 0.91]},
                "pass_all_k": {"value": 0.5, "passed": 1, "total": 2, "k": 2, "wilson_95": [0.09, 0.91]},
                "reliability_claimable": False,
                "reliability_note": "Incomplete trials are present; consistency is not claimable.",
                "performance": {
                    "latency": {"unit": "seconds", "mean": 0.1, "max": 0.2},
                    "model_calls": 0,
                    "deadline": {"unit": "seconds", "value": 60},
                },
                "scope": "synthetic test cohort with retained replay responses",
            }
        ],
        "uncertainty": {
            "method": "Wilson score interval on binomial case outcomes",
            "judge_error_included": False,
            "grading_basis": ["imported exact-output grades; no verifier ran"],
            "notes": "Reference-authoring error remains unquantified.",
        },
        "holdout_policy": {
            "split": "development",
            "case_origins": ["synthetic"],
            "statement": "Declared held-out status does not establish non-contamination.",
        },
        "verdict": {"color": "AMBER", "authorizes_execution": False},
        "limits": "Bounded local execution; no operational claim follows.",
    }
    value.update(overrides)
    value["card_sha256"] = digest({key: item for key, item in value.items() if key != "card_sha256"})
    return value


def make_receipt(card, **overrides):
    value = {
        "schema_version": "fabric.evalcard-receipt/v1",
        "card_sha256": card["card_sha256"],
        "correlation_id": card["evaluation"]["source_id"],
        "entry_id": "entry-001",
        "entry_hash": "e" * 64,
        "entry_type": ENTRY_TYPE,
        "chain_position": 3,
        "written_ts": 1792600000,
        "input_hash": card["card_sha256"],
        "hash_version": "v3",
    }
    value.update(overrides)
    return value


def test_fixture_card_is_valid_and_notarizable():
    fixture = json.loads((ROOT / "adapters" / "evalcard" / "fixtures" / "evaluation-card.json").read_text())
    assert validate_card(fixture) is fixture
    fields = ledger_fields(fixture)
    assert fields["idempotency_key"] == fixture["card_sha256"]


def test_valid_card_maps_to_ledger_fields():
    card = make_card()
    fields = ledger_fields(card)
    assert fields["entry_type"] == ENTRY_TYPE
    assert fields["agent_id"] == DEFAULT_AGENT_ID
    assert fields["source_id"] == DEFAULT_SOURCE_ID
    assert fields["content_type"] == "application/json"
    assert fields["correlation_id"] == "card-test-suite"
    assert fields["idempotency_key"] == card["card_sha256"]
    assert fields["input_hash"] == card["card_sha256"]
    assert json.loads(fields["content"].decode("utf-8")) == card


def test_unknown_schema_version_is_rejected():
    with pytest.raises(ContractError, match="unsupported schema_version"):
        validate_card(make_card(schema_version="fabric.evaluation-card/v2"))


def test_missing_required_field_is_rejected():
    card = make_card()
    del card["verdict"]
    card["card_sha256"] = digest({key: value for key, value in card.items() if key != "card_sha256"})
    with pytest.raises(ContractError, match="verdict"):
        validate_card(card)


def test_digest_mismatch_is_rejected():
    card = make_card()
    card["card_sha256"] = "f" * 64
    with pytest.raises(ContractError, match="card_sha256 does not match"):
        validate_card(card)


def test_card_authorizing_execution_is_rejected():
    card = make_card(verdict={"color": "GREEN", "authorizes_execution": True})
    with pytest.raises(ContractError, match="authorize execution"):
        validate_card(card)


def test_notarize_returns_receipt_record_bound_to_card_digest():
    card = make_card()
    client = MagicMock()
    client.issue_receipt.return_value = SimpleNamespace(
        entry_id="entry-042",
        entry_hash="ab" * 32,
        chain_position=7,
        written_ts=1792601234,
        input_hash=card["card_sha256"],
        hash_version="v3",
    )
    record = notarize(client, card)
    assert record["schema_version"] == "fabric.evalcard-receipt/v1"
    assert record["card_sha256"] == card["card_sha256"]
    assert record["entry_id"] == "entry-042"
    assert record["entry_hash"] == "ab" * 32
    assert record["chain_position"] == 7
    assert record["correlation_id"] == "card-test-suite"
    client.issue_receipt.assert_called_once()


def test_verify_rejects_receipt_for_a_different_card():
    client = MagicMock()
    receipt = make_receipt(make_card())
    other = make_card(verdict={"color": "RED", "authorizes_execution": False})
    with pytest.raises(ContractError, match="does not correspond"):
        verify(client, receipt, card=other)
    client.verify_proof.assert_not_called()


def test_verify_calls_verify_proof_with_entry_hash():
    client = MagicMock()
    client.verify_proof.return_value = SimpleNamespace(
        valid=True, entry_type=ENTRY_TYPE, chain_position=7, failure_reason=""
    )
    card = make_card()
    result = verify(client, make_receipt(card), card=card)
    assert result.valid is True
    client.verify_proof.assert_called_once_with("e" * 64, ENTRY_TYPE)
