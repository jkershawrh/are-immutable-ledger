#!/usr/bin/env python3
"""CPEX-to-Ledger adapter for the CPEX audit seam.

Reads CPEX audit records (OCSF 6003/ai_operation, JSONL) from stdin or
a file and writes them to the immutable ledger. Each record becomes a
ledger entry with:

  entry_type:           "cpex.decision" or "cpex.effect" (from record payload)
  agent_id:             ai_agent.uid (NOT metadata.uid)
  content:              JCS-canonicalized event bytes (envelope stripped)
  content_type:         "application/ocsf+json"
  source_id:            "cpex-audit-seam"
  correlation_id:       metadata.correlation_uid (conversation/run scope)
  idempotency_key:      metadata.uid (the record ID)
  input_hash:           SHA-256 of canonical content
  writer_signature:     unmapped.signature_b64 (base64-decoded)
  signer_key_reference: unmapped.signature_key_id

Gap detection: validates stream_seq continuity per (epoch, stream_id) —
including the head of every epoch, which opens at stream_seq 0 — epoch
ordering per stream_id, and emission_seq monotonicity. Alerts on gaps but
still writes records.

Stream ids are opaque to the adapter. A CPEX host that sets
plugin_settings.audit_stream_namespace stamps them as "<namespace>:<kind>"
(e.g. "gw-1:decision" / "gw-1:effect"); the namespace may itself contain
":", so anything that needs the kind back splits on the LAST colon
(rsplit(":", 1)). Nothing here does — entry_type comes from the record's
own content (unmapped."cpex.decision" / "cpex.effect"), never from the
stream id.

Usage:
  python cpex_to_ledger.py --file /var/log/cpex-audit.jsonl
  cat audit-stream.jsonl | python cpex_to_ledger.py
  python cpex_to_ledger.py --endpoint localhost:19292 --strict-gaps
"""

import argparse
import base64
import copy
import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdks", "python"))
from ledger_client import LedgerClient

SOURCE_ID = "cpex-audit-seam"
CONTENT_TYPE = "application/ocsf+json"

# Compatibility for records emitted before the AID-EMIT-1 nested shape.
LEGACY_STREAM_PREFIX_MAP = {
    "dec-": "decision",
    "eff-": "effect",
}

UNMAPPED_ENVELOPE_KEYS = ("signature_b64", "signature_key_id")

# The first stream_seq a host emits in an epoch. AID-EMIT-1 section 7 defines
# stream_seq as dense within (epoch, stream_id), and the reference host (CPEX)
# stamps from a zero-initialised counter, so every epoch opens at 0.
STREAM_HEAD_SEQ = 0


class GapDetector:
    """Tracks stream_seq continuity per (epoch, stream_id), the head of each
    epoch, epoch ordering per stream_id, and emission_seq monotonicity.

    Density is a per-(epoch, stream_id) property: a producer restart opens a
    new epoch and legitimately resets the counter, so a new epoch is never a
    gap. Two things ARE alerted that a tail-only check cannot see:

    * The head of every epoch. An epoch opens at stream_seq 0, so a first
      record above 0 means records 0..n-1 never arrived. The record emitted
      while the process is still coming up is the one most likely to be
      dropped, and it is exactly the one that leaves no tail to check
      against — so a restart that lost record 0 used to read as a clean,
      dense epoch. Applied to epoch-stamped records only: the legacy
      top-level shape predates section 7 and carries no epoch, so it has no
      defined head.

    * Epoch regression. Epochs are boot-ordered per stream, and since CPEX
      lets the host supply the epoch (plugin_settings.audit_epoch, a
      programmatic override that CPEX only warns about when it fails to
      advance) an older epoch arriving after a newer one is either a late
      replay of a dead process or a host that pinned its epoch — in both
      cases the completeness claim for that stream no longer holds, and it
      used to pass silently.
    """

    def __init__(self):
        self._last_seq = {}
        self._newest_epoch = {}
        self._last_emission_seq = {}

    def check(self, stream_id, stream_seq, emission_seq, epoch=None):
        alerts = []
        stream_key = (epoch, stream_id)

        if stream_key in self._last_seq:
            expected = self._last_seq[stream_key] + 1
            if stream_seq != expected:
                alerts.append(
                    f"GAP in {stream_id}: expected stream_seq {expected}, got {stream_seq}"
                )
        elif epoch is not None and stream_seq != STREAM_HEAD_SEQ:
            # First record seen for this (epoch, stream_id): it must be the
            # head. Reported once, here; the records that follow are then
            # checked against this (anomalous) tail, not re-flagged.
            alerts.append(
                f"GAP at head of {stream_id} epoch {epoch}: expected stream_seq "
                f"{STREAM_HEAD_SEQ}, got {stream_seq} "
                f"(records {STREAM_HEAD_SEQ}..{stream_seq - 1} not seen)"
            )

        self._last_seq[stream_key] = stream_seq

        if isinstance(epoch, int):
            newest = self._newest_epoch.get(stream_id)
            if isinstance(newest, int) and epoch < newest:
                alerts.append(
                    f"EPOCH REGRESSION in {stream_id}: epoch {epoch} after {newest}"
                )
            elif newest is None or epoch > newest:
                self._newest_epoch[stream_id] = epoch

        previous_emission_seq = self._last_emission_seq.get(epoch, -1)
        if emission_seq is not None and emission_seq <= previous_emission_seq:
            alerts.append(
                f"ORDERING: emission_seq {emission_seq} <= previous {previous_emission_seq}"
            )
        if emission_seq is not None:
            self._last_emission_seq[epoch] = emission_seq

        return alerts


