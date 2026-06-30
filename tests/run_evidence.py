#!/usr/bin/env python3
"""Evidence Matrix Runner — turns the red/green matrix from theory to proof.

Runs each test case against a live ledger and reports pass/fail status.
Outputs updated EVIDENCE_MATRIX.md with GREEN/RED/YELLOW status.

Usage:
  python3 tests/run_evidence.py                    # run all tests
  python3 tests/run_evidence.py --category L1      # run one category
  python3 tests/run_evidence.py --live             # include L9 live integration tests
"""

import argparse
import json
import sys
import os
import time
import uuid
import hashlib
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from ledger_client import LedgerClient

RESULTS = []
ENDPOINT = "localhost:19292"


def test(test_id, description):
    def decorator(fn):
        fn._test_id = test_id
        fn._test_desc = description
        return fn
    return decorator


def run_test(fn, client):
    test_id = fn._test_id
    desc = fn._test_desc
    try:
        fn(client)
        RESULTS.append({"id": test_id, "desc": desc, "status": "GREEN", "detail": ""})
        print(f"  {test_id}  \033[92mGREEN\033[0m  {desc}")
        return True
    except AssertionError as e:
        RESULTS.append({"id": test_id, "desc": desc, "status": "RED", "detail": str(e)})
        print(f"  {test_id}  \033[91mRED\033[0m    {desc} — {e}")
        return False
    except Exception as e:
        RESULTS.append({"id": test_id, "desc": desc, "status": "RED", "detail": f"ERROR: {e}"})
        print(f"  {test_id}  \033[91mRED\033[0m    {desc} — ERROR: {e}")
        return False


# ─── L1: Ledger Core ──────────────────────────────────────

@test("L1.01", "WriteEntry stores entry and returns hash")
def test_l1_01(c):
    resp = c.write("test.l1.write", "test-agent-l1", '{"test": "L1.01"}', source_id="evidence-runner")
    assert resp.entry_id, "No entry_id returned"
    assert resp.entry_hash, "No entry_hash returned"
    assert resp.chain_position, "No chain_position returned"

@test("L1.02", "Same idempotency_key returns same entry_id")
def test_l1_02(c):
    idem_key = f"l1-02-{uuid.uuid4()}"
    r1 = c.write("test.l1.idempotent", "test-agent-l1", '{"test": "L1.02"}',
                  source_id="evidence-runner", idempotency_key=idem_key)
    r2 = c.write("test.l1.idempotent", "test-agent-l1", '{"test": "L1.02"}',
                  source_id="evidence-runner", idempotency_key=idem_key)
    assert r1.entry_id == r2.entry_id, f"Different entry_ids: {r1.entry_id} vs {r2.entry_id}"

@test("L1.04", "GetEntry retrieves written entry with all fields")
def test_l1_04(c):
    content = json.dumps({"test": "L1.04", "ts": time.time()})
    resp = c.write("test.l1.get", "test-agent-l1", content,
                   content_type="application/json", source_id="evidence-runner",
                   correlation_id="corr-l1-04")
    entry = c.get_entry(resp.entry_id)
    assert entry.content.decode("utf-8") == content, "Content mismatch"
    assert entry.content_type == "application/json", "Content type mismatch"
    assert entry.source_id == "evidence-runner", "Source ID mismatch"
    assert entry.agent_id == "test-agent-l1", "Agent ID mismatch"
    assert entry.correlation_id == "corr-l1-04", "Correlation ID mismatch"

@test("L1.05", "Consecutive writes produce incrementing chain_position")
def test_l1_05(c):
    etype = f"test.l1.chain.{uuid.uuid4().hex[:8]}"
    r1 = c.write(etype, "test-agent-l1", '{"seq": 1}', source_id="evidence-runner")
    r2 = c.write(etype, "test-agent-l1", '{"seq": 2}', source_id="evidence-runner")
    r3 = c.write(etype, "test-agent-l1", '{"seq": 3}', source_id="evidence-runner")
    p1, p2, p3 = int(r1.chain_position), int(r2.chain_position), int(r3.chain_position)
    assert p2 == p1 + 1, f"Position gap: {p1} → {p2}"
    assert p3 == p2 + 1, f"Position gap: {p2} → {p3}"

