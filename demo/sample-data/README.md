# Sample Data Narrative

The sample events tell a coherent story across three independent systems.

## The Scenario

A "model-promotion-agent" needs to promote model `champion-v3` to production.

## The Timeline

| Time Offset | Source | Event | Agent ID | Detail |
|---|---|---|---|---|
| +100ms | ARE Foundation | Agent registered | `agt-demo-001` | type: model-promotion |
| +200ms | ARE Foundation | Passport issued | `agt-demo-001` | scope: model.promote:model/* |
| +500ms | Kagenti | Agent deployed | `spiffe://cluster.local/ns/team1/sa/model-promotion-agent` | image: model-agent:v3 |
| +800ms | OpenShell | Sandbox created | `sbx-demo-001` | policy: github-readonly |
| +1100ms | ARE Foundation | Scope evaluated | `agt-demo-001` | model.promote + model/champion-v3 -> ALLOW |
| +1200ms | Kagenti | Tool call | `spiffe://...` | tool: check-model-status, trace: `trace-aaa` |
| +1205ms | OpenShell | HTTP allow | `sbx-demo-001` | GET api.github.com, trace: `trace-aaa` |
| +2100ms | Kagenti | Tool call | `spiffe://...` | tool: promote-model, trace: `trace-bbb` |
| +2105ms | OpenShell | Network deny | `sbx-demo-001` | POST api.github.com BLOCKED, trace: `trace-bbb` |
| +2300ms | Kagenti | LLM request | `spiffe://...` | model: gpt-4, trace: `trace-ccc` |

## What the Demo Proves

1. **Cross-system correlation**: `trace-aaa` links a Kagenti tool call to an OpenShell network allow.
2. **Enforcement visibility**: `trace-bbb` shows Kagenti requested a write that OpenShell denied.
3. **Authorization gap**: OpenShell denied POST, but no ARE scope evaluation exists for that action — the drift detector finds this.
4. **Identity independence**: Three different agent IDs (`agt-*`, `spiffe://...`, `sbx-*`), none aware of the others.
5. **Chain integrity**: Each source's entries form an independent, verifiable hash chain.
