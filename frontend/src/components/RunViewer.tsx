import { useEffect, useState } from "react";

interface WorkflowRun {
  id: number;
  workflow: string;
  status: string;
  conclusion: string | null;
}

export default function RunViewer() {
  const [runs, setRuns] =
    useState<WorkflowRun[]>([]);

  useEffect(() => {
    setRuns([
      {
        id: 101,
        workflow: "MCP Backend",
        status: "completed",
        conclusion: "success"
      },
      {
        id: 102,
        workflow: "Deploy Frontend",
        status: "in_progress",
        conclusion: null
      }
    ]);
  }, []);

  return (
    <div>
      <h2>Workflow Runs</h2>

      {runs.map((run) => (
        <div
          key={run.id}
          className="panel"
          >
          <strong>{run.workflow}</strong>

          <div>Status: {run.status}</div>

          <div>
            Conclusion:
            {" "}
            {run.conclusion || "running"}
          </div>
        </div>
      ))}
    </div>
  );
}