def detect_record_type(event):
    unmapped = event.get("unmapped", {})
    if isinstance(unmapped, dict):
        if "cpex.decision" in unmapped:
            return "decision"
        if "cpex.effect" in unmapped:
            return "effect"

    # Accept the pre-AID-EMIT-1 shape for offline replay compatibility.
    stream_id = event.get("stream_id", "")
    for prefix, record_type in LEGACY_STREAM_PREFIX_MAP.items():
        if stream_id.startswith(prefix):
            return record_type
    return None


def extract_stream_stamps(event):
    """Extract AID-EMIT-1 section 7 stamps, with legacy fallback."""
    unmapped = event.get("unmapped", {})
    if isinstance(unmapped, dict):
        stream = unmapped.get("cpex.stream")
        if isinstance(stream, dict):
            return (
                stream.get("epoch"),
                stream.get("stream_id", ""),
                stream.get("stream_seq"),
                stream.get("emission_seq"),
            )

    return (
        event.get("epoch"),
        event.get("stream_id", ""),
        event.get("stream_seq"),
        event.get("emission_seq"),
    )


def extract_agent_id(event):
    ai_agent = event.get("ai_agent", {})
    uid = ai_agent.get("uid", "")
    if uid:
        return uid
    return event.get("agent_id", "unknown")


def extract_correlation_id(event):
    metadata = event.get("metadata", {})
    return metadata.get("correlation_uid", "")


def extract_idempotency_key(event):
    metadata = event.get("metadata", {})
    return metadata.get("uid", "")


def extract_writer_signature(event):
    unmapped = event.get("unmapped", {})
    sig_b64 = unmapped.get("signature_b64", "")
    if not sig_b64:
        return b""
    try:
        return base64.b64decode(sig_b64)
    except Exception:
        print(f"  WARNING: invalid base64 in signature_b64, skipping signature", file=sys.stderr)
        return b""


def extract_signer_key_reference(event):
    unmapped = event.get("unmapped", {})
    return unmapped.get("signature_key_id", "")


def canonicalize_content(event):
    """Return the AID-EMIT-1 covered bytes and their SHA-256 fingerprint.

    AID-EMIT-1 section 4 excludes the derived fingerprint and signature
    descriptors from the first attestation entry, plus the transitional raw
    signature fields under ``unmapped``. Chain identity and position fields,
    including ``prev_event``, remain covered.
    """
    content = copy.deepcopy(event)

    attestations = content.get("attestation_list")
    if (
        isinstance(attestations, list)
        and attestations
        and isinstance(attestations[0], dict)
    ):
        attestations[0].pop("fingerprint", None)
        attestations[0].pop("signatures", None)

    unmapped = content.get("unmapped", {})
    for key in UNMAPPED_ENVELOPE_KEYS:
        unmapped.pop(key, None)
    if not unmapped:
        content.pop("unmapped", None)
    elif unmapped != event.get("unmapped", {}):
        content["unmapped"] = unmapped

    try:
        from json_canonicalize import canonicalize
        canonical = canonicalize(content)
    except ImportError:
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    if isinstance(canonical, str):
        canonical_bytes = canonical.encode("utf-8")
    else:
        canonical_bytes = canonical

    content_hash = hashlib.sha256(canonical_bytes).hexdigest()
    return canonical_bytes, content_hash


