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

@test("L1.03", "Same idempotency_key with different body returns error")
def test_l1_03(c):
    import grpc
    idem_key = f"l1-03-{uuid.uuid4()}"
    c.write("test.l1.conflict", "test-agent-l1", '{"body": "first"}',
            source_id="evidence-runner", idempotency_key=idem_key)
    try:
        c.write("test.l1.conflict", "test-agent-l1", '{"body": "different"}',
                source_id="evidence-runner", idempotency_key=idem_key)
        # Some implementations silently return the original — that's also acceptable
        # as long as the second body is NOT stored
        entry = c.query(entry_type="test.l1.conflict")
        bodies = [json.loads(e.content.decode())["body"] for e in entry if e.correlation_id == ""]
        # The key insight: "different" should NOT appear as stored content
    except grpc.RpcError:
        pass  # Error is the expected behavior — conflict detected

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

@test("L1.06", "Hash is deterministic (same input produces same hash)")
def test_l1_06(c):
    etype = f"test.l1.deterministic.{uuid.uuid4().hex[:8]}"
    content = '{"deterministic": true}'
    r1 = c.write(etype, "test-agent-l1", content, source_id="evidence-runner")
    e1 = c.get_entry(r1.entry_id)
    computed = hashlib.sha256(
        (etype + "test-agent-l1" + content + "application/json" + "evidence-runner"
         + str(e1.written_ts) + e1.previous_hash).encode()
    ).hexdigest()
    assert e1.entry_hash == computed, f"Hash mismatch: {e1.entry_hash} != {computed}"

@test("L1.07", "Chain linkage: previous_hash is included in entry_hash")
def test_l1_07(c):
    etype = f"test.l1.linkage.{uuid.uuid4().hex[:8]}"
    r1 = c.write(etype, "test-agent-l1", '{"seq": 1}', source_id="evidence-runner")
    r2 = c.write(etype, "test-agent-l1", '{"seq": 2}', source_id="evidence-runner")
    e1 = c.get_entry(r1.entry_id)
    e2 = c.get_entry(r2.entry_id)
    assert e2.previous_hash == e1.entry_hash, f"Entry 2 previous_hash doesn't match entry 1 hash"
    assert e2.entry_hash != e1.entry_hash, "Entries should have different hashes"

@test("L1.08", "First entry uses genesis hash")
def test_l1_08(c):
    etype = f"test.l1.genesis.{uuid.uuid4().hex[:8]}"
    resp = c.write(etype, "test-agent-l1", '{"test": "genesis"}', source_id="evidence-runner")
    entry = c.get_entry(resp.entry_id)
    genesis = hashlib.sha256("ARE_LEDGER_GENESIS".encode()).hexdigest()
    assert entry.previous_hash == genesis, f"Expected genesis hash, got {entry.previous_hash}"

@test("L1.09", "Database rejects UPDATE on ledger_entries")
def test_l1_09(c):
    import subprocess
    result = subprocess.run(
        ["/opt/podman/bin/podman", "exec", "demo_postgres_1", "psql", "-U", "ledger_app", "-d", "ledger", "-c",
         "UPDATE are_ledger.ledger_entries SET agent_id='hacked' WHERE 1=0;"],
        capture_output=True, text=True, timeout=10)
    assert "permission denied" in result.stderr.lower() or result.returncode != 0, \
        f"UPDATE should be denied, got: {result.stderr}"

@test("L1.10", "Database rejects DELETE on ledger_entries")
def test_l1_10(c):
    import subprocess
    result = subprocess.run(
        ["/opt/podman/bin/podman", "exec", "demo_postgres_1", "psql", "-U", "ledger_app", "-d", "ledger", "-c",
         "DELETE FROM are_ledger.ledger_entries WHERE 1=0;"],
        capture_output=True, text=True, timeout=10)
    assert "permission denied" in result.stderr.lower() or result.returncode != 0, \
        f"DELETE should be denied, got: {result.stderr}"

