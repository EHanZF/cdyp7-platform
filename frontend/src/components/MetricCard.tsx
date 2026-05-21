type MetricCardProps = {
  title: string;
  value: number | string;
  note?: string;
};

export default function MetricCard({ title, value, note }: MetricCardProps) {
  return (
    <article className="card">
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      {note ? <div className="metric-note">{note}</div> : null}
    </article>
  );
}
