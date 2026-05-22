# CDYP7 PTC Codebeamer MCP Server

This MCP server uses the Python MCP SDK `FastMCP` server interface to expose PTC Codebeamer API v3 data as tools/resources for the CDYP7 dashboard.

## What it exposes

Tools:

- `cdyp7_cb_projects` — list accessible Codebeamer projects
- `cdyp7_cb_query_items` — query tracker items and normalize ALM fields
- `cdyp7_cb_dashboard` — build the dashboard JSON used by the HTML frontend

Resources:

- `cdyp7://dashboard/latest` — latest persisted dashboard state
- `cdyp7://receipts/latest` — latest persisted receipt

Prompt:

- `dashboard_triage_prompt` — summarizes how an agent should review delivery risk

## Required environment

```bash
export CB_URL="https://your-codebeamer-instance"
export CB_TOKEN="your-codebeamer-token"
export CB_DELIVERY_FIELDS="ALM_Delivery"
export CB_DELIVERY_DATE_FIELDS="Target Date"
```

Owner is mapped from Codebeamer `assignedTo`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-mcp.txt
```

## Run over stdio

```bash
MCP_TRANSPORT=stdio python app/mcp/ptc_codebeamer_mcp_server.py
```

## Run over Streamable HTTP

```bash
MCP_TRANSPORT=streamable-http python app/mcp/ptc_codebeamer_mcp_server.py
```

Then connect your MCP client to the SDK's HTTP MCP endpoint, typically:

```text
http://localhost:8000/mcp
```

## Generate dashboard state

Call the MCP tool:

```text
cdyp7_cb_dashboard(query="status != 'Closed'", persist=true)
```

It writes:

```text
data/results/latest.json
data/receipts/latest.json
```

These files can be served by GitHub Pages or any static file server for the HTML dashboard.

## CDYP7 boundary

The dashboard remains display-only. The MCP server owns the Codebeamer credential and produces receipt-backed, non-authoritative state unless promoted by your CDYP7 governance workflow.
