import ELK from "elkjs/lib/elk.bundled.js";
import type { Edge, Node } from "@xyflow/react";
import { nodeBoxSize } from "./ports";

const elk = new ELK();

type GraphNodeData = {
  nodeType?: string;
  config?: Record<string, unknown>;
};

/**
 * Back-edges are only those that close a cycle (target is on the current DFS
 * stack). Decline → a dedicated fail step is a forward branch and stays in
 * the layered layout so it does not jump to layer 0.
 */
export function findBackEdgeIds(nodes: Node[], edges: Edge[]): Set<string> {
  const ids = new Set(nodes.map((n) => n.id));
  const adj = new Map<string, Edge[]>();
  for (const e of edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) continue;
    const list = adj.get(e.source) || [];
    list.push(e);
    adj.set(e.source, list);
  }

  const incoming = new Map<string, number>();
  for (const n of nodes) incoming.set(n.id, 0);
  for (const e of edges) {
    if (ids.has(e.target)) incoming.set(e.target, (incoming.get(e.target) || 0) + 1);
  }

  const roots = nodes.filter((n) => {
    const t = String((n.data as GraphNodeData)?.nodeType || "");
    return t === "trigger" || (incoming.get(n.id) || 0) === 0;
  });
  const start = roots.length ? roots : nodes.slice(0, 1);

  const back = new Set<string>();
  const color = new Map<string, 0 | 1 | 2>(); // 0 white, 1 gray, 2 black

  const dfs = (nid: string) => {
    color.set(nid, 1);
    for (const e of adj.get(nid) || []) {
      const c = color.get(e.target) ?? 0;
      if (c === 1) {
        back.add(e.id);
        continue;
      }
      if (c === 0) dfs(e.target);
    }
    color.set(nid, 2);
  };

  for (const n of start) {
    if ((color.get(n.id) ?? 0) === 0) dfs(n.id);
  }
  for (const n of nodes) {
    if ((color.get(n.id) ?? 0) === 0) dfs(n.id);
  }
  return back;
}

export async function layoutWithElk(
  nodes: Node[],
  edges: Edge[],
  direction: "RIGHT" | "DOWN" = "RIGHT",
): Promise<Node[]> {
  const backIds = findBackEdgeIds(nodes, edges);
  const forward = edges.filter((e) => !backIds.has(e.id));
  const graph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": direction,
      "elk.spacing.nodeNode": "48",
      "elk.layered.spacing.nodeNodeBetweenLayers": "80",
      "elk.spacing.edgeNode": "28",
      "elk.spacing.edgeEdge": "18",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.cycleBreaking.strategy": "GREEDY",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.padding": "[32,32,32,32]",
    },
    children: nodes.map((n) => {
      const data = n.data as GraphNodeData | undefined;
      const box = nodeBoxSize(String(data?.nodeType || ""), data?.config);
      return {
        id: n.id,
        width: (n.measured?.width || n.width || box.w) as number,
        height: (n.measured?.height || n.height || box.h) as number,
      };
    }),
    edges: forward.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  };

  const layouted = await elk.layout(graph as unknown as Parameters<typeof elk.layout>[0]);
  const pos = new Map(
    (layouted.children || []).map((c) => [c.id, { x: c.x || 0, y: c.y || 0 }]),
  );
  return nodes.map((n) => ({
    ...n,
    position: pos.get(n.id) || n.position,
  }));
}
