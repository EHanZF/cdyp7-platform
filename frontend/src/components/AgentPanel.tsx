export default function AgentPanel() {
  const dispatchTask = () => {
    alert("Dispatching MCP task");
  };

  return (
    <div>
      <h2>Agent Control</h2>

      <button onClick={dispatchTask}>
        Dispatch MCP Task
      </button>
    </div>
  );
}