# CPEX → OCSF → Immutable Ledger demo

Jeff's merged [AI-Identity #499](https://github.com/Levaj2000/AI-Identity/pull/499)
runner owns evidence production and AID-EMIT-1 verification. It writes:

- `records.ndjson` — six signed OCSF records across two producer epochs
- `demo-pub.pem` — the corresponding verification key

After that runner reports `PASS`, hand its output directory to the ledger:

```bash
./demo/cpex-ocsf-ledger/run-ledger-demo.sh /path/to/runner/output
```

The wrapper starts the local ledger stack if needed, imports all six records,
checks that the two epoch-scoped sequences are gap-free, verifies the ledger's
`cpex.*` hash chains, asserts that `agent-7` and conversation
`run-4bf92f35` span all six entries, and confirms that the signed request join key
`corr-7f3e2a91` remains on exactly one retained record. Conversation-level
`metadata.correlation_uid` maps to the ledger's `correlation_id`; the
per-request key is not overloaded into that field.

The producer restart deliberately creates a new attestation `chain_uid` while
retaining the host-named stream `gw-1:decision`. Both epochs open at
`stream_seq` 0. This is valid: CPEX density is scoped to
`(epoch, stream_id)`, emitter attestation continuity is scoped to `chain_uid`,
and ledger durability is independently scoped to `entry_type`.

Open `cpex-ocsf-ledger.html` for the presenter view and six-beat script.
