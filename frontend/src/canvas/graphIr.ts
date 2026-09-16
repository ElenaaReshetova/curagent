import { MarkerType, type Edge, type Node } from "@xyflow/react";
import type { GraphKind, NodeRegistryEntry, WorkflowEdge, WorkflowGraph } from "../types";
import { nodeBoxSize } from "./ports";
import { isGovernanceNode } from "../governance";

const EDGE_STYLE = { stroke: "#94a3b8", strokeWidth: 2 };
const MARKER = { type: MarkerType.ArrowClosed, width: 14, height: 14, color: "#94a3b8" };

export const DEFAULT_EDGE_OPTIONS = {
  type: "selectable" as const,
  markerEnd: MARKER,
  style: EDGE_STYLE,
  interactionWidth: 40,
  deletable: true,
  selectable: true,
};

/** True when nodes already have a real saved layout (not missing / stacked / origin). */
export function hasSavedLayout(nodes: { position?: { x?: number; y?: number } | null }[]): boolean {
  if (!nodes.length) return true;
  const pts: { x: number; y: number }[] = [];
  for (const n of nodes) {
    const x = n.position?.x;
    const y = n.position?.y;
    if (x == null || y == null || Number.isNaN(Number(x)) || Number.isNaN(Number(y))) continue;
    pts.push({ x: Number(x), y: Number(y) });
  }
  if (!pts.length) return false;
  if (nodes.length === 1) return true;
  if (pts.length < nodes.length && pts.length < 2) return false;
  const keys = new Set(pts.map((p) => `${Math.round(p.x)},${Math.round(p.y)}`));
  if (keys.size <= 1) return false;
  return true;
}

export function toFlowNodes(graph: WorkflowGraph, registry: NodeRegistryEntry[]): Node[] {
  const byType = Object.fromEntries(registry.map((e) => [e.type, e]));
  return graph.nodes
    .map((n) => {
      let nodeType = n.type as string;
      let config = { ...(n.config || {}) };
      if (nodeType === "end" || String(config.type || "").toUpperCase() === "END") {
        return null;
      }
      if (nodeType === "subflow" || String(config.type || "").toUpperCase() === "SUBFLOW") {
        nodeType = "subflow";
        config = { ...config, type: "SUBFLOW" };
      }
      const box = nodeBoxSize(nodeType, config);
      const locked = isGovernanceNode({ id: n.id, config, metadata: n.metadata });
      const x = n.position?.x;
      const y = n.position?.y;
      return {
        id: n.id,
        type: "workflow",
        position: {
          x: x == null || Number.isNaN(Number(x)) ? 0 : Number(x),
          y: y == null || Number.isNaN(Number(y)) ? 0 : Number(y),
        },
        width: box.w,
        height: box.h,
        deletable: !locked,
        data: {
          label: n.label,
          nodeType,
          entry: byType[nodeType],
          config,
          metadata: locked ? { ...(n.metadata || {}), immutable: true, governance: true } : n.metadata || {},
        },
      };
    })
    .filter(Boolean) as Node[];
}

export function humanEdgeLabel(handle: string | null | undefined, label: string | null | undefined): string | undefined {
  if (label && String(label).trim()) return String(label);
  const h = String(handle || "").toLowerCase();
  if (!h || h === "out") return undefined;
  const map: Record<string, string> = {
    approve: "Approve",
    changes: "На доработку",
    reject: "Reject",
    decline: "Decline",
    yes: "Yes",
    no: "No",
    pass: "Yes",
    fail: "No",
    true: "Yes",
    false: "No",
  };
  return map[h] || handle || undefined;
}

export function toFlowEdges(graph: WorkflowGraph): Edge[] {
  return graph.edges.map((e) => {
    const handle = e.sourceHandle || e.condition || undefined;
    return styleEdge({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: handle,
      targetHandle: e.targetHandle || "in",
      label: humanEdgeLabel(handle, e.label),
      data: {
        condition: e.condition || handle || null,
        fallback: e.fallback ?? false,
        waypoint: e.waypoint || undefined,
      },
    });
  });
}

export function styleEdge(e: Edge): Edge {
  const handle = String(e.sourceHandle || (e.data && (e.data as { condition?: string }).condition) || "").toLowerCase();
  let color = "#94a3b8";
  if (["approve", "yes", "pass", "true"].includes(handle)) color = "#16a34a";
  if (["changes", "clarify", "request_changes"].includes(handle)) color = "#d97706";
  if (["reject", "decline", "no", "fail", "false"].includes(handle)) color = "#dc2626";
  return {
    ...e,
    type: "selectable",
    animated: false,
    deletable: e.deletable !== false,
    selectable: e.selectable !== false,
    interactionWidth: e.interactionWidth ?? 40,
    style: {
      ...EDGE_STYLE,
      stroke: color,
      ...(e.style || {}),
    },
    markerEnd: { ...MARKER, color },
    label: e.label,
    data: {
      ...(typeof e.data === "object" && e.data ? e.data : {}),
      condition: handle && handle !== "out" ? handle : (e.data as { condition?: string } | undefined)?.condition ?? null,
      waypoint: (e.data as { waypoint?: { x: number; y: number } } | undefined)?.waypoint,
    },
  };
}

export function edgeToIr(e: Edge): WorkflowEdge {
  const handle = (e.sourceHandle || undefined) as string | undefined;
  const dataCond =
    e.data && typeof (e.data as { condition?: string }).condition === "string"
      ? String((e.data as { condition: string }).condition)
      : null;
  const label = typeof e.label === "string" ? e.label : null;
  const condition = dataCond || (handle && handle !== "out" ? handle : null) || null;
  const fallback = (e.data as { fallback?: boolean } | undefined)?.fallback;
  const waypoint = (e.data as { waypoint?: { x: number; y: number } } | undefined)?.waypoint;
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: handle || condition,
    targetHandle: e.targetHandle || "in",
    condition,
    fallback: fallback ?? false,
    label: label || condition,
    waypoint: waypoint || null,
  };
}

export function fromFlow(
  kind: GraphKind,
  name: string,
  graphId: string,
  nodes: Node[],
  edges: Edge[],
  base?: WorkflowGraph,
): WorkflowGraph {
  return {
    graphId,
    version: base?.version || "0.1.0",
    name: name || base?.name || "",
    description: base?.description || "",
    kind,
    entrypoints: nodes.filter((n) => (n.data as { nodeType?: string }).nodeType === "trigger").map((n) => n.id),
    nodes: nodes.map((n) => ({
      id: n.id,
      type: (n.data as { nodeType: WorkflowGraph["nodes"][number]["type"] }).nodeType,
      label: (n.data as { label: string }).label,
      position: n.position,
      config: (n.data as { config?: Record<string, unknown> }).config || {},
      metadata: (n.data as { metadata?: Record<string, unknown> }).metadata || {},
    })),
    edges: edges.map(edgeToIr),
    policies: base?.policies || null,
    produces: base?.produces || [],
    metadata: base?.metadata || {},
    variables: base?.variables || [],
  };
}

export function emptyGraph(kind: GraphKind): WorkflowGraph {
  return {
    graphId: "",
    version: "0.1.0",
    name: kind === "stage" ? "Сценарий" : "Е2Е сценарий",
    kind,
    entrypoints: [],
    nodes: [],
    edges: [],
    policies: {},
  };
}
