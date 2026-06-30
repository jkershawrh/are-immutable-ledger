#!/usr/bin/env python3
"""OCSF-to-Ledger adapter for NVIDIA OpenShell.

Reads OCSF v1.7.0 JSONL events from stdin or a file and writes them
to the immutable ledger. Each OCSF event becomes a ledger entry with:

  entry_type:     "openshell.<class_name>" (e.g., "openshell.http_activity")
  agent_id:       metadata.uid (sandbox ID)
  content:        raw OCSF JSON bytes (unmodified)
  content_type:   "application/ocsf+json"
  source_id:      "openshell-supervisor"
  correlation_id: unmapped.request_id or unmapped.trace_id if present

Usage:
  openshell logs my-sandbox --tail | python ocsf_to_ledger.py
  python ocsf_to_ledger.py --file /var/log/openshell-ocsf.log
  cat sample_events.jsonl | python ocsf_to_ledger.py
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdks", "python"))
from ledger_client import LedgerClient

OCSF_CLASS_MAP = {
    4001: "network_activity",
    4002: "http_activity",
    4003: "ssh_activity",
    1007: "process_activity",
    2004: "detection_finding",
    6002: "app_lifecycle",
    5001: "config_state_change",
}


def extract_entry_type(event):
    class_uid = event.get("class_uid")
    if class_uid and class_uid in OCSF_CLASS_MAP:
        return f"openshell.{OCSF_CLASS_MAP[class_uid]}"
    class_name = event.get("class_name", "unknown")
    return f"openshell.{class_name.lower().replace(' ', '_')}"


def extract_agent_id(event):
    metadata = event.get("metadata", {})
    uid = metadata.get("uid", "")
    if uid:
        return uid
    container = event.get("container", {})
    return container.get("uid", "unknown-sandbox")


def extract_correlation_id(event):
    unmapped = event.get("unmapped", {})
    for key in ("request_id", "trace_id", "traceparent", "correlation_id"):
        val = unmapped.get(key, "")
        if val:
            return val
    return ""


def process_line(client, line, stats):
    line = line.strip()
    if not line:
        return

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        stats["parse_errors"] += 1
        return

    if "class_uid" not in event and "class_name" not in event:
        stats["skipped"] += 1
        return

    entry_type = extract_entry_type(event)
    agent_id = extract_agent_id(event)
    correlation_id = extract_correlation_id(event)

    try:
        resp = client.write(
            entry_type=entry_type,
            agent_id=agent_id,
            content=line,
            content_type="application/ocsf+json",
            source_id="openshell-supervisor",
            correlation_id=correlation_id,
        )
        stats["written"] += 1
        action = event.get("action", event.get("activity_name", ""))
        severity = event.get("severity", "")
        print(f"  [{resp.chain_position:>3}] {entry_type:<35} {action:<12} {severity}")
    except Exception as e:
        stats["write_errors"] += 1
        print(f"  ERROR writing {entry_type}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Bridge OpenShell OCSF events to the immutable ledger")
    parser.add_argument("--file", "-f", help="Read from file instead of stdin")
    parser.add_argument("--endpoint", default="localhost:19092", help="Ledger gRPC endpoint")
    parser.add_argument("--follow", action="store_true", help="Follow file for new lines (like tail -f)")
    args = parser.parse_args()

    client = LedgerClient(args.endpoint)
    stats = {"written": 0, "parse_errors": 0, "write_errors": 0, "skipped": 0}

    print(f"\n  OCSF-to-Ledger Adapter (OpenShell)")
    print(f"  Ledger: {args.endpoint}")
    print(f"  Source: {'stdin' if not args.file else args.file}\n")

    try:
        if args.file:
            with open(args.file) as f:
                for line in f:
                    process_line(client, line, stats)
        else:
            for line in sys.stdin:
                process_line(client, line, stats)
    except KeyboardInterrupt:
        pass

    print(f"\n  Written: {stats['written']}  Errors: {stats['write_errors']}  "
          f"Parse errors: {stats['parse_errors']}  Skipped: {stats['skipped']}\n")

    client.close()


if __name__ == "__main__":
    main()
