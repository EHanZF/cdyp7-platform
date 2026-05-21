import type { ALMDashboardState } from "../types/alm";

export async function fetchDashboardState(): Promise<ALMDashboardState | null> {
  const configuredUrl = import.meta.env.VITE_DASHBOARD_STATE_URL;
  const defaultUrl = `${import.meta.env.BASE_URL}data/results/latest.json`;
  const url = `${configuredUrl || defaultUrl}?ts=${Date.now()}`;

  const response = await fetch(url, {
    headers: {
      Accept: "application/json"
    }
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as ALMDashboardState;
}

export async function dispatchDashboardRefresh(query: string): Promise<void> {
  // Production integration point:
  // 1. Request a short-lived GitHub App token from a token broker.
  // 2. POST repository_dispatch with event_type = "mcp.invoke".
  // 3. Let GitHub Actions run the Python MCP harness.
  // 4. Browser never receives Codebeamer credentials.
  console.info("Dispatch dashboard refresh requested", { query });
}
