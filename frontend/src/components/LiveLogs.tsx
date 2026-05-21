import { useEffect, useState } from "react";

export default function LiveLogs() {
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      setLogs((prev) => [
        ...prev,
        `[${new Date().toISOString()}] MCP heartbeat`
      ]);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h2>Live Logs</h2>

      <pre className="logs-panel">
        {logs.join("\n")}
      </pre>
    </div>
  );
}
