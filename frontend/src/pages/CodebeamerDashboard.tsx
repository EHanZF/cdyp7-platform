import { useMemo, useState } from "react";
import { dispatchDashboardRefresh } from "../api/dashboardApi";
import ALMItemsTable from "../components/ALMItemsTable";
import BreakdownBars from "../components/BreakdownBars";
import DashboardToolbar from "../components/DashboardToolbar";
import DeliveryTimeline from "../components/DeliveryTimeline";
import Header from "../components/Header";
import MetricCard from "../components/MetricCard";
import OwnerLoadPanel from "../components/OwnerLoadPanel";
import ReceiptPanel from "../components/ReceiptPanel";
import { useDashboardState } from "../hooks/useDashboardState";
import type { ALMDashboardState } from "../types/alm";
import { countBy, deriveDeliveries, isAtRisk, isClosed } from "../utils/metrics";

const demoState: ALMDashboardState = {
  generatedAt: new Date().toISOString(),
  source: "codebeamer-demo",
  authority: "non_authoritative",
  receiptBacked: true,
  receiptId: "demo-rcpt-001",
  totals: { items: 6, open: 5, inProgress: 2, closed: 1, highPriority: 3 },
  byStatus: { Open: 2, "In Progress": 1, Blocked: 1, Review: 1, Done: 1 },
  byPriority: { Critical: 1, High: 2, Medium: 2, Low: 1 },
  byTracker: { Requirements: 2, "Test Cases": 1, Defects: 1, Tasks: 1, "Test Runs": 1 },
  items: [
    {
      id: 1001,
      name: "Brake response timing requirement verification",
      tracker: "System Requirements",
      status: "In Progress",
      priority: "Critical",
      assignedTo: ["A. Patel"],
      storyPoints: 3,
      dueDate: "2026-06-12T00:00:00Z",
      versions: [],
      subjects: [],
      children: [],
      customFields: { ASIL: "D" },
      remaining: 3
    },
    {
      id: 1002,
      name: "Trace test cases to braking requirements",
      tracker: "Test Cases",
      status: "Open",
      priority: "High",
      assignedTo: ["M. Chen"],
      storyPoints: 5,
      dueDate: "2026-06-17T00:00:00Z",
      versions: [],
      subjects: [],
      children: [],
      customFields: {},
      remaining: 5
    },
    {
      id: 1003,
      name: "Resolve CAN timing defect",
      tracker: "Defects",
      status: "Blocked",
      priority: "Blocker",
      assignedTo: ["J. Rivera"],
      storyPoints: 2,
      dueDate: "2026-05-20T00:00:00Z",
      versions: [],
      subjects: [],
      children: [],
      customFields: {},
      remaining: 2,
      blocked: true
    },
    {
      id: 1004,
      name: "Update delivery acceptance criteria",
      tracker: "Requirements",
      status: "Review",
      priority: "Medium",
      assignedTo: ["S. Morgan"],
      storyPoints: 4,
      dueDate: "2026-07-02T00:00:00Z",
      versions: [],
      subjects: [],
      children: [],
      customFields: {},
      remaining: 4
    },
    {
      id: 1005,
      name: "Architecture review action items",
      tracker: "Tasks",
      status: "Open",
      priority: "Low",
      assignedTo: ["A. Patel", "S. Morgan"],
      storyPoints: 6,
      dueDate: "2026-07-10T00:00:00Z",
      versions: [],
      subjects: [],
      children: [],
      customFields: {},
      remaining: 6
    },
    {
      id: 1006,
      name: "Software integration test execution",
      tracker: "Test Runs",
      status: "Done",
      priority: "High",
      assignedTo: ["M. Chen"],
      storyPoints: 0,
      dueDate: "2026-06-01T00:00:00Z",
      versions: [],
      subjects: [],
      children: [],
      customFields: {},
      remaining: 0
    }
  ]
};

export default function CodebeamerDashboard() {
  const { dashboard, loading, lastError } = useDashboardState();
  const [query, setQuery] = useState("type = 'Requirement'");
  const [search, setSearch] = useState("");
  const [dispatching, setDispatching] = useState(false);
  const [demo, setDemo] = useState(false);

  const activeDashboard = demo ? demoState : dashboard;

  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    if (!activeDashboard) return [];
    if (!normalizedSearch) return activeDashboard.items;

    return activeDashboard.items.filter((item) =>
      [item.id, item.name, item.status, item.priority, item.tracker, item.assignedTo.join(", ")]
        .map((value) => String(value ?? "").toLowerCase())
        .some((value) => value.includes(normalizedSearch))
    );
  }, [activeDashboard, search]);

  const deliveries = activeDashboard?.deliveries ?? deriveDeliveries(activeDashboard?.items ?? []);
  const openItems = filteredItems.filter((item) => !isClosed(item.status));
  const remaining = openItems.reduce(
    (sum, item) => sum + (item.remaining ?? item.storyPoints ?? 1),
    0
  );
  const riskCount = filteredItems.filter(isAtRisk).length;

  async function handleRefresh() {
    setDispatching(true);
    try {
      await dispatchDashboardRefresh(query);
      window.alert("Dashboard refresh dispatched through MCP.");
    } finally {
      setDispatching(false);
    }
  }

  if (loading && !activeDashboard) {
    return (
      <div className="dashboard-page">
        <Header live={false} statusText="Loading dashboard state" />
      </div>
    );
  }

  if (!activeDashboard) {
    return (
      <div className="dashboard-page">
        <Header live={false} statusText={lastError ?? "Waiting for data"} />
        <DashboardToolbar
          query={query}
          search={search}
          dispatching={dispatching}
          onQueryChange={setQuery}
          onSearchChange={setSearch}
          onRefresh={handleRefresh}
          onLoadDemo={() => setDemo(true)}
        />
        <div className="empty">No dashboard data found. Use Demo or dispatch a Codebeamer refresh.</div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <Header live={true} statusText={demo ? "Demo data loaded" : "Dashboard state loaded"} />
      <DashboardToolbar
        query={query}
        search={search}
        dispatching={dispatching}
        onQueryChange={setQuery}
        onSearchChange={setSearch}
        onRefresh={handleRefresh}
        onLoadDemo={() => setDemo(true)}
      />

      <section className="grid stats">
        <MetricCard title="Open Items" value={openItems.length} note="Items not closed/done/accepted" />
        <MetricCard title="Remaining Items" value={remaining} note="Remaining in selected delivery" />
        <MetricCard
          title="Delivery Completion"
          value={`${activeDashboard.totals.closed}/${activeDashboard.totals.items}`}
        />
        <MetricCard title="High Priority" value={activeDashboard.totals.highPriority} />
        <MetricCard title="At-Risk Items" value={riskCount} note="High priority, blocked, or overdue" />
      </section>

      <section className="grid two-col">
        <DeliveryTimeline deliveries={deliveries} />
        <OwnerLoadPanel items={openItems} />
      </section>

      <section className="grid three-col">
        <BreakdownBars title="Status" data={countBy(filteredItems, "status")} />
        <BreakdownBars title="Priority" data={countBy(filteredItems, "priority")} />
        <BreakdownBars title="Tracker / Type" data={countBy(filteredItems, "tracker")} />
      </section>

      <ALMItemsTable items={filteredItems} />
      <ReceiptPanel dashboard={activeDashboard} />
    </div>
  );
}
