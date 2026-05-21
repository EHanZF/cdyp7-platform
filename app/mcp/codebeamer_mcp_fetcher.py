#!/usr/bin/env python3
"""
CDYP7 MCP Codebeamer Dashboard Fetcher.

Fetch Codebeamer ALM tracker items through the Codebeamer REST API v3,
normalize them into the JSON contract expected by the CDYP7 dashboard,
and write:

- data/results/latest.json
- data/receipts/latest.json

The module can also run as a tiny local HTTP endpoint for the dashboard app:

- GET /api/codebeamer/dashboard

Security boundary:
Do not run this in the browser. Keep CB_TOKEN, CB_USERNAME, and CB_PASSWORD
in GitHub Actions secrets, a backend proxy, or a trusted MCP runner.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from app.mcp.codebeamer_fields import custom_fields_to_map, name_of, names_of

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=too-many-instance-attributes
# pylint: disable=arguments-differ
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code


try:
    import requests
except ImportError as exc:
    raise SystemExit("Missing dependency: requests. Install with: pip install requests") from exc


DEFAULT_CLOSED_STATUSES = {
    "closed",
    "done",
    "accepted",
    "resolved",
    "verified",
}

DEFAULT_IN_PROGRESS_STATUSES = {
    "in progress",
    "implementation",
    "review",
    "in review",
    "testing",
}

DEFAULT_HIGH_PRIORITIES = {
    "high",
    "critical",
    "blocker",
    "urgent",
}

DEFAULT_DELIVERY_FIELD_NAMES = [
    "Delivery",
    "Release",
    "Target Release",
    "Fix Version",
    "Version",
    "Sprint",
    "Iteration",
]

DEFAULT_DELIVERY_DATE_FIELD_NAMES = [
    "Delivery Date",
    "Target Date",
    "Due Date",
    "Planned End Date",
    "Planned Release Date",
    "End Date",
]

DEFAULT_REMAINING_FIELD_NAMES = [
    "Remaining",
    "Remaining Items",
    "Remaining Estimate",
    "Remaining Effort",
    "Story Points",
    "Points Remaining",
]

DEFAULT_BLOCKED_FIELD_NAMES = [
    "Blocked",
    "Is Blocked",
    "Blocker",
]


@dataclass
class Config:
    cb_url: str
    cb_token: str | None
    cb_username: str | None
    cb_password: str | None
    query: str
    page_size: int
    max_pages: int
    output_path: Path
    receipt_path: Path
    verify_tls: bool
    timeout: int
    delivery_field_names: list[str]
    delivery_date_field_names: list[str]
    remaining_field_names: list[str]
    blocked_field_names: list[str]

    @classmethod
    def from_env(cls, args: argparse.Namespace) -> "Config":
        cb_url = args.cb_url or os.getenv("CB_URL", "").rstrip("/")

        if not cb_url:
            raise SystemExit("CB_URL is required, e.g. https://codebeamer.example.com")

        query = args.query or os.getenv("CB_QUERY", "status != 'Closed'")
        output_path = Path(args.output or os.getenv("CDYP7_OUTPUT", "data/results/latest.json"))
        receipt_path = Path(args.receipt or os.getenv("CDYP7_RECEIPT", "data/receipts/latest.json"))

        return cls(
            cb_url=cb_url,
            cb_token=args.cb_token or os.getenv("CB_TOKEN"),
            cb_username=args.cb_username or os.getenv("CB_USERNAME"),
            cb_password=args.cb_password or os.getenv("CB_PASSWORD"),
            query=query,
            page_size=int(args.page_size or os.getenv("CB_PAGE_SIZE", "100")),
            max_pages=int(args.max_pages or os.getenv("CB_MAX_PAGES", "25")),
            output_path=output_path,
            receipt_path=receipt_path,
            verify_tls=str(os.getenv("CB_VERIFY_TLS", "true")).lower() not in {"0", "false", "no"},
            timeout=int(os.getenv("CB_TIMEOUT", "30")),
            delivery_field_names=csv_env(
                "CB_DELIVERY_FIELDS",
                DEFAULT_DELIVERY_FIELD_NAMES,
            ),
            delivery_date_field_names=csv_env(
                "CB_DELIVERY_DATE_FIELDS",
                DEFAULT_DELIVERY_DATE_FIELD_NAMES,
            ),
            remaining_field_names=csv_env(
                "CB_REMAINING_FIELDS",
                DEFAULT_REMAINING_FIELD_NAMES,
            ),
            blocked_field_names=csv_env(
                "CB_BLOCKED_FIELDS",
                DEFAULT_BLOCKED_FIELD_NAMES,
            ),
        )


def csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)

    if not value:
        return default

    return [item.strip() for item in value.split(",") if item.strip()]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    normalized = re.sub(
        r"[^a-zA-Z0-9]+",
        "-",
        value.strip().lower(),
    ).strip("-")

    return normalized or "unassigned"


def parse_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return value != 0

    return str(value).strip().lower() in {
        "true",
        "yes",
        "y",
        "1",
        "blocked",
        "blocker",
    }


def first_present(data: dict[str, Any], names: Iterable[str]) -> Any:
    lower_map = {str(key).strip().lower(): value for key, value in data.items()}

    for name in names:
        key = name.strip().lower()

        if key in lower_map:
            return lower_map[key]

    return None


def safe_number(value: Any, fallback: float = 0) -> float:
    try:
        if value is None or value == "":
            return fallback

        return float(value)

    except (TypeError, ValueError):
        return fallback


class CodebeamerClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        if config.cb_token:
            self.session.headers.update({"Authorization": f"Bearer {config.cb_token}"})
        elif config.cb_username and config.cb_password:
            raw = f"{config.cb_username}:{config.cb_password}".encode("utf-8")
            token = base64.b64encode(raw).decode("ascii")
            self.session.headers.update({"Authorization": f"Basic {token}"})
        else:
            raise SystemExit("Provide CB_TOKEN or CB_USERNAME + CB_PASSWORD")

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.cb_url}{path}"
        response = self.session.post(
            url,
            json=payload,
            timeout=self.config.timeout,
            verify=self.config.verify_tls,
        )
        response.raise_for_status()

        return response.json()

    def query_items(self, query_string: str) -> tuple[list[dict[str, Any]], int]:
        all_items: list[dict[str, Any]] = []
        total = 0

        for page in range(1, self.config.max_pages + 1):
            payload = {
                "page": page,
                "pageSize": self.config.page_size,
                "queryString": query_string,
            }

            data = self.post("/api/v3/items/query", payload)
            total = int(data.get("total") or total or 0)
            batch = data.get("items") or []

            if not batch:
                break

            all_items.extend(batch)

            if total and len(all_items) >= total:
                break

            if len(batch) < self.config.page_size:
                break

        return all_items, total or len(all_items)


def normalize_item(item: dict[str, Any], config: Config) -> dict[str, Any]:
    custom = custom_fields_to_map(item.get("customFields"))

    version_names = names_of(item.get("versions"))
    delivery_value = (
        first_present(custom, config.delivery_field_names)
        or item.get("deliveryName")
        or item.get("release")
        or item.get("version")
        or (version_names[0] if version_names else None)
        or "Unassigned"
    )

    if isinstance(delivery_value, list):
        delivery_name = delivery_value[0] if delivery_value else "Unassigned"
    else:
        delivery_name = name_of(delivery_value) or "Unassigned"

    delivery_date = (
        first_present(custom, config.delivery_date_field_names)
        or item.get("deliveryDate")
        or item.get("dueDate")
        or item.get("plannedEndDate")
        or item.get("targetDate")
    )

    remaining_value = first_present(custom, config.remaining_field_names)

    if remaining_value is None:
        remaining_value = item.get("remaining")

    if remaining_value is None:
        remaining_value = item.get("storyPoints")

    if remaining_value is None:
        remaining_value = 1

    blocked_value = first_present(custom, config.blocked_field_names)

    owners = names_of(item.get("assignedTo") or item.get("owners") or item.get("assignees"))

    if not owners and item.get("owner"):
        owners = names_of(item.get("owner"))

    item_id = item.get("id")
    status = name_of(item.get("status")) or "Unknown"
    priority = name_of(item.get("priority")) or "Unspecified"
    tracker = name_of(item.get("tracker")) or item.get("typeName") or item.get("type") or "Unknown"

    return {
        "id": item_id,
        "title": (
            item.get("name") or item.get("title") or item.get("summary") or f"Item {item_id}"
        ),
        "deliveryId": slug(str(delivery_name)),
        "deliveryName": delivery_name,
        "deliveryDate": delivery_date,
        "status": status,
        "priority": priority,
        "owners": owners or ["Unassigned"],
        "owner": ", ".join(owners) if owners else "Unassigned",
        "tracker": tracker,
        "type": item.get("typeName") or tracker,
        "dueDate": item.get("dueDate") or delivery_date,
        "remaining": safe_number(remaining_value, 1),
        "blocked": parse_boolish(blocked_value) or "block" in status.lower(),
        "modifiedAt": item.get("modifiedAt"),
        "createdAt": item.get("createdAt"),
        "url": item.get("url") or item.get("webUrl") or "",
        "customFields": custom,
        "rawRefs": {
            "children": names_of(item.get("children")),
            "subjects": names_of(item.get("subjects")),
            "versions": version_names,
        },
    }


def is_closed(status: str) -> bool:
    return (status or "").strip().lower() in DEFAULT_CLOSED_STATUSES


def build_deliveries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

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

        if is_closed(item.get("status", "")):
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
    raw_items: list[dict[str, Any]],
    total_reported: int,
    config: Config,
) -> dict[str, Any]:
    items = [normalize_item(item, config) for item in raw_items]

    by_status = Counter(item["status"] for item in items)
    by_priority = Counter(item["priority"] for item in items)
    by_tracker = Counter(item["tracker"] for item in items)
    by_owner: dict[str, int] = defaultdict(int)

    for item in items:
        for owner in item.get("owners") or ["Unassigned"]:
            by_owner[owner] += 1

    open_items = [item for item in items if not is_closed(item.get("status", ""))]

    remaining_sum = sum(safe_number(item.get("remaining"), 1) for item in open_items)

    at_risk = sum(
        1
        for item in open_items
        if item.get("blocked") or item.get("priority", "").lower() in DEFAULT_HIGH_PRIORITIES
    )

    return {
        "generatedAt": utc_now(),
        "source": "codebeamer",
        "authority": "non_authoritative",
        "receiptBacked": True,
        "query": config.query,
        "totalReportedByCodebeamer": total_reported,
        "deliveries": build_deliveries(items),
        "totals": {
            "items": len(items),
            "openItems": len(open_items),
            "remaining": remaining_sum,
            "atRisk": at_risk,
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
    config: Config,
    dashboard: dict[str, Any],
    started_at: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    receipt_id = f"rcpt_{timestamp}_{uuid.uuid4().hex[:8]}"

    return {
        "receipt_id": receipt_id,
        "tool": "cdyp7.cb.dashboard.fetch",
        "source": "codebeamer",
        "authority": "non_authoritative",
        "receipt_backed": True,
        "semantic_verification_required": False,
        "human_approved": False,
        "startedAt": started_at,
        "generatedAt": utc_now(),
        "elapsedMs": elapsed_ms,
        "input": {
            "query": config.query,
            "pageSize": config.page_size,
            "maxPages": config.max_pages,
        },
        "output": {
            "items": dashboard.get("totals", {}).get("items"),
            "openItems": dashboard.get("totals", {}).get("openItems"),
            "deliveries": len(dashboard.get("deliveries", [])),
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def fetch_once(config: Config) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = utc_now()
    start = time.time()
    client = CodebeamerClient(config)
    raw_items, total = client.query_items(config.query)
    dashboard = build_dashboard(raw_items, total, config)
    elapsed_ms = int((time.time() - start) * 1000)
    receipt = build_receipt(config, dashboard, started_at, elapsed_ms)
    dashboard["receiptId"] = receipt["receipt_id"]

    write_json(config.output_path, dashboard)
    write_json(config.receipt_path, receipt)

    return dashboard, receipt


class DashboardHandler(BaseHTTPRequestHandler):
    config: Config
    cache: dict[str, Any] = {
        "data": None,
        "receipt": None,
        "updated": 0,
        "error": None,
    }
    ttl_seconds: int = 30

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/api/codebeamer/dashboard":
            self.send_response(404)
            self._cors()
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        try:
            now = time.time()

            if not self.cache["data"] or now - self.cache["updated"] > self.ttl_seconds:
                data, receipt = fetch_once(self.config)
                self.cache.update(
                    {
                        "data": data,
                        "receipt": receipt,
                        "updated": now,
                        "error": None,
                    }
                )

            self._json(200, self.cache["data"])

        except Exception as exc:
            self.cache["error"] = str(exc)
            self._json(
                502,
                {
                    "error": "Codebeamer dashboard fetch failed",
                    "detail": str(exc),
                    "generatedAt": utc_now(),
                },
            )

    def _json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> None:
        origin = os.getenv("CDYP7_CORS_ORIGIN", "*")

        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization",
        )

    def log_message(  # pylint: disable=redefined-builtin
        self,
        format: str,
        *args: Any,
    ) -> None:
        message = format % args
        timestamp = self.log_date_time_string()
        sys.stderr.write(f"[{timestamp}] {message}\n")


def serve(config: Config, host: str, port: int, ttl: int) -> None:
    DashboardHandler.config = config
    DashboardHandler.ttl_seconds = ttl
    server = ThreadingHTTPServer((host, port), DashboardHandler)

    print(
        "Serving CDYP7 Codebeamer dashboard endpoint at "
        f"http://{host}:{port}/api/codebeamer/dashboard"
    )

    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Codebeamer ALM data for the CDYP7 dashboard"
    )
    sub = parser.add_subparsers(dest="command")

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--cb-url",
            help="Codebeamer base URL, e.g. https://cb.example.com",
        )
        subparser.add_argument(
            "--cb-token",
            help="Codebeamer bearer token. Prefer CB_TOKEN env var.",
        )
        subparser.add_argument(
            "--cb-username",
            help="Codebeamer username. Prefer CB_USERNAME env var.",
        )
        subparser.add_argument(
            "--cb-password",
            help="Codebeamer password. Prefer CB_PASSWORD env var.",
        )
        subparser.add_argument("--query", help="CbQL query string")
        subparser.add_argument("--page-size", type=int, help="Codebeamer page size")
        subparser.add_argument("--max-pages", type=int, help="Maximum pages to fetch")
        subparser.add_argument("--output", help="Dashboard JSON output path")
        subparser.add_argument("--receipt", help="Receipt JSON output path")

    fetch_parser = sub.add_parser("fetch", help="Fetch once and write JSON files")
    add_common(fetch_parser)

    serve_parser = sub.add_parser(
        "serve",
        help="Serve /api/codebeamer/dashboard for the dashboard app",
    )
    add_common(serve_parser)
    serve_parser.add_argument(
        "--host",
        default=os.getenv("CDYP7_HOST", "127.0.0.1"),
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CDYP7_PORT", "8787")),
    )
    serve_parser.add_argument(
        "--ttl",
        type=int,
        default=int(os.getenv("CDYP7_CACHE_TTL", "30")),
    )

    args = parser.parse_args()

    if not args.command:
        args.command = "fetch"

    return args


def main() -> None:
    args = parse_args()
    config = Config.from_env(args)

    if args.command == "serve":
        serve(config, args.host, args.port, args.ttl)
        return

    dashboard, receipt = fetch_once(config)

    print(
        json.dumps(
            {
                "ok": True,
                "items": len(dashboard["items"]),
                "receipt_id": receipt["receipt_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
