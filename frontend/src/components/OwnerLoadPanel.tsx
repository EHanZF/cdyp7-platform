import type { ALMItem } from "../types/alm";
import BreakdownBars from "./BreakdownBars";

type OwnerLoadPanelProps = {
  items: ALMItem[];
};

export default function OwnerLoadPanel({ items }: OwnerLoadPanelProps) {
  const ownerCounts = items.reduce<Record<string, number>>((acc, item) => {
    const owners = item.assignedTo.length ? item.assignedTo : ["Unassigned"];

    for (const owner of owners) {
      acc[owner] = (acc[owner] ?? 0) + (item.remaining ?? 1);
    }

    return acc;
  }, {});

  return <BreakdownBars title="Ownership Load" data={ownerCounts} />;
}
