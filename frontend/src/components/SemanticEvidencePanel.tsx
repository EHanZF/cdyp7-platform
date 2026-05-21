import type {
  SemanticEvidence,
  RequirementMatch
} from "../types/mcp";

interface Props {
  evidence?: SemanticEvidence;
  loading?: boolean;
}

function EvidenceCard({
  match
}: {
  match: RequirementMatch;
}) {
  return (
    <div
      style={{
        border: "1px solid #ccc",
        borderRadius: "8px",
        padding: "12px",
        marginBottom: "12px",
        background: "#fafafa"
      }}
    >
      <div>
        <strong>
          {match.requirement_id}
        </strong>
      </div>

      <div>
        Similarity Score:
        {" "}
        {(match.score * 100).toFixed(1)}%
      </div>

      <div
        style={{
          marginTop: "8px"
        }}
      >
        {match.content}
      </div>
    </div>
  );
}

export default function SemanticEvidencePanel({
  evidence,
  loading = false
}: Props) {
  if (loading) {
    return (
      <div>
        <h2>Semantic Evidence</h2>
        <div>Loading evidence...</div>
      </div>
    );
  }

  if (
    !evidence ||
    evidence.matches.length === 0
  ) {
    return (
      <div>
        <h2>Semantic Evidence</h2>
        <div>No evidence found.</div>
      </div>
    );
  }

  return (
    <div>
      <h2>Semantic Evidence</h2>

      <div
        style={{
          marginBottom: "16px"
        }}
      >
        Evidence matches:
        {" "}
        {evidence.matches.length}
      </div>

      {evidence.matches.map((match) => (
        <EvidenceCard
          key={match.requirement_id}
          match={match}
        />
      ))}
    </div>
  );
}