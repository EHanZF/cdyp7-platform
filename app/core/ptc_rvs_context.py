import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.audit import audit_event
from app.core.ptc_rvs_client import PtcRvsClient
from app.core.ptc_rvs_sanitizer import (
    item_from_field_map,
    project_from_field_map,
    sanitize_payload,
)
from app.core.ptc_rvs_store import put_context
from app.core.ptc_rvs_templates import (
    PROJECT_FIELD_MAP,
    RVS_FIELD_MAP,
    resolve_query,
)


BOUNDARY_CONTRACT = {
    "authority_effect": "none",
    "persistence_effect": "none_by_default",
    "promotion_gate": "closed_for_authority",
    "write_paths": "none",
    "frontend_access": "prohibited_direct_to_rvs",
    "agent_use": "read_only_context_bootstrap",
}


MAX_ITEMS_DEFAULT = int(os.getenv("PTC_RVS_MAX_ITEMS", "250"))
MAX_PROJECTS_DEFAULT = int(os.getenv("PTC_RVS_MAX_PROJECTS", "50"))
FOCUS_LIMIT = int(os.getenv("PTC_RVS_FOCUS_LIMIT", "25"))
ENABLE_LINKED_ALM_DELIVERY_LOOKUP = (
    os.getenv("PTC_RVS_ENABLE_LINKED_ALM_DELIVERY_LOOKUP", "false").lower()
    == "true"
)
LINKED_LOOKUP_CONCURRENCY = int(
    os.getenv("PTC_RVS_LINKED_LOOKUP_CONCURRENCY", "8")
)

class PtcRvsContextRequest(BaseModel):
    query_name: str = Field(min_length=1, max_length=128)
    release_id: str | None = Field(default=None, max_length=128)
    variant_id: str | None = Field(default=None, max_length=256)
    max_items: int = Field(default=MAX_ITEMS_DEFAULT, ge=1, le=MAX_ITEMS_DEFAULT)
    max_projects: int = Field(default=MAX_PROJECTS_DEFAULT, ge=1, le=MAX_PROJECTS_DEFAULT)


class ReceiptLimits(BaseModel):
    max_items: int
    returned_items: int
    max_projects: int
    returned_projects: int
    items_truncated: bool
    projects_truncated: bool


class ContextReceipt(BaseModel):
    authority: Literal["ptc_rvs"] = "ptc_rvs"
    fetched_at: str
    query_name: str
    release_id: str | None = None
    variant_id: str | None = None
    templates_enforced: bool = True
    limits: ReceiptLimits
    redaction_applied: bool
    correlation_id: str
    boundary_contract: dict[str, str]


class PtcRvsContextResponse(BaseModel):
    status: Literal["success"]
    context_id: str
    context_uri: str
    receipt: ContextReceipt
    context: dict[str, Any]


def new_correlation_id() -> str:
    return str(uuid.uuid4())


