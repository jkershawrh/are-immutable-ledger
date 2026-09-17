# Praxis PPE to OCSF immutable-ledger contract

Status: **preview integration contract**

This contract defines how a Praxis Policy Engine (PPE) decision can become
portable, tamper-evident audit evidence without placing the immutable ledger in
the authorization path. It is suitable for adapter development and lab
validation. It does not claim that a released Praxis image currently includes
a native immutable-ledger audit sink.

PPE was selectively ported from CPEX, but it is a separate producer. A Praxis
deployment emits `praxis.ppe.*` entry types; a ContextForge deployment using
CPEX emits `cpex.*` entry types. Consumers must not treat those namespaces as
interchangeable or run both engines merely to duplicate the same decision.

## Responsibility boundary

```text
application -> Praxis AI -> PPE -> model or tool backend
                            |
                            +-> OCSF adapter -> immutable ledger -> proof receipt
```

- Praxis AI hosts the request path and propagates the request trace context.
- PPE evaluates policy and owns the allow, deny, or transform decision.
- The adapter serializes the completed decision as OCSF and submits it after
  the decision is made.
- The ledger stores opaque evidence and returns a proof receipt.
- OpenShift supplies workload identity, Secret handling, network policy,
  deployment, and observability boundaries.

Ledger availability must not silently change an allow into a deny or a deny
into an allow. The operator selects and tests one explicit audit delivery mode:

- **fail-closed audit:** the request is not completed unless evidence is
  accepted, for workflows whose policy requires durable evidence;
- **buffered audit:** the decision is preserved in a bounded durable outbox and
  replayed with its original idempotency key; or
- **best-effort audit:** loss is observable and alerted, and the deployment
  makes no completeness claim.

## Producer event

The adapter accepts one completed PPE decision. The required logical fields
are independent of PPE's internal Rust representation so the contract can
remain stable while upstream serialization evolves.

| Field | Requirement |
| --- | --- |
| `schema_version` | Exactly `praxis.ppe.audit.v1` for this contract |
| `event_id` | Globally unique identifier for retry-safe ledger submission |
| `occurred_at` | RFC 3339 timestamp assigned by the enforcement host |
| `trace_id` | Exact request trace identifier propagated through Praxis |
| `decision` | `allow`, `deny`, or `transform` |
| `policy_id` | Stable policy identifier; not sensitive policy source |
| `policy_version` | Version or digest of the evaluated policy bundle |
| `subject_id` | Pseudonymous workload, tenant, or principal identifier |
| `resource` | Model, route, or tool identifier covered by the decision |
| `reason_code` | Stable machine-readable reason; no prompt text |
| `duration_ms` | Optional policy evaluation duration |
| `input_hash` | SHA-256 digest of the canonical decision subject |

Raw prompts, completions, bearer tokens, model-provider credentials, and
unredacted sensitive values are prohibited. If a policy transforms content,
the event records the transform identifier and digests of the covered values,
not the sensitive values themselves.

## OCSF representation

Until an upstream AI-specific OCSF profile is pinned by both producers, the
adapter uses the same OCSF `6003` / `ai_operation` convention as the CPEX audit
adapter and preserves Praxis-specific fields under `unmapped`:

```json
{
  "class_uid": 6003,
  "class_name": "AI Operation",
  "activity_name": "Policy Decision",
  "metadata": {
    "uid": "<event_id>",
    "correlation_uid": "<trace_id>",
    "version": "1.0.0"
  },
  "ai_agent": {"uid": "<subject_id>"},
  "unmapped": {
    "praxis.ppe.schema_version": "praxis.ppe.audit.v1",
    "praxis.ppe.decision": "allow",
    "praxis.ppe.policy_id": "model-access",
    "praxis.ppe.policy_version": "sha256:<digest>",
    "praxis.ppe.resource": "model/example",
    "praxis.ppe.reason_code": "policy_allow",
    "praxis.ppe.input_hash": "<sha256>"
  }
}
```

The adapter rejects unknown schema versions and missing required fields. An
OCSF mapping change requires a new fixture and a contract-version decision.

## Ledger mapping

| OCSF/PPE value | Ledger field |
| --- | --- |
| `unmapped."praxis.ppe.decision"` | `entry_type`: `praxis.ppe.policy.<decision>.v1` |
| `ai_agent.uid` | `agent_id` |
| canonical OCSF document | `content` with `content_type: application/json` |
| `metadata.correlation_uid` | `correlation_id` |
| `metadata.uid` | `idempotency_key` |
| stable Praxis/PPE deployment identity | `source_id` |
| `unmapped."praxis.ppe.input_hash"` | `input_hash` |

The exact `trace_id` used by the Praxis lab UI and gateway evidence view is the
ledger `correlation_id`. It must not be replaced with a "latest trace" lookup.

## Receipt handling

The returned proof receipt establishes only that the ledger accepted and can
verify the recorded bytes. It does not make the decision correct, authenticate
the subject, grant access, or establish regulatory compliance.

The adapter or evidence collector records `entry_hash`, `entry_type`,
`hash_version`, `entry_id`, `written_ts`, and `input_hash`. It must not inject
the receipt back into the current request as an authorization credential.
Cross-hop guardrail reuse is a separate protocol requiring issuer signature,
freshness, policy scope, input-hash comparison, and local authorization as
defined in the fleet ecosystem contract.

## Minimum conformance tests

An implementation conforms only when automated tests prove:

1. allow and deny decisions map to separate versioned entry types;
2. retries with the same `event_id` are idempotent;
3. the exact Praxis trace ID retrieves the corresponding ledger entry;
4. secret and prompt canaries do not appear in the OCSF document or receipt;
5. a receipt verifies using both `entry_hash` and `entry_type`;
6. ledger loss follows the configured delivery mode and is observable;
7. an unknown schema version and malformed `input_hash` fail validation; and
8. the adapter never changes the PPE authorization result.

## Upstream readiness gate

The lab may call this path `live` only after a pinned Praxis/PPE build exposes
a stable serialized decision or audit-plugin interface and the target
OpenShift deployment passes the minimum conformance tests. Until then, the lab
uses a versioned fixture and labels the exercise **preview**.

