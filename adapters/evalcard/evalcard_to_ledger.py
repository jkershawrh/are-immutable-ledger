#!/usr/bin/env python3
"""Fabric evaluation-card notarization adapter.

Consumes governed-agent-fabric evaluation cards (``fabric.evaluation-card/v1``,
pinned at ``contracts/fabric-evaluation-card-v1.schema.json``) and asks the
immutable ledger to issue a tamper-evident proof receipt. The card digest is
both the idempotency key and the input hash, so notarizing the same card
twice cannot create two entries, and any later edit to the card breaks the
binding. The adapter is not in the authorization path; a receipt proves the
card bytes were recorded, not that the card's claims are true.
"""

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "sdks", "python")
)
from ledger_client import LedgerClient


SCHEMA_VERSION = "fabric.evaluation-card/v1"
RECEIPT_SCHEMA_VERSION = "fabric.evalcard-receipt/v1"
ENTRY_TYPE = "fabric.evaluation-card.v1"
CONTENT_TYPE = "application/json"
DEFAULT_SOURCE_ID = "fabric-evalcard-adapter"
DEFAULT_AGENT_ID = "governed-agent-fabric"
REQUIRED_TOP = {
    "schema_version",
    "card_sha256",
    "issued_at",
    "mode",
    "construct",
    "evaluation",
    "systems",
    "uncertainty",
    "holdout_policy",
    "verdict",
    "limits",
}
REQUIRED_EVALUATION = {
    "source_schema_version",
    "source_id",
    "binding_sha256",
    "measured_sha256",
    "split",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """The evaluation card does not conform to the pinned contract."""


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_card(card):
    if not isinstance(card, dict):
        raise ContractError("card must be a JSON object")
    if card.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"unsupported schema_version: {card.get('schema_version')!r}")
    missing = sorted(REQUIRED_TOP - card.keys())
    if missing:
        raise ContractError(f"missing required fields: {', '.join(missing)}")
    card_sha = card["card_sha256"]
    if not SHA256_RE.fullmatch(str(card_sha)):
        raise ContractError("card_sha256 must be a 64-character SHA-256 hex digest")
    body = {key: value for key, value in card.items() if key != "card_sha256"}
    if digest(body) != card_sha:
        raise ContractError("card_sha256 does not match the card body")
    evaluation = card["evaluation"]
    if not isinstance(evaluation, dict) or REQUIRED_EVALUATION - evaluation.keys():
        raise ContractError("evaluation block is missing binding fields")
    if not isinstance(card["systems"], list) or not card["systems"]:
        raise ContractError("systems must be a non-empty list")
    if not isinstance(card["verdict"], dict):
        raise ContractError("verdict must be an object")
    if card["verdict"].get("authorizes_execution") is not False:
        raise ContractError("cards that authorize execution cannot be notarized")
    return card


def ledger_fields(card, source_id=DEFAULT_SOURCE_ID, agent_id=DEFAULT_AGENT_ID):
    validate_card(card)
    return {
        "entry_type": ENTRY_TYPE,
        "agent_id": agent_id,
        "content": canonical(card),
        "content_type": CONTENT_TYPE,
        "source_id": source_id,
        "correlation_id": card["evaluation"]["source_id"],
        "idempotency_key": card["card_sha256"],
        "input_hash": card["card_sha256"],
    }


def notarize(client, card, source_id=DEFAULT_SOURCE_ID, agent_id=DEFAULT_AGENT_ID):
    fields = ledger_fields(card, source_id=source_id, agent_id=agent_id)
    receipt = client.issue_receipt(**fields)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "card_sha256": card["card_sha256"],
        "correlation_id": fields["correlation_id"],
        "entry_id": receipt.entry_id,
        "entry_hash": receipt.entry_hash,
        "entry_type": ENTRY_TYPE,
        "chain_position": receipt.chain_position,
        "written_ts": receipt.written_ts,
        "input_hash": receipt.input_hash,
        "hash_version": receipt.hash_version,
    }


def verify(client, receipt, card=None):
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ContractError(f"unsupported receipt schema_version")
    if card is not None and receipt.get("card_sha256") != card.get("card_sha256"):
        raise ContractError("receipt does not correspond to the provided card")
    return client.verify_proof(receipt["entry_hash"], ENTRY_TYPE)


def write_new(path, value):
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    notarize_parser = sub.add_parser("notarize", help="Notarize a card and write its proof receipt")
    notarize_parser.add_argument("--card", required=True)
    notarize_parser.add_argument("--receipt-output")
    notarize_parser.add_argument("--endpoint", default="localhost:19292")
    notarize_parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    verify_parser = sub.add_parser("verify", help="Verify a proof receipt against the ledger")
    verify_parser.add_argument("--receipt", required=True)
    verify_parser.add_argument("--card")
    verify_parser.add_argument("--endpoint", default="localhost:19292")
    args = parser.parse_args()

    if args.command == "notarize":
        with open(args.card, encoding="utf-8") as handle:
            card = json.load(handle)
        with LedgerClient(args.endpoint) as client:
            record = notarize(client, card, source_id=args.source_id)
        output = args.receipt_output or str(args.card) + ".receipt.json"
        write_new(output, record)
        print(json.dumps(record))
        return 0

    with open(args.receipt, encoding="utf-8") as handle:
        receipt = json.load(handle)
    card = None
    if args.card:
        with open(args.card, encoding="utf-8") as handle:
            card = json.load(handle)
    with LedgerClient(args.endpoint) as client:
        result = verify(client, receipt, card=card)
    print(
        json.dumps(
            {
                "valid": bool(result.valid),
                "entry_type": result.entry_type,
                "chain_position": result.chain_position,
                "failure_reason": result.failure_reason,
            }
        )
    )
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
