export interface MCPRequest {
  tool: string;
  input: Record<string, unknown>;
}

export interface RequirementMatch {
  requirement_id: string;
  score: number;
  content: string;
}

export interface SemanticEvidence {
  matches: RequirementMatch[];
}

export interface GraphNode {
  id: string;
  name: string;
  links?: { id: string }[];
}

export interface LiveRunState {
  updated: string;
}

export interface Receipt {
  receipt_id: string;
  tool?: string;
  authority?: string;
}