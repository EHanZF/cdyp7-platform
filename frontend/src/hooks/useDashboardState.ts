import { useCallback, useEffect, useState } from "react";
import { fetchDashboardState } from "../api/dashboardApi";
import type { ALMDashboardState } from "../types/alm";

export function useDashboardState(refreshMs = 5000) {
  const [dashboard, setDashboard] = useState<ALMDashboardState | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastError, setLastError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const state = await fetchDashboardState();
      setDashboard(state);
      setLastError(state ? null : "No dashboard state found");
    } catch (error) {
      setLastError(error instanceof Error ? error.message : "Unknown dashboard error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    const id = window.setInterval(reload, refreshMs);
    return () => window.clearInterval(id);
  }, [reload, refreshMs]);

  return { dashboard, loading, lastError, reload };
}
