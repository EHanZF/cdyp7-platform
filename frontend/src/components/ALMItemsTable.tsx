import type { ALMItem } from "../types/alm";
import { formatDate, initials } from "../utils/format";
import { isClosed, isHighPriority, isOverdue } from "../utils/metrics";

type ALMItemsTableProps = {
  items: ALMItem[];
};

function riskLabel(item: ALMItem): string {
  if (item.blocked) return "Blocked";
  if (isOverdue(item.dueDate)) return "Overdue";
  if (isHighPriority(item.priority)) return "High focus";
  return "On track";
}

export default function ALMItemsTable({ items }: ALMItemsTableProps) {
  const openItems = items.filter((item) => !isClosed(item.status));

  return (
    <section className="card">
      <div className="table-heading">
        <div>
          <h2>Open ALM Items</h2>
          <p className="subtitle">
            Latest Codebeamer items including owner, due date, status, priority, tracker,
            and remaining scope.
          </p>
        </div>
      </div>
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Status</th>
              <th>Priority</th>
              <th>Owner</th>
              <th>Tracker</th>
              <th>Due / Delivery Date</th>
              <th>Remaining</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {openItems.length === 0 ? (
              <tr>
                <td colSpan={9}>
                  <div className="empty">No open items match the current filters.</div>
                </td>
              </tr>
            ) : (
              openItems.map((item) => {
                const owners = item.assignedTo.length ? item.assignedTo : ["Unassigned"];
                return (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noreferrer">
                          {item.name}
                        </a>
                      ) : (
                        item.name
                      )}
                    </td>
                    <td>
                      <span className="badge open">{item.status ?? "Unknown"}</span>
                    </td>
                    <td>
                      <span className="badge risk">{item.priority ?? "Unspecified"}</span>
                    </td>
                    <td>
                      <div className="owner-list">
                        {owners.map((owner) => (
                          <span className="avatar" key={owner} title={owner}>
                            {initials(owner)}
                          </span>
                        ))}
                        <span>{owners.join(", ")}</span>
                      </div>
                    </td>
                    <td>{item.tracker ?? "Unknown"}</td>
                    <td>{formatDate(item.dueDate || item.deliveryDate)}</td>
                    <td>{item.remaining ?? item.storyPoints ?? 1}</td>
                    <td>{riskLabel(item)}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
