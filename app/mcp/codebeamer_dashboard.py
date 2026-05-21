"""Codebeamer dashboard normalization and aggregation utilities."""

import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import requests

from app.mcp.codebeamer_fields import custom_fields_to_map, name_of, names_of

CB_URL = os.getenv("CB_URL")
CB_TOKEN = os.getenv("CB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {CB_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 30


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw Codebeamer item into the CDYP7 ALM dashboard contract."""
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
    url = f"{CB_URL}/api/v3/items/query"

    payload = {
        "page": 1,
        "pageSize": page_size,
        "queryString": query_string,
    }

    response = requests.post(
        url,
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    data = response.json()

    return data.get("items", [])


def build_dashboard(query_string: str) -> dict[str, Any]:
    """Build the receipt-backed ALM dashboard state for the React frontend."""
    raw_items = fetch_codebeamer_items(query_string)
    items = [normalize_item(item) for item in raw_items]

    by_status = Counter(item.get("status") or "Unknown" for item in items)
    by_priority = Counter(item.get("priority") or "Unknown" for item in items)
    by_tracker = Counter(item.get("tracker") or "Unknown" for item in items)

    open_count = sum(
        count for status, count in by_status.items() if status.lower() in ["new", "open", "draft"]
    )

    in_progress_count = sum(
        count
        for status, count in by_status.items()
        if status.lower() in ["in progress", "in review", "review"]
    )

    closed_count = sum(
        count
        for status, count in by_status.items()
        if status.lower() in ["closed", "done", "resolved", "accepted"]
    )

    high_priority_count = sum(
        count
        for priority, count in by_priority.items()
        if priority.lower() in ["high", "critical", "blocker"]
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
