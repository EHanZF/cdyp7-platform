from typing import Mapping

QUERY_TEMPLATES: dict[str, str] = {
    "active_items": "state!=Closed",
    "open_traceability_items": "state!=Closed AND category=Traceability",
    "unlinked_requirements": "state!=Closed AND traceStatus=Unlinked",
    "tests_missing_results": "state!=Closed AND traceStatus=MissingResult",
    "high_priority_open_items": "state!=Closed AND priority=High",
}

RVS_FIELD_MAP: dict[str, str] = {
    "id": "ID",
    "type": "type",
    "summary": "summary",
    "state": "state",
    "owner": "assignedUser",
    "priority": "priority",
    "modified_at": "modifiedDate",
    "created_at": "createdDate",
    "release": "releaseId",
    "variant": "variantId",
    "trace_status": "traceStatus",
    "requirement_id": "requirementId",
    "test_case_id": "testCaseId",
    "test_result_id": "testResultId",
    "category": "category",
    "alm_item_number": "ALM_Item",
    "alm_delivery": "ALM_Delivery",
    "alm_delivery_source": "ALM_Delivery_Source",
    "alm_delivery_linked_item_number": "ALM_Delivery_Linked_Item_Number",
    "alm_delivery_lookup_status": "ALM_Delivery_Lookup_Status",
    "alm_delivery_lookup_error_type": "ALM_Delivery_Lookup_Error_Type",
    "alm_delivery_lookup_redaction_applied": "ALM_Delivery_Lookup_Redaction_Applied",
    "linked_alm_number": "Linked_ALM_Number",
}

PROJECT_FIELD_MAP: dict[str, str] = {
    "id": "id",
    "name": "name",
    "description": "description",
    "state": "state",
    "type": "type",
}


def escape_query_literal(value: str) -> str:
    """Escape only server-controlled scoped literal values; not for arbitrary query input."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def resolve_query(
    query_name: str,
    release_id: str | None = None,
    variant_id: str | None = None,
    field_map: Mapping[str, str] = RVS_FIELD_MAP,
) -> str:
    """Resolve a production query from approved templates only."""
    if query_name not in QUERY_TEMPLATES:
        raise ValueError(f"Unknown query_name: {query_name}")

    query = QUERY_TEMPLATES[query_name]

    if release_id:
        query += f' AND {field_map["release"]}="{escape_query_literal(release_id)}"'

    if variant_id:
        query += f' AND {field_map["variant"]}="{escape_query_literal(variant_id)}"'

    return query
