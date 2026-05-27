import time

from app.core.ptc_rvs_store import clear_context_store, get_context, put_context


def test_context_resource_expires_after_ttl():
    clear_context_store()
    context_id = put_context({"hello": "world"}, ttl_seconds=0)
    time.sleep(0.01)
    assert get_context(context_id) is None
