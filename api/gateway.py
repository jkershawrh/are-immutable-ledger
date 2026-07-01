"""REST API gateway — wraps the ledger gRPC service for the frontend."""

import json
import os
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from ledger_client import LedgerClient

app = Flask(__name__)
CORS(app)

ENDPOINT = os.environ.get("LEDGER_ENDPOINT", "localhost:19292")


def get_client():
    return LedgerClient(ENDPOINT)


def entry_to_dict(e):
    try:
        content_parsed = json.loads(e.content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        content_parsed = None
    return {
        "entry_id": e.entry_id,
        "entry_type": e.entry_type,
        "agent_id": e.agent_id,
        "content_raw": e.content.decode("utf-8", errors="replace"),
        "content": content_parsed,
        "content_type": e.content_type,
        "source_id": e.source_id,
        "correlation_id": e.correlation_id,
        "entry_hash": e.entry_hash,
        "previous_hash": e.previous_hash,
        "chain_position": e.chain_position,
        "written_ts": e.written_ts,
    }


@app.route("/api/entries")
def get_entries():
    c = get_client()
    kwargs = {}
    for key in ("agent_id", "entry_type", "source_id", "correlation_id"):
        val = request.args.get(key, "")
        if val:
            kwargs[key] = val
    entries = c.query(**kwargs)
    c.close()
    return jsonify([entry_to_dict(e) for e in sorted(entries, key=lambda x: x.written_ts)])


@app.route("/api/summary")
def get_summary():
    c = get_client()
    entries = c.query()
    by_source = {}
    by_type = {}
    for e in entries:
        by_source.setdefault(e.source_id, []).append(e)
        by_type.setdefault(e.entry_type, []).append(e)
    corr_ids = set(e.correlation_id for e in entries if e.correlation_id)
    cross_system = 0
    for cid in corr_ids:
        sources = set(e.source_id for e in entries if e.correlation_id == cid)
        if len(sources) > 1:
            cross_system += 1
    c.close()
    return jsonify({
        "total_entries": len(entries),
        "sources": {s: len(es) for s, es in by_source.items()},
        "chain_types": len(by_type),
        "correlation_ids": len(corr_ids),
        "cross_system_correlations": cross_system,
    })


@app.route("/api/chains")
def get_chains():
    c = get_client()
    entries = c.query()
    by_type = {}
    for e in entries:
        by_type.setdefault(e.entry_type, []).append(e)
    chains = []
    for entry_type, es in sorted(by_type.items()):
        source = "unknown"
        if "openshell" in entry_type:
            source = "openshell"
        elif "kagenti" in entry_type:
            source = "kagenti"
        elif "are." in entry_type:
            source = "are"
        elif "standalone" in entry_type:
            source = "standalone"
        chains.append({
            "entry_type": entry_type,
            "count": len(es),
            "source": source,
            "entries": [entry_to_dict(e) for e in sorted(es, key=lambda x: x.chain_position)],
        })
    c.close()
    return jsonify(chains)


@app.route("/api/verify")
def verify_all():
    c = get_client()
    entries = c.query()
    types = sorted(set(e.entry_type for e in entries))
    results = []
    for t in types:
        v = c.verify_chain(t)
        results.append({
            "entry_type": t,
            "chain_valid": v.chain_valid,
            "entries_checked": v.entries_checked,
            "failure_reason": v.failure_reason or "",
            "first_invalid_entry_id": v.first_invalid_entry_id or "",
        })
    c.close()
    all_valid = all(r["chain_valid"] for r in results)
    return jsonify({"all_valid": all_valid, "chains": results})


@app.route("/api/verify/<path:entry_type>")
def verify_chain(entry_type):
    c = get_client()
    v = c.verify_chain(entry_type)
    c.close()
    return jsonify({
        "entry_type": entry_type,
        "chain_valid": v.chain_valid,
        "entries_checked": v.entries_checked,
        "failure_reason": v.failure_reason or "",
    })


@app.route("/api/timeline")
def get_timeline():
    c = get_client()
    entries = c.query()
    sorted_entries = sorted(entries, key=lambda e: e.written_ts)
    corr_map = {}
    for e in sorted_entries:
        if e.correlation_id:
            corr_map.setdefault(e.correlation_id, []).append(e.entry_id)
    cross_links = {cid: ids for cid, ids in corr_map.items() if len(set(
        next((e2.source_id for e2 in entries if e2.entry_id == eid), "") for eid in ids
    )) > 0}
    c.close()
    return jsonify({
        "entries": [entry_to_dict(e) for e in sorted_entries],
        "correlations": {cid: ids for cid, ids in corr_map.items() if len(ids) > 1},
    })


@app.route("/api/drift")
def get_drift():
    c = get_client()
    entries = c.query()
    denials = [e for e in entries if
               b"Denied" in e.content or b"Blocked" in e.content or
               "deny" in e.entry_type]
    scope_evals = [e for e in entries if "scope" in e.entry_type and "evaluated" in e.entry_type]
    gaps = []
    for d in denials:
        if not d.correlation_id:
            continue
        matching = [s for s in scope_evals if s.correlation_id == d.correlation_id]
        if not matching:
            try:
                content = json.loads(d.content.decode("utf-8"))
                detail = content.get("message", content.get("dst", "denied request"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = "denied request"
            gaps.append({
                "entry_id": d.entry_id,
                "correlation_id": d.correlation_id,
                "agent_id": d.agent_id,
                "source_id": d.source_id,
                "entry_type": d.entry_type,
                "detail": str(detail),
            })
    c.close()
    return jsonify({
        "gaps": gaps,
        "total_denials": len(denials),
        "total_scope_evals": len(scope_evals),
    })


if __name__ == "__main__":
    port = int(os.environ.get("GATEWAY_PORT", "18099"))
    app.run(host="0.0.0.0", port=port, debug=True)
