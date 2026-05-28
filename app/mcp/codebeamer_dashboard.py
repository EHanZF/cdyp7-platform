"""Codebeamer dashboard normalization and aggregation utilities."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import requests

from app.mcp.codebeamer_fields import (
    custom_fields_to_map,
    name_of,
    names_of,
)

REQUEST_TIMEOUT = 30


def require_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def codebeamer_headers() -> dict[str, str]:
    """Build Codebeamer request headers from environment configuration."""
    token = require_env("CB_TOKEN")

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw Codebeamer item into the CDYP7 dashboard contract."""
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "tracker": name_of(item.get("tracker")),
        "typeName": item.get("typeName"),
        "status": name_of(item.get("status")),
        "priority": name_of(item.get("priority")),
        "assignedTo": names_of(item.get("assignedTo")),
        "storyPoints": item.get("storyPoints"),
        "createdAt": item.get("createdAt"),
        "modifiedAt": item.get("modifiedAt"),
        "versions": names_of(item.get("versions")),
        "subjects": names_of(item.get("subjects")),
        "children": names_of(item.get("children")),
        "customFields": custom_fields_to_map(item.get("customFields")),
    }


def fetch_codebeamer_items(
    query_string: str,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Fetch Codebeamer tracker items using the configured query string."""
    base_url = require_env("CB_URL")
    url = f"{base_url}/api/v3/items/query"

    payload: dict[str, Any] = {
        "page": 1,
        "pageSize": page_size,
        "queryString": query_string,
    }

    response = requests.post(
        url,
        json=payload,
        headers=codebeamer_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    data: dict[str, Any] = response.json()
    items = data.get("items", [])

    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def count_statuses(
    by_status: Counter[str],
    matching_statuses: set[str],
) -> int:
    """Count items whose status appears in a target status set."""
    return sum(count for status, count in by_status.items() if status.lower() in matching_statuses)


def count_priorities(
    by_priority: Counter[str],
    matching_priorities: set[str],
) -> int:
    """Count items whose priority appears in a target priority set."""
    return sum(
        count for priority, count in by_priority.items() if priority.lower() in matching_priorities
    )


def build_dashboard(query_string: str) -> dict[str, Any]:
    """Build the receipt-backed ALM dashboard state for the React frontend."""
    raw_items = fetch_codebeamer_items(query_string)
    items = [normalize_item(item) for item in raw_items]

    by_status: Counter[str] = Counter(str(item.get("status") or "Unknown") for item in items)
    by_priority: Counter[str] = Counter(str(item.get("priority") or "Unknown") for item in items)
    by_tracker: Counter[str] = Counter(str(item.get("tracker") or "Unknown") for item in items)

    open_count = count_statuses(
        by_status,
        {"new", "open", "draft"},
    )
    in_progress_count = count_statuses(
        by_status,
        {"in progress", "in review", "review"},
    )
    closed_count = count_statuses(
        by_status,
        {"closed", "done", "resolved", "accepted"},
    )
    high_priority_count = count_priorities(
        by_priority,
        {"high", "critical", "blocker"},
    )

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "codebeamer",
        "authority": "non_authoritative",
        "receiptBacked": True,
        "query": query_string,
        "totals": {
            "items": len(items),
            "open": open_count,
            "inProgress": in_progress_count,
            "closed": closed_count,
            "highPriority": high_priority_count,
        },
        "byStatus": dict(by_status),
        "byPriority": dict(by_priority),
        "byTracker": dict(by_tracker),
        "items": items,
    }
