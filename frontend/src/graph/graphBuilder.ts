import type { GraphNode } from "../types/mcp";

export function buildTraceabilityGraph(
  requirements: GraphNode[]
) {
  return {
    nodes: requirements.map((req, index) => ({
      id: req.id,
      position: {
        x: index * 150,
        y: 100
      },
      data: {
        label: req.name
      },
      type: "default"
    })),

    edges: requirements.flatMap((req) =>
      (req.links || []).map((link) => ({
        id: `${req.id}-${link.id}`,
        source: req.id,
        target: link.id
      }))
    )
  };
}