# CDYP7 PTC RV&S MCP Adapter

Temporary adapter for RV&S / Integrity before Codebeamer migration is complete.

## Server

Configured default server:

```text
skobde-mks.kobde.trw.com:7001
```

## Prerequisites

- PTC RV&S / Integrity client installed on the MCP host
- `im` CLI available on PATH, or set `RVS_IM_EXE`
- VPN/network access to the RV&S server

## Install

```powershell
pip install -r requirements-rvs-mcp.txt
```

## PowerShell environment

```powershell
$env:RVS_HOST = "skobde-mks.kobde.trw.com"
$env:RVS_PORT = "7001"
$env:RVS_USER = "your-user"
$env:RVS_PASSWORD = "your-password"
$env:RVS_FIELDS = "ID,Summary,State,Assigned User,Type,Priority,ALM_Delivery,Target Date"
$env:RVS_DELIVERY_FIELD = "ALM_Delivery"
$env:RVS_DELIVERY_DATE_FIELD = "Target Date"
$env:RVS_OWNER_FIELD = "Assigned User"
```

## Check connection

```powershell
im connect --hostname=skobde-mks.kobde.trw.com --port=7001 --user=$env:RVS_USER --password=$env:RVS_PASSWORD --batch
```

## Generate dashboard JSON once

```powershell
python app/mcp/ptc_rvs_mcp_server.py fetch
```

Outputs:

```text
data/results/latest.json
data/receipts/latest.json
```

## Run as MCP server

```powershell
$env:MCP_TRANSPORT = "streamable-http"
python app/mcp/ptc_rvs_mcp_server.py serve
```

Tools:

- `cdyp7_rvs_connection_check`
- `cdyp7_rvs_dashboard`