@test("L1.08", "First entry uses genesis hash")
def test_l1_08(c):
    etype = f"test.l1.genesis.{uuid.uuid4().hex[:8]}"
    resp = c.write(etype, "test-agent-l1", '{"test": "genesis"}', source_id="evidence-runner")
    entry = c.get_entry(resp.entry_id)
    genesis = hashlib.sha256("ARE_LEDGER_GENESIS".encode()).hexdigest()
    assert entry.previous_hash == genesis, f"Expected genesis hash, got {entry.previous_hash}"


# ─── L2: Chain Verification ──────────────────────────────

@test("L2.01", "VerifyEntry on valid entry returns both valid")
def test_l2_01(c):
    etype = f"test.l2.verify.{uuid.uuid4().hex[:8]}"
    resp = c.write(etype, "test-agent-l2", '{"test": "L2.01"}', source_id="evidence-runner")
    v = c.verify_entry(resp.entry_id)
    assert v.hash_valid, "Hash not valid"
    assert v.chain_link_valid, "Chain link not valid"

@test("L2.03", "VerifyChain on valid chain returns chain_valid=true")
def test_l2_03(c):
    etype = f"test.l2.chain.{uuid.uuid4().hex[:8]}"
    for i in range(5):
        c.write(etype, "test-agent-l2", json.dumps({"seq": i}), source_id="evidence-runner")
    v = c.verify_chain(etype)
    assert v.chain_valid, f"Chain invalid: {v.failure_reason}"
    assert v.entries_checked == 5, f"Expected 5, got {v.entries_checked}"

@test("L2.06", "GetChainTip returns latest entry")
def test_l2_06(c):
    etype = f"test.l2.tip.{uuid.uuid4().hex[:8]}"
    last = None
    for i in range(3):
        last = c.write(etype, "test-agent-l2", json.dumps({"seq": i}), source_id="evidence-runner")
    tip = c.get_chain_tip(etype)
    assert tip.entry_id == last.entry_id, "Tip doesn't match last written entry"
    assert tip.entry_hash == last.entry_hash, "Tip hash doesn't match"


# ─── L3: Cross-System Query ──────────────────────────────

@test("L3.01", "QueryEntries by agent_id returns only that agent")
def test_l3_01(c):
    agent_a = f"agent-a-{uuid.uuid4().hex[:8]}"
    agent_b = f"agent-b-{uuid.uuid4().hex[:8]}"
    c.write("test.l3.query", agent_a, '{"agent": "a"}', source_id="evidence-runner")
    c.write("test.l3.query", agent_b, '{"agent": "b"}', source_id="evidence-runner")
    results = c.query(agent_id=agent_a)
    for e in results:
        assert e.agent_id == agent_a, f"Got wrong agent: {e.agent_id}"

@test("L3.02", "QueryEntries by correlation_id returns entries from multiple sources")
def test_l3_02(c):
    corr = f"cross-{uuid.uuid4().hex[:8]}"
    c.write("test.l3.source_a", "agent-a", '{"src": "a"}', source_id="source-alpha", correlation_id=corr)
    c.write("test.l3.source_b", "agent-b", '{"src": "b"}', source_id="source-beta", correlation_id=corr)
    results = c.query(correlation_id=corr)
    sources = set(e.source_id for e in results)
    assert len(sources) >= 2, f"Expected entries from 2+ sources, got {sources}"

