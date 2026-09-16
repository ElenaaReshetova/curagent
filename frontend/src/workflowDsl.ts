/** Workflow DSL ↔ React Flow canvas helpers.

Workflows have no End node — leaf actions/conditions terminate the run.
CONDITION branches use ``options`` + connection ``sourceOptionIdentifier``.
INPUT uses ``outlets`` + ``sourceOutletIdentifier``.
*/

import type { GraphKind, WorkflowEdge, WorkflowGraph, WorkflowNode, NodeType } from "./types";
import { isGovernanceNode, readProduces } from "./governance";

const CANVAS_TO_CONFIG: Record<string, string> = {
  trigger: "SELF_SERVE_TRIGGER",
  ai_agent: "AI_AGENT",
  ai: "AI",
  webhook: "WEBHOOK",
  condition: "CONDITION",
  input: "INPUT",
  upsert_entity: "UPSERT_ENTITY",
  kafka: "KAFKA",
  integration_action: "INTEGRATION_ACTION",
  internal_service: "INTERNAL_SERVICE",
  subflow: "SUBFLOW",
};

const CONFIG_TO_CANVAS: Record<string, NodeType> = {
  SELF_SERVE_TRIGGER: "trigger",
  EVENT_TRIGGER: "trigger",
  SCHEDULE_TRIGGER: "trigger",
  AI_AGENT: "ai_agent",
  AI: "ai",
  WEBHOOK: "webhook",
  CONDITION: "condition",
  INPUT: "input",
  UPSERT_ENTITY: "upsert_entity",
  KAFKA: "kafka",
  INTEGRATION_ACTION: "integration_action",
  INTERNAL_SERVICE: "internal_service",
  SUBFLOW: "subflow",
};

export type WorkflowDsl = {
  identifier: string;
  title: string;
  description?: string;
  nodes: Array<{
    identifier: string;
    title: string;
    description?: string;
    config: Record<string, unknown>;
  }>;
  connections: Array<{
    sourceIdentifier: string;
    targetIdentifier: string;
    sourceOutletIdentifier?: string | null;
    sourceOptionIdentifier?: string | null;
    fallback?: boolean;
  }>;
  ui?: {
    positions?: Record<string, { x: number; y: number }>;
    kind?: GraphKind;
    edgeWaypoints?: Record<string, { x: number; y: number }>;
  };
  produces?: string[];
};

export function isWorkflowDsl(doc: unknown): doc is WorkflowDsl {
  if (!doc || typeof doc !== "object") return false;
  const value = doc as Record<string, unknown>;
  return (
    typeof value.identifier === "string" &&
    Array.isArray(value.nodes) &&
    Array.isArray(value.connections) &&
    !Array.isArray(value.edges)
  );
}

export function isCanvasWorkflowGraph(doc: unknown): doc is WorkflowGraph {
  if (!doc || typeof doc !== "object") return false;
  const value = doc as Record<string, unknown>;
  return (
    Array.isArray(value.nodes) &&
    Array.isArray(value.edges) &&
    value.nodes.every((node) => !!node && typeof node === "object" && typeof (node as { id?: unknown }).id === "string")
  );
}

/** Accept the canonical workflow DSL and the API's canvas projection. */
export function workflowDocumentToCanvas(
  document: unknown,
  kind: GraphKind = "e2e",
): WorkflowGraph | null {
  let value = document;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return null;
    }
  }
  if (isWorkflowDsl(value)) return workflowDslToCanvas(value, kind);
  if (!isCanvasWorkflowGraph(value)) return null;
  return {
    ...value,
    graphId: value.graphId || "",
    version: value.version || "0.1.0",
    name: value.name || "",
    kind: value.kind || kind,
    entrypoints: value.entrypoints || [],
    nodes: value.nodes,
    edges: value.edges,
  };
}

export function edgeLayoutKey(source: string, target: string, handle?: string | null) {
  const h = handle && handle !== "out" ? handle : "";
  return `${source}::${target}::${h}`;
}

