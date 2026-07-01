#!/usr/bin/env python3
"""Proof Explorer — query, verify, and analyze the immutable ledger.

Commands:
  query       Query entries by agent-id, correlation-id, source, or entry-type
  timeline    Chronological cross-system timeline
  verify      Verify hash chain integrity
  summary     Overview of all chains and sources
  drift       Detect authorization gaps across systems
"""

import argparse
import json
import sys
import os
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from ledger_client import LedgerClient

# ANSI colors
BLUE = "\033[94m"
GREEN = "\033[92m"
PURPLE = "\033[95m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

SOURCE_COLORS = {
    "are": BLUE,
    "openshell": GREEN,
    "kagenti": PURPLE,
    "standalone": YELLOW,
}


def color_source(source_id):
    for prefix, color in SOURCE_COLORS.items():
        if prefix in source_id.lower():
            return f"{color}{source_id}{RESET}"
    return source_id


def color_entry_type(entry_type):
    for prefix, color in SOURCE_COLORS.items():
        if entry_type.startswith(prefix):
            return f"{color}{entry_type}{RESET}"
    return entry_type


def format_ts(ts_ms):
    if not ts_ms:
        return "N/A"
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%H:%M:%S.") + f"{ts_ms % 1000:03d}"


def truncate(s, length=30):
    s = str(s)
    return s[:length] + "..." if len(s) > length else s


