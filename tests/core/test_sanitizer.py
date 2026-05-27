from app.core.ptc_rvs_sanitizer import item_from_field_map, project_from_field_map, sanitize_payload
from app.core.ptc_rvs_templates import PROJECT_FIELD_MAP, RVS_FIELD_MAP


def test_forbidden_secret_keys_redacted():
    payload = {"id": 1, "nested": {"sessionToken": "abc", "safe": "ok"}}
    sanitized, redacted = sanitize_payload(payload)
    assert redacted is True
    assert sanitized["nested"]["sessionToken"] == "__REDACTED__"
    assert sanitized["nested"]["safe"] == "ok"


def test_project_allowlist_applied():
    raw = {"id": "P1", "name": "Project", "password": "bad", "extra": "drop"}
    sanitized, _ = sanitize_payload(raw)
    normalized = project_from_field_map(sanitized, PROJECT_FIELD_MAP)
    assert normalized == {"id": "P1", "name": "Project"}


def test_item_allowlist_applied():
    raw = {"ID": "123", "summary": "Hello", "token": "bad", "unknown": "drop"}
    sanitized, _ = sanitize_payload(raw)
    normalized = item_from_field_map(sanitized, RVS_FIELD_MAP)
    assert normalized == {"id": "123", "summary": "Hello"}