async def build_ptc_rvs_context(
    body: PtcRvsContextRequest,
    rvs: PtcRvsClient,
    correlation_id: str | None = None,
) -> PtcRvsContextResponse:
    correlation_id = correlation_id or new_correlation_id()
    fetched_at = datetime.now(timezone.utc).isoformat()

    query = resolve_query(
        query_name=body.query_name,
        release_id=body.release_id,
        variant_id=body.variant_id,
        field_map=RVS_FIELD_MAP,
    )

    audit_event(
        "context.bootstrap.requested",
        correlation_id=correlation_id,
        authority="ptc_rvs",
        query_name=body.query_name,
        release_id=body.release_id,
        variant_id=body.variant_id,
        templates_enforced=True,
    )

    projects_raw, items_raw = await asyncio.gather(
        rvs.get_projects(),
        rvs.get_items(query=query, limit=body.max_items + 1),
    )

    projects_truncated = len(projects_raw) > body.max_projects
    items_truncated = len(items_raw) > body.max_items

    projects_raw = projects_raw[: body.max_projects]
    items_raw = items_raw[: body.max_items]

    sanitized_projects, project_redacted = sanitize_payload(projects_raw)
    sanitized_items, item_redacted = sanitize_payload(items_raw)

    redaction_applied = project_redacted or item_redacted

    projects = [
        project_from_field_map(project, PROJECT_FIELD_MAP)
        for project in sanitized_projects
        if isinstance(project, dict)
    ]

    items: list[dict[str, Any]] = []

    for raw_item in sanitized_items:
        if not isinstance(raw_item, dict):
            continue

        normalized_item = item_from_field_map(raw_item, RVS_FIELD_MAP)
        normalized_item["alm_delivery"] = derive_alm_delivery(normalized_item)

        items.append(normalized_item)

    if ENABLE_LINKED_ALM_DELIVERY_LOOKUP:
        items = await enrich_items_with_linked_alm_delivery(
            items=items,
            rvs=rvs,
            correlation_id=correlation_id,
        )

    focus = build_traceability_focus(items)

    context = {
        "source": "ptc_rvs",
        "fetched_at": fetched_at,
        "query_name": body.query_name,
        "release_id": body.release_id,
        "variant_id": body.variant_id,
        "summary": {
            "project_count": len(projects),
            "item_count": len(items),
            "items_truncated": items_truncated,
            "projects_truncated": projects_truncated,
            "high_priority_count": len(focus["high_priority_open_items"]),
            "unlinked_requirement_count": len(focus["unlinked_requirements"]),
            "tests_missing_results_count": len(focus["tests_missing_results"]),
            "alm_delivery_count": len(
                {
                    item.get("alm_delivery")
                    for item in items
                    if item.get("alm_delivery")
                }
            ),
        },
        "projects": projects,
        "items": items,
        "focus": focus,
        "agent_guidance": {
            "authority": "Context only. Do not treat as authoritative mutation state.",
            "allowed_next_steps": [
                "summarize_context",
                "identify_traceability_gaps",
                "request_item_detail_by_id",
                "propose_non_authoritative_remediation_plan",
            ],
            "forbidden_next_steps": [
                "write_to_rvs",
                "mutate_authoritative_alm_state",
                "construct_free_form_rvs_query",
            ],
        },
    }

    context_id = put_context(context)
    context_uri = f"context://ptc-rvs/bootstrap/{context_id}"

    receipt = ContextReceipt(
        fetched_at=fetched_at,
        query_name=body.query_name,
        release_id=body.release_id,
        variant_id=body.variant_id,
        limits=ReceiptLimits(
            max_items=body.max_items,
            returned_items=len(items),
            max_projects=body.max_projects,
            returned_projects=len(projects),
            items_truncated=items_truncated,
            projects_truncated=projects_truncated,
        ),
        redaction_applied=redaction_applied,
        correlation_id=correlation_id,
        boundary_contract=BOUNDARY_CONTRACT,
    )

    audit_event(
        "context.bootstrap.completed",
        correlation_id=correlation_id,
        authority="ptc_rvs",
        query_name=body.query_name,
        returned_items=len(items),
        returned_projects=len(projects),
        items_truncated=items_truncated,
        projects_truncated=projects_truncated,
        redaction_applied=redaction_applied,
        context_id=context_id,
        context_uri=context_uri,
    )

    return PtcRvsContextResponse(
        status="success",
        context_id=context_id,
        context_uri=context_uri,
        receipt=receipt,
        context=context,
    )


def derive_alm_delivery(item):
    """Derive the ALM delivery identifier from normalized RV&S/PTC item data.

    Priority:
    1. Explicit ALM delivery fields
    2. linked_alm_number
    3. alm_item_number
    """
    if not item:
        return None

    explicit_delivery = (
        item.get("alm_delivery")
        or item.get("ALM_Delivery")
        or item.get("delivery")
        or item.get("deliveryName")
        or item.get("delivery_name")
    )
    if explicit_delivery:
        return str(explicit_delivery)

    linked_alm_number = item.get("linked_alm_number") or item.get("linkedAlmNumber")
    if linked_alm_number:
        return str(linked_alm_number)

    alm_item_number = item.get("alm_item_number") or item.get("almItemNumber")
    if alm_item_number:
        return str(alm_item_number)

    return None

def normalize_alm_delivery_from_number(linked_number: str) -> str | None:
    """
    Convert a linked ALM item number into an ALM_Delivery value.

    PR1 behavior:
      - return the linked number as the delivery reference
      - preserve provenance without inventing authoritative data.

    Later production enhancement:
      - resolve linked_number through a template-only item-detail lookup
      - extract authoritative ALM_Delivery from the linked item.
    """

    value = linked_number.strip()

    if not value:
        return None

    return value

