#!/usr/bin/env python3
"""Standalone agent writer — proves any system can write to the ledger.

This is the simplest possible integration: one gRPC call per event,
your own agent ID, your own event format, chained and verifiable.
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from ledger_client import LedgerClient

AGENT_ID = "standalone-demo-agent"
SOURCE = "standalone-demo"
TRACE_ID = "demo-trace-standalone-001"


def main():
    client = LedgerClient("localhost:19092")

    events = [
        {
            "entry_type": "standalone.agent.started",
            "content": {"task": "model promotion check", "framework": "none", "started_at": int(time.time() * 1000)},
        },
        {
            "entry_type": "standalone.tool.call",
            "content": {"tool": "check-model-status", "model": "champion-v3", "result": "ready"},
        },
        {
            "entry_type": "standalone.decision.made",
            "content": {"decision": "promote", "model": "champion-v3", "confidence": 0.95},
        },
        {
            "entry_type": "standalone.agent.completed",
            "content": {"task": "model promotion check", "outcome": "success", "duration_ms": 4200},
        },
    ]

    print(f"\n{'='*60}")
    print(f"  Standalone Agent Writer")
    print(f"  Agent ID: {AGENT_ID}")
    print(f"  Trace:    {TRACE_ID}")
    print(f"{'='*60}\n")

    for event in events:
        resp = client.write(
            entry_type=event["entry_type"],
            agent_id=AGENT_ID,
            content=json.dumps(event["content"]),
            content_type="application/json",
            source_id=SOURCE,
            correlation_id=TRACE_ID,
        )
        print(f"  [{resp.chain_position:>3}] {event['entry_type']:<35} hash={resp.entry_hash[:16]}...")

    print(f"\n  {len(events)} entries written. Chain started.\n")

    tip = client.get_chain_tip("standalone.agent.started")
    print(f"  Chain tip for 'standalone.agent.started': position={tip.chain_position}, hash={tip.entry_hash[:16]}...")

    verification = client.verify_chain("standalone.agent.started")
    status = "VALID" if verification.chain_valid else f"INVALID: {verification.failure_reason}"
    print(f"  Chain verification: {status} ({verification.entries_checked} entries checked)")
    print()

    client.close()


if __name__ == "__main__":
    main()
