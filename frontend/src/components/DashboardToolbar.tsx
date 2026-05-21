type DashboardToolbarProps = {
  query: string;
  search: string;
  dispatching: boolean;
  onQueryChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
  onLoadDemo: () => void;
};

export default function DashboardToolbar({
  query,
  search,
  dispatching,
  onQueryChange,
  onSearchChange,
  onRefresh,
  onLoadDemo
}: DashboardToolbarProps) {
  return (
    <section className="toolbar" aria-label="Dashboard controls">
      <div>
        <label htmlFor="queryInput">Codebeamer Query</label>
        <input
          id="queryInput"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="type = 'Requirement'"
        />
      </div>
      <div>
        <label htmlFor="searchInput">Search</label>
        <input
          id="searchInput"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="ID, title, owner, status..."
        />
      </div>
      <button onClick={onRefresh} disabled={dispatching}>
        {dispatching ? "Dispatching..." : "Refresh"}
      </button>
      <button className="secondary" onClick={onLoadDemo}>
        Demo
      </button>
    </section>
  );
}
