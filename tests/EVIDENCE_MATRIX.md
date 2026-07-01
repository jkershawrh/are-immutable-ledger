# Evidence Matrix — Immutable Ledger for Agentic Systems

Status: `RED` = failing/untested | `GREEN` = passing | `YELLOW` = partial

Last run: tests/evidence-results.json (60/60 GREEN; remaining matrix rows are not automated by the runner)

---

## L1: Ledger Core (Append-Only Guarantees)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L1.01 | WriteEntry stores entry and returns hash | entry_id, entry_hash, chain_position returned | GREEN | tests/evidence-results.json |
| L1.02 | WriteEntry with same idempotency_key returns same entry_id | No duplicate, same response | GREEN | tests/evidence-results.json |
| L1.03 | WriteEntry with same idempotency_key but different body returns error | ALREADY_EXISTS or conflict | GREEN | tests/evidence-results.json |
| L1.04 | GetEntry retrieves written entry with all fields intact | content, content_type, source_id match input | GREEN | tests/evidence-results.json |
| L1.05 | Consecutive writes to same entry_type produce incrementing chain_position | position N+1 after position N | GREEN | tests/evidence-results.json |
| L1.06 | Entry hash is deterministic for the stored entry | SHA-256 of V2 canonical envelope matches | GREEN | tests/evidence-results.json |
| L1.07 | Entry hash includes previous_hash (chain linkage) | Changing previous_hash changes entry_hash | GREEN | tests/evidence-results.json |
| L1.08 | First entry in chain uses genesis hash | previous_hash = SHA-256("ARE_LEDGER_GENESIS") | GREEN | tests/evidence-results.json |
| L1.09 | Database rejects UPDATE on ledger_entries | Permission denied on UPDATE attempt | GREEN | tests/evidence-results.json |
| L1.10 | Database rejects DELETE on ledger_entries | Permission denied on DELETE attempt | GREEN | tests/evidence-results.json |
| L1.11 | Service refuses to start if UPDATE permission exists | Startup failure with clear error | GREEN | tests/evidence-results.json |

## L2: Chain Verification

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L2.01 | VerifyEntry on valid entry returns hash_valid=true, chain_link_valid=true | Both true | GREEN | tests/evidence-results.json |
| L2.02 | VerifyEntry on tampered content returns hash_valid=false | Detects content modification | GREEN | tests/evidence-results.json |
| L2.03 | VerifyChain on valid chain returns chain_valid=true | All entries verified | GREEN | tests/evidence-results.json |
| L2.04 | VerifyChain on chain with gap returns chain_valid=false | Detects missing entry | YELLOW | not automated in run_evidence.py |
| L2.05 | VerifyChain reports entries_checked count | Count matches chain length | GREEN | tests/evidence-results.json |
| L2.06 | GetChainTip returns latest entry for entry_type | Correct entry_id, hash, position | GREEN | tests/evidence-results.json |
| L2.07 | VerifyChain on empty chain returns appropriate response | No error, 0 entries checked | GREEN | tests/evidence-results.json |

## L3: Cross-System Query

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L3.01 | QueryEntries by agent_id returns only that agent's entries | Filter works across entry_types | GREEN | tests/evidence-results.json |
| L3.02 | QueryEntries by correlation_id returns entries from multiple sources | Cross-system join by trace ID | GREEN | tests/evidence-results.json |
| L3.03 | QueryEntries by source_id returns only that source | Source isolation | GREEN | tests/evidence-results.json |
| L3.04 | QueryEntries by entry_type prefix returns matching entries | Namespace filtering works | GREEN | tests/evidence-results.json |
| L3.05 | QueryEntries with time range filters correctly | from_ts and to_ts respected | GREEN | tests/evidence-results.json |
| L3.06 | QueryEntries pagination returns all entries across pages | next_page_token works | GREEN | tests/evidence-results.json |
| L3.07 | Multiple sources write concurrently without corruption | No chain integrity violations | GREEN | tests/evidence-results.json |

## L4: Identity Independence

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L4.01 | Three different agent_id formats coexist | agt-*, spiffe://, sbx-* all accepted | GREEN | tests/evidence-results.json |
| L4.02 | Query by one agent_id does not return others | Identity isolation | GREEN | tests/evidence-results.json |
| L4.03 | Same correlation_id links entries with different agent_ids | Cross-identity correlation works | GREEN | tests/evidence-results.json |
| L4.04 | No shared identity registry required | Each source uses its own ID format | YELLOW | not automated in run_evidence.py |

## L5: Adapter — OCSF (OpenShell)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L5.01 | Valid OCSF JSONL line produces ledger entry | entry_type = openshell.<class> | GREEN | tests/evidence-results.json |
| L5.02 | class_uid 4001 maps to openshell.network_activity | Correct entry_type | GREEN | tests/evidence-results.json |
| L5.03 | class_uid 4002 maps to openshell.http_activity | Correct entry_type | GREEN | tests/evidence-results.json |
| L5.04 | metadata.uid extracted as agent_id | Sandbox ID preserved | GREEN | tests/evidence-results.json |
| L5.05 | unmapped.request_id extracted as correlation_id | Trace context preserved | GREEN | tests/evidence-results.json |
| L5.06 | Raw OCSF JSON preserved as content bytes | Lossless storage | GREEN | tests/evidence-results.json |
| L5.07 | Malformed JSON line skipped without crash | Error count incremented | GREEN | tests/evidence-results.json |
| L5.08 | Non-OCSF JSON line skipped | Lines without class_uid ignored | GREEN | tests/evidence-results.json |
| L5.09 | Adapter reads from stdin (pipe mode) | openshell logs | adapter works | GREEN | tests/evidence-results.json |

