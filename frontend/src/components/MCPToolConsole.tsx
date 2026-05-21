import { useState } from "react";

export default function MCPToolConsole() {
  const [tool, setTool] = useState("");

  const invokeTool = () => {
    alert(`Invoking MCP tool: ${tool}`);
  };

  return (
    <div>
      <h2>MCP Tool Console</h2>

      <input
        value={tool}
        onChange={(e) => setTool(e.target.value)}
        placeholder="cdyp7.cb.read"
      />

      <button onClick={invokeTool}>
        Execute
      </button>
    </div>
  );
}