"""REST API - async gateway for the immutable ledger.

Proxies the REST surface to the gRPC service via the Python SDK. Requests are
handled asynchronously; the previous Flask implementation accumulated threads
under sustained write load and leaked memory, which is why it was replaced.

Read/audit endpoints:
  GET  /api/entries, /api/summary, /api/chains, /api/verify, /api/timeline, /api/drift

Write endpoints:
  POST /api/entries              - WriteEntry
  POST /api/receipts             - IssueReceipt (write + get proof hash)

Receipt verification:
  GET  /api/receipts/verify      - VerifyProof by hash + type
  GET  /api/entries/by-hash      - GetEntryByHash (full content by hash)
  GET  /api/receipts/chain       - trust chain for a correlation_id

Probes:
  GET  /healthz                  - never requires authentication
"""

import asyncio
import hmac
import json
import os
import sys
from functools import partial
from typing import Optional

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from ledger_client import LedgerClient

ENDPOINT = os.environ.get("LEDGER_ENDPOINT", "localhost:19292")
GATEWAY_API_TOKEN = os.environ.get("GATEWAY_API_TOKEN", "")
DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def cors_origins():
    configured = os.environ.get("GATEWAY_CORS_ORIGINS", "")
    if not configured:
        return DEFAULT_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="Immutable Ledger Gateway")


@app.exception_handler(RequestValidationError)
async def _query_validation_returns_400(request: Request, exc: RequestValidationError):
    """Preserve the REST contract of the gateway this replaces.

    FastAPI answers a malformed query parameter with 422. The previous
    implementation answered 400, and clients such as fleet-llm-d's ledger
    HTTP client were written against that, so changing it would be an
    unannounced API break.
    """
    return JSONResponse({"error": "invalid request parameters"}, status_code=400)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


# See api/gateway.py for the rationale. Kept identical so the two copies
# cannot drift on a security control while both exist.
ALLOW_UNAUTHENTICATED = os.environ.get(
    "GATEWAY_ALLOW_UNAUTHENTICATED", ""
).strip().lower() in {"1", "true", "yes"}

if not GATEWAY_API_TOKEN and not ALLOW_UNAUTHENTICATED:
    raise SystemExit(
        "GATEWAY_API_TOKEN is not set. The ledger gateway writes evidence and "
        "will not run unauthenticated. Set GATEWAY_API_TOKEN, or set "
        "GATEWAY_ALLOW_UNAUTHENTICATED=true for local development."
    )

UNAUTHENTICATED_PATHS = {"/healthz"}


@app.get("/healthz")
async def healthz():
    """Liveness and readiness probe. Never requires credentials."""
    return {"status": "ok", "service": "are-ledger-gateway"}


@app.middleware("http")
async def authorize(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in UNAUTHENTICATED_PATHS:
        return await call_next(request)
    if not GATEWAY_API_TOKEN:
        return await call_next(request)  # only via GATEWAY_ALLOW_UNAUTHENTICATED
    expected = f"Bearer {GATEWAY_API_TOKEN}"
    presented = request.headers.get("Authorization", "")
    if not hmac.compare_digest(presented, expected):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


_client = None


def get_client():
    """Return a module-level singleton LedgerClient (reused across requests).

    The async rewrite originally constructed a fresh LedgerClient on every
    call. That opens a new gRPC channel per request, which is exactly the
    kind of per-request resource growth this gateway replaced Flask to
    avoid, so the singleton behaviour is preserved here.
    """
    global _client
    if _client is None:
        _client = LedgerClient(ENDPOINT)
    return _client


def _entry_to_dict(e):
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
        "input_hash": e.input_hash,
        "writer_signature": e.writer_signature.hex() if e.writer_signature else "",
        "signer_key_reference": e.signer_key_reference if hasattr(e, "signer_key_reference") else "",
        "attestation_report": e.attestation_report.hex() if e.attestation_report else "",
        "hash_version": e.hash_version,
    }