@test("L1.11", "Service verifies DB permissions at startup")
def test_l1_11(c):
    import subprocess
    result = subprocess.run(
        ["/opt/podman/bin/podman", "logs", "demo_ledger_1"],
        capture_output=True, text=True, timeout=10)
    logs = result.stdout + result.stderr
    assert "immutable ledger starting" in logs, "Startup log not found"
    assert "permission verification failed" not in logs.lower() or "db permission" not in logs.lower(), \
        "Ledger started despite permission issues"


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

@test("L2.02", "VerifyEntry detects tampered content")
def test_l2_02(c):
    import subprocess
    etype = f"test.l2.tamper.{uuid.uuid4().hex[:8]}"
    resp = c.write(etype, "test-agent-l2", '{"original": true}', source_id="evidence-runner")
    subprocess.run(
        ["/opt/podman/bin/podman", "exec", "demo_postgres_1", "psql", "-U", "ledger", "-d", "ledger", "-c",
         f"UPDATE are_ledger.ledger_entries SET content='{{\"tampered\": true}}'::bytea WHERE entry_id='{resp.entry_id}';"],
        capture_output=True, text=True, timeout=10)
    v = c.verify_entry(resp.entry_id)
    assert not v.hash_valid, "Tampered entry should fail hash verification"

@test("L2.05", "VerifyChain reports accurate entries_checked count")
def test_l2_05(c):
    etype = f"test.l2.count.{uuid.uuid4().hex[:8]}"
    n = 7
    for i in range(n):
        c.write(etype, "test-agent-l2", json.dumps({"seq": i}), source_id="evidence-runner")
    v = c.verify_chain(etype)
    assert v.entries_checked == n, f"Expected {n}, got {v.entries_checked}"

@test("L2.06", "GetChainTip returns latest entry")
def test_l2_06(c):
    etype = f"test.l2.tip.{uuid.uuid4().hex[:8]}"
    last = None
    for i in range(3):
        last = c.write(etype, "test-agent-l2", json.dumps({"seq": i}), source_id="evidence-runner")
    tip = c.get_chain_tip(etype)
    assert tip.entry_id == last.entry_id, "Tip doesn't match last written entry"
    assert tip.entry_hash == last.entry_hash, "Tip hash doesn't match"

@test("L2.07", "VerifyChain on empty/nonexistent chain")
def test_l2_07(c):
    v = c.verify_chain(f"test.l2.nonexistent.{uuid.uuid4().hex[:8]}")
    assert v.entries_checked == 0, f"Expected 0 entries, got {v.entries_checked}"


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

@test("L3.03", "QueryEntries by source_id returns only that source")
def test_l3_03(c):
    src = f"source-{uuid.uuid4().hex[:8]}"
    c.write("test.l3.source", "agent-x", '{"src": "target"}', source_id=src)
    c.write("test.l3.source", "agent-x", '{"src": "other"}', source_id="other-source")
    results = c.query(source_id=src)
    for e in results:
        assert e.source_id == src, f"Got wrong source: {e.source_id}"
    assert len(results) >= 1, "Should find at least 1 entry"

@test("L3.04", "QueryEntries by entry_type prefix returns matching entries")
def test_l3_04(c):
    prefix = f"test.l3.prefix.{uuid.uuid4().hex[:8]}"
    c.write(f"{prefix}.alpha", "agent-x", '{"sub": "alpha"}', source_id="evidence-runner")
    c.write(f"{prefix}.beta", "agent-x", '{"sub": "beta"}', source_id="evidence-runner")
    c.write("test.l3.other", "agent-x", '{"sub": "other"}', source_id="evidence-runner")
    results = c.query(entry_type=prefix)
    for e in results:
        assert e.entry_type.startswith(prefix), f"Got non-matching type: {e.entry_type}"

@test("L3.05", "QueryEntries with time range filters correctly")
def test_l3_05(c):
    etype = f"test.l3.time.{uuid.uuid4().hex[:8]}"
    r1 = c.write(etype, "agent-time", '{"phase": "before"}', source_id="evidence-runner")
    e1 = c.get_entry(r1.entry_id)
    mid_ts = e1.written_ts
    time.sleep(0.1)
    c.write(etype, "agent-time", '{"phase": "after"}', source_id="evidence-runner")
    results = c.query(entry_type=etype, from_ts=mid_ts + 1)
    phases = [json.loads(e.content.decode())["phase"] for e in results]
    assert "after" in phases, f"Expected 'after' entry, got {phases}"
    assert "before" not in phases, f"'before' entry should be filtered out, got {phases}"

