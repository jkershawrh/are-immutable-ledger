Just went through the CPEX demo — the architecture is clean. The seven enforcement points (APL gate, PDP, token exchange, body rewrite, PII scan, session taint, audit log) are exactly the kind of composable pipeline where proof receipts add value.

Here's what I think the joint demo looks like:

**The integration point is `run(audit-log)`.**  CPEX already emits structured audit records as a policy step. The ledger replaces or sits alongside that step — instead of just logging, it issues a verifiable receipt.

Concrete example using your scenario 08 (session taint):

```
Bob calls get_compensation
  → CPEX: APL gate passes (role.hr) ✓
  → CPEX: PDP (Cedar) permits ✓
  → CPEX: token exchange mints audience-scoped JWT
  → CPEX: taint(secret, session) marks the session
  → NEW: IssueReceipt(type="cpex.compensation.accessed", input_hash=SHA256(request))
  → Receipt hash travels in X-Proof-Receipt header

Bob calls send_email (same session)
  → CPEX: session taint check → "secret" label present → DENY
  → NEW: IssueReceipt(type="cpex.email.denied", content={"reason":"session_tainted_secret"})
  → Both receipts queryable: receipt-chain --correlation-id <session>
  → Auditor sees: compensation accessed → session tainted → email blocked
  → Full chain hash-verified, tamper-evident
```

The key for CPEX is that `input_hash` handles the body rewrite case. When Praxis redacts `args.ssn` for Eve:

```
Pre-redaction:  input_hash = SHA256(original request with SSN)
Post-redaction: input_hash = SHA256(redacted request without SSN)
→ Downstream can tell the receipt covers a DIFFERENT payload
→ Re-checks if needed, issues its own receipt
```

**What I can bring to the demo:**
- Ledger running as a compose service (Rust, PostgreSQL, gRPC + REST)
- REST endpoint for CPEX to call: `POST /api/receipts` and `GET /api/receipts/verify`
- The receipt-chain CLI to show the full trust chain across enforcement points
- Evidence tests (we're at 146 automated tests including receipt security red team)

**What I'd need from your side:**
- A CPEX policy step or plugin that calls the ledger REST API on allow/deny decisions
- The session taint scenario wired up (your scenario 08 is the killer demo)
- Keycloak + Praxis running alongside the ledger compose

The demo narrative writes itself: "Three users, same tool, different outcomes — and every enforcement decision is hash-chained and independently verifiable. The auditor doesn't need to trust the gateway. They verify the chain."

Let me know when you'd want to start — I can have the ledger compose ready for your Praxis setup to call.
