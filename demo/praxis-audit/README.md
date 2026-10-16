# Praxis audit demo: agent tool calls, provably on record

The [joint-cpex](../joint-cpex/) demo told the story with simulated receipts:
its scripts called the ledger REST API directly, standing in for a gateway
plugin that did not exist yet. This demo runs the real pipeline:

```text
HR copilot agent / curl
    │  MCP tools/call, Keycloak tokens
    ▼
Praxis gateway (:8090)            praxis-proxy 0.7.4 + PPE policy filter
    │  ├─ identity (Keycloak JWT), APL policy, CEL, session taint (Valkey),
    │  │  RFC 8693 token exchange, SSN redaction, PII scan
    │  └─ ocsf-audit sink ── stderr: one OCSF 6003 record per ruling,
    │                         hash-chained and DSSE-signed (AID-EMIT-1)
    ▼                                     │
HR MCP server (:9100)                     ▼
                         adapters/cpex/cpex_to_ledger.py
                                          │  one receipt per record
                                          ▼
                                 ARE ledger (gRPC :19292) ── PostgreSQL
```

Same realm, users and tools as joint-cpex, same story. What changed is that
every receipt now comes from a record the gateway itself wrote and signed.

## Who built what

This demo is a joint effort across three projects, and the credit splits
the same way:

