import type { ALMItem, DeliverySummary } from "../types/alm";

const closedStatuses = ["closed", "done", "accepted", "resolved", "verified"];
const inProgressStatuses = ["in progress", "implementation", "review", "in review", "testing"];
const highPriorities = ["high", "critical", "blocker", "urgent"];

function lower(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

export function isClosed(status?: string): boolean {
  return closedStatuses.includes(lower(status));
}

export function isInProgress(status?: string): boolean {
  return inProgressStatuses.includes(lower(status));
}

export function isHighPriority(priority?: string): boolean {
  return highPriorities.includes(lower(priority));
}

export function isOverdue(date?: string): boolean {
  if (!date) return false;
  const end = new Date(date);
  end.setHours(23, 59, 59, 999);
  return end < new Date();
}

export function isAtRisk(item: ALMItem): boolean {
  return Boolean(item.blocked) || isHighPriority(item.priority) || isOverdue(item.dueDate);
}

export function countBy(items: ALMItem[], key: keyof ALMItem): Record<string, number> {
  return items.reduce<Record<string, number>>((acc, item) => {
    const label = String(item[key] ?? "Unknown");
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
  }, {});
}

export function deriveDeliveries(items: ALMItem[]): DeliverySummary[] {
  const map = new Map<string, DeliverySummary>();

  for (const item of items) {
    const name = item.deliveryName || "Unassigned";
    const id =
      name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") ||
      "unassigned";

    const current = map.get(id) ?? {
      id,
      name,
      deliveryDate: item.deliveryDate || item.dueDate,
      totalItems: 0,
      completedItems: 0,
      remainingItems: 0
    };

    current.totalItems += 1;

    if (isClosed(item.status)) {
      current.completedItems += 1;
    } else {
      current.remainingItems += 1;
    }

    map.set(id, current);
  }

  return Array.from(map.values());
}
