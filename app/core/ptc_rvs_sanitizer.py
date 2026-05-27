import re
from typing import Any, Mapping

FORBIDDEN_KEY_PATTERNS = [
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r".*token.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r".*cookie.*", re.IGNORECASE),
    re.compile(r".*session.*", re.IGNORECASE),
    re.compile(r".*auth.*", re.IGNORECASE),
]

ITEM_OUTPUT_FIELDS = {
    "id",
    "type",
    "summary",
    "state",
    "owner",
    "priority",
    "modified_at",
    "created_at",
    "release",
    "variant",
    "trace_status",
    "requirement_id",
    "test_case_id",
    "test_result_id",
    "category",
    "alm_item_number",
    "linked_alm_number",
    "alm_delivery",
    "alm_delivery_source",
    "alm_delivery_linked_item_number",
    "alm_delivery_lookup_status",
    "alm_delivery_lookup_error_type",
    "alm_delivery_lookup_redaction_applied"

}

PROJECT_OUTPUT_FIELDS = {"id", "name", "description", "state", "type"}


def is_forbidden_key(key: str) -> bool:
    return any(pattern.match(key) for pattern in FORBIDDEN_KEY_PATTERNS)


def sanitize_payload(value: Any) -> tuple[Any, bool]:
    """Recursively redact sensitive-looking keys instead of hard-failing."""
    redaction_applied = False

    def _sanitize(node: Any) -> Any:
        nonlocal redaction_applied
        if isinstance(node, dict):
            sanitized: dict[str, Any] = {}
            for key, val in node.items():
                if is_forbidden_key(str(key)):
                    sanitized[key] = "__REDACTED__"
                    redaction_applied = True
                else:
                    sanitized[key] = _sanitize(val)
            return sanitized
        if isinstance(node, list):
            return [_sanitize(item) for item in node]
        return node

    return _sanitize(value), redaction_applied


def project_from_field_map(raw: Mapping[str, Any], project_field_map: Mapping[str, str]) -> dict[str, Any]:
    """Normalize a raw RV&S project into stable CDYP7 project fields."""
    return {
        output_name: raw.get(source_name)
        for output_name, source_name in project_field_map.items()
        if output_name in PROJECT_OUTPUT_FIELDS and source_name in raw
    }


def item_from_field_map(raw: Mapping[str, Any], rvs_field_map: Mapping[str, str]) -> dict[str, Any]:
    """Normalize a raw RV&S item into stable CDYP7 item fields."""
    return {
        output_name: raw.get(source_name)
        for output_name, source_name in rvs_field_map.items()
        if output_name in ITEM_OUTPUT_FIELDS and source_name in raw
    }
