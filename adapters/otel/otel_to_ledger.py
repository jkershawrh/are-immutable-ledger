#!/usr/bin/env python3
"""OTEL-to-Ledger adapter for Kagenti / any OpenTelemetry system.

Reads OTEL trace spans from stdin (OTEL Collector debug exporter output
or OTLP JSON export) and writes them to the immutable ledger.

Each span becomes a ledger entry with:
  entry_type:     "kagenti.<span_name>" (e.g., "kagenti.tool.call")
  agent_id:       service.name or SPIFFE ID from resource attributes
  content:        raw span JSON bytes
  content_type:   "application/otlp+json"
  source_id:      "kagenti-otel-collector"
  correlation_id: traceId from span context

Usage:
  kubectl logs -n kagenti-system deploy/otel-collector -f | python otel_to_ledger.py
  python otel_to_ledger.py --file exported-spans.json
  cat sample_spans.json | python otel_to_ledger.py
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdks", "python"))
from ledger_client import LedgerClient

SPAN_NAME_MAP = {
    "tools/call": "kagenti.tool.call",
    "tools/list": "kagenti.tool.list",
    "agent.deploy": "kagenti.agent.deployed",
    "agent.start": "kagenti.agent.started",
    "agent.stop": "kagenti.agent.stopped",
    "llm.request": "kagenti.llm.request",
    "llm.response": "kagenti.llm.response",
    "a2a.task.send": "kagenti.a2a.task.sent",
    "a2a.task.receive": "kagenti.a2a.task.received",
    "a2a.task.complete": "kagenti.a2a.task.completed",
}


def extract_entry_type(span):
    name = span.get("name", span.get("span_name", "unknown"))
    if name in SPAN_NAME_MAP:
        return SPAN_NAME_MAP[name]
    return f"kagenti.{name.lower().replace('/', '.').replace(' ', '_')}"


def extract_agent_id(span):
    resource = span.get("resource", {})
    attrs = resource.get("attributes", {})
    if isinstance(attrs, list):
        attr_dict = {a["key"]: a.get("value", {}).get("stringValue", "") for a in attrs}
    else:
        attr_dict = attrs

    for key in ("spiffe.id", "service.name", "k8s.pod.name", "agent.id"):
        val = attr_dict.get(key, "")
        if val:
            return val

    for key in ("service.name", "agent_id", "agent.id"):
        val = span.get(key, "")
        if val:
            return val

    return "unknown-agent"


def extract_trace_id(span):
    for key in ("traceId", "trace_id", "traceID"):
        val = span.get(key, "")
        if val:
            return val
    context = span.get("spanContext", span.get("context", {}))
    return context.get("traceId", context.get("trace_id", ""))


def try_parse_span(line):
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    if "resourceSpans" in obj:
        spans = []
        for rs in obj["resourceSpans"]:
            resource = rs.get("resource", {})
            for ss in rs.get("scopeSpans", []):
                for span in ss.get("spans", []):
                    span["resource"] = resource
                    spans.append(span)
        return spans

    if "name" in obj or "span_name" in obj:
        return [obj]

    return None


def process_line(client, line, stats):
    spans = try_parse_span(line)
    if not spans:
        if line.strip():
            stats["skipped"] += 1
        return

    for span in spans:
        entry_type = extract_entry_type(span)
        agent_id = extract_agent_id(span)
        trace_id = extract_trace_id(span)

        try:
            resp = client.write(
                entry_type=entry_type,
                agent_id=agent_id,
                content=json.dumps(span),
                content_type="application/otlp+json",
                source_id="kagenti-otel-collector",
                correlation_id=trace_id,
            )
            stats["written"] += 1
            name = span.get("name", span.get("span_name", ""))
            print(f"  [{resp.chain_position:>3}] {entry_type:<35} span={name:<20} trace={trace_id[:16]}")
        except Exception as e:
            stats["write_errors"] += 1
            print(f"  ERROR writing {entry_type}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Bridge OTEL spans to the immutable ledger")
    parser.add_argument("--file", "-f", help="Read from file instead of stdin")
    parser.add_argument("--endpoint", default="localhost:19092", help="Ledger gRPC endpoint")
    args = parser.parse_args()

    client = LedgerClient(args.endpoint)
    stats = {"written": 0, "write_errors": 0, "skipped": 0}

    print(f"\n  OTEL-to-Ledger Adapter (Kagenti)")
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
          f"Skipped: {stats['skipped']}\n")

    client.close()


if __name__ == "__main__":
    main()
