"""
MCP contract models.
"""

from pydantic import BaseModel


class ToolEnvelope(BaseModel):
    """
    MCP tool result envelope.
    """

    tool: str
    authority: str
    receipt_backed: bool = False
    result: dict = {}
