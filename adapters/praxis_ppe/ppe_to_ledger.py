#!/usr/bin/env python3
"""Reference Praxis PPE audit-event adapter.

This preview adapter consumes the producer-neutral ``praxis.ppe.audit.v1``
shape defined in ``contracts/praxis-ppe-ocsf-ledger-contract.md``. It maps a
completed PPE decision to OCSF 6003 and asks the immutable ledger to issue a
proof receipt. It is not a native Praxis/PPE plugin and is not in the
authorization path.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "sdks", "python")
)
from ledger_client import LedgerClient


SCHEMA_VERSION = "praxis.ppe.audit.v1"
CONTENT_TYPE = "application/ocsf+json"
DEFAULT_SOURCE_ID = "praxis-ppe-preview-adapter"
DECISIONS = {"allow", "deny", "transform"}
REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "occurred_at",
    "trace_id",
    "decision",
    "policy_id",
    "policy_version",
    "subject_id",
    "resource",
    "reason_code",
    "input_hash",
}
OPTIONAL_FIELDS = {"duration_ms", "transform_id"}
FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "completion",
    "credential",
    "model_api_key",
    "password",
    "prompt",
    "secret",
    "token",
}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ContractError(ValueError):
    """The producer event does not conform to the preview contract."""


def _find_forbidden_key(value, path="event"):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                return f"{path}.{key}"
            found = _find_forbidden_key(nested, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found = _find_forbidden_key(nested, f"{path}[{index}]")
            if found:
                return found
    return None


def validate_event(event):
    if not isinstance(event, dict):
        raise ContractError("event must be a JSON object")

    forbidden = _find_forbidden_key(event)
    if forbidden:
        raise ContractError(f"sensitive-content field is prohibited: {forbidden}")

    missing = sorted(REQUIRED_FIELDS - event.keys())
    if missing:
        raise ContractError(f"missing required fields: {', '.join(missing)}")

    unknown = sorted(event.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS)
    if unknown:
        raise ContractError(f"unknown fields: {', '.join(unknown)}")

    if event["schema_version"] != SCHEMA_VERSION:
        raise ContractError(
            f"unsupported schema_version: {event['schema_version']!r}"
        )
    if event["decision"] not in DECISIONS:
        raise ContractError(f"unsupported decision: {event['decision']!r}")
    if not SHA256_RE.fullmatch(str(event["input_hash"])):
        raise ContractError("input_hash must be a 64-character SHA-256 hex digest")

    try:
        occurred_at = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ContractError("occurred_at must be an RFC 3339 timestamp") from None
    if occurred_at.tzinfo is None:
        raise ContractError("occurred_at must include an RFC 3339 timezone")

    for field in REQUIRED_FIELDS - {"input_hash"}:
        if not isinstance(event[field], str) or not event[field].strip():
            raise ContractError(f"{field} must be a non-empty string")

    if "duration_ms" in event:
        duration = event["duration_ms"]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ContractError("duration_ms must be a non-negative number")
        if duration < 0:
            raise ContractError("duration_ms must be a non-negative number")

    if event["decision"] == "transform" and not event.get("transform_id"):
        raise ContractError("transform decisions require transform_id")
    if "transform_id" in event and (
        not isinstance(event["transform_id"], str) or not event["transform_id"].strip()
    ):
        raise ContractError("transform_id must be a non-empty string")

    return event


def map_to_ocsf(event):
    """Validate and map one logical PPE decision to an OCSF document."""
    validate_event(event)

    unmapped = {
        "praxis.ppe.schema_version": event["schema_version"],
        "praxis.ppe.decision": event["decision"],
        "praxis.ppe.policy_id": event["policy_id"],
        "praxis.ppe.policy_version": event["policy_version"],
        "praxis.ppe.resource": event["resource"],
        "praxis.ppe.reason_code": event["reason_code"],
        "praxis.ppe.input_hash": event["input_hash"].lower(),
    }
    if "duration_ms" in event:
        unmapped["praxis.ppe.duration_ms"] = event["duration_ms"]
    if "transform_id" in event:
        unmapped["praxis.ppe.transform_id"] = event["transform_id"]

    return {
        "class_uid": 6003,
        "class_name": "AI Operation",
        "activity_name": "Policy Decision",
        "time": event["occurred_at"],
        "metadata": {
            "uid": event["event_id"],
            "correlation_uid": event["trace_id"],
            "version": "1.0.0",
        },
        "ai_agent": {"uid": event["subject_id"]},
        "unmapped": unmapped,
    }


def canonicalize_ocsf(ocsf_event):
    """Return deterministic UTF-8 JSON bytes for ledger storage."""
    return json.dumps(
        ocsf_event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def ledger_fields(event, source_id=DEFAULT_SOURCE_ID):
    ocsf_event = map_to_ocsf(event)
    content = canonicalize_ocsf(ocsf_event)
    decision = event["decision"]
    return {
        "entry_type": f"praxis.ppe.policy.{decision}.v1",
        "agent_id": event["subject_id"],
        "content": content,
        "content_type": CONTENT_TYPE,
        "source_id": source_id,
        "correlation_id": event["trace_id"],
        "idempotency_key": event["event_id"],
        "input_hash": event["input_hash"].lower(),
    }


def process_line(client, line, stats, *, source_id=DEFAULT_SOURCE_ID):
    line = line.strip()
    if not line:
        return None

    try:
        event = json.loads(line)
    except json.JSONDecodeError as exc:
        stats["parse_errors"] += 1
        print(f"  REJECTED invalid JSON: {exc}", file=sys.stderr)
        return None

    try:
        fields = ledger_fields(event, source_id=source_id)
    except ContractError as exc:
        stats["contract_errors"] += 1
        print(f"  REJECTED contract violation: {exc}", file=sys.stderr)
        return None

    try:
        receipt = client.issue_receipt(**fields)
    except Exception as exc:
        stats["write_errors"] += 1
        print(f"  ERROR writing {fields['entry_type']}: {exc}", file=sys.stderr)
        return None

    stats["written"] += 1
    print(
        f"  [{receipt.chain_position:>3}] {fields['entry_type']:<34} "
        f"trace={fields['correlation_id']}"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(
        description="Map Praxis PPE preview events to OCSF ledger receipts"
    )
    parser.add_argument("--file", "-f", help="Read JSONL from a file instead of stdin")
    parser.add_argument(
        "--endpoint", default="localhost:19292", help="Ledger gRPC endpoint"
    )
    parser.add_argument(
        "--source-id", default=DEFAULT_SOURCE_ID, help="Stable adapter deployment ID"
    )
    args = parser.parse_args()

    stats = {
        "written": 0,
        "parse_errors": 0,
        "contract_errors": 0,
        "write_errors": 0,
    }
    client = LedgerClient(args.endpoint)
    source = open(args.file, encoding="utf-8") if args.file else sys.stdin

    try:
        for line in source:
            process_line(client, line, stats, source_id=args.source_id)
    finally:
        if args.file:
            source.close()
        client.close()

    print(
        "\n  Written: {written}  Contract errors: {contract_errors}  "
        "Parse errors: {parse_errors}  Write errors: {write_errors}\n".format(**stats)
    )
    if stats["parse_errors"] or stats["contract_errors"] or stats["write_errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