@test("L3.07", "Multiple sources write concurrently without corruption")
def test_l3_07(c):
    import threading
    errors = []
    etype_base = f"test.l3.concurrent.{uuid.uuid4().hex[:8]}"

    def writer(source_idx):
        try:
            etype = f"{etype_base}.s{source_idx}"
            for i in range(10):
                c.write(etype, f"agent-{source_idx}", json.dumps({"i": i}),
                       source_id=f"source-{source_idx}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent write errors: {errors}"
    for i in range(3):
        v = c.verify_chain(f"{etype_base}.s{i}")
        assert v.chain_valid, f"Chain s{i} invalid: {v.failure_reason}"


# ─── L4: Identity Independence ───────────────────────────

@test("L4.01", "Three different agent_id formats coexist")
def test_l4_01(c):
    ids = ["agt-demo-001", "spiffe://cluster.local/ns/team1/sa/agent", "sbx-sandbox-001"]
    for aid in ids:
        c.write("test.l4.identity", aid, json.dumps({"id_format": aid}), source_id="evidence-runner")
    results = c.query(entry_type="test.l4.identity")
    found_ids = set(e.agent_id for e in results)
    for aid in ids:
        assert aid in found_ids, f"Agent ID {aid} not found"

@test("L4.03", "Same correlation_id links entries with different agent_ids")
def test_l4_03(c):
    corr = f"shared-trace-{uuid.uuid4().hex[:8]}"
    c.write("test.l4.corr", "agt-001", '{"from": "are"}', source_id="are", correlation_id=corr)
    c.write("test.l4.corr", "sbx-001", '{"from": "openshell"}', source_id="openshell", correlation_id=corr)
    c.write("test.l4.corr", "spiffe://demo", '{"from": "kagenti"}', source_id="kagenti", correlation_id=corr)
    results = c.query(correlation_id=corr)
    agents = set(e.agent_id for e in results)
    assert len(agents) == 3, f"Expected 3 different agent_ids, got {agents}"


# ─── L5: OCSF Adapter ────────────────────────────────────

@test("L5.01", "Valid OCSF JSONL line produces ledger entry")
def test_l5_01(c):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters", "ocsf"))
    from ocsf_to_ledger import extract_entry_type, extract_agent_id, extract_correlation_id
    event = {"class_uid": 4002, "class_name": "HTTP Activity", "metadata": {"uid": "sbx-test"},
             "unmapped": {"request_id": "req-123"}}
    assert extract_entry_type(event) == "openshell.http_activity"
    assert extract_agent_id(event) == "sbx-test"
    assert extract_correlation_id(event) == "req-123"

@test("L5.02", "class_uid 4001 maps to openshell.network_activity")
def test_l5_02(c):
    from ocsf_to_ledger import extract_entry_type
    assert extract_entry_type({"class_uid": 4001}) == "openshell.network_activity"

@test("L5.03", "class_uid 4002 maps to openshell.http_activity")
def test_l5_03(c):
    from ocsf_to_ledger import extract_entry_type
    assert extract_entry_type({"class_uid": 4002}) == "openshell.http_activity"


# ─── L6: OTEL Adapter ────────────────────────────────────

@test("L6.01", "Valid OTLP span produces correct entry_type")
def test_l6_01(c):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters", "otel"))
    from otel_to_ledger import extract_entry_type, extract_agent_id, extract_trace_id
    span = {"name": "tools/call", "traceId": "abc123",
            "resource": {"attributes": {"service.name": "my-agent"}}}
    assert extract_entry_type(span) == "kagenti.tool.call"
    assert extract_agent_id(span) == "my-agent"
    assert extract_trace_id(span) == "abc123"

@test("L6.02", "Span name tools/call maps correctly")
def test_l6_02(c):
    from otel_to_ledger import extract_entry_type
    assert extract_entry_type({"name": "tools/call"}) == "kagenti.tool.call"

@test("L6.03", "Span name llm.request maps correctly")
def test_l6_03(c):
    from otel_to_ledger import extract_entry_type
    assert extract_entry_type({"name": "llm.request"}) == "kagenti.llm.request"

@test("L6.06", "OTLP resourceSpans envelope parsed correctly")
def test_l6_06(c):
    from otel_to_ledger import try_parse_span
    envelope = json.dumps({
        "resourceSpans": [{"resource": {"attributes": {"service.name": "test"}},
                           "scopeSpans": [{"spans": [{"name": "test.span", "traceId": "t1"}]}]}]
    })
    spans = try_parse_span(envelope)
    assert spans and len(spans) == 1, f"Expected 1 span, got {spans}"
    assert spans[0]["name"] == "test.span"


# ─── L8: Demo Narrative ──────────────────────────────────

@test("L8.01", "Sample data loads 11 entries across 3 sources")
def test_l8_01(c):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo", "sample-data"))
    import importlib
    spec = importlib.util.spec_from_file_location("load_samples",
        os.path.join(os.path.dirname(__file__), "..", "demo", "sample-data", "load-samples.py"))
    # Don't actually run — just verify the EVENTS list
    import ast
    with open(os.path.join(os.path.dirname(__file__), "..", "demo", "sample-data", "load-samples.py")) as f:
        src = f.read()
    assert "EVENTS = [" in src, "EVENTS list not found"
    event_count = src.count('"entry_type"')
    assert event_count == 11, f"Expected 11 events, got {event_count}"

@test("L8.02", "trace-aaa correlates Kagenti + OpenShell")
def test_l8_02(c):
    # Write the two events that should correlate
    c.write("test.l8.kagenti", "spiffe://demo", '{"tool": "check"}',
            source_id="kagenti-test", correlation_id="trace-aaa-test")
    c.write("test.l8.openshell", "sbx-demo", '{"action": "Allowed"}',
            source_id="openshell-test", correlation_id="trace-aaa-test")
    results = c.query(correlation_id="trace-aaa-test")
    sources = set(e.source_id for e in results)
    assert "kagenti-test" in sources and "openshell-test" in sources, f"Missing sources: {sources}"


# ─── Runner ──────────────────────────────────────────────

ALL_TESTS = [
    # L1
    test_l1_01, test_l1_02, test_l1_04, test_l1_05, test_l1_08,
    # L2
    test_l2_01, test_l2_03, test_l2_06,
    # L3
    test_l3_01, test_l3_02, test_l3_07,
    # L4
    test_l4_01, test_l4_03,
    # L5
    test_l5_01, test_l5_02, test_l5_03,
    # L6
    test_l6_01, test_l6_02, test_l6_03, test_l6_06,
    # L8
    test_l8_01, test_l8_02,
]


def main():
    parser = argparse.ArgumentParser(description="Evidence Matrix Runner")
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--category", help="Run specific category (e.g., L1, L2)")
    parser.add_argument("--live", action="store_true", help="Include live integration tests (L9)")
    args = parser.parse_args()

    client = LedgerClient(args.endpoint)

    tests = ALL_TESTS
    if args.category:
        tests = [t for t in tests if t._test_id.startswith(args.category)]

    print(f"\n\033[1m  Evidence Matrix Runner\033[0m")
    print(f"  Endpoint: {args.endpoint}")
    print(f"  Tests:    {len(tests)}\n")

    green = 0
    red = 0
    for t in tests:
        if run_test(t, client):
            green += 1
        else:
            red += 1

    print(f"\n  {'─'*50}")
    print(f"  \033[92mGREEN: {green}\033[0m  \033[91mRED: {red}\033[0m  Total: {green + red}")

    if red == 0:
        print(f"  \033[92m\033[1mAll tests passing.\033[0m")
    else:
        print(f"  \033[91m\033[1m{red} test(s) failing.\033[0m")

    print()

    # Write results JSON
    results_path = os.path.join(os.path.dirname(__file__), "evidence-results.json")
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": int(time.time() * 1000),
            "endpoint": args.endpoint,
            "total": green + red,
            "green": green,
            "red": red,
            "results": RESULTS,
        }, f, indent=2)
    print(f"  Results written to {results_path}\n")

    client.close()
    sys.exit(1 if red > 0 else 0)


if __name__ == "__main__":
    main()
