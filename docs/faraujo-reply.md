Great question- You're correct that payload transformation between hops is the edge case where a receipt from upstream doesn't fully subsume the downstream check.

The design handles this in layers:

Adjacent hops (no transformation): This is where receipts eliminate redundancy cleanly. AuthBridge checks the payload → issues receipt → MCP Gateway receives the same payload → verifies receipt → skips re-check. The receipt content includes a hash of what was checked, so the verifier can confirm it's looking at the same data.

Transforming hops: When a hop modifies the payload (redaction, enrichment, schema transformation), the upstream receipt proves the pre-transform check. The downstream service has two choices:

1. Trust the transform + receipt together — if the transformation is known to be safe (e.g., field redaction can only remove PII, not add it), the downstream accepts "PII scan clean before redaction" as sufficient.

2. Re-check and issue a new receipt — if the transformation could invalidate the upstream check (e.g., enrichment adds new content that wasn't scanned), the downstream runs its own check and issues its own receipt. Now the ledger has both: "AuthBridge checked the original, Gateway checked after transform" — the full chain of what was verified at each stage.

The ledger doesn't decide which path to take — that's policy. But it records both receipts with the same correlation ID, so an auditor can see: this payload was checked before and after transformation, by different enforcement points, and both proofs are independently verifiable.

The gap this reveals is that the current receipt doesn't carry a content hash of *what* was checked — it proves a check ran, but not what the input was. Adding an optional `input_hash` field to the receipt would let a verifier confirm "this receipt covers the exact payload I'm looking at." That's a concrete improvement we could add.

Short answer: adjacent hops = receipts skip redundant checks. Transforming hops = each stage proves its own check, the ledger chains both. The correlation ID links the full story.