def extract_detail(entry):
    try:
        content = json.loads(entry.content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""

    if "effect" in content:
        return f"{content.get('action_class', '')} -> {content['effect']}"
    if "action" in content:
        return content["action"]
    if "activity_name" in content:
        method = content.get("unmapped", {}).get("http_method", "")
        dst = content.get("dst_endpoint", {}).get("domain", "")
        act = content.get("activity_name", "")
        disp = content.get("disposition", "")
        parts = [p for p in [method or act, dst, disp] if p]
        return " ".join(parts)
    if "tool.name" in content:
        return f"tool={content['tool.name']}"
    if "span_name" in content:
        return content["span_name"]
    if "scope_set" in content:
        scopes = content["scope_set"]
        if scopes:
            return f"scope: {scopes[0].get('action_class', '')}:{scopes[0].get('resource_pattern', '')}"
    if "task" in content:
        return content["task"]
    if "decision" in content:
        return content["decision"]
    if "message" in content:
        return truncate(content["message"], 50)

    return ""


def print_entries(entries, show_hash=False):
    if not entries:
        print("  No entries found.\n")
        return

    print()
    if show_hash:
        print(f"  {'TIME':<15} {'SOURCE':<22} {'ENTRY TYPE':<35} {'AGENT ID':<30} {'HASH':<18} {'DETAIL'}")
        print(f"  {'─'*15} {'─'*22} {'─'*35} {'─'*30} {'─'*18} {'─'*30}")
    else:
        print(f"  {'TIME':<15} {'SOURCE':<22} {'ENTRY TYPE':<35} {'AGENT ID':<30} {'DETAIL'}")
        print(f"  {'─'*15} {'─'*22} {'─'*35} {'─'*30} {'─'*30}")

    for e in sorted(entries, key=lambda x: x.written_ts):
        ts = format_ts(e.written_ts)
        source = color_source(e.source_id)
        etype = color_entry_type(e.entry_type)
        agent = truncate(e.agent_id, 28)
        detail = extract_detail(e)

        if show_hash:
            h = e.entry_hash[:16] + "..."
            print(f"  {ts:<15} {source:<33} {etype:<46} {agent:<30} {h:<18} {detail}")
        else:
            print(f"  {ts:<15} {source:<33} {etype:<46} {agent:<30} {detail}")
    print()


def cmd_query(args, client):
    kwargs = {}
    if args.agent_id:
        kwargs["agent_id"] = args.agent_id
    if args.correlation_id:
        kwargs["correlation_id"] = args.correlation_id
    if args.source:
        kwargs["source_id"] = args.source
    if args.entry_type:
        kwargs["entry_type"] = args.entry_type

    print(f"\n{BOLD}  Query: {kwargs or 'all entries'}{RESET}")
    entries = client.query(**kwargs)
    print_entries(entries, show_hash=args.show_hash)
    print(f"  {len(entries)} entries returned.\n")


def cmd_timeline(args, client):
    if args.session:
        entries = client.query(correlation_id=args.session)
    elif args.agent_id:
        entries = client.query(agent_id=args.agent_id)
    else:
        entries = client.query()

    label = args.session or args.agent_id or "all"
    print(f"\n{BOLD}  Timeline: {label}{RESET}")
    print_entries(entries)

    sources = set(e.source_id for e in entries)
    corr_ids = set(e.correlation_id for e in entries if e.correlation_id)
    multi_source_corr = set()
    for cid in corr_ids:
        cid_sources = set(e.source_id for e in entries if e.correlation_id == cid)
        if len(cid_sources) > 1:
            multi_source_corr.add(cid)

    print(f"  Sources: {len(sources)} ({', '.join(sorted(sources))})")
    print(f"  Correlation IDs: {len(corr_ids)}")
    if multi_source_corr:
        print(f"  {GREEN}Cross-system correlations: {len(multi_source_corr)}{RESET}")
        for cid in sorted(multi_source_corr):
            cid_sources = sorted(set(e.source_id for e in entries if e.correlation_id == cid))
            print(f"    {cid}: {' + '.join(cid_sources)}")
    print()


def cmd_verify(args, client):
    print(f"\n{BOLD}  Chain Verification{RESET}\n")

    all_entries = client.query()
    entry_types = sorted(set(e.entry_type for e in all_entries))

    if args.entry_type:
        entry_types = [et for et in entry_types if et.startswith(args.entry_type)]

    if not entry_types:
        print("  No chains found.\n")
        return

    all_valid = True
    for et in entry_types:
        result = client.verify_chain(et)
        if result.chain_valid:
            status = f"{GREEN}VALID{RESET}"
        else:
            status = f"{RED}INVALID: {result.failure_reason}{RESET}"
            all_valid = False

        color = ""
        for prefix, c in SOURCE_COLORS.items():
            if et.startswith(prefix):
                color = c
                break
        print(f"  {color}{et:<40}{RESET}  {status}  ({result.entries_checked} entries)")

    print()
    if all_valid:
        print(f"  {GREEN}{BOLD}All {len(entry_types)} chains verified. 0 tampered.{RESET}\n")
    else:
        print(f"  {RED}{BOLD}Chain verification FAILED.{RESET}\n")


def cmd_summary(args, client):
    print(f"\n{BOLD}  Ledger Summary{RESET}\n")

    all_entries = client.query()
    if not all_entries:
        print("  Ledger is empty.\n")
        return

    by_source = {}
    by_type = {}
    for e in all_entries:
        by_source.setdefault(e.source_id, []).append(e)
        by_type.setdefault(e.entry_type, []).append(e)

    print(f"  Total entries: {BOLD}{len(all_entries)}{RESET}")
    print(f"  Sources:       {len(by_source)}")
    print(f"  Chain types:   {len(by_type)}")
    print()

    print(f"  {'SOURCE':<25} {'ENTRIES':>8} {'CHAINS':>8} {'AGENT IDS':>10}")
    print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*10}")
    for source in sorted(by_source):
        entries = by_source[source]
        chains = len(set(e.entry_type for e in entries))
        agents = len(set(e.agent_id for e in entries))
        print(f"  {color_source(source):<36} {len(entries):>8} {chains:>8} {agents:>10}")

    print()
    corr_ids = set(e.correlation_id for e in all_entries if e.correlation_id)
    multi_source = 0
    for cid in corr_ids:
        sources = set(e.source_id for e in all_entries if e.correlation_id == cid)
        if len(sources) > 1:
            multi_source += 1

    print(f"  Cross-system correlations: {BOLD}{multi_source}{RESET} "
          f"(out of {len(corr_ids)} correlation IDs)")
    print()