export function canvasToWorkflowDsl(graph: WorkflowGraph): WorkflowDsl {
  const positions: Record<string, { x: number; y: number }> = {};
  const byId = new Map((graph.nodes || []).map((n) => [n.id, n]));
  const nodes = (graph.nodes || [])
    .filter((n) => n.type !== ("end" as NodeType) && String(n.config?.type || "").toUpperCase() !== "END")
    .map((n) => {
      if (n.position && Number.isFinite(Number(n.position.x)) && Number.isFinite(Number(n.position.y))) {
        positions[n.id] = { x: Number(n.position.x), y: Number(n.position.y) };
      }
      const cfg = { ...(n.config || {}) };
      if (!cfg.type) {
        cfg.type =
          n.type === "trigger"
            ? (cfg.triggerType as string) || "SELF_SERVE_TRIGGER"
            : CANVAS_TO_CONFIG[n.type] || String(n.type).toUpperCase();
      }
      // CONDITION: uses options[]
      if (String(cfg.type).toUpperCase() === "CONDITION") {
        delete (cfg as { outlets?: unknown }).outlets;
        delete (cfg as { outcomes?: unknown }).outcomes;
      }
      delete (cfg as { skill_keys?: unknown }).skill_keys;
      delete (cfg as { skill_key?: unknown }).skill_key;
      delete (cfg as { rule_keys?: unknown }).rule_keys;
      if (String(cfg.type).toUpperCase() !== "SUBFLOW") {
        delete (cfg as { playbook_key?: unknown }).playbook_key;
        delete (cfg as { flow_key?: unknown }).flow_key;
        delete (cfg as { graph_key?: unknown }).graph_key;
        delete (cfg as { graph_id?: unknown }).graph_id;
        delete (cfg as { graph_kind?: unknown }).graph_kind;
      }
      delete (cfg as { testOutputs?: unknown }).testOutputs;
      const locked = isGovernanceNode({ id: n.id, config: cfg, metadata: n.metadata });
      if (locked) {
        cfg.governance = true;
        cfg.immutable = true;
      }
      return {
        identifier: n.id,
        title: n.label || n.id,
        config: cfg,
      };
    });
  const keep = new Set(nodes.map((n) => n.identifier));
  const edgeWaypoints: Record<string, { x: number; y: number }> = {};
  const connections = (graph.edges || [])
    .filter((e) => keep.has(e.source) && keep.has(e.target))
    .map((e) => {
      const handle = e.sourceHandle || e.condition || undefined;
      if (e.waypoint && Number.isFinite(e.waypoint.x) && Number.isFinite(e.waypoint.y)) {
        edgeWaypoints[edgeLayoutKey(e.source, e.target, handle)] = { x: e.waypoint.x, y: e.waypoint.y };
      }
      const src = byId.get(e.source);
      const srcType = String(src?.config?.type || "").toUpperCase() || (src?.type === "condition" ? "CONDITION" : src?.type === "input" ? "INPUT" : "");
      if (srcType === "CONDITION") {
        return {
          sourceIdentifier: e.source,
          targetIdentifier: e.target,
          sourceOptionIdentifier: handle || undefined,
          fallback: e.fallback ?? false,
        };
      }
      return {
        sourceIdentifier: e.source,
        targetIdentifier: e.target,
        sourceOutletIdentifier: handle || undefined,
        fallback: e.fallback ?? false,
      };
    });
  return {
    identifier: graph.graphId || "workflow",
    title: graph.name || "",
    description: graph.description || "",
    produces: readProduces(graph),
    nodes,
    connections,
    ui: { positions, kind: graph.kind, ...(Object.keys(edgeWaypoints).length ? { edgeWaypoints } : {}) },
  };
}

export function workflowDslToCanvas(dsl: WorkflowDsl, kind: GraphKind = "e2e"): WorkflowGraph {
  const positions = dsl.ui?.positions || {};
  const nodes: WorkflowNode[] = (dsl.nodes || [])
    .filter((n) => String((n.config || {}).type || "").toUpperCase() !== "END")
    .map((n) => {
      const cfgType = String((n.config || {}).type || "").toUpperCase();
      const type: NodeType = CONFIG_TO_CANVAS[cfgType] || (cfgType.toLowerCase() as NodeType);
      const config = { ...(n.config || {}) };
      const locked = isGovernanceNode({ id: n.identifier, config });
      return {
        id: n.identifier,
        type,
        label: n.title || n.identifier,
        position: positions[n.identifier] || { x: 0, y: 0 },
        config,
        metadata: locked ? { immutable: true, governance: true } : undefined,
      };
    });
  const keep = new Set(nodes.map((n) => n.id));
  const wps = dsl.ui?.edgeWaypoints || {};
  const edges: WorkflowEdge[] = (dsl.connections || [])
    .filter((c) => keep.has(c.sourceIdentifier) && keep.has(c.targetIdentifier))
    .map((c, i) => {
      const handle = c.sourceOptionIdentifier || c.sourceOutletIdentifier || undefined;
      const wp = wps[edgeLayoutKey(c.sourceIdentifier, c.targetIdentifier, handle)];
      return {
        id: `c${i}-${c.sourceIdentifier}-${c.targetIdentifier}`,
        source: c.sourceIdentifier,
        target: c.targetIdentifier,
        sourceHandle: handle,
        condition: handle,
        fallback: c.fallback,
        waypoint: wp || null,
      };
    });
  return {
    graphId: dsl.identifier,
    version: "0.1.0",
    name: dsl.title,
    description: dsl.description || "",
    kind: dsl.ui?.kind || kind,
    produces: dsl.produces || [],
    entrypoints: nodes.filter((n) => n.type === "trigger").map((n) => n.id),
    nodes,
    edges,
  };
}
