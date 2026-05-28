#!/usr/bin/env python3
"""
CDYP7 PTC Codebeamer MCP Server.

MCP server using the official MCP Python SDK FastMCP interface.
It connects to the PTC Codebeamer REST API v3 and exposes read-only
project-management dashboard tools for the CDYP7 dashboard.

Security posture:
- Codebeamer credentials stay on the MCP host/server.
- Browser/static dashboard does not receive Codebeamer credentials.
- Tools return non-authoritative, receipt-backed dashboard envelopes.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CDYP7-PTC-Codebeamer-MCP", json_response=True)

CLOSED_STATUSES = {"closed", "done", "accepted", "resolved", "verified"}
HIGH_PRIORITIES = {"high", "critical", "blocker", "urgent"}

DEFAULT_DELIVERY_FIELD_NAMES = [
    "ALM_Delivery",
    "Delivery",
    "Release",
    "Target Release",
    "Fix Version",
    "Sprint",
]

DEFAULT_DELIVERY_DATE_FIELD_NAMES = [
    "Target Date",
    "Delivery Date",
    "Due Date",
    "Planned End Date",
    "End Date",
]

DEFAULT_REMAINING_FIELD_NAMES = [
    "Remaining",
    "Remaining Items",
    "Remaining Estimate",
    "Remaining Effort",
    "Story Points",
]

DEFAULT_BLOCKED_FIELD_NAMES = [
    "Blocked",
    "Is Blocked",
    "Blocker",
]

Transport = Literal["stdio", "sse", "streamable-http"]


def _csv_env(name: str, default: List[str]) -> List[str]:
    """Read a comma-separated environment variable as a list."""
    value = os.getenv(name)
    if not value:
        return default

    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class CodebeamerConfig:
    """Configuration for Codebeamer API access and output paths."""

    base_url: str
    token: Optional[str]
    username: Optional[str]
    password: Optional[str]
    timeout: float = 30.0
    verify_tls: bool = True
    page_size: int = 100
    max_pages: int = 25
    output_path: Path = Path("data/results/latest.json")
    receipt_path: Path = Path("data/receipts/latest.json")
    delivery_fields: List[str] = field(default_factory=list)
    delivery_date_fields: List[str] = field(default_factory=list)
    remaining_fields: List[str] = field(default_factory=list)
    blocked_fields: List[str] = field(default_factory=list)

    @staticmethod
    def from_env() -> "CodebeamerConfig":
        """Build Codebeamer configuration from environment variables."""
        base_url = os.getenv("CB_URL", "").rstrip("/")
        if not base_url:
            raise ValueError("CB_URL is required")

        return CodebeamerConfig(
            base_url=base_url,
            token=os.getenv("CB_TOKEN"),
            username=os.getenv("CB_USERNAME"),
            password=os.getenv("CB_PASSWORD"),
            timeout=float(os.getenv("CB_TIMEOUT", "30")),
            verify_tls=os.getenv("CB_VERIFY_TLS", "true").lower() not in {"0", "false", "no"},
            page_size=int(os.getenv("CB_PAGE_SIZE", "100")),
            max_pages=int(os.getenv("CB_MAX_PAGES", "25")),
            output_path=Path(os.getenv("CDYP7_OUTPUT", "data/results/latest.json")),
            receipt_path=Path(os.getenv("CDYP7_RECEIPT", "data/receipts/latest.json")),
            delivery_fields=_csv_env(
                "CB_DELIVERY_FIELDS",
                DEFAULT_DELIVERY_FIELD_NAMES,
            ),
            delivery_date_fields=_csv_env(
                "CB_DELIVERY_DATE_FIELDS",
                DEFAULT_DELIVERY_DATE_FIELD_NAMES,
            ),
            remaining_fields=_csv_env(
                "CB_REMAINING_FIELDS",
                DEFAULT_REMAINING_FIELD_NAMES,
            ),
            blocked_fields=_csv_env(
                "CB_BLOCKED_FIELDS",
                DEFAULT_BLOCKED_FIELD_NAMES,
            ),
        )


class CodebeamerClient:
    """Async Codebeamer REST client used by the MCP tools."""

    def __init__(self, config: CodebeamerConfig):
        self.config = config
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        elif config.username and config.password:
            raw = f"{config.username}:{config.password}".encode("utf-8")
            encoded = base64.b64encode(raw).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"
        else:
            raise ValueError("Provide CB_TOKEN or CB_USERNAME + CB_PASSWORD")

        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout,
            verify=config.verify_tls,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def get(self, path: str) -> Any:
        """Run a GET request and return decoded JSON."""
        response = await self.client.get(path)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, payload: Dict[str, Any]) -> Any:
        """Run a POST request and return decoded JSON."""
        response = await self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    async def query_items(
        self,
        query: str,
        page_size: Optional[int] = None,
        max_pages: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Query Codebeamer items using the API query endpoint."""
        resolved_page_size = page_size or self.config.page_size
        resolved_max_pages = max_pages or self.config.max_pages

        all_items: List[Dict[str, Any]] = []
        total = 0

        for page in range(1, resolved_max_pages + 1):
            payload = {
                "page": page,
                "pageSize": resolved_page_size,
                "queryString": query,
            }

            data = await self.post("/api/v3/items/query", payload)
            batch = data.get("items") or []
            total = int(data.get("total") or total or len(batch))
            all_items.extend(batch)

            if not batch:
                break

            if len(batch) < resolved_page_size:
                break

            if total and len(all_items) >= total:
                break

        return all_items, total or len(all_items)