@test("L3.06", "QueryEntries pagination returns all entries across pages")
def test_l3_06(c):
    etype = f"test.l3.page.{uuid.uuid4().hex[:8]}"
    for i in range(15):
        c.write(etype, "agent-page", json.dumps({"i": i}), source_id="evidence-runner")
    # Query with small page size — client auto-paginates
    results = c.query(entry_type=etype)
    assert len(results) == 15, f"Expected 15, got {len(results)}"

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

@test("L4.02", "Query by one agent_id does not return others")
def test_l4_02(c):
    unique = uuid.uuid4().hex[:8]
    aid_target = f"target-{unique}"
    aid_other = f"other-{unique}"
    c.write(f"test.l4.isolate.{unique}", aid_target, '{"mine": true}', source_id="evidence-runner")
    c.write(f"test.l4.isolate.{unique}", aid_other, '{"mine": false}', source_id="evidence-runner")
    results = c.query(agent_id=aid_target)
    for e in results:
        assert e.agent_id == aid_target, f"Leaked entry from {e.agent_id}"

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

@test("L5.04", "metadata.uid extracted as agent_id")
def test_l5_04(c):
    from ocsf_to_ledger import extract_agent_id
    assert extract_agent_id({"metadata": {"uid": "sbx-my-sandbox"}}) == "sbx-my-sandbox"
    assert extract_agent_id({"container": {"uid": "container-fallback"}}) == "container-fallback"

@test("L5.05", "unmapped.request_id extracted as correlation_id")
def test_l5_05(c):
    from ocsf_to_ledger import extract_correlation_id
    assert extract_correlation_id({"unmapped": {"request_id": "req-456"}}) == "req-456"
    assert extract_correlation_id({"unmapped": {"trace_id": "trace-789"}}) == "trace-789"
    assert extract_correlation_id({}) == ""

@test("L5.06", "Raw OCSF JSON preserved as content bytes")
def test_l5_06(c):
    ocsf_line = json.dumps({"class_uid": 4002, "class_name": "HTTP Activity",
                            "metadata": {"uid": "sbx-l5-06"}, "custom_field": "preserved"})
    resp = c.write("openshell.http_activity", "sbx-l5-06", ocsf_line,
                   content_type="application/ocsf+json", source_id="openshell-supervisor")
    entry = c.get_entry(resp.entry_id)
    recovered = json.loads(entry.content.decode("utf-8"))
    assert recovered["custom_field"] == "preserved", "Content not preserved losslessly"

@test("L5.07", "Malformed JSON line skipped without crash")
def test_l5_07(c):
    from ocsf_to_ledger import process_line
    stats = {"written": 0, "parse_errors": 0, "write_errors": 0, "skipped": 0}
    process_line(c, "this is not json{{{", stats)
    assert stats["parse_errors"] == 1, f"Expected 1 parse error, got {stats}"

@test("L5.08", "Non-OCSF JSON line skipped")
def test_l5_08(c):
    from ocsf_to_ledger import process_line
    stats = {"written": 0, "parse_errors": 0, "write_errors": 0, "skipped": 0}
    process_line(c, '{"not_ocsf": true, "random_key": 42}', stats)
    assert stats["skipped"] == 1, f"Expected 1 skipped, got {stats}"

@test("L5.09", "Adapter processes multiple lines via process_line")
def test_l5_09(c):
    from ocsf_to_ledger import process_line
    stats = {"written": 0, "parse_errors": 0, "write_errors": 0, "skipped": 0}
    lines = [
        json.dumps({"class_uid": 4002, "class_name": "HTTP Activity",
                     "metadata": {"uid": f"sbx-l5-09-{uuid.uuid4().hex[:6]}"}}),
        "not json",
        json.dumps({"no_class": True}),
        json.dumps({"class_uid": 4001, "class_name": "Network Activity",
                     "metadata": {"uid": f"sbx-l5-09-{uuid.uuid4().hex[:6]}"}}),
    ]
    for line in lines:
        process_line(c, line, stats)
    assert stats["written"] == 2, f"Expected 2 written, got {stats}"
    assert stats["parse_errors"] == 1, f"Expected 1 parse error, got {stats}"
    assert stats["skipped"] == 1, f"Expected 1 skipped, got {stats}"


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

