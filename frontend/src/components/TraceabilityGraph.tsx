import ReactFlow from "reactflow";
import "reactflow/dist/style.css";

const nodes = [
  {
    id: "REQ-1",
    position: { x: 100, y: 100 },
    data: {
      label: "Brake Requirement"
    },
    type: "default"
  },
  {
    id: "TEST-1",
    position: { x: 400, y: 100 },
    data: {
      label: "Validation Test"
    },
    type: "default"
  }
];

const edges = [
  {
    id: "edge-1",
    source: "REQ-1",
    target: "TEST-1"
  }
];

export default function TraceabilityGraph() {
  return (
    <div className="graph-container">
      <h2>Traceability Graph</h2>

      <ReactFlow
        nodes={nodes}
        edges={edges}
      />
    </div>
  );
}