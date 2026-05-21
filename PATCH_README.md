# CDYP7 Platform UI Hardening Patch

This patch is intended to be extracted over the existing `cdyp7-platform` repository.

It hardens the frontend by replacing scaffold UI pieces with a typed React + TypeScript implementation of the CDYP7 MCP Codebeamer ALM Dashboard.

## What this patch adds

- React/TypeScript ALM dashboard components
- Strong ALM dashboard state types
- Repo-backed dashboard state loading from `public/data/results/latest.json`
- Delivery timeline, owner load, status/priority/tracker breakdowns
- Open ALM item table
- Receipt / authority panel
- Stable Vite config for GitHub Pages
- VS Code launch/task configs for Edge debugging
- Sample dashboard JSON so the page renders immediately

## Apply

From the root of your existing `cdyp7-platform` repo:

```powershell
Expand-Archive .\cdyp7-platform-ui-hardening-patch.zip -DestinationPath . -Force
```

Or copy the files manually into matching paths.

## Validate

```powershell
cd frontend
npm install
npm run build
npm run dev
```

Then open:

```text
http://localhost:5173/cdyp7-platform/
```

## Notes

This patch intentionally does not replace the Python MCP backend. It only hardens the web UI layer.