## L6: Adapter — OTEL (Kagenti)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L6.01 | Valid OTLP JSON span produces ledger entry | entry_type = kagenti.<span_name> | GREEN | tests/evidence-results.json |
| L6.02 | Span name "tools/call" maps to kagenti.tool.call | Correct entry_type | GREEN | tests/evidence-results.json |
| L6.03 | Span name "llm.request" maps to kagenti.llm.request | Correct entry_type | GREEN | tests/evidence-results.json |
| L6.04 | resource.attributes.service.name extracted as agent_id | Agent identity preserved | GREEN | tests/evidence-results.json |
| L6.05 | traceId extracted as correlation_id | Trace context preserved | GREEN | tests/evidence-results.json |
| L6.06 | OTLP resourceSpans envelope parsed correctly | Nested spans extracted | GREEN | tests/evidence-results.json |
| L6.07 | Flat span JSON parsed correctly | Single-span lines work | GREEN | tests/evidence-results.json |
| L6.08 | Malformed JSON skipped without crash | Error count incremented | GREEN | tests/evidence-results.json |

## L7: Proof Explorer CLI

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L7.01 | `proof query --agent-id X` returns correct entries | Filter matches | YELLOW | not automated in run_evidence.py |
| L7.02 | `proof query --correlation-id X` returns cross-system entries | Multiple sources in result | YELLOW | not automated in run_evidence.py |
| L7.03 | `proof timeline --all` shows chronological order | Sorted by written_ts | YELLOW | not automated in run_evidence.py |
| L7.04 | `proof timeline --all` identifies cross-system correlations | Reports multi-source trace IDs | YELLOW | not automated in run_evidence.py |
| L7.05 | `proof verify --all` verifies all chains | Reports VALID for clean chains | YELLOW | not automated in run_evidence.py |
| L7.06 | `proof summary` shows correct counts per source | Matches actual entry counts | YELLOW | not automated in run_evidence.py |
| L7.07 | `proof drift` detects missing scope evaluation for denied request | Reports authorization gap | YELLOW | not automated in run_evidence.py |
| L7.08 | `proof drift` reports clean when no gaps exist | "No authorization gaps detected" | YELLOW | not automated in run_evidence.py |

## L8: Demo Narrative

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L8.01 | Sample data loads 11 entries across 3 sources | 11 entries written | GREEN | tests/evidence-results.json |
| L8.02 | trace-aaa correlates Kagenti tool.call + OpenShell http_activity | Both entries returned for trace-aaa | GREEN | tests/evidence-results.json |
| L8.03 | trace-bbb correlates Kagenti tool.call + OpenShell network_activity (DENY) | Denial visible cross-system | GREEN | tests/evidence-results.json |
| L8.04 | Drift detection finds trace-bbb authorization gap | POST denied but no scope eval | GREEN | tests/evidence-results.json |
| L8.05 | Three independent chains verify clean | are.*, openshell.*, kagenti.* all VALID | GREEN | tests/evidence-results.json |
| L8.06 | Standalone agent creates separate chain | standalone.* entries independent | GREEN | tests/evidence-results.json |

## L9: Live Integration (requires running systems)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L9.01 | OpenShell sandbox OCSF events flow through adapter to ledger | Real OCSF events stored and verifiable | GREEN | tests/evidence-results.json |
| L9.02 | OpenShell network allow produces openshell.http_activity entry | Real allow event captured | GREEN | tests/evidence-results.json |
| L9.03 | OpenShell network deny produces openshell.network_activity entry | Real deny event captured | GREEN | tests/evidence-results.json |
| L9.04 | Kagenti OTEL collector spans flow through adapter to ledger | Real OTEL spans stored and verifiable | GREEN | tests/evidence-results.json |
| L9.05 | Live cross-system correlation works with real trace IDs | W3C traceparent or X-Request-ID joins entries | GREEN | tests/evidence-results.json |

## L10: Resilience

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L10.01 | Concurrent writes from multiple sources don't corrupt chains | Advisory locks prevent race conditions | GREEN | tests/evidence-results.json |
| L10.02 | Chain integrity violation triggers retry (up to 5 attempts) | Circuit breaker behavior documented | GREEN | tests/evidence-results.json |
| L10.03 | Large content (up to 1 MiB) accepted | Content size within limit stored | GREEN | tests/evidence-results.json |
| L10.04 | Content exceeding max size rejected | Clear error, no partial write | GREEN | tests/evidence-results.json |
| L10.05 | Ledger restart preserves all chains | Chains verify after restart | GREEN | tests/evidence-results.json |

---

## Summary

| Category | Total | Green | Yellow | Red |
|---|---|---|---|---|
| L1: Ledger Core | 11 | 11 | 0 | 0 |
| L2: Chain Verification | 7 | 6 | 1 | 0 |
| L3: Cross-System Query | 7 | 7 | 0 | 0 |
| L4: Identity Independence | 4 | 3 | 1 | 0 |
| L5: OCSF Adapter | 9 | 9 | 0 | 0 |
| L6: OTEL Adapter | 8 | 8 | 0 | 0 |
| L7: Proof Explorer | 8 | 0 | 8 | 0 |
| L8: Demo Narrative | 6 | 6 | 0 | 0 |
| L9: Live Integration | 5 | 5 | 0 | 0 |
| L10: Resilience | 5 | 5 | 0 | 0 |
| **TOTAL** | **70** | **60** | **10** | **0** |