def parse_transport(value: str) -> Transport:
    """Validate MCP transport mode."""
    allowed = {"stdio", "sse", "streamable-http"}
    if value not in allowed:
        raise ValueError(f"Invalid transport: {value}")

    return value  # type: ignore[return-value]


def _now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    """Normalize a string into a stable slug."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-") or "unassigned"


def _name(value: Any) -> str:
    """Return a display name from a Codebeamer value/reference."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, dict):
        for key in ("name", "label", "value"):
            if value.get(key) is not None:
                return str(value[key])

        if value.get("id") is not None:
            return str(value["id"])

    return str(value)


def _names(value: Any) -> List[str]:
    """Return display names from a Codebeamer list/reference field."""
    if value is None:
        return []

    if isinstance(value, list):
        return [name for name in (_name(item) for item in value) if name]

    name = _name(value)
    return [name] if name else []


def _custom_fields(fields: Any) -> Dict[str, Any]:
    """Convert Codebeamer customFields into a lookup dictionary."""
    result: Dict[str, Any] = {}

    if not isinstance(fields, list):
        return result

    for field_item in fields:
        if not isinstance(field_item, dict):
            continue

        key = str(field_item.get("name") or field_item.get("fieldId") or "unknown")

        if "value" in field_item:
            result[key] = field_item.get("value")
        elif "values" in field_item:
            result[key] = _names(field_item.get("values"))
        else:
            result[key] = None

    return result


def _first_present(data: Dict[str, Any], names: Iterable[str]) -> Any:
    """Return the first matching value from a case-insensitive lookup."""
    lookup = {str(key).lower(): value for key, value in data.items()}

    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]

    return None


def _boolish(value: Any) -> bool:
    """Interpret common truthy values as booleans."""
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return value != 0

    return str(value).strip().lower() in {
        "true",
        "yes",
        "1",
        "blocked",
        "blocker",
    }


def _number(value: Any, fallback: float = 0) -> float:
    """Parse a numeric value with fallback."""
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _is_closed(status: str) -> bool:
    """Return True if the status is considered closed."""
    return (status or "").strip().lower() in CLOSED_STATUSES


def normalize_item(
    item: Dict[str, Any],
    cfg: CodebeamerConfig,
) -> Dict[str, Any]:
    """Normalize a raw Codebeamer item to the CDYP7 dashboard shape."""
    custom = _custom_fields(item.get("customFields"))

    versions = _names(item.get("versions"))
    delivery_raw = (
        _first_present(custom, cfg.delivery_fields)
        or item.get("deliveryName")
        or item.get("release")
        or item.get("version")
        or (versions[0] if versions else None)
        or "Unassigned"
    )

    delivery_name = (
        delivery_raw[0]
        if isinstance(delivery_raw, list) and delivery_raw
        else _name(delivery_raw) or "Unassigned"
    )

    target_date = (
        _first_present(custom, cfg.delivery_date_fields)
        or item.get("targetDate")
        or item.get("dueDate")
        or item.get("plannedEndDate")
    )

    remaining_raw = _first_present(custom, cfg.remaining_fields)
    if remaining_raw is None:
        remaining_raw = item.get("remaining") or item.get("storyPoints") or 1

    owners = _names(item.get("assignedTo")) or _names(item.get("owner")) or ["Unassigned"]

    status = _name(item.get("status")) or "Unknown"
    priority = _name(item.get("priority")) or "Unspecified"
    tracker = _name(item.get("tracker")) or item.get("typeName") or "Unknown"
    blocked_raw = _first_present(custom, cfg.blocked_fields)

    item_id = item.get("id")

    return {
        "id": item_id,
        "title": (
            item.get("name") or item.get("title") or item.get("summary") or f"Item {item_id}"
        ),
        "deliveryId": _slug(str(delivery_name)),
        "deliveryName": delivery_name,
        "deliveryDate": target_date,
        "status": status,
        "priority": priority,
        "owners": owners,
        "owner": ", ".join(owners),
        "tracker": tracker,
        "type": item.get("typeName") or tracker,
        "dueDate": item.get("dueDate") or target_date,
        "remaining": _number(remaining_raw, 1),
        "blocked": _boolish(blocked_raw) or "block" in status.lower(),
        "modifiedAt": item.get("modifiedAt"),
        "createdAt": item.get("createdAt"),
        "url": item.get("url") or item.get("webUrl") or "",
        "customFields": custom,
        "rawRefs": {
            "children": _names(item.get("children")),
            "subjects": _names(item.get("subjects")),
            "versions": versions,
        },
    }


