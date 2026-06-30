# OTEL-to-Ledger Adapter (Kagenti)

Bridges OpenTelemetry trace spans to the immutable ledger. Works with Kagenti's OTEL Collector or any system that exports OTLP JSON.

## Usage

```bash
# From Kagenti OTEL Collector logs
kubectl logs -n kagenti-system deploy/otel-collector -f | python otel_to_ledger.py

# From an OTLP JSON export file
python otel_to_ledger.py --file exported-spans.json

# Custom ledger endpoint
python otel_to_ledger.py --endpoint ledger.internal:19092
```

## Supported Span Formats

- **OTLP JSON** (`resourceSpans` → `scopeSpans` → `spans`) — standard OTEL export
- **Flat span JSON** (single span object per line) — debug/log output

## Field Mapping

| OTEL Field | Ledger Field | Example |
|---|---|---|
| `name` | `entry_type` | `kagenti.tool.call` |
| `resource.attributes.service.name` | `agent_id` | `model-promotion-agent` |
| `traceId` | `correlation_id` | `4bf92f3577b34da6a3ce929d0e0e4736` |
| Full span JSON | `content` | Raw bytes |
| (constant) | `content_type` | `application/otlp+json` |
| (constant) | `source_id` | `kagenti-otel-collector` |

## Production Path

For production, this adapter would become a custom OTEL Collector exporter plugin (Go), directly calling the ledger gRPC service from within the collector pipeline.
