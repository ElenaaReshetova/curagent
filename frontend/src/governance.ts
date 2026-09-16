import type { WorkflowNode } from "./types";

export const GOVERNANCE_TAIL_ID = "governance-tail";

export const ARTIFACT_TYPES: { value: string; label: string }[] = [
  { value: "BUSINESS_REQUIREMENTS", label: "Business Requirements" },
  { value: "SYSTEM_REQUIREMENTS", label: "System Requirements" },
  { value: "TEST_CASE_PACK", label: "Test Case Pack" },
  { value: "CODE_ANALYSIS", label: "Code Analysis" },
  { value: "ARCHITECTURE", label: "Architecture" },
  { value: "GENERAL", label: "General artifact" },
];

export function isGovernanceNode(node: {
  id?: string;
  config?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  data?: { config?: Record<string, unknown>; metadata?: Record<string, unknown> };
}): boolean {
  const cfg = node.config || node.data?.config || {};
  const meta = node.metadata || node.data?.metadata || {};
  return (
    String(node.id || "").startsWith("governance-") ||
    node.id === GOVERNANCE_TAIL_ID ||
    node.id === "stage-artifact-gate" ||
    !!meta.immutable ||
    !!meta.governance ||
    !!cfg.governance ||
    !!cfg.immutable ||
    cfg.service === "policy.evaluate"
  );
}

export function isGovernanceEdge(
  source: string,
  target: string,
  nodes: Array<{ id: string; data?: { config?: Record<string, unknown>; metadata?: Record<string, unknown> }; config?: Record<string, unknown> }>,
): boolean {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const src = byId.get(source);
  const tgt = byId.get(target);
  return !!(src && isGovernanceNode(src)) || !!(tgt && isGovernanceNode(tgt));
}

/** Drop locked gates whose producer/anchor was removed with the branch. */
export function pruneOrphanGovernance<N extends { id: string; data?: { config?: Record<string, unknown> } }, E extends { source: string; target: string }>(
  nodes: N[],
  edges: E[],
): { nodes: N[]; edges: E[]; removed: string[] } {
  const live = new Set(nodes.map((n) => n.id));
  const removed: string[] = [];
  for (const node of nodes) {
    if (!isGovernanceNode({ id: node.id, data: node.data as any })) continue;
    const cfg = node.data?.config || {};
    const producer = String(cfg.producer || cfg.anchor || "").trim();
    const fromId = node.id.startsWith("governance-") ? node.id.slice("governance-".length) : "";
    const anchor = producer || fromId;
    const incoming = edges.filter((e) => e.target === node.id && live.has(e.source) && e.source !== node.id);
    if ((anchor && !live.has(anchor)) || incoming.length === 0) {
      removed.push(node.id);
    }
  }
  if (!removed.length) return { nodes, edges, removed };
  const drop = new Set(removed);
  return {
    nodes: nodes.filter((n) => !drop.has(n.id)),
    edges: edges.filter((e) => !drop.has(e.source) && !drop.has(e.target)),
    removed,
  };
}

export function readProduces(graph: { produces?: string[] | null; policies?: Record<string, unknown> | null }): string[] {
  const fromGraph = graph.produces || [];
  const fromPolicies = (graph.policies as { produces?: string[] } | null)?.produces || [];
  const raw = fromGraph.length ? fromGraph : fromPolicies;
  return Array.from(new Set(raw.map((p) => String(p).trim()).filter(Boolean)));
}

export function asProducesList(node: WorkflowNode | null | undefined): string {
  return String(node?.config?.produces || "");
}

export function artifactLabel(value: string): string {
  const hit = ARTIFACT_TYPES.find((t) => t.value === value);
  return hit ? hit.label : value;
}

export function artifactLabels(values: string[]): string {
  return values.map(artifactLabel).filter(Boolean).join(", ");
}

const PUBLICATION_TYPES = new Set(["KAFKA", "INTEGRATION_ACTION", "UPSERT_ENTITY"]);
const PUBLICATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function isPublicationNode(node: {
  id?: string;
  type?: string;
  config?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  data?: { nodeType?: string; config?: Record<string, unknown>; metadata?: Record<string, unknown> };
}): boolean {
  if (isGovernanceNode(node)) return false;
  const cfg = node.config || node.data?.config || {};
  const t = String(cfg.type || node.type || node.data?.nodeType || "").toUpperCase();
  if (cfg.publication) return true;
  if (PUBLICATION_TYPES.has(t)) return true;
  if (t === "WEBHOOK") {
    return PUBLICATION_METHODS.has(String(cfg.method || "POST").toUpperCase());
  }
  return false;
}

export function graphHasPublication(nodes: Array<{
  id?: string;
  type?: string;
  config?: Record<string, unknown> | null;
  data?: { nodeType?: string; config?: Record<string, unknown> };
}>): boolean {
  return nodes.some((n) => isPublicationNode(n));
}
