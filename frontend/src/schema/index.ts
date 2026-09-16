/**
 * Graph IR types are kept in sync with Python pydantic models via:
 *   .venv/bin/python scripts/sync_graph_schema.py
 * Source of truth for JSON Schema: config/platform/workflow-graph.schema.json
 * (also copied to this folder).
 */
import schema from "./workflow-graph.schema.json";

export { schema as workflowGraphSchema };

export const NODE_TYPES = (schema.nodeTypes || []) as string[];

/** Lightweight structural check — not a full JSON Schema validator. */
export function assertWorkflowGraphShape(value: unknown): value is {
  nodes: unknown[];
  edges: unknown[];
  kind?: string;
} {
  if (!value || typeof value !== "object") return false;
  const g = value as Record<string, unknown>;
  return Array.isArray(g.nodes) && Array.isArray(g.edges);
}

export function knownNodeType(type: string): boolean {
  return NODE_TYPES.includes(type);
}