def cmd_drift(args, client):
    print(f"\n{BOLD}  Drift Detection{RESET}\n")

    all_entries = client.query()

    allows = [e for e in all_entries if "allow" in e.entry_type or
              (e.entry_type.startswith("openshell.") and "Allowed" in e.content.decode("utf-8", errors="ignore"))]
    denials = [e for e in all_entries if "deny" in e.entry_type or "network_activity" in e.entry_type and
               "Denied" in e.content.decode("utf-8", errors="ignore")]
    scope_evals = [e for e in all_entries if "scope" in e.entry_type and "evaluated" in e.entry_type]

    scope_actions = set()
    for se in scope_evals:
        try:
            content = json.loads(se.content)
            action = content.get("action_class", "")
            resource = content.get("resource", "")
            if action:
                scope_actions.add((action, resource))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    gaps = []
    for entry in denials:
        corr = entry.correlation_id
        if not corr:
            continue
        matching_scope = [se for se in scope_evals if se.correlation_id == corr]
        if not matching_scope:
            try:
                content = json.loads(entry.content)
                dst = content.get("dst_endpoint", {}).get("domain", "unknown")
                method = content.get("unmapped", {}).get("http_method", "")
                msg = content.get("message", "")
                detail = f"{method} {dst}" if method else msg or "denied request"
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = "denied request"
            gaps.append({
                "entry_id": entry.entry_id,
                "correlation_id": corr,
                "agent_id": entry.agent_id,
                "detail": detail,
                "source": entry.source_id,
            })

    if not gaps:
        print(f"  {GREEN}No authorization gaps detected.{RESET}")
        print(f"  Checked {len(denials)} denials against {len(scope_evals)} scope evaluations.\n")
        return

    print(f"  {YELLOW}Found {len(gaps)} authorization gap(s):{RESET}\n")
    for gap in gaps:
        print(f"  {RED}GAP{RESET}: {gap['detail']}")
        print(f"       Agent:       {gap['agent_id']}")
        print(f"       Correlation: {gap['correlation_id']}")
        print(f"       Source:      {gap['source']}")
        print(f"       Issue:       Denied by sandbox but no governance scope evaluation found")
        print()

    print(f"  {len(gaps)} gap(s) detected. {len(denials)} denials checked, "
          f"{len(scope_evals)} scope evaluations found.\n")


def main():
    parser = argparse.ArgumentParser(description="Proof Explorer — query, verify, and analyze the immutable ledger")
    parser.add_argument("--endpoint", default="localhost:19292", help="Ledger gRPC endpoint")
    sub = parser.add_subparsers(dest="command", required=True)

    q = sub.add_parser("query", help="Query ledger entries")
    q.add_argument("--agent-id", help="Filter by agent ID")
    q.add_argument("--correlation-id", help="Filter by correlation ID (cross-system join)")
    q.add_argument("--source", help="Filter by source system")
    q.add_argument("--entry-type", help="Filter by entry type prefix")
    q.add_argument("--show-hash", action="store_true", help="Show entry hashes")

    t = sub.add_parser("timeline", help="Cross-system timeline view")
    t.add_argument("--session", help="Filter by session/correlation ID")
    t.add_argument("--agent-id", help="Filter by agent ID")
    t.add_argument("--all", action="store_true", help="Show all entries")

    v = sub.add_parser("verify", help="Verify hash chain integrity")
    v.add_argument("--entry-type", help="Verify chains matching this prefix")
    v.add_argument("--all", action="store_true", help="Verify all chains")

    sub.add_parser("summary", help="Ledger overview")

    d = sub.add_parser("drift", help="Detect authorization gaps")
    d.add_argument("--agent-id", help="Check specific agent")

    args = parser.parse_args()
    client = LedgerClient(args.endpoint)

    commands = {
        "query": cmd_query,
        "timeline": cmd_timeline,
        "verify": cmd_verify,
        "summary": cmd_summary,
        "drift": cmd_drift,
    }

    try:
        commands[args.command](args, client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