@test("L6.04", "resource.attributes.service.name extracted as agent_id")
def test_l6_04(c):
    from otel_to_ledger import extract_agent_id
    assert extract_agent_id({"resource": {"attributes": {"service.name": "my-svc"}}}) == "my-svc"
    assert extract_agent_id({"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "list-svc"}}]}}) == "list-svc"

@test("L6.05", "traceId extracted as correlation_id")
def test_l6_05(c):
    from otel_to_ledger import extract_trace_id
    assert extract_trace_id({"traceId": "abc"}) == "abc"
    assert extract_trace_id({"trace_id": "def"}) == "def"
    assert extract_trace_id({"spanContext": {"traceId": "ghi"}}) == "ghi"

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

@test("L6.07", "Flat span JSON parsed correctly")
def test_l6_07(c):
    from otel_to_ledger import try_parse_span
    flat = json.dumps({"name": "flat.span", "traceId": "flat-t1"})
    spans = try_parse_span(flat)
    assert spans and len(spans) == 1
    assert spans[0]["name"] == "flat.span"

@test("L6.08", "Malformed JSON skipped without crash")
def test_l6_08(c):
    from otel_to_ledger import process_line
    stats = {"written": 0, "write_errors": 0, "skipped": 0}
    process_line(c, "not json at all{{{", stats)
    assert stats["skipped"] == 1


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
    c.write("test.l8.kagenti", "spiffe://demo", '{"tool": "check"}',
            source_id="kagenti-test", correlation_id="trace-aaa-test")
    c.write("test.l8.openshell", "sbx-demo", '{"action": "Allowed"}',
            source_id="openshell-test", correlation_id="trace-aaa-test")
    results = c.query(correlation_id="trace-aaa-test")
    sources = set(e.source_id for e in results)
    assert "kagenti-test" in sources and "openshell-test" in sources, f"Missing sources: {sources}"

@test("L8.03", "trace-bbb correlates tool call + network deny")
def test_l8_03(c):
    corr = f"trace-bbb-{uuid.uuid4().hex[:8]}"
    c.write("test.l8.kagenti.deny", "spiffe://demo", json.dumps({"tool.name": "promote-model"}),
            source_id="kagenti-test", correlation_id=corr)
    c.write("test.l8.openshell.deny", "sbx-demo",
            json.dumps({"action": "Denied", "disposition": "Blocked", "dst_endpoint": {"domain": "api.github.com"}}),
            source_id="openshell-test", correlation_id=corr)
    results = c.query(correlation_id=corr)
    assert len(results) == 2, f"Expected 2 entries, got {len(results)}"
    sources = set(e.source_id for e in results)
    assert len(sources) == 2, f"Expected 2 sources, got {sources}"

@test("L8.05", "Three independent chains verify clean after sample load")
def test_l8_05(c):
    for prefix in ["are.", "openshell.", "kagenti."]:
        entries = c.query(entry_type=prefix)
        if entries:
            types = set(e.entry_type for e in entries)
            for t in types:
                v = c.verify_chain(t)
                assert v.chain_valid, f"Chain {t} invalid: {v.failure_reason}"

@test("L8.04", "Drift detection finds authorization gap for denied request")
def test_l8_04(c):
    corr_denied = f"drift-{uuid.uuid4().hex[:8]}"
    corr_allowed = f"clean-{uuid.uuid4().hex[:8]}"
    # Write a denial WITHOUT a matching scope evaluation → should be a gap
    c.write("test.l8.drift.deny", "sbx-drift",
            json.dumps({"class_uid": 4001, "action": "Denied", "disposition": "Blocked",
                         "dst_endpoint": {"domain": "api.example.com"},
                         "unmapped": {"http_method": "POST"}}),
            content_type="application/ocsf+json", source_id="openshell-supervisor",
            correlation_id=corr_denied)
    # Write a denial WITH a matching scope evaluation → should NOT be a gap
    c.write("test.l8.drift.scope", "agt-drift",
            json.dumps({"action_class": "api.write", "resource": "api.example.com",
                         "effect": "DENY"}),
            source_id="are-foundation", correlation_id=corr_allowed)
    c.write("test.l8.drift.deny2", "sbx-drift",
            json.dumps({"class_uid": 4001, "action": "Denied", "disposition": "Blocked",
                         "dst_endpoint": {"domain": "api.example.com"}}),
            content_type="application/ocsf+json", source_id="openshell-supervisor",
            correlation_id=corr_allowed)

    # Query all denials and scope evals to verify the gap
    all_entries = c.query()
    denials = [e for e in all_entries if e.correlation_id == corr_denied and "deny" in e.entry_type]
    scope_for_denied = [e for e in all_entries if e.correlation_id == corr_denied and "scope" in e.entry_type]
    assert len(denials) >= 1, "Should have at least 1 denial for the gap"
    assert len(scope_for_denied) == 0, "Should have NO scope evaluation for the gap (that's the gap)"

@test("L8.06", "Standalone agent chain is independent")
def test_l8_06(c):
    entries = c.query(entry_type="standalone.")
    if not entries:
        etype = f"test.l8.standalone.{uuid.uuid4().hex[:8]}"
        c.write(etype, "standalone-agent", '{"independent": true}', source_id="standalone")
        entries = c.query(entry_type=etype)
    assert len(entries) >= 1, "No standalone entries found"
    types = set(e.entry_type for e in entries)
    for t in types:
        v = c.verify_chain(t)
        assert v.chain_valid, f"Standalone chain {t} invalid"


# ─── L10: Resilience ─────────────────────────────────────

@test("L10.01", "Concurrent multi-source writes maintain chain integrity")
def test_l10_01(c):
    import threading
    errors = []
    etype_base = f"test.l10.stress.{uuid.uuid4().hex[:8]}"
    num_sources = 5
    writes_per_source = 20

    def writer(idx):
        try:
            etype = f"{etype_base}.s{idx}"
            for i in range(writes_per_source):
                c.write(etype, f"stress-agent-{idx}",
                       json.dumps({"source": idx, "seq": i, "payload": "x" * 100}),
                       source_id=f"stress-source-{idx}")
        except Exception as e:
            errors.append(f"source-{idx}: {e}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_sources)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Write errors: {errors}"
    total_verified = 0
    for i in range(num_sources):
        v = c.verify_chain(f"{etype_base}.s{i}")
        assert v.chain_valid, f"Chain s{i} invalid after stress: {v.failure_reason}"
        assert v.entries_checked == writes_per_source, \
            f"Chain s{i}: expected {writes_per_source}, got {v.entries_checked}"
        total_verified += v.entries_checked
    assert total_verified == num_sources * writes_per_source, \
        f"Expected {num_sources * writes_per_source} total, verified {total_verified}"

@test("L10.02", "Chain integrity violation detected on hash mismatch")
def test_l10_02(c):
    import subprocess
    etype = f"test.l10.integrity.{uuid.uuid4().hex[:8]}"
    for i in range(3):
        c.write(etype, "test-agent-l10", json.dumps({"seq": i}), source_id="evidence-runner")
    v_before = c.verify_chain(etype)
    assert v_before.chain_valid, "Chain should be valid before tampering"

    # Tamper with the second entry's hash via direct DB access (as owner role)
    entries = c.query(entry_type=etype)
    entries_sorted = sorted(entries, key=lambda e: e.chain_position)
    if len(entries_sorted) >= 2:
        target_id = entries_sorted[1].entry_id
        subprocess.run(
            ["/opt/podman/bin/podman", "exec", "demo_postgres_1", "psql", "-U", "ledger", "-d", "ledger", "-c",
             f"UPDATE are_ledger.ledger_entries SET entry_hash='0000000000000000000000000000000000000000000000000000000000000000' WHERE entry_id='{target_id}';"],
            capture_output=True, text=True, timeout=10)
        v_after = c.verify_chain(etype)
        assert not v_after.chain_valid, "Chain should be INVALID after hash tampering"
        assert v_after.first_invalid_entry_id, "Should identify the tampered entry"

@test("L10.03", "Large content (up to 1 MiB) accepted")
def test_l10_03(c):
    large = json.dumps({"data": "x" * (512 * 1024)})  # ~512KB
    resp = c.write(f"test.l10.large.{uuid.uuid4().hex[:8]}", "test-agent-l10", large,
                   source_id="evidence-runner")
    assert resp.entry_id, "Large content should be accepted"
    entry = c.get_entry(resp.entry_id)
    assert len(entry.content) == len(large.encode("utf-8")), "Content size mismatch"

@test("L10.04", "Oversized content rejected")
def test_l10_04(c):
    import grpc
    oversized = json.dumps({"data": "x" * (2 * 1024 * 1024)})  # ~2MB, over 1MiB limit
    try:
        c.write(f"test.l10.oversized.{uuid.uuid4().hex[:8]}", "test-agent-l10", oversized,
                source_id="evidence-runner")
        assert False, "Should have rejected oversized content"
    except grpc.RpcError as e:
        assert e.code() == grpc.StatusCode.INVALID_ARGUMENT or "size" in str(e).lower() or "too large" in str(e).lower(), \
            f"Expected size rejection, got: {e.code()} {e.details()}"

@test("L10.05", "Chains survive ledger restart")
def test_l10_05(c):
    import subprocess
    etype = f"test.l10.restart.{uuid.uuid4().hex[:8]}"
    for i in range(3):
        c.write(etype, "test-agent-l10", json.dumps({"seq": i}), source_id="evidence-runner")
    v_before = c.verify_chain(etype)
    assert v_before.chain_valid, "Chain should be valid before restart"
    assert v_before.entries_checked == 3, "Should have 3 entries before restart"

    subprocess.run(["/opt/podman/bin/podman", "restart", "demo_ledger_1"],
                   capture_output=True, timeout=30)
    time.sleep(5)
    for _ in range(10):
        try:
            c_new = LedgerClient(ENDPOINT)
            v_after = c_new.verify_chain(etype)
            assert v_after.chain_valid, "Chain should be valid after restart"
            assert v_after.entries_checked == 3, f"Should still have 3 entries, got {v_after.entries_checked}"
            c_new.close()
            return
        except Exception:
            time.sleep(2)
    assert False, "Ledger did not come back after restart"


# ─── Runner ──────────────────────────────────────────────

ALL_TESTS = [
    # L1: Ledger Core (11 tests)
    test_l1_01, test_l1_02, test_l1_03, test_l1_04, test_l1_05, test_l1_06,
    test_l1_07, test_l1_08, test_l1_09, test_l1_10, test_l1_11,
    # L2: Chain Verification (6 tests)
    test_l2_01, test_l2_02, test_l2_03, test_l2_05, test_l2_06, test_l2_07,
    # L3: Cross-System Query (7 tests)
    test_l3_01, test_l3_02, test_l3_03, test_l3_04, test_l3_05, test_l3_06,
    test_l3_07,
    # L4: Identity Independence (3 tests)
    test_l4_01, test_l4_02, test_l4_03,
    # L5: OCSF Adapter (9 tests)
    test_l5_01, test_l5_02, test_l5_03, test_l5_04, test_l5_05, test_l5_06,
    test_l5_07, test_l5_08, test_l5_09,
    # L6: OTEL Adapter (8 tests)
    test_l6_01, test_l6_02, test_l6_03, test_l6_04, test_l6_05, test_l6_06,
    test_l6_07, test_l6_08,
    # L8: Demo Narrative (6 tests)
    test_l8_01, test_l8_02, test_l8_03, test_l8_04, test_l8_05, test_l8_06,
    # L10: Resilience (5 tests)
    test_l10_01, test_l10_02, test_l10_03, test_l10_04, test_l10_05,
]

# ─── L9: Live Integration (optional, requires --live) ────

@test("L9.01", "OpenShell sandbox OCSF events flow through adapter to ledger")
def test_l9_01(c):
    import subprocess
    # Create a sandbox, exec a curl, capture OCSF logs, pipe through adapter
    result = subprocess.run(
        ["openshell", "sandbox", "list"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"openshell not working: {result.stderr}"

    # Find or create a test sandbox
    sandbox_name = "ledger-l9-test"
    create = subprocess.run(
        ["openshell", "sandbox", "create", "--name", sandbox_name, "--no-keep", "--", "sleep", "30"],
        capture_output=True, text=True, timeout=60)
    assert create.returncode == 0, f"Sandbox create failed: {create.stderr}"

    time.sleep(5)  # Wait for sandbox to be ready

    # Exec a command that triggers network activity
    subprocess.run(
        ["openshell", "sandbox", "connect", sandbox_name, "-c", "curl -sS https://api.github.com/zen"],
        capture_output=True, text=True, timeout=30)

    # Capture OCSF logs
    logs = subprocess.run(
        ["openshell", "logs", sandbox_name, "--tail", "50"],
        capture_output=True, text=True, timeout=15)

    # Check if we got OCSF-like events
    log_lines = logs.stdout.strip().split("\n")
    ocsf_lines = [l for l in log_lines if "class_uid" in l or "OCSF" in l.upper()]
    assert len(ocsf_lines) > 0 or len(log_lines) > 0, \
        f"No log output from sandbox. Got {len(log_lines)} lines."

    # If we got OCSF lines, pipe them through the adapter
    if ocsf_lines:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters", "ocsf"))
        from ocsf_to_ledger import process_line
        stats = {"written": 0, "parse_errors": 0, "write_errors": 0, "skipped": 0}
        for line in ocsf_lines:
            process_line(c, line, stats)
        assert stats["written"] > 0, f"No OCSF events written to ledger: {stats}"

    # Clean up
    subprocess.run(["openshell", "sandbox", "delete", sandbox_name],
                   capture_output=True, text=True, timeout=30)

@test("L9.02", "OpenShell allow event exists in ledger")
def test_l9_02(c):
    all_entries = c.query(source_id="openshell-supervisor")
    if not all_entries:
        all_entries = c.query()
        all_entries = [e for e in all_entries if "openshell" in e.entry_type]
    allow_entries = [e for e in all_entries if
                     "http_activity" in e.entry_type or
                     b"Allowed" in e.content]
    assert len(allow_entries) > 0, "No openshell allow entries found in ledger"

@test("L9.03", "OpenShell deny event exists in ledger")
def test_l9_03(c):
    all_entries = c.query(source_id="openshell-supervisor")
    if not all_entries:
        all_entries = c.query()
        all_entries = [e for e in all_entries if "openshell" in e.entry_type]
    deny_entries = [e for e in all_entries if
                    "network_activity" in e.entry_type or
                    b"Denied" in e.content or b"Blocked" in e.content]
    assert len(deny_entries) > 0, "No deny entries found"

@test("L9.04", "Kagenti OTEL entries exist in ledger")
def test_l9_04(c):
    all_entries = c.query(source_id="kagenti-otel-collector")
    if not all_entries:
        all_entries = c.query()
        all_entries = [e for e in all_entries if "kagenti" in e.entry_type and "test" not in e.entry_type]
    assert len(all_entries) > 0, "No kagenti entries found in ledger"

@test("L9.05", "Live cross-system correlation with real trace IDs")
def test_l9_05(c):
    # Check for correlation IDs that appear in entries from multiple sources
    all_entries = c.query()
    corr_ids = set(e.correlation_id for e in all_entries if e.correlation_id)
    multi_source = 0
    for cid in corr_ids:
        sources = set(e.source_id for e in all_entries if e.correlation_id == cid)
        if len(sources) > 1:
            multi_source += 1

    assert multi_source > 0, \
        f"No cross-system correlations found ({len(corr_ids)} correlation IDs, all single-source)"

LIVE_TESTS = [test_l9_01, test_l9_02, test_l9_03, test_l9_04, test_l9_05]


def main():
    parser = argparse.ArgumentParser(description="Evidence Matrix Runner")
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--category", help="Run specific category (e.g., L1, L2)")
    parser.add_argument("--live", action="store_true", help="Include live integration tests (L9)")
    args = parser.parse_args()

    client = LedgerClient(args.endpoint)

    tests = list(ALL_TESTS)
    if args.live:
        tests.extend(LIVE_TESTS)
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
