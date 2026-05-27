import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.ptc_rvs_routes import router


def test_unauthorized_caller_rejected_for_dev_header_gate():
    async def run_test():
        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/context/ptc-rvs/bootstrap", json={"query_name": "active_items"})
        assert response.status_code == 403

    asyncio.run(run_test())