def build_deliveries(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build delivery summaries from normalized dashboard items."""
    grouped: Dict[str, Dict[str, Any]] = {}

    for item in items:
        key = item.get("deliveryId") or "unassigned"

        delivery = grouped.setdefault(
            key,
            {
                "id": key,
                "name": item.get("deliveryName") or "Unassigned",
                "deliveryDate": item.get("deliveryDate"),
                "totalItems": 0,
                "completedItems": 0,
                "remainingItems": 0,
            },
        )

        delivery["totalItems"] += 1

        if _is_closed(item.get("status", "")):
            delivery["completedItems"] += 1
        else:
            delivery["remainingItems"] += 1

        if not delivery.get("deliveryDate") and item.get("deliveryDate"):
            delivery["deliveryDate"] = item.get("deliveryDate")

    return sorted(
        grouped.values(),
        key=lambda delivery: delivery.get("deliveryDate") or "9999-12-31",
    )


def build_dashboard(
    items: List[Dict[str, Any]],
    query: str,
    total_reported: int,
) -> Dict[str, Any]:
    """Build the CDYP7 Codebeamer dashboard envelope."""
    by_status = Counter(item["status"] for item in items)
    by_priority = Counter(item["priority"] for item in items)
    by_tracker = Counter(item["tracker"] for item in items)
    by_owner: Dict[str, int] = defaultdict(int)

    for item in items:
        for owner in item.get("owners") or ["Unassigned"]:
            by_owner[owner] += 1

    open_items = [item for item in items if not _is_closed(item.get("status", ""))]

    return {
        "generatedAt": _now(),
        "source": "ptc-codebeamer",
        "authority": "non_authoritative",
        "receiptBacked": True,
        "query": query,
        "totalReportedByCodebeamer": total_reported,
        "deliveries": build_deliveries(items),
        "totals": {
            "items": len(items),
            "openItems": len(open_items),
            "remaining": sum(_number(item.get("remaining"), 1) for item in open_items),
            "atRisk": sum(
                1
                for item in open_items
                if item.get("blocked") or item.get("priority", "").lower() in HIGH_PRIORITIES
            ),
        },
        "breakdowns": {
            "status": dict(by_status),
            "priority": dict(by_priority),
            "tracker": dict(by_tracker),
            "owner": dict(
                sorted(
                    by_owner.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ),
        },
        "items": items,
    }


def build_receipt(
    tool: str,
    input_payload: Dict[str, Any],
    output_summary: Dict[str, Any],
    elapsed_ms: int,
) -> Dict[str, Any]:
    """Build a non-authoritative receipt envelope."""
    receipt_id = (
        f"rcpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_" f"{uuid.uuid4().hex[:8]}"
    )

    return {
        "receipt_id": receipt_id,
        "tool": tool,
        "source": "ptc-codebeamer",
        "authority": "non_authoritative",
        "receipt_backed": True,
        "semantic_verification_required": False,
        "human_approved": False,
        "generatedAt": _now(),
        "elapsedMs": elapsed_ms,
        "input": input_payload,
        "output": output_summary,
    }


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON data to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


async def _client() -> CodebeamerClient:
    """Create a configured Codebeamer client."""
    return CodebeamerClient(CodebeamerConfig.from_env())


@mcp.tool()
async def cdyp7_cb_projects() -> Dict[str, Any]:
    """List accessible PTC Codebeamer projects."""
    started = time.time()
    client = await _client()

    try:
        projects = await client.get("/api/v3/projects")

        if isinstance(projects, dict) and "items" in projects:
            projects_list = projects["items"]
        else:
            projects_list = projects if isinstance(projects, list) else []

        result = [
            {"id": project.get("id"), "name": project.get("name")}
            for project in projects_list
            if isinstance(project, dict)
        ]

        elapsed = int((time.time() - started) * 1000)

        return {
            "status": "ok",
            "authority": "non_authoritative",
            "receipt": build_receipt(
                "cdyp7.cb.projects",
                {},
                {"projects": len(result)},
                elapsed,
            ),
            "projects": result,
        }
    finally:
        await client.close()


@mcp.tool()
async def cdyp7_cb_query_items(
    query: str = "status != 'Closed'",
    page_size: int = 100,
    max_pages: int = 10,
) -> Dict[str, Any]:
    """Query PTC Codebeamer tracker items."""
    started = time.time()
    client = await _client()
    cfg = client.config

    try:
        raw_items, total = await client.query_items(
            query,
            page_size=page_size,
            max_pages=max_pages,
        )
        items = [normalize_item(item, cfg) for item in raw_items]
        elapsed = int((time.time() - started) * 1000)

        receipt = build_receipt(
            "cdyp7.cb.query_items",
            {
                "query": query,
                "page_size": page_size,
                "max_pages": max_pages,
            },
            {
                "items": len(items),
                "totalReported": total,
            },
            elapsed,
        )

        return {
            "status": "ok",
            "authority": "non_authoritative",
            "receiptBacked": True,
            "receiptId": receipt["receipt_id"],
            "receipt": receipt,
            "items": items,
            "totalReportedByCodebeamer": total,
        }
    finally:
        await client.close()


@mcp.tool()
async def cdyp7_cb_dashboard(
    query: str = "status != 'Closed'",
    page_size: int = 100,
    max_pages: int = 25,
    persist: bool = True,
) -> Dict[str, Any]:
    """Build the CDYP7 dashboard state from PTC Codebeamer."""
    started = time.time()
    client = await _client()
    cfg = client.config

    try:
        raw_items, total = await client.query_items(
            query,
            page_size=page_size,
            max_pages=max_pages,
        )
        normalized = [normalize_item(item, cfg) for item in raw_items]
        dashboard = build_dashboard(normalized, query, total)
        elapsed = int((time.time() - started) * 1000)

        receipt = build_receipt(
            "cdyp7.cb.dashboard",
            {
                "query": query,
                "page_size": page_size,
                "max_pages": max_pages,
                "persist": persist,
            },
            {
                "items": dashboard["totals"]["items"],
                "openItems": dashboard["totals"]["openItems"],
                "deliveries": len(dashboard["deliveries"]),
            },
            elapsed,
        )
        dashboard["receiptId"] = receipt["receipt_id"]

        if persist:
            _write_json(cfg.output_path, dashboard)
            _write_json(cfg.receipt_path, receipt)

        return dashboard
    finally:
        await client.close()


@mcp.resource("cdyp7://dashboard/latest")
def latest_dashboard() -> str:
    """Return the last persisted CDYP7 dashboard JSON state."""
    path = Path(os.getenv("CDYP7_OUTPUT", "data/results/latest.json"))

    if not path.exists():
        return json.dumps({"error": "No dashboard state has been generated yet."})

    return path.read_text(encoding="utf-8")


@mcp.resource("cdyp7://receipts/latest")
def latest_receipt() -> str:
    """Return the last persisted CDYP7 dashboard receipt."""
    path = Path(os.getenv("CDYP7_RECEIPT", "data/receipts/latest.json"))

    if not path.exists():
        return json.dumps({"error": "No receipt has been generated yet."})

    return path.read_text(encoding="utf-8")


@mcp.prompt()
def dashboard_triage_prompt() -> str:
    """Prompt template for reviewing dashboard risk and delivery health."""
    return (
        "Review the latest CDYP7 Codebeamer dashboard state. "
        "Focus on open items, ALM_Delivery grouping, Target Date risk, "
        "assignedTo ownership load, blocked items, and high-priority items. "
        "Summarize risks and recommended follow-up actions."
    )


if __name__ == "__main__":
    transport = parse_transport(os.getenv("MCP_TRANSPORT", "stdio"))
    mcp.run(transport=transport)