def process_line(client, line, stats, gap_detector, *, write_only=False):
    line = line.strip()
    if not line:
        return

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        stats["parse_errors"] += 1
        return

    record_type = detect_record_type(event)
    if record_type is None:
        stats["skipped"] += 1
        return

    epoch, stream_id, stream_seq, emission_seq = extract_stream_stamps(event)

    if stream_id and stream_seq is not None:
        gaps = gap_detector.check(stream_id, stream_seq, emission_seq, epoch)
        for gap_msg in gaps:
            print(f"  WARNING: {gap_msg}", file=sys.stderr)
            stats["gaps_detected"] += 1

    entry_type = f"cpex.{record_type}"
    agent_id = extract_agent_id(event)
    correlation_id = extract_correlation_id(event)
    idempotency_key = extract_idempotency_key(event)
    writer_signature = extract_writer_signature(event)
    signer_key_ref = extract_signer_key_reference(event)

    canonical_bytes, content_hash = canonicalize_content(event)

    write_kwargs = dict(
        entry_type=entry_type,
        agent_id=agent_id,
        content=canonical_bytes,
        content_type=CONTENT_TYPE,
        source_id=SOURCE_ID,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        input_hash=content_hash,
        writer_signature=writer_signature,
        signer_key_reference=signer_key_ref,
    )

    try:
        if write_only:
            resp = client.write(**write_kwargs)
            pos = resp.chain_position
        else:
            resp = client.issue_receipt(**write_kwargs)
            pos = resp.chain_position
        stats["written"] += 1
        seq_info = f"seq={stream_seq}" if stream_seq is not None else ""
        print(f"  [{pos:>3}] {entry_type:<20} agent={agent_id:<20} {seq_info}")
    except Exception as e:
        stats["write_errors"] += 1
        print(f"  ERROR writing {entry_type}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Bridge CPEX audit records to the immutable ledger"
    )
    parser.add_argument("--file", "-f", help="Read from file instead of stdin")
    parser.add_argument(
        "--endpoint", default="localhost:19092", help="Ledger gRPC endpoint"
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
        help="Use WriteEntry instead of IssueReceipt (no receipt data)",
    )
    parser.add_argument(
        "--strict-gaps",
        action="store_true",
        help="Exit with error code if gaps detected",
    )
    args = parser.parse_args()

    client = LedgerClient(args.endpoint)
    stats = {
        "written": 0,
        "parse_errors": 0,
        "write_errors": 0,
        "skipped": 0,
        "gaps_detected": 0,
    }
    gap_detector = GapDetector()

    print(f"\n  CPEX-to-Ledger Adapter")
    print(f"  Ledger: {args.endpoint}")
    print(f"  Source: {'stdin' if not args.file else args.file}")
    print(f"  Mode:   {'WriteEntry' if args.write_only else 'IssueReceipt'}\n")

    try:
        if args.file:
            with open(args.file) as f:
                for line in f:
                    process_line(
                        client, line, stats, gap_detector, write_only=args.write_only
                    )
        else:
            for line in sys.stdin:
                process_line(
                    client, line, stats, gap_detector, write_only=args.write_only
                )
    except KeyboardInterrupt:
        pass

    print(
        f"\n  Written: {stats['written']}  Errors: {stats['write_errors']}  "
        f"Parse errors: {stats['parse_errors']}  Skipped: {stats['skipped']}  "
        f"Gaps: {stats['gaps_detected']}\n"
    )

    client.close()

    if args.strict_gaps and stats["gaps_detected"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
