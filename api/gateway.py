"""REST API — full ledger surface for frontends, CLIs, and external integrations.

Read/audit endpoints:
  GET  /api/entries, /api/summary, /api/chains, /api/verify, /api/timeline, /api/drift

Write endpoints:
  POST /api/entries              — WriteEntry
  POST /api/receipts             — IssueReceipt (write + get proof hash)

Receipt verification:
  GET  /api/receipts/verify      — VerifyProof by hash + type
  GET  /api/entries/by-hash      — GetEntryByHash (full content by hash)
  GET  /api/receipts/chain       — trust chain for a correlation_id
"""

import json
import os
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from ledger_client import LedgerClient

app = Flask(__name__)

ENDPOINT = os.environ.get("LEDGER_ENDPOINT", "localhost:19292")
GATEWAY_API_TOKEN = os.environ.get("GATEWAY_API_TOKEN", "")
DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def cors_origins():
    configured = os.environ.get("GATEWAY_CORS_ORIGINS", "")
    if not configured:
        return DEFAULT_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


CORS(app, origins=cors_origins())


@app.before_request
def authorize_gateway_request():
    if request.method == "OPTIONS" or not GATEWAY_API_TOKEN:
        return None
    expected = f"Bearer {GATEWAY_API_TOKEN}"
    if request.headers.get("Authorization", "") != expected:
        return jsonify({"error": "unauthorized"}), 401
    return None


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
        "writer_signature": e.writer_signature.hex() if e.writer_signature else "",
        "signer_key_reference": e.signer_key_reference if hasattr(e, 'signer_key_reference') else "",
        "attestation_report": e.attestation_report.hex() if e.attestation_report else "",
    }


@app.route("/api/entries", methods=["POST"])
def write_entry():
    c = get_client()
    body = request.get_json()
    resp = c.write(
        entry_type=body.get("entry_type", ""),
        agent_id=body.get("agent_id", ""),
        content=body.get("content", ""),
        content_type=body.get("content_type", "application/json"),
        source_id=body.get("source_id", ""),
        correlation_id=body.get("correlation_id", ""),
        idempotency_key=body.get("idempotency_key", ""),
        input_hash=body.get("input_hash", ""),
    )
    c.close()
    return jsonify({
        "entry_id": resp.entry_id,
        "entry_hash": resp.entry_hash,
        "chain_position": resp.chain_position,
        "written_ts": resp.written_ts,
    }), 201


@app.route("/api/receipts", methods=["POST"])
def issue_receipt():
    c = get_client()
    body = request.get_json()
    receipt = c.issue_receipt(
        entry_type=body.get("entry_type", ""),
        agent_id=body.get("agent_id", ""),
        content=body.get("content", ""),
        content_type=body.get("content_type", "application/json"),
        source_id=body.get("source_id", ""),
        correlation_id=body.get("correlation_id", ""),
        idempotency_key=body.get("idempotency_key", ""),
        input_hash=body.get("input_hash", ""),
        writer_signature=bytes.fromhex(body["writer_signature"]) if body.get("writer_signature") else b"",
        signer_key_reference=body.get("signer_key_reference", ""),
        attestation_report=bytes.fromhex(body["attestation_report"]) if body.get("attestation_report") else b"",
    )
    c.close()
    return jsonify({
        "entry_hash": receipt.entry_hash,
        "entry_type": receipt.entry_type,
        "chain_position": receipt.chain_position,
        "written_ts": receipt.written_ts,
        "entry_id": receipt.entry_id,
        "input_hash": receipt.input_hash,
        "writer_signature": receipt.writer_signature.hex() if receipt.writer_signature else "",
        "signer_key_reference": receipt.signer_key_reference,
        "attestation_report": receipt.attestation_report.hex() if receipt.attestation_report else "",
    }), 201


@app.route("/api/receipts/verify")
def verify_proof():
    c = get_client()
    entry_hash = request.args.get("hash", "")
    entry_type = request.args.get("type", "")
    if not entry_hash or not entry_type:
        return jsonify({"error": "hash and type query params required"}), 400
    v = c.verify_proof(entry_hash, entry_type)
    c.close()
    return jsonify({
        "valid": v.valid,
        "entry_type": v.entry_type,
        "agent_id": v.agent_id,
        "source_id": v.source_id,
        "correlation_id": v.correlation_id,
        "content_type": v.content_type,
        "input_hash": v.input_hash,
        "written_ts": v.written_ts,
        "chain_position": v.chain_position,
        "failure_reason": v.failure_reason or "",
        "writer_signature": v.writer_signature.hex() if v.writer_signature else "",
        "signer_key_reference": v.signer_key_reference,
        "attestation_report": v.attestation_report.hex() if v.attestation_report else "",
    })


@app.route("/api/entries/by-hash")
def get_entry_by_hash():
    c = get_client()
    entry_hash = request.args.get("hash", "")
    entry_type = request.args.get("type", "")
    if not entry_hash or not entry_type:
        return jsonify({"error": "hash and type query params required"}), 400
    entry = c.get_entry_by_hash(entry_hash, entry_type)
    c.close()
    return jsonify(entry_to_dict(entry))


@app.route("/api/receipts/chain")
def receipt_chain():
    c = get_client()
    corr = request.args.get("correlation_id", "")
    if not corr:
        return jsonify({"error": "correlation_id query param required"}), 400
    entries = c.query(correlation_id=corr)
    c.close()
    sorted_entries = sorted(entries, key=lambda e: e.written_ts)
    return jsonify({
        "correlation_id": corr,
        "hops": len(sorted_entries),
        "sources": list(set(e.source_id for e in sorted_entries)),
        "entries": [entry_to_dict(e) for e in sorted_entries],
    })


@app.route("/api/entries", methods=["GET"])
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
        elif "gov." in entry_type:
            source = "governance"
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
    host = os.environ.get("GATEWAY_HOST", "127.0.0.1")
    debug = os.environ.get("GATEWAY_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
