# Evidence Matrix — Immutable Ledger for Agentic Systems

Status: `RED` = failing/untested | `GREEN` = passing | `YELLOW` = partial

Last run: _not yet executed_

---

## L1: Ledger Core (Append-Only Guarantees)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L1.01 | WriteEntry stores entry and returns hash | entry_id, entry_hash, chain_position returned | RED | |
| L1.02 | WriteEntry with same idempotency_key returns same entry_id | No duplicate, same response | RED | |
| L1.03 | WriteEntry with same idempotency_key but different body returns error | ALREADY_EXISTS or conflict | RED | |
| L1.04 | GetEntry retrieves written entry with all fields intact | content, content_type, source_id match input | RED | |
| L1.05 | Consecutive writes to same entry_type produce incrementing chain_position | position N+1 after position N | RED | |
| L1.06 | Entry hash is deterministic (same input → same hash) | SHA-256(entry_type + agent_id + content + ...) matches | RED | |
| L1.07 | Entry hash includes previous_hash (chain linkage) | Changing previous_hash changes entry_hash | RED | |
| L1.08 | First entry in chain uses genesis hash | previous_hash = SHA-256("ARE_LEDGER_GENESIS") | RED | |
| L1.09 | Database rejects UPDATE on ledger_entries | Permission denied on UPDATE attempt | RED | |
| L1.10 | Database rejects DELETE on ledger_entries | Permission denied on DELETE attempt | RED | |
| L1.11 | Service refuses to start if UPDATE permission exists | Startup failure with clear error | RED | |

## L2: Chain Verification

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L2.01 | VerifyEntry on valid entry returns hash_valid=true, chain_link_valid=true | Both true | RED | |
| L2.02 | VerifyEntry on tampered content returns hash_valid=false | Detects content modification | RED | |
| L2.03 | VerifyChain on valid chain returns chain_valid=true | All entries verified | RED | |
| L2.04 | VerifyChain on chain with gap returns chain_valid=false | Detects missing entry | RED | |
| L2.05 | VerifyChain reports entries_checked count | Count matches chain length | RED | |
| L2.06 | GetChainTip returns latest entry for entry_type | Correct entry_id, hash, position | RED | |
| L2.07 | VerifyChain on empty chain returns appropriate response | No error, 0 entries checked | RED | |

## L3: Cross-System Query

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L3.01 | QueryEntries by agent_id returns only that agent's entries | Filter works across entry_types | RED | |
| L3.02 | QueryEntries by correlation_id returns entries from multiple sources | Cross-system join by trace ID | RED | |
| L3.03 | QueryEntries by source_id returns only that source | Source isolation | RED | |
| L3.04 | QueryEntries by entry_type prefix returns matching entries | Namespace filtering works | RED | |
| L3.05 | QueryEntries with time range filters correctly | from_ts and to_ts respected | RED | |
| L3.06 | QueryEntries pagination returns all entries across pages | next_page_token works | RED | |
| L3.07 | Multiple sources write concurrently without corruption | No chain integrity violations | RED | |

## L4: Identity Independence

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L4.01 | Three different agent_id formats coexist | agt-*, spiffe://, sbx-* all accepted | RED | |
| L4.02 | Query by one agent_id does not return others | Identity isolation | RED | |
| L4.03 | Same correlation_id links entries with different agent_ids | Cross-identity correlation works | RED | |
| L4.04 | No shared identity registry required | Each source uses its own ID format | RED | |

## L5: Adapter — OCSF (OpenShell)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L5.01 | Valid OCSF JSONL line produces ledger entry | entry_type = openshell.<class> | RED | |
| L5.02 | class_uid 4001 maps to openshell.network_activity | Correct entry_type | RED | |
| L5.03 | class_uid 4002 maps to openshell.http_activity | Correct entry_type | RED | |
| L5.04 | metadata.uid extracted as agent_id | Sandbox ID preserved | RED | |
| L5.05 | unmapped.request_id extracted as correlation_id | Trace context preserved | RED | |
| L5.06 | Raw OCSF JSON preserved as content bytes | Lossless storage | RED | |
| L5.07 | Malformed JSON line skipped without crash | Error count incremented | RED | |
| L5.08 | Non-OCSF JSON line skipped | Lines without class_uid ignored | RED | |
| L5.09 | Adapter reads from stdin (pipe mode) | openshell logs | adapter works | RED | |

