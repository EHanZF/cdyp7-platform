import type { ALMDashboardState } from "../types/alm";
import { formatDateTime } from "../utils/format";

type ReceiptPanelProps = {
  dashboard: ALMDashboardState;
};

export default function ReceiptPanel({ dashboard }: ReceiptPanelProps) {
  return (
    <section className="card">
      <h2>CDYP7 Receipt / Authority</h2>
      <p className="footer-note">
        Source: {dashboard.source}. Authority: {dashboard.authority}. Receipt backed:{" "}
        {String(dashboard.receiptBacked)}. Receipt ID: {dashboard.receiptId ?? "not provided"}.
        Generated: {formatDateTime(dashboard.generatedAt)}.
      </p>
    </section>
  );
}
