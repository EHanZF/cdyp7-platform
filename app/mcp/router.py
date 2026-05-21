"""
MCP tool router for CDYP7 orchestration.
"""

from app.mcp.codebeamer_adapter import (
    create_requirement,
    delete_requirement,
    read_requirement,
    update_requirement,
)
from app.mcp.rag_pipeline import build_rag_evidence
from app.mcp.semantic_search import semantic_search


class MCPToolError(Exception):
    """Raised when an unknown MCP tool is invoked."""


def route_tool_call(tool: str, payload: dict):
    """
    Route MCP tool calls to the appropriate adapter implementation.
    """

    if tool == "cdyp7.cb.create":
        return create_requirement(payload)

    if tool == "cdyp7.cb.read":
        return read_requirement(payload["id"])

    if tool == "cdyp7.cb.update":
        return update_requirement(payload["id"], payload)

    if tool == "cdyp7.cb.delete":
        return delete_requirement(payload["id"])

    if tool == "cdyp7.semantic.search":
        return semantic_search(payload)

    if tool == "cdyp7.rag.build":
        return build_rag_evidence(payload)

    raise MCPToolError(f"Unknown MCP tool: {tool}")
