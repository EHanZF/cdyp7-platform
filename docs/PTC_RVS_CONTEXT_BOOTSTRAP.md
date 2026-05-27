# CDYP7 PTC RV&S Context Bootstrap Boundary

```yaml
accepted_control:
  name: cdyp7_ptc_rvs_context_bootstrap
  status: implementation_ready_with_environment_specific_edits
  integration_model: read_only_context_adapter
  agent_access_model: backend_only
  mcp_mode: optional_resource_handoff
  authority_effect: none
  persistence_effect: none_by_default
  promotion_gate: closed_for_authority
  write_paths: none
  source_system_authority: ptc_rvs
  frontend_direct_access_to_rvs: prohibited
  environment_specific_edits_required: true
```

## Boundary Statement

The PTC RV&S bootstrapper is a read-only CDYP7 context adapter.

It may retrieve, sanitize, summarize, and stage RV&S context for agent workflows.

It must not write to RV&S, mutate authoritative ALM state, approve requirements, close items, change traceability, or promote generated content.

RV&S remains the source system of record.

CDYP7 returns non-authoritative starting context only.

## Locked Architecture

```text
Copilot / Agent
  -> CDYP7 MCP Gateway or CDYP7 API Boundary
  -> Template-only RV&S Query Resolver
  -> PTC RV&S Read-only Client
  -> Recursive Redactor
  -> Allowlist Normalizer
  -> Bounded Agent Context JSON
  -> Receipt Metadata
  -> Optional context:// Resource Handoff
```

## PR1 Scope

```yaml
pr1_include:
  - FastAPI route: /api/context/ptc-rvs/bootstrap
  - template-only query resolver
  - pooled httpx.AsyncClient
  - recursive redaction
  - field allowlist projection
  - item/project count caps
  - response byte cap
  - receipt metadata
  - structured audit logs
  - in-memory context store with TTL
  - optional context_uri response
  - unit tests for sanitizer, templates, limits, receipts

pr1_defer:
  - production OAuth/JWT validation
  - mTLS enforcement
  - Redis/shared context store
  - final RV&S endpoint mapping confirmation
  - final RV&S field-name mapping confirmation
  - full MCP server wrapper
```

## Required Before Commit

```yaml
required_before_commit:
  rvs_api_mapping:
    - confirm_rvs_projects_endpoint
    - confirm_rvs_issues_endpoint
    - confirm_query_parameter_name
    - confirm_limit_parameter_name

  rvs_field_mapping:
    - confirm_release_field
    - confirm_variant_field
    - confirm_trace_status_field
    - confirm_priority_field
    - confirm_modified_date_field
    - confirm_requirement_id_field
    - confirm_test_case_id_field
    - confirm_test_result_id_field
```

## Production Gate

```yaml
production_gate_open_when:
  - actual_rvs_api_paths_confirmed
  - actual_rvs_field_names_confirmed
  - query_templates_enforced
  - arbitrary_query_disabled
  - service_principal_or_jwt_auth_enabled
  - credentials_stored_in_approved_secret_store
  - response_size_limit_enforced
  - item_count_limit_enforced
  - project_count_limit_enforced
  - recursive_redaction_enabled
  - allowlist_projection_enabled
  - audit_events_emitted
  - no_write_methods_exposed
  - context_store_moved_to_shared_store_if_multi_instance
```
