# CPEX Adapter

Bridges CPEX audit seam records (OCSF 6003/ai_operation, JSONL) to the immutable ledger. This is the "guinea pig consumer" for testing the audit seam shape from [contextforge-org/cpex#166](https://github.com/contextforge-org/cpex/pull/166) before the native Rust sink lands.

First adapter to use `writer_signature` and `signer_key_reference` fields. First adapter with stream gap detection.

## Usage

```bash
# From stdin (pipe from CPEX audit output)
cat audit-stream.jsonl | python cpex_to_ledger.py

# From file
python cpex_to_ledger.py --file /var/log/cpex-audit.jsonl

# Custom endpoint + strict gap checking (CI mode)
python cpex_to_ledger.py --endpoint localhost:19292 --strict-gaps --file audit.jsonl

# Fire-and-forget mode (WriteEntry, no receipts)
python cpex_to_ledger.py --write-only --file audit.jsonl
```

## Field Mapping

| OCSF 6003 Field | Ledger Field | Notes |
|---|---|---|
| `unmapped."cpex.decision"` / `unmapped."cpex.effect"` | `entry_type` | `cpex.decision` or `cpex.effect`; legacy `dec-*`/`eff-*` top-level stream prefixes remain accepted for replay |
| `ai_agent.uid` | `agent_id` | NOT `metadata.uid` (record ID) |
| `metadata.correlation_uid` | `correlation_id` | Conversation/run correlation; deliberately not the per-request identifier |
| `metadata.uid` | `idempotency_key` | Record ID — unique per event |
| JCS-canonicalized event | `content` | Envelope fields stripped |
| SHA-256 of canonical content | `input_hash` | |
| `unmapped.signature_b64` | `writer_signature` | Base64-decoded |
| `unmapped.signature_key_id` | `signer_key_reference` | |

## Gap Detection

The adapter validates two counters from the CPEX audit seam:

- **`stream_seq`** (per `(epoch, stream_id)`) — completeness claim. Dense within its stream and process lifetime, **opening at 0** (CPEX stamps from a zero-initialised counter); a gap means a missing record. The adapter alerts on interior gaps and on the head of every epoch — a first record above 0 means records `0..n-1` never arrived, which a tail-only check cannot see. A new epoch on the same stream is a producer restart: a boundary, never a gap.
- **`epoch`** (per `stream_id`) — boot-ordered. An older epoch arriving after a newer one on the same stream (a late replay of a dead process, or a host-supplied `plugin_settings.audit_epoch` that failed to advance — CPEX only warns) is alerted as an epoch regression.
- **`emission_seq`** (global within an epoch) — ordering claim only. Legitimately sparse for single-stream consumers. The adapter alerts on non-monotonic values (ordering violations) but not on gaps.

`stream_id` is opaque. A CPEX host that sets `plugin_settings.audit_stream_namespace` stamps it as `<namespace>:<kind>` (`gw-1:decision`, `gw-1:effect`); the namespace may itself contain `:`, so recover the kind with `rsplit(":", 1)` if you ever need it. The adapter never does — `entry_type` comes from the record's own content, and the Rev 3 joint-demo bundle (`tests/fixtures/aid_emit_1_rev3_bundle.jsonl`) is one such stream across two epochs.

Current AID-EMIT-1 records carry all four stamps under `unmapped."cpex.stream"`. Top-level stamps remain accepted only for replaying the adapter's legacy input shape.

The signed per-request join key remains at
`unmapped."cmf.request.request_id"` inside `content`. It is not overloaded into
the conversation-scoped `correlation_id`; a separately indexed ledger request
field requires its own API and storage contract.

Gap detection is **alert-and-continue** — records are still written to the ledger. Use `--strict-gaps` to exit with code 1 if any gaps are detected (CI quality gate).

## Content Canonicalization

Covered bytes follow [AID-EMIT-1 section 4](https://github.com/Levaj2000/AI-Identity/blob/main/docs/specs/aid-emit-1.md): `attestation_list[0].fingerprint`, `attestation_list[0].signatures`, `unmapped.signature_b64`, and `unmapped.signature_key_id` are stripped before JCS canonicalization (RFC 8785). An empty `unmapped` object is removed. Attestation identity, authority, chain identity, and `prev_event` remain covered. The resulting SHA-256 `input_hash` therefore reproduces the emitter fingerprint; the ledger's V3 entry hash then durably binds those canonical content bytes with ledger metadata and chain position.

## Production Path

This Python CLI adapter is for testing and offline replay. The production integration is a native Rust gRPC client inside the CPEX ocsf-audit plugin, calling the ledger directly as a sink (see `docs/cpex-integration-draft.md`).
