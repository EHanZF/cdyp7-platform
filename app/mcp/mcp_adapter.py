"""
CDYP7 MCP adapter for PTC RV&S.

Exposes RV&S dashboard functionality via an embedded MCP interface.
No RV&S CLI logic lives in this module.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Literal

from mcp.server.fastmcp import FastMCP

from app.mcp.rvs_client import (
    RVSConfig,
    build_dashboard,
    normalize_rvs_item,
    parse_tabular_im_output,
    receipt,
    run_im_issues,
    write_json,
)

Transport = Literal["stdio", "sse", "streamable-http"]

mcp = FastMCP("CDYP7-PTC-RVS-MCP", json_response=True)


def parse_transport(value: str) -> Transport:
    """Validate MCP transport mode."""
    allowed = {"stdio", "sse", "streamable-http"}
    if value not in allowed:
        raise ValueError(f"Invalid transport: {value}")
    return value  # type: ignore[return-value]


@mcp.tool()
def cdyp7_rvs_dashboard(
    query: str = "",
    query_definition: str = "",
    persist: bool = True,
) -> Dict[str, Any]:
    """Fetch RV&S items and build the CDYP7 dashboard JSON."""
    start = time.time()
    cfg = RVSConfig()
    query_used = query or cfg.query or query_definition or cfg.query_definition or "All"

    output = run_im_issues(
        cfg,
        query=query or None,
        query_definition=query_definition or None,
    )

    rows = parse_tabular_im_output(output, cfg.fields)
    items = [normalize_rvs_item(row, cfg) for row in rows]
    dashboard = build_dashboard(items, query_used)

    elapsed_ms = int((time.time() - start) * 1000)
    rcpt = receipt(
        "cdyp7.rvs.dashboard",
        {"query": query_used, "fields": cfg.fields},
        {
            "items": len(items),
            "deliveries": len(dashboard["deliveries"]),
        },
        elapsed_ms,
    )
    dashboard["receiptId"] = rcpt["receipt_id"]

    if persist:
        write_json(cfg.output_path, dashboard)
        write_json(cfg.receipt_path, rcpt)

    return dashboard


@mcp.resource("cdyp7://rvs/dashboard/latest")
def latest_dashboard() -> str:
    """Return the latest persisted RV&S dashboard JSON."""
    path = Path(os.getenv("CDYP7_OUTPUT", "data/results/latest.json"))
    if not path.exists():
        return json.dumps({"error": "No RV&S dashboard state has been generated yet."})
    return path.read_text(encoding="utf-8")


def main() -> None:
    """CLI entrypoint for MCP server."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="stdio | sse | streamable-http",
    )
    parsed_args = parser.parse_args()
    transport = parse_transport(parsed_args.transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
