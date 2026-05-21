# CDYP7 MCP Codebeamer Fetcher

This folder contains a matching Python fetcher for the `cdyp7-codebeamer-dashboard.html` Page application.

## Files

- `codebeamer_mcp_fetcher.py` — standalone Python MCP-style Codebeamer fetcher
- `requirements.txt` — runtime dependency

## Environment variables

```bash
export CB_URL="https://your-codebeamer-instance"
export CB_TOKEN="your-codebeamer-token"
export CB_QUERY="status != 'Closed'"
```

Optional field mapping overrides:

```bash
export CB_DELIVERY_FIELDS="Delivery,Release,Target Release,Fix Version,Sprint"
export CB_DELIVERY_DATE_FIELDS="Delivery Date,Target Date,Due Date,Planned End Date"
export CB_REMAINING_FIELDS="Remaining,Remaining Estimate,Story Points"
export CB_BLOCKED_FIELDS="Blocked,Is Blocked,Blocker"
```

## Fetch once and write dashboard JSON

```bash
pip install -r requirements.txt
python codebeamer_mcp_fetcher.py fetch
```

Outputs:

```text
data/results/latest.json
data/receipts/latest.json
```

## Serve directly for the HTML Page app

```bash
python codebeamer_mcp_fetcher.py serve --host 127.0.0.1 --port 8787
```

Then set the dashboard endpoint field to:

```text
http://127.0.0.1:8787/api/codebeamer/dashboard
```

## GitHub Actions usage

```yaml
- name: Fetch Codebeamer dashboard data
  env:
    CB_URL: ${{ secrets.CB_URL }}
    CB_TOKEN: ${{ secrets.CB_TOKEN }}
    CB_QUERY: "status != 'Closed'"
  run: |
    pip install -r requirements.txt
    python codebeamer_mcp_fetcher.py fetch
```