## L6: Adapter — OTEL (Kagenti)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L6.01 | Valid OTLP JSON span produces ledger entry | entry_type = kagenti.<span_name> | RED | |
| L6.02 | Span name "tools/call" maps to kagenti.tool.call | Correct entry_type | RED | |
| L6.03 | Span name "llm.request" maps to kagenti.llm.request | Correct entry_type | RED | |
| L6.04 | resource.attributes.service.name extracted as agent_id | Agent identity preserved | RED | |
| L6.05 | traceId extracted as correlation_id | Trace context preserved | RED | |
| L6.06 | OTLP resourceSpans envelope parsed correctly | Nested spans extracted | RED | |
| L6.07 | Flat span JSON parsed correctly | Single-span lines work | RED | |
| L6.08 | Malformed JSON skipped without crash | Error count incremented | RED | |

## L7: Proof Explorer CLI

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L7.01 | `proof query --agent-id X` returns correct entries | Filter matches | RED | |
| L7.02 | `proof query --correlation-id X` returns cross-system entries | Multiple sources in result | RED | |
| L7.03 | `proof timeline --all` shows chronological order | Sorted by written_ts | RED | |
| L7.04 | `proof timeline --all` identifies cross-system correlations | Reports multi-source trace IDs | RED | |
| L7.05 | `proof verify --all` verifies all chains | Reports VALID for clean chains | RED | |
| L7.06 | `proof summary` shows correct counts per source | Matches actual entry counts | RED | |
| L7.07 | `proof drift` detects missing scope evaluation for denied request | Reports authorization gap | RED | |
| L7.08 | `proof drift` reports clean when no gaps exist | "No authorization gaps detected" | RED | |

## L8: Demo Narrative

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L8.01 | Sample data loads 11 entries across 3 sources | 11 entries written | RED | |
| L8.02 | trace-aaa correlates Kagenti tool.call + OpenShell http_activity | Both entries returned for trace-aaa | RED | |
| L8.03 | trace-bbb correlates Kagenti tool.call + OpenShell network_activity (DENY) | Denial visible cross-system | RED | |
| L8.04 | Drift detection finds trace-bbb authorization gap | POST denied but no scope eval | RED | |
| L8.05 | Three independent chains verify clean | are.*, openshell.*, kagenti.* all VALID | RED | |
| L8.06 | Standalone agent creates separate chain | standalone.* entries independent | RED | |

## L9: Live Integration (requires running systems)

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L9.01 | OpenShell sandbox OCSF events flow through adapter to ledger | Real OCSF events stored and verifiable | RED | |
| L9.02 | OpenShell network allow produces openshell.http_activity entry | Real allow event captured | RED | |
| L9.03 | OpenShell network deny produces openshell.network_activity entry | Real deny event captured | RED | |
| L9.04 | Kagenti OTEL collector spans flow through adapter to ledger | Real OTEL spans stored and verifiable | RED | |
| L9.05 | Live cross-system correlation works with real trace IDs | W3C traceparent or X-Request-ID joins entries | RED | |

## L10: Resilience

| ID | Test | Expected | Status | Evidence |
|---|---|---|---|---|
| L10.01 | Concurrent writes from multiple sources don't corrupt chains | Advisory locks prevent race conditions | RED | |
| L10.02 | Chain integrity violation triggers retry (up to 5 attempts) | Circuit breaker behavior documented | RED | |
| L10.03 | Large content (up to 1 MiB) accepted | Content size within limit stored | RED | |
| L10.04 | Content exceeding max size rejected | Clear error, no partial write | RED | |
| L10.05 | Ledger restart preserves all chains | Chains verify after restart | RED | |

---

## Summary

| Category | Total | Green | Yellow | Red |
|---|---|---|---|---|
| L1: Ledger Core | 11 | 0 | 0 | 11 |
| L2: Chain Verification | 7 | 0 | 0 | 7 |
| L3: Cross-System Query | 7 | 0 | 0 | 7 |
| L4: Identity Independence | 4 | 0 | 0 | 4 |
| L5: OCSF Adapter | 9 | 0 | 0 | 9 |
| L6: OTEL Adapter | 8 | 0 | 0 | 8 |
| L7: Proof Explorer | 8 | 0 | 0 | 8 |
| L8: Demo Narrative | 6 | 0 | 0 | 6 |
| L9: Live Integration | 5 | 0 | 0 | 5 |
| L10: Resilience | 5 | 0 | 0 | 5 |
| **TOTAL** | **70** | **0** | **0** | **70** |
