# OCSF-to-Ledger Adapter (OpenShell)

Bridges NVIDIA OpenShell OCSF v1.7.0 security events to the immutable ledger.

## How It Works

OpenShell's sandbox supervisor emits structured OCSF events as JSONL. This adapter reads those events and writes each one as a ledger entry, preserving the raw OCSF JSON as content.

## Usage

```bash
# From live OpenShell sandbox logs
openshell logs my-sandbox --tail | python ocsf_to_ledger.py

# From a JSONL file
python ocsf_to_ledger.py --file /var/log/openshell-ocsf.log

# Custom ledger endpoint
python ocsf_to_ledger.py --endpoint ledger.internal:19092
```

## Field Mapping

| OCSF Field | Ledger Field | Example |
|---|---|---|
| `class_uid` / `class_name` | `entry_type` | `openshell.http_activity` |
| `metadata.uid` | `agent_id` | `sbx-abc123` |
| `unmapped.request_id` | `correlation_id` | `trace-aaa` |
| Full OCSF JSON | `content` | Raw bytes |
| (constant) | `content_type` | `application/ocsf+json` |
| (constant) | `source_id` | `openshell-supervisor` |

## Production Path

For production integration, this adapter pattern would become a tracing layer inside OpenShell's `openshell-ocsf` crate, following the existing `OcsfJsonlLayer` pattern. The adapter would write directly to the ledger gRPC service instead of to a file.
