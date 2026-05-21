import AgentPanel from "../components/AgentPanel";
import RunViewer from "../components/RunViewer";
import ReceiptViewer from "../components/ReceiptViewer";
import TraceabilityGraph from "../components/TraceabilityGraph";
import SemanticEvidencePanel from "../components/SemanticEvidencePanel";
import HITLApprovalPanel from "../components/HITLApprovalPanel";
import LiveLogs from "../components/LiveLogs";
import MCPToolConsole from "../components/MCPToolConsole";
import "../styles/dashboard.css";

import type {
  SemanticEvidence,
  Receipt
} from "../types/mcp";

const mockEvidence: SemanticEvidence = {
  matches: [
    {
      requirement_id: "REQ-001",
      score: 0.98,
      content: "Brake timing requirement"
    },
    {
      requirement_id: "REQ-002",
      score: 0.92,
      content: "ABS validation requirement"
    }
  ]
};

const mockReceipt: Receipt = {
  receipt_id: "rcpt-001",
  authority: "non_authoritative",
  tool: "cdyp7.semantic.search"
};

export default function Dashboard() {
  return (
    <div className="dashboard">
      <h1>CDYP7 MCP Dashboard</h1>

      <AgentPanel />

      <RunViewer />

      <LiveLogs />

      <MCPToolConsole />

      <SemanticEvidencePanel
        evidence={mockEvidence}
      />

      <TraceabilityGraph />

      <HITLApprovalPanel
        receipt={mockReceipt}
      />

      <ReceiptViewer />
    </div>
  );
}