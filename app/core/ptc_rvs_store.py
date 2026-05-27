import hashlib
import time
import uuid
from typing import Any

_CONTEXT_STORE: dict[str, dict[str, Any]] = {}
DEFAULT_CONTEXT_TTL_SECONDS = 15 * 60


def put_context(context: dict[str, Any], ttl_seconds: int = DEFAULT_CONTEXT_TTL_SECONDS) -> str:
    context_id = hashlib.sha256(f"{uuid.uuid4()}:{time.time()}".encode("utf-8")).hexdigest()[:32]
    _CONTEXT_STORE[context_id] = {
        "created_at": time.time(),
        "ttl_seconds": ttl_seconds,
        "context": context,
    }
    return context_id


def get_context(context_id: str) -> dict[str, Any] | None:
    record = _CONTEXT_STORE.get(context_id)
    if not record:
        return None
    if time.time() - record["created_at"] > record["ttl_seconds"]:
        _CONTEXT_STORE.pop(context_id, None)
        return None
    return record["context"]


def cleanup_context_store() -> None:
    now = time.time()
    expired = [
        context_id
        for context_id, record in _CONTEXT_STORE.items()
        if now - record["created_at"] > record["ttl_seconds"]
    ]
    for context_id in expired:
        _CONTEXT_STORE.pop(context_id, None)


def clear_context_store() -> None:
    _CONTEXT_STORE.clear()