- **The ARE immutable ledger and its proof layer** (this repository:
  hash-chained storage, proof receipts, the proof explorer, the demo
  compose stack) were started and are maintained by Jonathan Kershaw.
  The canonical repository is
  [jkershawrh/are-immutable-ledger](https://github.com/jkershawrh/are-immutable-ledger);
  the demo pins a commit of it, and any fork is a working copy.
- **The Praxis policy engine, its executor audit seam and the enforcement
  shown here** (identity, APL policy, CEL, session taint, token exchange,
  redaction) are the Praxis team's work at IBM, in particular Frederico
  Araujo and Teryl Taylor
  ([praxis-proxy/policy](https://github.com/praxis-proxy/policy)).
- **The `ocsf-audit` sink, the AID-EMIT-1 alignment of the CPEX adapter,
  and this demo** (gateway host, scenarios, chat walkthrough, recorder)
  were built by Jeff Leva. The adapter alignment was joint work: Jeff's
  aid.* compatibility and integration, together with the upstream
  covered-bytes, correlation and gap rules. Review from Jonathan Kershaw,
  Frederico Araujo and Teryl Taylor is invited.

The integration discussions that led here were started by Jonathan Kershaw
with the Praxis team; this directory is their outcome, not a separate
project.

## Run it

```bash
./run-demo.sh               # business story, scenarios 01-04
./run-demo.sh --deep-dive   # record fields shown, plus 05 and 06
```

No time to run it? [SAMPLE-RUN.md](SAMPLE-RUN.md) is a full `--deep-dive`
transcript.

Presenting it? [agent/CHAT.md](agent/CHAT.md) runs the same beats as a live
conversation: `agent/chat.py` is an LLM agent whose every tool call goes
through the gateway, and `tools/watch-records.sh` shows each verdict land as
a signed record in a second pane.

Needs Docker, a Rust toolchain (1.92+), `jq`, `openssl`, and Python 3.10+
with `pip install -r ../../adapters/cpex/requirements.txt`. The first run
builds the ledger image and the gateway, which takes several minutes. The
gateway runs on the host, not in Compose, so Keycloak's `localhost` issuer
matches and the restart beat can `kill -9` a real process. Praxis refuses to
run as root.

## The story, scenario by scenario

Each scenario opens with who is acting, what the policy says and what risk it
avoids, and closes with what the auditor gets.

| # | Scenario | Business framing | What the auditor gets |
|---|---|---|---|
| 01 | HR reads compensation | Bob (HR) reads a salary through the agent; the call goes out on a scoped token | Four chained, signed OCSF records (identity, token exchange, authorize, response) and a verified ledger receipt |
| 02 | Engineer denied | Alice (engineering) tries the same; `require(role.hr)` refuses | A signed deny naming the principal, the tool and the policy line (`status_code`) |
| 03 | **Prompt injection blocked** | A wiki page tells Bob's agent to email the salary record to `payroll-audit@evil.test`; the agent obeys; the gateway refuses because the session read secret data | The doc read, the salary read and the refused exfiltration as one chain, with `session_tainted_secret` inside the signed bytes; the HR system sent nothing |
| 04 | SSN redacted | Eve (HR, no `view_ssn`) asks for the SSN and gets `[REDACTED]` | Allow-after-modify with differing `aid.content` digests, and the SSN nowhere in the audit trail |
| 05 | Crash and restart *(deep dive)* | `kill -9` the gateway mid-shift | A new epoch with `stream_seq` back at 0; the adapter reports `EPOCH CHANGE`, not a gap |
| 06 | Tamper and loss *(deep dive)* | Flip one deny to allow; delete one record | The AID-EMIT-1 validator, with only the public key, flags the edit (fingerprint, signature, broken link) and the deletion (stream gap) |

Scenario 03 is the headline. The agent ([agent/agent.py](agent/agent.py))
is deliberately naive: it treats an `AGENT INSTRUCTION` comment in tool
output as a task. Two independent rules stop it
([config/policy.yaml](config/policy.yaml)): the session is tainted `secret`
once it reads compensation, and email may only go to `@corp.com`. The taint
rule fires first; the domain rule catches the same email from a clean session.

## What is in this directory

| Path | What it is |
|---|---|
| `gateway/` | The Praxis host: stock `praxis-proxy` 0.7.4 plus host-registered `audit/ocsf` and `validator/pii-scan` factories, and `mcp_classify` |
| `config/praxis.yaml` | Listener, filter chain, upstream |
| `config/policy.yaml` | The PPE policy (adapted from the praxis-demos HR policy) with the `ocsf-audit` sink |
| `hr-mcp-server/` | joint-cpex's HR MCP server plus `fetch_doc` (the injected page) and `GET /sent` |
| `keycloak/` | joint-cpex's `cpex-demo` realm (bob, alice, eve, charlie) |
| `agent/agent.py` | The scripted agent for scenario 03 |
| `agent/chat.py` | The live LLM agent for presenting (vendored from praxis-proxy/demos), with [CHAT.md](agent/CHAT.md) |
| `scenarios/` | 01-06 and their shared helpers |
| `tools/` | Gateway start/stop, ledger receipt lookup, pinned validator fetch, live record watcher |

`out/` (records, logs) and `keys/` (the generated signing key) are
git-ignored.

## Querying the records

The records are plain OCSF, so any SIEM or `jq` reads them:

```bash
# every denial, with who, what and why
grep '^{' out/gateway.stderr | jq -c 'select(.action=="Denied")
  | {who: .actor.user.uid, roles: .actor.roles, tool: .tool.name, why: .status_code}'

# every ruling that changed a payload
grep '^{' out/gateway.stderr | jq -c 'select(.unmapped."aid.content".input_hash
  != .unmapped."aid.content".output_hash) | {tool: .tool.name, steps: .unmapped."aid.decision".steps}'
```

## Known issues and upstream asks

Found while wiring the merged sink into a real Praxis host. Each is worked
around here; the first needs an upstream fix.

1. **The sink could not load beside any route.** Under `dispatch: policy`
   (the default) the APL visitor rejected a hookless audit sink as "no step
   names `ocsf-audit`, so it can never run", and naming it in `run()` denied
   every request. Fixed in
   [Levaj2000/policy#2](https://github.com/Levaj2000/policy/pull/2), which
   `gateway/Cargo.toml` pins until it lands in praxis-proxy/policy.
2. **No keyed content digests through Praxis.** Praxis 0.7.4 registers no
   secret provider backends with the engine it builds, so
   `content_provenance_key` cannot name a secret. The demo uses `unkeyed`
   (plain SHA-256), which the engine warns about at every load.
3. **`read_subject` alone gives an empty actor.** The plugin README lists five
   capabilities; `actor.roles` and `actor.user.groups` also need
   `read_roles` and `read_teams`.
4. **The MCP classifier is a stand-in.** Praxis's policy filter needs
   `mcp.method` from the `mcp` filter in praxis-proxy/ai, which is not
   published. `gateway/src/mcp_classify.rs` sets the two keys and nothing
   else.
5. **Sample output is v0.5 behavior.** Argument rendering, per-sink streams
   and stream ids change when the audit serialization split lands (R5, R7,
   R24 in the requirements). The validator is pinned to AID-EMIT-1
   1.2.0-draft (`abc7bd8`), as praxis-proxy/policy cites it.

AuthBridge and multi-hop scenarios (joint-cpex 05-07) are out of scope for
this version.

## Moving it to praxis-demos

The directory is self-contained apart from the ledger it feeds:
`docker-compose.yml` builds the ledger from this repo's root and mounts its
migrations, and the scenarios call `adapters/cpex/` and `proof-explorer/`.
In praxis-demos, point those at a published ledger image and a vendored copy
of the adapter.
