Hey all — Kersh here. Thanks for the add. I've been circling around agentic governance for awhile. I have been talking about the immutable ledger concept with a few of you and how it might fit the guardrail placement problem.

**The problem it addresses:** The taxonomy doc (Hai, Evaline, Morgan) identifies guardrail duplication across enforcement points — the same PII scan runs at AuthBridge, again at the MCP Gateway, possibly again at the AI Gateway. Section 6.4 asks what component owns cross-session provenance. Section 6.2 notes "a policy is only as trustworthy as the state it reads."

**What the ledger does:** Centralized proof, decentralized enforcement. When AuthBridge runs a guardrail, it calls `IssueReceipt` — the ledger records the decision and returns a compact proof hash. That hash travels as an `X-Proof-Receipt` header. The MCP Gateway calls `VerifyProof` (0.6ms p50) — confirms the guardrail ran, who ran it, when, for which request — and skips re-running it.

Three primitives:
- `IssueReceipt` — write a decision, get a portable proof hash
- `VerifyProof` — validate a hash, get the issuer/source/correlation without re-checking
- `GetEntryByHash` — fetch full decision content when the verifier needs details

Every receipt is SHA-256 hash-chained, tamper-evident, and independently verifiable. Change the content, agent, or correlation ID after the fact and verification fails.

**What it doesn't do:** It's not a PDP, not a guardrail engine, not a replacement for OPA/Keycloak/AuthBridge. It sits after the decision — proving the check ran, not making the check. David's concern about recursive PDPs doesn't apply — this is the audit + coordination layer, not another enforcement point.

**Running code:** https://github.com/jkershawrh/are-immutable-ledger
146 automated tests (security, adversarial, red team). Live integration tested with OpenShell OCSF events and Kagenti OTEL traces. There's a visual walkthrough at the repo if anyone wants to see the multi-hop receipt flow animated step by step.

Happy to demo, pair, or just answer questions. Mostly here to learn what the actual integration points would look like from your side.