async def enrich_items_with_linked_alm_delivery(
    items: list[dict[str, Any]],
    rvs: PtcRvsClient,
    correlation_id: str,
) -> list[dict[str, Any]]:
    """
    Read-only linked item enrichment.

    For each primary item:
      - find linked ALM item number
      - fetch linked item through approved JSON API/gateway
      - read ALM_Delivery from the linked item
      - attach that value to the primary item

    This does not mutate RV&S.
    """
    semaphore = asyncio.Semaphore(LINKED_LOOKUP_CONCURRENCY)

    async def enrich_one(item: dict[str, Any]) -> dict[str, Any]:
        linked_number = get_linked_alm_number(item)

        if not linked_number:
            item["alm_delivery_lookup_status"] = "no_linked_number"
            return item

        try:
            async with semaphore:
                linked_raw = await rvs.get_item_by_number(str(linked_number))

            linked_sanitized, redacted = sanitize_payload(linked_raw)

            if not isinstance(linked_sanitized, dict):
                item["alm_delivery_lookup_status"] = "linked_item_invalid_shape"
                return item

            linked_normalized = item_from_field_map(
                linked_sanitized,
                RVS_FIELD_MAP,
            )

            linked_delivery = (
                linked_normalized.get("alm_delivery")
                or linked_sanitized.get("ALM_Delivery")
                or linked_sanitized.get("ALM Delivery")
                or linked_sanitized.get("alm_delivery")
            )

            if linked_delivery:
                item["alm_delivery"] = str(linked_delivery)
                item["alm_delivery_source"] = "linked_item_lookup"
                item["alm_delivery_linked_item_number"] = str(linked_number)
                item["alm_delivery_lookup_status"] = "resolved"
            else:
                item["alm_delivery_lookup_status"] = "linked_item_missing_alm_delivery"
                item["alm_delivery_linked_item_number"] = str(linked_number)

            if redacted:
                item["alm_delivery_lookup_redaction_applied"] = True

            return item

        except Exception as exc:
            # Do not fail the whole bootstrap if one linked lookup fails.
            item["alm_delivery_lookup_status"] = "lookup_failed"
            item["alm_delivery_lookup_error_type"] = type(exc).__name__
            item["alm_delivery_linked_item_number"] = str(linked_number)

            audit_event(
                "context.bootstrap.alm_delivery_lookup_failed",
                correlation_id=correlation_id,
                authority="ptc_rvs",
                linked_item_number=str(linked_number),
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            return item

    enriched = await asyncio.gather(
        *(enrich_one(item) for item in items)
    )

    return list(enriched)


def get_linked_alm_number(item: dict[str, Any]) -> str | None:
    linked_number = (
        item.get("linked_alm_number")
        or item.get("alm_item_number")
        or item.get("requirement_id")
        or item.get("test_case_id")
        or item.get("test_result_id")
    )

    if not linked_number:
        return None

    value = str(linked_number).strip()

    if not value:
        return None

    return value

def build_traceability_focus(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    def compact(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "summary": item.get("summary"),
            "state": item.get("state"),
            "priority": item.get("priority"),
            "trace_status": item.get("trace_status"),
            "modified_at": item.get("modified_at"),
            "alm_item_number": item.get("alm_item_number"),
            "linked_alm_number": item.get("linked_alm_number"),
            "alm_delivery": item.get("alm_delivery"),
        }

    high_priority = [
        compact(item)
        for item in items
        if str(item.get("priority", "")).lower() == "high"
    ][:FOCUS_LIMIT]

    unlinked_requirements = [
        compact(item)
        for item in items
        if str(item.get("trace_status", "")).lower() == "unlinked"
    ][:FOCUS_LIMIT]

    tests_missing_results = [
        compact(item)
        for item in items
        if str(item.get("trace_status", "")).lower()
        in {"missingresult", "missing_result", "missing result"}
    ][:FOCUS_LIMIT]

    items_with_alm_delivery = [
        compact(item)
        for item in items
        if item.get("alm_delivery")
    ][:FOCUS_LIMIT]

    return {
        "high_priority_open_items": high_priority,
        "unlinked_requirements": unlinked_requirements,
        "tests_missing_results": tests_missing_results,
        "items_with_alm_delivery": items_with_alm_delivery,
    }
