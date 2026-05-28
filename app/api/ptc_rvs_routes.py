import os

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.audit import audit_event
from app.core.ptc_rvs_client import (
    PTC_RVS_BASE_URL,
    PTC_RVS_PROJECTS_PATH,
    PTC_RVS_ITEM_LOOKUP_PATH,
    PTC_RVS_ISSUES_PATH,
    PTC_RVS_QUERY_PARAM,
    PTC_RVS_LIMIT_PARAM,
    PTC_RVS_ITEM_NUMBER_PARAM,
    PtcRvsClient,
    validate_fixed_base_url,
)
from app.core.ptc_rvs_context import (
    PtcRvsContextRequest,
    PtcRvsContextResponse,
    build_ptc_rvs_context,
)
from app.core.ptc_rvs_store import cleanup_context_store, get_context

router = APIRouter(prefix="/api/context/ptc-rvs", tags=["PTC RV&S Context"])


# =============================================================================
# PR1 / Environment Configuration
# =============================================================================

ALLOWED_CALLER_HEADER = os.getenv("CDYP7_ALLOWED_CONTEXT_CALLER", "mcp-gateway")

PTC_RVS_USER = os.getenv("PTC_RVS_USER", "")
PTC_RVS_PASS = os.getenv("PTC_RVS_PASS", "")

HTTP_CONNECT_TIMEOUT_SECONDS = float(os.getenv("PTC_RVS_CONNECT_TIMEOUT", "5"))
HTTP_READ_TIMEOUT_SECONDS = float(os.getenv("PTC_RVS_READ_TIMEOUT", "20"))

# PR1 local/internal certificate debugging switch.
#
# Production guidance:
#   Do not leave this false in production.
#   Use an approved internal CA bundle instead.
#
# Local debug:
#   $env:PTC_RVS_VERIFY_TLS = "false"
#
PTC_RVS_VERIFY_TLS = os.getenv("PTC_RVS_VERIFY_TLS", "true").lower() == "true"


# =============================================================================
# Route Guard
# =============================================================================


async def require_backend_caller(
    x_cdyp7_caller: str | None = Header(default=None),
) -> None:
    """
    PR1 development gate.

    Production replacement:
      - OAuth/JWT/service principal validation
      - mTLS or gateway identity validation
      - Deny direct frontend-originated requests
    """
    if x_cdyp7_caller != ALLOWED_CALLER_HEADER:
        raise HTTPException(
            status_code=403,
            detail="Direct frontend or unauthorized caller is prohibited",
        )


def get_rvs_client(request: Request) -> PtcRvsClient:
    return PtcRvsClient(request.app.state.ptc_rvs_http_client)


# =============================================================================
# Routes
# =============================================================================


@router.post(
    "/bootstrap",
    response_model=PtcRvsContextResponse,
    dependencies=[Depends(require_backend_caller)],
)
async def bootstrap_ptc_rvs_context(
    body: PtcRvsContextRequest,
    request: Request,
    rvs: PtcRvsClient = Depends(get_rvs_client),
):
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get(
        "X-CDYP7-Correlation-ID"
    )

    try:
        return await build_ptc_rvs_context(
            body=body,
            rvs=rvs,
            correlation_id=correlation_id,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except HTTPException:
        raise

    except Exception as exc:
        audit_event(
            "context.bootstrap.failed",
            correlation_id=correlation_id,
            authority="ptc_rvs",
            query_name=body.query_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        # PR1 diagnostic detail.
        #
        # Production recommendation:
        #   Replace with a generic message and preserve details only in logs.
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Failed to bootstrap PTC RV&S context",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "diagnostic": {
                    "base_url": PTC_RVS_BASE_URL,
                    "verify_tls": PTC_RVS_VERIFY_TLS,
                    "likely_causes": [
                        "RV&S endpoint returned HTML instead of JSON",
                        "RV&S web UI endpoint used instead of REST/JSON endpoint",
                        "TLS certificate validation failed",
                        "authentication/session required",
                        "endpoint path mapping is incorrect",
                        "response JSON shape differs from adapter expectations",
                    ],
                },
            },
        ) from exc


@router.get(
    "/resources/{context_id}",
    dependencies=[Depends(require_backend_caller)],
)
async def read_context_resource(context_id: str):
    cleanup_context_store()

    context = get_context(context_id)
    if not context:
        raise HTTPException(
            status_code=404,
            detail="Context resource not found or expired",
        )

    return {
        "status": "success",
        "context_id": context_id,
        "context": context,
    }


# =============================================================================
# Pooled HTTP Client Factory
# =============================================================================


def make_pooled_http_client() -> httpx.AsyncClient:
    """
    Create the shared pooled HTTP client used by the PTC RV&S adapter.

    This is intentionally backend-only and read-only. The client is attached to
    FastAPI app.state on startup and closed on shutdown.
    """
    validate_fixed_base_url(PTC_RVS_BASE_URL)

    timeout = httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        read=HTTP_READ_TIMEOUT_SECONDS,
        write=HTTP_READ_TIMEOUT_SECONDS,
        pool=HTTP_CONNECT_TIMEOUT_SECONDS,
    )

    limits = httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
        keepalive_expiry=30,
    )

    auth = None
    if PTC_RVS_USER and PTC_RVS_PASS:
        auth = httpx.BasicAuth(PTC_RVS_USER, PTC_RVS_PASS)

    audit_event(
        "context.bootstrap.http_client.created",
        authority="ptc_rvs",
        base_url=PTC_RVS_BASE_URL,
        projects_path=PTC_RVS_PROJECTS_PATH,
        item_lookup_path=PTC_RVS_ITEM_LOOKUP_PATH,
        item_number_param=PTC_RVS_ITEM_NUMBER_PARAM,
        issues_path=PTC_RVS_ISSUES_PATH,
        query_param=PTC_RVS_QUERY_PARAM,
        limit_param=PTC_RVS_LIMIT_PARAM,
        verify_tls=PTC_RVS_VERIFY_TLS,
        basic_auth_configured=bool(auth),
    )

    return httpx.AsyncClient(
        base_url=PTC_RVS_BASE_URL,
        timeout=timeout,
        limits=limits,
        auth=auth,
        verify=PTC_RVS_VERIFY_TLS,
        headers={
            "Accept": "application/json",
            "User-Agent": "CDYP7-RVS-Context-Bootstrapper/PR1",
        },
    )
