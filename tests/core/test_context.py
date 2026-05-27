import asyncio

from app.core.ptc_rvs_context import BOUNDARY_CONTRACT, PtcRvsContextRequest, build_ptc_rvs_context
from app.core.ptc_rvs_store import clear_context_store
from app.core.ptc_rvs_context import derive_alm_delivery


def test_alm_delivery_derived_from_linked_alm_number():
    item = {
        "linked_alm_number": "CR-12345",
    }

    assert derive_alm_delivery(item) == "CR-12345"


def test_alm_delivery_prefers_explicit_field():
    item = {
        "alm_delivery": "DEL-999",
        "linked_alm_number": "CR-12345",
    }

    assert derive_alm_delivery(item) == "DEL-999"


def test_alm_delivery_falls_back_to_alm_item_number():
    item = {
        "alm_item_number": "TASK-456",
    }

    assert derive_alm_delivery(item) == "TASK-456"


class FakeRvsClient:
    async def get_projects(self):
        return [
            {"id": "P1", "name": "One"},
            {"id": "P2", "name": "Two"},
            {"id": "P3", "name": "Three"},
        ]

    async def get_items(self, query: str, limit: int):
        assert "state!=Closed" in query
        assert limit == 3
        return [
            {"ID": "1", "summary": "High", "priority": "High", "traceStatus": "Linked"},
            {"ID": "2", "summary": "Unlinked", "priority": "Low", "traceStatus": "Unlinked"},
            {"ID": "3", "summary": "Truncate", "priority": "Low", "traceStatus": "MissingResult"},
        ]


def test_max_items_max_projects_receipt_and_boundary_contract():
    async def run_test():
        clear_context_store()
        body = PtcRvsContextRequest(query_name="active_items", max_items=2, max_projects=2)
        response = await build_ptc_rvs_context(body, FakeRvsClient(), correlation_id="corr-test")

        assert response.status == "success"
        assert response.receipt.boundary_contract == BOUNDARY_CONTRACT
        assert response.receipt.limits.returned_items == 2
        assert response.receipt.limits.returned_projects == 2
        assert response.receipt.limits.items_truncated is True
        assert response.receipt.limits.projects_truncated is True
        assert response.context["summary"]["high_priority_count"] == 1
        assert response.context["summary"]["unlinked_requirement_count"] == 1

    asyncio.run(run_test())