async def _run_sync(fn, *args, **kwargs):
    """Run a synchronous gRPC call in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


@app.post("/api/entries", status_code=201)
async def write_entry(request: Request):
    body = await request.json()
    c = get_client()
    resp = await _run_sync(
        c.write,
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
    return {
        "entry_id": resp.entry_id,
        "entry_hash": resp.entry_hash,
        "chain_position": resp.chain_position,
        "written_ts": resp.written_ts,
        "hash_version": resp.hash_version,
    }


@app.post("/api/receipts", status_code=201)
async def issue_receipt(request: Request):
    body = await request.json()
    c = get_client()
    receipt = await _run_sync(
        c.issue_receipt,
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
    return {
        "entry_hash": receipt.entry_hash,
        "entry_type": receipt.entry_type,
        "chain_position": receipt.chain_position,
        "written_ts": receipt.written_ts,
        "entry_id": receipt.entry_id,
        "input_hash": receipt.input_hash,
        "writer_signature": receipt.writer_signature.hex() if receipt.writer_signature else "",
        "signer_key_reference": receipt.signer_key_reference,
        "attestation_report": receipt.attestation_report.hex() if receipt.attestation_report else "",
        "hash_version": receipt.hash_version,
    }


@app.get("/api/receipts/verify")
async def verify_proof(hash: str = Query(""), type: str = Query("")):
    if not hash or not type:
        return JSONResponse({"error": "hash and type query params required"}, status_code=400)
    c = get_client()
    v = await _run_sync(c.verify_proof, hash, type)
    return {
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
        "hash_version": v.hash_version,
    }


@app.get("/api/entries/by-hash")
async def get_entry_by_hash(hash: str = Query(""), type: str = Query("")):
    if not hash or not type:
        return JSONResponse({"error": "hash and type query params required"}, status_code=400)
    c = get_client()
    entry = await _run_sync(c.get_entry_by_hash, hash, type)
    return _entry_to_dict(entry)


@app.get("/api/receipts/chain")
async def receipt_chain(correlation_id: str = Query("")):
    if not correlation_id:
        return JSONResponse({"error": "correlation_id query param required"}, status_code=400)
    c = get_client()
    entries = await _run_sync(c.query, correlation_id=correlation_id)
    sorted_entries = sorted(entries, key=lambda e: e.written_ts)
    return {
        "correlation_id": correlation_id,
        "hops": len(sorted_entries),
        "sources": list(set(e.source_id for e in sorted_entries)),
        "entries": [_entry_to_dict(e) for e in sorted_entries],
    }


@app.get("/api/entries")
async def get_entries(
    agent_id: str = Query(""),
    entry_type: str = Query(""),
    source_id: str = Query(""),
    correlation_id: str = Query(""),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    page_size: int = Query(100),
    page_token: str = Query(""),
):
    c = get_client()
    kwargs = {}
    if agent_id: kwargs["agent_id"] = agent_id
    if entry_type: kwargs["entry_type"] = entry_type
    if source_id: kwargs["source_id"] = source_id
    if correlation_id: kwargs["correlation_id"] = correlation_id
    if from_ts is not None: kwargs["from_ts"] = from_ts
    if to_ts is not None: kwargs["to_ts"] = to_ts
    entries, next_token, total_count = await _run_sync(
        c.query_page, page_size=page_size, page_token=page_token, **kwargs)
    return {
        "entries": [_entry_to_dict(e) for e in entries],
        "next_page_token": next_token,
        "total_count": total_count,
    }


@app.get("/api/summary")
async def get_summary():
    c = get_client()
    entries = await _run_sync(c.query)
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
    return {
        "total_entries": len(entries),
        "sources": {s: len(es) for s, es in by_source.items()},
        "chain_types": len(by_type),
        "correlation_ids": len(corr_ids),
        "cross_system_correlations": cross_system,
    }


@app.get("/api/chains")
async def get_chains():
    c = get_client()
    entries = await _run_sync(c.query)
    by_type = {}
    for e in entries:
        by_type.setdefault(e.entry_type, []).append(e)
    chains = []
    for entry_type, es in sorted(by_type.items()):
        chains.append({
            "entry_type": entry_type,
            "count": len(es),
            "entries": [_entry_to_dict(e) for e in sorted(es, key=lambda x: x.chain_position)],
        })
    return chains


@app.get("/api/verify")
async def verify_all():
    c = get_client()
    entries = await _run_sync(c.query)
    types = sorted(set(e.entry_type for e in entries))
    results = []
    for t in types:
        v = await _run_sync(c.verify_chain, t)
        results.append({
            "entry_type": t,
            "chain_valid": v.chain_valid,
            "entries_checked": v.entries_checked,
            "failure_reason": v.failure_reason or "",
            "first_invalid_entry_id": v.first_invalid_entry_id or "",
        })
    all_valid = all(r["chain_valid"] for r in results)
    return {"all_valid": all_valid, "chains": results}


@app.get("/api/verify/{entry_type:path}")
async def verify_chain(entry_type: str):
    c = get_client()
    v = await _run_sync(c.verify_chain, entry_type)
    return {
        "entry_type": entry_type,
        "chain_valid": v.chain_valid,
        "entries_checked": v.entries_checked,
        "failure_reason": v.failure_reason or "",
    }


@app.get("/api/timeline")
async def get_timeline():
    c = get_client()
    entries = await _run_sync(c.query)
    sorted_entries = sorted(entries, key=lambda e: e.written_ts)
    corr_map = {}
    for e in sorted_entries:
        if e.correlation_id:
            corr_map.setdefault(e.correlation_id, []).append(e.entry_id)
    return {
        "entries": [_entry_to_dict(e) for e in sorted_entries],
        "correlations": {cid: ids for cid, ids in corr_map.items() if len(ids) > 1},
    }


@app.get("/api/drift")
async def get_drift():
    c = get_client()
    entries = await _run_sync(c.query)
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
    return {
        "gaps": gaps,
        "total_denials": len(denials),
        "total_scope_evals": len(scope_evals),
    }


if __name__ == "__main__":
    import uvicorn

    # Same env contract the Flask entrypoint honoured, so deployment manifests
    # and the demo stack do not need to change.
    uvicorn.run(
        app,
        host=os.environ.get("GATEWAY_HOST", "127.0.0.1"),
        port=int(os.environ.get("GATEWAY_PORT", "18099")),
        log_level=os.environ.get("GATEWAY_LOG_LEVEL", "info"),
    )
