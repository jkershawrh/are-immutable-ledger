#!/usr/bin/env python3
"""Load sample cross-system events into the ledger.

Tells the story of a model promotion agent:
- Governance authorizes it (passport, scope, policy)
- Kagenti deploys and orchestrates it (agent lifecycle, tool calls, LLM)
- OpenShell sandboxes it (network allow/deny, sandbox lifecycle)

Three identity systems. Three event formats. One verifiable timeline.
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdks", "python"))
from ledger_client import LedgerClient

BASE_TS = int(time.time() * 1000)


EVENTS = [
    # --- Governance authority decisions ---
    {
        "entry_type": "gov.agent.registered",
        "agent_id": "agt-demo-001",
        "source_id": "governance-service",
        "correlation_id": "session-demo-001",
        "content_type": "application/json",
        "content": {
            "agent_type": "model-promotion",
            "owner_id": "platform-team",
            "status": "ACTIVE",
        },
        "offset_ms": 100,
    },
    {
        "entry_type": "gov.passport.issued",
        "agent_id": "agt-demo-001",
        "source_id": "governance-service",
        "correlation_id": "session-demo-001",
        "content_type": "application/json",
        "content": {
            "passport_id": "ppt-demo-001",
            "passport_type": "standard",
            "scope_set": [
                {"action_class": "model.promote_to_production", "resource_pattern": "model/*"}
            ],
            "status": "ACTIVE",
            "issued_by": "platform-team",
        },
        "offset_ms": 200,
    },
    {
        "entry_type": "gov.scope.evaluated",
        "agent_id": "agt-demo-001",
        "source_id": "governance-service",
        "correlation_id": "session-demo-001",
        "content_type": "application/json",
        "content": {
            "action_class": "model.promote_to_production",
            "resource": "model/champion-v3",
            "effect": "ALLOW",
            "reason": "scope matched requested passport",
            "executed": False,
        },
        "offset_ms": 1100,
    },

    # --- Kagenti orchestration traces ---
    {
        "entry_type": "kagenti.agent.deployed",
        "agent_id": "spiffe://cluster.local/ns/team1/sa/model-promotion-agent",
        "source_id": "kagenti-otel-collector",
        "correlation_id": "session-demo-001",
        "content_type": "application/otlp+json",
        "content": {
            "span_name": "agent.deploy",
            "service.name": "model-promotion-agent",
            "k8s.deployment.name": "model-promotion-agent",
            "k8s.namespace.name": "team1",
            "container.image.name": "model-promotion-agent:v3",
        },
        "offset_ms": 500,
    },
    {
        "entry_type": "kagenti.tool.call",
        "agent_id": "spiffe://cluster.local/ns/team1/sa/model-promotion-agent",
        "source_id": "kagenti-otel-collector",
        "correlation_id": "trace-aaa",
        "content_type": "application/otlp+json",
        "content": {
            "span_name": "tools/call",
            "tool.name": "check-model-status",
            "tool.mcp_server": "model-registry",
            "traceId": "trace-aaa",
        },
        "offset_ms": 1200,
    },
    {
        "entry_type": "kagenti.tool.call",
        "agent_id": "spiffe://cluster.local/ns/team1/sa/model-promotion-agent",
        "source_id": "kagenti-otel-collector",
        "correlation_id": "trace-bbb",
        "content_type": "application/otlp+json",
        "content": {
            "span_name": "tools/call",
            "tool.name": "promote-model",
            "tool.mcp_server": "deployment-service",
            "traceId": "trace-bbb",
        },
        "offset_ms": 2100,
    },
    {
        "entry_type": "kagenti.llm.request",
        "agent_id": "spiffe://cluster.local/ns/team1/sa/model-promotion-agent",
        "source_id": "kagenti-otel-collector",
        "correlation_id": "trace-ccc",
        "content_type": "application/otlp+json",
        "content": {
            "span_name": "llm.request",
            "gen_ai.system": "openai",
            "gen_ai.request.model": "gpt-4",
            "gen_ai.usage.prompt_tokens": 1250,
            "gen_ai.usage.completion_tokens": 340,
            "traceId": "trace-ccc",
        },
        "offset_ms": 2300,
    },

    # --- OpenShell sandbox events ---
    {
        "entry_type": "openshell.sandbox.created",
        "agent_id": "sbx-demo-001",
        "source_id": "openshell-supervisor",
        "correlation_id": "session-demo-001",
        "content_type": "application/ocsf+json",
        "content": {
            "class_uid": 6002, "class_name": "Application Lifecycle",
            "activity_id": 1, "activity_name": "Start",
            "severity_id": 1, "severity": "Informational",
            "message": "Sandbox created with policy github-readonly",
            "metadata": {"uid": "sbx-demo-001", "product": {"name": "OpenShell Sandbox Supervisor"}},
            "container": {"name": "demo-sandbox", "uid": "sbx-demo-001"},
        },
        "offset_ms": 800,
    },
    {
        "entry_type": "openshell.http_activity",
        "agent_id": "sbx-demo-001",
        "source_id": "openshell-supervisor",
        "correlation_id": "trace-aaa",
        "content_type": "application/ocsf+json",
        "content": {
            "class_uid": 4002, "class_name": "HTTP Activity",
            "activity_id": 3, "activity_name": "Get",
            "severity_id": 1, "severity": "Informational",
            "action_id": 1, "action": "Allowed",
            "disposition_id": 1, "disposition": "Allowed",
            "http_request": {"http_method": "GET", "url": {"hostname": "api.github.com", "path": "/repos/org/model-champion-v3"}},
            "dst_endpoint": {"domain": "api.github.com", "port": 443},
            "metadata": {"uid": "sbx-demo-001"},
        },
        "offset_ms": 1205,
    },
    {
        "entry_type": "openshell.network_activity",
        "agent_id": "sbx-demo-001",
        "source_id": "openshell-supervisor",
        "correlation_id": "trace-bbb",
        "content_type": "application/ocsf+json",
        "content": {
            "class_uid": 4001, "class_name": "Network Activity",
            "activity_id": 5, "activity_name": "Refuse",
            "severity_id": 3, "severity": "Medium",
            "action_id": 2, "action": "Denied",
            "disposition_id": 2, "disposition": "Blocked",
            "message": "POST /repos/org/model-champion-v3/deployments not permitted by policy",
            "dst_endpoint": {"domain": "api.github.com", "port": 443},
            "metadata": {"uid": "sbx-demo-001"},
            "unmapped": {"http_method": "POST", "path": "/repos/org/model-champion-v3/deployments"},
        },
        "offset_ms": 2105,
    },
]


def main():
    client = LedgerClient("localhost:19292")

    print(f"\n{'='*60}")
    print(f"  Loading Cross-System Sample Data")
    print(f"{'='*60}\n")

    sorted_events = sorted(EVENTS, key=lambda e: e["offset_ms"])

    for event in sorted_events:
        resp = client.write(
            entry_type=event["entry_type"],
            agent_id=event["agent_id"],
            content=json.dumps(event["content"]),
            content_type=event["content_type"],
            source_id=event["source_id"],
            correlation_id=event["correlation_id"],
        )
        source = event["source_id"].split("-")[0]
        print(f"  +{event['offset_ms']:>5}ms  [{source:<12}]  {event['entry_type']:<35}  agent={event['agent_id'][:25]}")

    print(f"\n  {len(sorted_events)} entries loaded across 3 source systems.\n")

    for entry_type_prefix in ["gov.", "kagenti.", "openshell."]:
        entries = client.query(entry_type=entry_type_prefix)
        if entries:
            types = set(e.entry_type for e in entries)
            print(f"  {entry_type_prefix}* — {len(entries)} entries across {len(types)} chains")

    print()
    client.close()


if __name__ == "__main__":
    main()
