import pytest

from app.core.ptc_rvs_templates import resolve_query


def test_query_template_unknown_name_rejected():
    with pytest.raises(ValueError):
        resolve_query("state=Closed")


def test_arbitrary_query_not_accepted():
    with pytest.raises(ValueError):
        resolve_query("state!=Closed AND priority=High")


def test_release_variant_literals_escaped():
    query = resolve_query("active_items", release_id='R-"123', variant_id='V\\A')
    assert 'releaseId="R-\\"123"' in query
    assert 'variantId="V\\\\A"' in query
