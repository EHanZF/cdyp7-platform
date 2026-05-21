type HeaderProps = {
  live: boolean;
  statusText: string;
};

export default function Header({ live, statusText }: HeaderProps) {
  return (
    <header className="dashboard-header">
      <div>
        <h1>CDYP7 MCP Codebeamer ALM Dashboard</h1>
        <p className="subtitle">
          Visual project-management status for open ALM items, delivery timing, task ownership,
          and remaining delivery scope. Data is pulled through the CDYP7 MCP backend so
          Codebeamer credentials stay out of the browser.
        </p>
      </div>
      <div className="status-pill" aria-live="polite">
        <span className={`dot ${live ? "live" : ""}`} />
        <span>{statusText}</span>
      </div>
    </header>
  );
}
