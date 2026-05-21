import type { DeliverySummary } from "../types/alm";
import { formatDate } from "../utils/format";

type DeliveryTimelineProps = {
  deliveries: DeliverySummary[];
};

export default function DeliveryTimeline({ deliveries }: DeliveryTimelineProps) {
  return (
    <article className="card">
      <h2>Delivery Timeline</h2>
      <p className="subtitle spacing-bottom">
        Delivery date, remaining scope, completion, and schedule risk.
      </p>
      {deliveries.length === 0 ? (
        <div className="empty">No delivery data found.</div>
      ) : (
        deliveries.map((delivery) => {
          const completed = delivery.completedItems;
          const total = delivery.totalItems;
          const pct = total ? Math.round((completed / total) * 100) : 0;

          return (
            <div className="timeline-item" key={delivery.id}>
              <div className="date-chip">{formatDate(delivery.deliveryDate)}</div>
              <div>
                <strong>{delivery.name}</strong>
                <progress className="delivery-progress" max={100} value={pct} />
                <div className="footer-note">
                  {completed}/{total} complete · {delivery.remainingItems} remaining
                </div>
              </div>
              <strong>{pct}%</strong>
            </div>
          );
        })
      )}
    </article>
  );
}
