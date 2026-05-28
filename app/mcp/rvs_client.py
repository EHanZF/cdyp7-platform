"""
PTC RV&S client utilities for CDYP7.

Contains all RV&S CLI interaction, parsing, normalization,
dashboard aggregation, receipt generation, and persistence.
No MCP or transport logic lives here.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import uuid
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CLOSED_STATES = {
    "closed",
    "done",
    "accepted",
    "resolved",
    "verified",
    "complete",
    "completed",
}
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
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    """Normalize a string into a slug."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-") or "unassigned"


def csv_env(name: str, default: List[str]) -> List[str]:
    """Read a CSV list from an environment variable."""
    value = os.getenv(name)
    if not value:
        return default
    return [x.strip() for x in value.split(",") if x.strip()]


def is_closed(state: str) -> bool:
    """Return True if a state is considered closed."""
    return str(state or "").strip().lower() in CLOSED_STATES


def number(value: Any, fallback: float = 1) -> float:
    """Parse a numeric value with fallback."""
    try:
        if value in (None, ""):
            return fallback
        return float(value)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


def split_owners(value: str) -> List[str]:
    """Split an owner field into a list of owners."""
    if not value:
        return ["Unassigned"]
    for sep in [",", ";"]:
        if sep in value:
            return [p.strip() for p in value.split(sep) if p.strip()]
    return [value.strip()] or ["Unassigned"]


def receipt(
    tool: str,
    input_payload: Dict[str, Any],
    output_summary: Dict[str, Any],
    elapsed_ms: int,
) -> Dict[str, Any]:
    """Generate a non-authoritative receipt record."""
    return {
        "receipt_id": (
            f"rvs_rcpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}"
        ),
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
    """Configuration holder for RV&S CLI execution."""

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
        """Build base CLI arguments for `im issues`."""
        args = [
            self.im_exe,
            "issues",
            f"--hostname={self.host}",
            f"--port={self.port}",
            "--batch",
            "--noapplyDisplayPattern",
        ]
        if self.user:
            args.append(f"--user={self.user}")
        if self.password:
            args.append("--password=***REDACTED***")
        return args


def run_im_issues(
    cfg: RVSConfig,
    query: Optional[str] = None,
    query_definition: Optional[str] = None,
) -> str:
    """Run the RV&S `im issues` command and return stdout."""
    fields = ",".join(cfg.fields)
    args = cfg.base_args() + [
        f"--fields={fields}",
        "--fieldsDelim=\t",
    ]

    q = query or cfg.query
    qd = query_definition or cfg.query_definition

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
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "RV&S im issues failed\n"
            f"exit: {completed.returncode}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    return completed.stdout


def parse_tabular_im_output(
    text: str,
    expected_fields: List[str],
) -> List[Dict[str, str]]:
    """Parse tab-delimited RV&S output."""
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

    parsed: List[Dict[str, str]] = []
    for row in data_rows:
        item: Dict[str, str] = {}
        for idx, header in enumerate(headers):
            item[header] = row[idx].strip() if idx < len(row) else ""
        if any(item.values()):
            parsed.append(item)
    return parsed


def normalize_rvs_item(
    row: Dict[str, str],
    cfg: RVSConfig,
) -> Dict[str, Any]:
    """Normalize a raw RV&S row into dashboard item format."""
    item_id = row.get("ID") or row.get("Id") or ""
    summary = row.get(cfg.summary_field) or f"Item {item_id}"
    state = row.get(cfg.state_field) or "Unknown"
    priority = row.get(cfg.priority_field) or "Unspecified"
    delivery = row.get(cfg.delivery_field) or "Unassigned"
    target_date = row.get(cfg.delivery_date_field) or ""
    owners = split_owners(row.get(cfg.owner_field) or "")
    tracker = row.get(cfg.type_field) or "RV&S Item"
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
        "blocked": ("block" in state.lower() or priority.lower() in {"blocker"}),
        "rawFields": row,
    }


def build_deliveries(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Aggregate items into deliveries."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = item["deliveryId"]
        d = grouped.setdefault(
            key,
            {
                "id": key,
                "name": item.get("deliveryName") or "Unassigned",
                "deliveryDate": item.get("deliveryDate") or "",
                "totalItems": 0,
                "completedItems": 0,
                "remainingItems": 0,
            },
        )
        d["totalItems"] += 1
        if is_closed(item.get("status", "")):
            d["completedItems"] += 1
        else:
            d["remainingItems"] += 1
    return list(grouped.values())


def build_dashboard(
    items: List[Dict[str, Any]],
    query_used: str,
) -> Dict[str, Any]:
    """Build the final dashboard JSON structure."""
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
        "deliveries": build_deliveries(items),
        "totals": {
            "items": len(items),
            "openItems": len(open_items),
            "remaining": sum(number(i.get("remaining"), 1) for i in open_items),
            "atRisk": sum(
                1
                for i in open_items
                if i.get("blocked") or str(i.get("priority", "")).lower() in HIGH_PRIORITIES
            ),
        },
        "breakdowns": {
            "status": dict(by_status),
            "priority": dict(by_priority),
            "tracker": dict(by_tracker),
            "owner": dict(by_owner),
        },
        "items": items,
    }


def write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON data to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
