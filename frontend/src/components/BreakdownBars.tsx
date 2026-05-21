type BreakdownBarsProps = {
  title: string;
  data: Record<string, number>;
};

export default function BreakdownBars({ title, data }: BreakdownBarsProps) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, value]) => value), 1);

  return (
    <article className="card">
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <div className="empty">No data in scope.</div>
      ) : (
        entries.map(([label, value]) => (
          <div className="bar-row" key={label}>
            <div className="bar-label">
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
            <progress className="bar-progress" max={max} value={value} aria-label={label} />
          </div>
        ))
      )}
    </article>
  );
}
