export async function listWorkflowRuns() {
  return [
    {
      id: 101,
      status: "completed",
      conclusion: "success",
      workflow: "MCP Backend"
    },
    {
      id: 102,
      status: "in_progress",
      conclusion: null,
      workflow: "Deploy Frontend"
    }
  ];
}