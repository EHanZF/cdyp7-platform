"""Shared Codebeamer field normalization helpers."""

from typing import Any


def name_of(value: Any) -> str:
    """Return a display name from a Codebeamer value or reference object."""
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


def names_of(values: Any) -> list:
    """Return display names from a Codebeamer list/reference field."""
    if values is None:
        return []

    if isinstance(values, list):
        return [name for name in (name_of(value) for value in values) if name]

    one = name_of(values)

    return [one] if one else []


def custom_fields_to_map(fields: Any) -> dict[str, Any]:
    """Normalize Codebeamer customFields into a field-name dictionary."""
    result: dict[str, Any] = {}

    if not isinstance(fields, list):
        return result

    for field in fields:
        if not isinstance(field, dict):
            continue

        key = str(field.get("name") or field.get("fieldId") or "unknown")

        if "value" in field:
            result[key] = field.get("value")
        elif "values" in field:
            result[key] = names_of(field.get("values"))
        else:
            result[key] = None

    return result
