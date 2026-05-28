"""PTC RV&S payload sanitization utilities.

These helpers remove secret-bearing and unsafe fields before data is exposed
through the CDYP7 gateway or MCP adapter.
"""

from __future__ import annotations

from typing import Any, cast

SECRET_KEYS = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "apikey",
    "secret",
    "client_secret",
}

FORBIDDEN_KEYS = {
    "policy_override",
    "release_override",
    "receipt_override",
    "hitl_override",
    "authority_override",
}


def _is_forbidden_key(key: str) -> bool:
    """Return True if a field name must be removed."""
    normalized = key.strip().lower()
    return normalized in SECRET_KEYS or normalized in FORBIDDEN_KEYS


def _redact_value(key: str, value: Any) -> Any:
    """Redact or recursively sanitize a value."""
    if _is_forbidden_key(key):
        return "***REDACTED***"

    if isinstance(value, dict):
        return sanitize_payload(value)

    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]

    return value


def sanitize_payload(payload: Any) -> Any:
    """Sanitize dictionaries, lists, and primitive payload values."""
    if isinstance(payload, dict):
        return {
            key: _redact_value(str(key), value)
            for key, value in payload.items()
            if not _is_forbidden_key(str(key))
        }

    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]

    return payload


def item_from_field_map(
    field_map: dict[str, Any],
    *_args: Any,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Build a sanitized item dictionary from an RV&S field map."""
    item = {
        "id": field_map.get("ID") or field_map.get("Id"),
        "summary": field_map.get("Summary"),
        "state": field_map.get("State"),
        "assignedUser": field_map.get("Assigned User"),
        "type": field_map.get("Type"),
        "priority": field_map.get("Priority"),
        "delivery": field_map.get("ALM_Delivery"),
        "targetDate": field_map.get("Target Date"),
        "rawFields": field_map,
    }
    return cast(dict[str, Any], sanitize_payload(item))


def project_from_field_map(
    field_map: dict[str, Any],
    *_args: Any,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Build a sanitized project dictionary from an RV&S field map."""
    project = {
        "id": field_map.get("Project ID") or field_map.get("Project"),
        "name": field_map.get("Project Name") or field_map.get("Project"),
        "delivery": field_map.get("ALM_Delivery"),
        "rawFields": field_map,
    }
    return cast(dict[str, Any], sanitize_payload(project))
