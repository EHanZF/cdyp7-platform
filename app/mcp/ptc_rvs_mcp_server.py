#!/usr/bin/env python3
"""
CDYP7 PTC RV&S MCP Server

Temporary RV&S adapter for pre-Codebeamer migration.
Uses the PTC RV&S / Integrity CLI (`im`) to query ALM items from:
  skobde-mks-im.kobde.trw.com:7001

This exposes the same dashboard JSON contract used by the Codebeamer dashboard:
  data/results/latest.json
  data/receipts/latest.json

Prerequisites on the MCP host:
- PTC RV&S / Integrity Lifecycle Manager client installed
- `im` executable available on PATH, or set RVS_IM_EXE
- Network/VPN access to the RV&S server
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CDYP7-PTC-RVS-MCP", json_response=True)

CLOSED_STATES = {"closed", "done", "accepted", "resolved", "verified", "complete", "completed"}
HIGH_PRIORITIES = {"high", "critical", "blocker", "urgent"}

DEFAULT_FIELDS = [
    "ID",
    "Summary",
    "State",
    "Assigned User",
    "Type",
    "Priority",
    "ALM_Delivery",
    "Target Date",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-") or "unassigned"


def csv_env(name: str, default: List[str]) -> List[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [x.strip() for x in value.split(",") if x.strip()]


def is_closed(state: str) -> bool:
    return str(state or "").strip().lower() in CLOSED_STATES


def number(value: Any, fallback: float = 1) -> float:
    try:
        if value in (None, ""):
            return fallback
        return float(value)
    except Exception:
        return fallback


def split_owners(value: str) -> List[str]:
    if not value:
        return ["Unassigned"]
    parts = []
    for sep in [",", ";"]:
        if sep in value:
            parts = [p.strip() for p in value.split(sep) if p.strip()]
            break
    if not parts:
        parts = [value.strip()]
    return parts or ["Unassigned"]


def receipt(tool: str, input_payload: Dict[str, Any], output_summary: Dict[str, Any], elapsed_ms: int) -> Dict[str, Any]:
    return {
        "receipt_id": f"rvs_rcpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "tool": tool,
        "source": "ptc-rvs",
        "authority": "non_authoritative",
        "receipt_backed": True,
        "semantic_verification_required": False,
        "human_approved": False,
        "generatedAt": utc_now(),
        "elapsedMs": elapsed_ms,
        "input": input_payload,
        "output": output_summary,
    }


class RVSConfig:
    def __init__(self) -> None:
        self.host = os.getenv("RVS_HOST", "skobde-mks-im.kobde.trw.com")
        self.port = os.getenv("RVS_PORT", "7001")
        self.user = os.getenv("RVS_USER", "")
        self.password = os.getenv("RVS_PASSWORD", "")
        self.im_exe = os.getenv("RVS_IM_EXE", "im")
        self.query = os.getenv("RVS_QUERY", "")
        self.query_definition = os.getenv("RVS_QUERY_DEFINITION", "")
        self.fields = csv_env("RVS_FIELDS", DEFAULT_FIELDS)
        self.delivery_field = os.getenv("RVS_DELIVERY_FIELD", "ALM_Delivery")
        self.delivery_date_field = os.getenv("RVS_DELIVERY_DATE_FIELD", "Target Date")
        self.owner_field = os.getenv("RVS_OWNER_FIELD", "Assigned User")
        self.state_field = os.getenv("RVS_STATE_FIELD", "State")
        self.summary_field = os.getenv("RVS_SUMMARY_FIELD", "Summary")
        self.type_field = os.getenv("RVS_TYPE_FIELD", "Type")
        self.priority_field = os.getenv("RVS_PRIORITY_FIELD", "Priority")
        self.remaining_field = os.getenv("RVS_REMAINING_FIELD", "Remaining")
        self.output_path = Path(os.getenv("CDYP7_OUTPUT", "data/results/latest.json"))
        self.receipt_path = Path(os.getenv("CDYP7_RECEIPT", "data/receipts/latest.json"))
        self.timeout = int(os.getenv("RVS_TIMEOUT", "120"))

    def base_args(self) -> List[str]:
        args = [self.im_exe, "issues", f"--hostname={self.host}", f"--port={self.port}", "--batch", "--noapplyDisplayPattern"]
        if self.user:
            args.append(f"--user={self.user}")
        if self.password:
            args.append(f"--password={self.password}")
        return args


def run_im_issues(cfg: RVSConfig, query: Optional[str] = None, query_definition: Optional[str] = None) -> str:
    fields = ",".join(cfg.fields)

    # Use tab delimiter to make parsing more stable.
    args = cfg.base_args() + [
        f"--fields={fields}",
        "--fieldsDelim=\t",
    ]

    q = query if query is not None else cfg.query
    qd = query_definition if query_definition is not None else cfg.query_definition

    if q:
        args.append(f"--query={q}")
    elif qd:
        args.append(f"--queryDefinition={qd}")
    else:
        args.append("--query=Find Liv Projects All My Work")

    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=cfg.timeout,
        shell=False,
    )

    if completed.returncode != 0:
        safe_args = []
        for arg in args:
            if arg.startswith("--password="):
                safe_args.append("--password=***REDACTED***")
            else:
                safe_args.append(arg)

        raise RuntimeError(
            "RV&S im issues failed\n"
            f"command: {' '.join(safe_args)}\n"
            f"exit: {completed.returncode}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    return completed.stdout


def parse_tabular_im_output(text: str, expected_fields: List[str]) -> List[Dict[str, str]]:
    """Parse im issues tabular output.

    Preferred output has a header row followed by tab-delimited records. If the header is absent,
    the configured field order is used.
    """
    lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    reader = csv.reader(lines, delimiter="\t")
    rows = list(reader)
    if not rows:
        return []

    first = [c.strip() for c in rows[0]]
    expected_lower = {f.lower() for f in expected_fields}
    first_lower = {c.lower() for c in first}

    if len(first_lower & expected_lower) >= 2:
        headers = first
        data_rows = rows[1:]
    else:
        headers = expected_fields
        data_rows = rows

    parsed = []
    for row in data_rows:
        item = {}
        for idx, header in enumerate(headers):
            item[header] = row[idx].strip() if idx < len(row) else ""
        if any(item.values()):
            parsed.append(item)
    return parsed


def normalize_rvs_item(row: Dict[str, str], cfg: RVSConfig) -> Dict[str, Any]:
    item_id = row.get("ID") or row.get("Id") or row.get("Issue ID") or ""
    summary = row.get(cfg.summary_field) or row.get("Summary") or f"Item {item_id}"
    state = row.get(cfg.state_field) or row.get("State") or "Unknown"
    priority = row.get(cfg.priority_field) or row.get("Priority") or "Unspecified"
    delivery = row.get(cfg.delivery_field) or "Unassigned"
    target_date = row.get(cfg.delivery_date_field) or ""
    owners = split_owners(row.get(cfg.owner_field) or row.get("Assigned User") or "")
    tracker = row.get(cfg.type_field) or row.get("Type") or "RV&S Item"
    remaining = number(row.get(cfg.remaining_field), 1)

    return {
        "id": item_id,
        "title": summary,
        "deliveryId": slug(delivery),
        "deliveryName": delivery,
        "deliveryDate": target_date,
        "status": state,
        "priority": priority,
        "owners": owners,
        "owner": ", ".join(owners),
        "tracker": tracker,
        "type": tracker,
        "dueDate": target_date,
        "remaining": remaining,
        "blocked": "block" in state.lower() or priority.lower() in {"blocker"},
        "modifiedAt": row.get("Modified Date") or row.get("Modified") or "",
        "createdAt": row.get("Created Date") or row.get("Created") or "",
        "url": "",
        "rawFields": row,
    }


def build_deliveries(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = item["deliveryId"]
        d = grouped.setdefault(key, {
            "id": key,
            "name": item.get("deliveryName") or "Unassigned",
            "deliveryDate": item.get("deliveryDate") or "",
            "totalItems": 0,
            "completedItems": 0,
            "remainingItems": 0,
        })
        d["totalItems"] += 1
        if is_closed(item.get("status", "")):
            d["completedItems"] += 1
        else:
            d["remainingItems"] += 1
        if not d.get("deliveryDate") and item.get("deliveryDate"):
            d["deliveryDate"] = item.get("deliveryDate")
    return sorted(grouped.values(), key=lambda d: d.get("deliveryDate") or "9999-12-31")


def build_dashboard(items: List[Dict[str, Any]], query_used: str) -> Dict[str, Any]:
    by_status = Counter(i["status"] for i in items)
    by_priority = Counter(i["priority"] for i in items)
    by_tracker = Counter(i["tracker"] for i in items)
    by_owner: Dict[str, int] = defaultdict(int)
    for item in items:
        for owner in item.get("owners") or ["Unassigned"]:
            by_owner[owner] += 1

    open_items = [i for i in items if not is_closed(i.get("status", ""))]
    return {
        "generatedAt": utc_now(),
        "source": "ptc-rvs",
        "authority": "non_authoritative",
        "receiptBacked": True,
        "query": query_used,
        "server": "skobde-mks-im.kobde.trw.com:7001",
        "deliveries": build_deliveries(items),
        "totals": {
            "items": len(items),
            "openItems": len(open_items),
            "remaining": sum(number(i.get("remaining"), 1) for i in open_items),
            "atRisk": sum(1 for i in open_items if i.get("blocked") or str(i.get("priority", "")).lower() in HIGH_PRIORITIES),
        },
        "breakdowns": {
            "status": dict(by_status),
            "priority": dict(by_priority),
            "tracker": dict(by_tracker),
            "owner": dict(sorted(by_owner.items(), key=lambda kv: kv[1], reverse=True)),
        },
        "items": items,
    }


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@mcp.tool()
def cdyp7_rvs_dashboard(query: str = "", query_definition: str = "", persist: bool = True) -> Dict[str, Any]:
    """Fetch RV&S items using `im issues` and build the CDYP7 dashboard JSON."""
    start = time.time()
    cfg = RVSConfig()
    q_used = query or cfg.query or query_definition or cfg.query_definition or "All"
    output = run_im_issues(cfg, query=query or None, query_definition=query_definition or None)
    rows = parse_tabular_im_output(output, cfg.fields)
    items = [normalize_rvs_item(row, cfg) for row in rows]
    dashboard = build_dashboard(items, q_used)
    elapsed_ms = int((time.time() - start) * 1000)
    rcpt = receipt("cdyp7.rvs.dashboard", {"query": q_used, "fields": cfg.fields}, {"items": len(items), "deliveries": len(dashboard["deliveries"])}, elapsed_ms)
    dashboard["receiptId"] = rcpt["receipt_id"]

    if persist:
        write_json(cfg.output_path, dashboard)
        write_json(cfg.receipt_path, rcpt)

    return dashboard


@mcp.tool()
def cdyp7_rvs_connection_check() -> Dict[str, Any]:
    """Check that the RV&S CLI can reach skobde-mks-im.kobde.trw.com:7001."""
    cfg = RVSConfig()
    args = [cfg.im_exe, "connect", f"--hostname={cfg.host}", f"--port={cfg.port}", "--batch"]
    if cfg.user:
        args.append(f"--user={cfg.user}")
    if cfg.password:
        args.append(f"--password={cfg.password}")
    completed = subprocess.run(args, capture_output=True, text=True, timeout=cfg.timeout, shell=False)
    return {
        "status": "ok" if completed.returncode == 0 else "failed",
        "server": f"{cfg.host}:{cfg.port}",
        "exitCode": completed.returncode,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


@mcp.resource("cdyp7://rvs/dashboard/latest")
def latest_dashboard() -> str:
    path = Path(os.getenv("CDYP7_OUTPUT", "data/results/latest.json"))
    if not path.exists():
        return json.dumps({"error": "No RV&S dashboard state has been generated yet."})
    return path.read_text(encoding="utf-8")


def run_once() -> None:
    dashboard = cdyp7_rvs_dashboard(query=os.getenv("RVS_QUERY", ""), query_definition=os.getenv("RVS_QUERY_DEFINITION", ""), persist=True)
    print(json.dumps({
        "ok": True,
        "source": dashboard.get("source"),
        "items": dashboard.get("totals", {}).get("items"),
        "openItems": dashboard.get("totals", {}).get("openItems"),
        "deliveries": len(dashboard.get("deliveries", [])),
        "receiptId": dashboard.get("receiptId"),
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "fetch"])
    args = parser.parse_args()
    if args.command == "fetch":
        run_once()
    else:
        mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))
