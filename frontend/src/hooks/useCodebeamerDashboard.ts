import { useEffect, useState } from "react";

export type ALMItem = {
  id: number;
  name: string;
  tracker?: string;
  typeName?: string;
  status?: string;
  priority?: string;
  assignedTo: string[];
  storyPoints?: number;
  createdAt?: string;
  modifiedAt?: string;
  versions: string[];
  subjects: string[];
  children: string[];
  customFields: Record<string, unknown>;
};

export type ALMDashboardState = {
  generatedAt: string;
  source: string;
  authority: string;
  receiptBacked: boolean;
  totals: {
    items: number;
    open: number;
    inProgress: number;
    closed: number;
    highPriority: number;
  };
  byStatus: Record<string, number>;
  byPriority: Record<string, number>;
  byTracker: Record<string, number>;
  items: ALMItem[];
};

export function useCodebeamerDashboard() {
  const [dashboard, setDashboard] = useState<ALMDashboardState | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    const url =
      `https://raw.githubusercontent.com/${import.meta.env.VITE_OWNER}/${import.meta.env.VITE_REPO}/main/data/results/latest.json?ts=${Date.now()}`;

    const response = await fetch(url);

    if (response.ok) {
      const data = await response.json();
      setDashboard(data);
    }

    setLoading(false);
  }

  useEffect(() => {
    load();

    const interval = window.setInterval(load, 5000);

    return () => window.clearInterval(interval);
  }, []);

  return {
    dashboard,
    loading,
    reload: load
  };
}