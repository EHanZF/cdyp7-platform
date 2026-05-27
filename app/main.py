from fastapi import FastAPI

from app.api.ptc_rvs_routes import make_pooled_http_client, router
from app.core.audit import audit_event
from app.core.ptc_rvs_context import BOUNDARY_CONTRACT
from app.core.ptc_rvs_client import PTC_RVS_BASE_URL


def create_app() -> FastAPI:
    app = FastAPI(title="CDYP7 PTC RV&S Context Bootstrapper")

    @app.on_event("startup")
    async def startup() -> None:
        app.state.ptc_rvs_http_client = make_pooled_http_client()
        audit_event(
            "context.bootstrap.service.started",
            authority="ptc_rvs",
            base_url=PTC_RVS_BASE_URL,
            boundary_contract=BOUNDARY_CONTRACT,
        )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await app.state.ptc_rvs_http_client.aclose()
        audit_event("context.bootstrap.service.stopped", authority="ptc_rvs")

    app.include_router(router)
    return app


app = create_app()
