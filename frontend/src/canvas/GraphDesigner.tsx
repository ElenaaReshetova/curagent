import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  ReactFlow,
  SelectionMode,
  addEdge,
  useEdgesState,
  useNodesState,
  useNodesInitialized,
  type Connection,
  type Edge,
  type Node,
  type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  forwardRef,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createApi } from "../api/client";
import { layoutWithElk } from "./elkLayout";
import { PropertyInspector, defaultConfigFor } from "../inspector/PropertyInspector";
import { FALLBACK_REGISTRY, registryForKind } from "../registry/catalog";
import type {
  DesignerHandle,
  DesignerMountOptions,
  GraphKind,
  NodePreset,
  NodeRegistryEntry,
  NodeType,
  WorkflowGraph,
  WorkflowNode,
} from "../types";
import {
  canvasToWorkflowDsl,
  isWorkflowDsl,
  workflowDocumentToCanvas,
  workflowDslToCanvas,
} from "../workflowDsl";
import { isGovernanceNode, pruneOrphanGovernance } from "../governance";
import { nodeTypes, RunHighlightContext } from "./WorkflowNode";
import { edgeTypes, EdgeEditContext } from "./SelectableEdge";
import { nodeBoxSize, outletIdSet } from "./ports";
import {
  DEFAULT_EDGE_OPTIONS,
  emptyGraph,
  fromFlow,
  hasSavedLayout,
  humanEdgeLabel,
  styleEdge,
  toFlowEdges,
  toFlowNodes,
} from "./graphIr";

type PaletteKind = "trigger" | "action" | "condition" | "input";

type HistorySnap = { nodes: Node[]; edges: Edge[]; meta: WorkflowGraph };

function cloneHistorySnap(nodes: Node[], edges: Edge[], meta: WorkflowGraph): HistorySnap {
  return {
    nodes: nodes.map((n) => ({
      ...n,
      position: { ...n.position },
      data: { ...(n.data as object) },
      selected: false,
    })),
    edges: edges.map((e) => ({
      ...e,
      selected: false,
      data: e.data && typeof e.data === "object" ? { ...(e.data as object) } : e.data,
    })),
    meta: { ...meta, produces: [...(meta.produces || [])], nodes: meta.nodes || [], edges: meta.edges || [] },
  };
}

function isEditableHotkeyTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return !!target.closest("textarea, input, select, [contenteditable='true']");
}

const PRESET_ICONS: Record<string, string> = {
  trigger: "▶",
  webhook: "⇢",
  ai_agent: "✦",
  ai: "✦",
  input: "✓",
  condition: "◇",
  upsert_entity: "▣",
  kafka: "⇢",
  integration_action: "⇢",
  internal_service: "⇢",
  subflow: "↳",
};

const PALETTE_W_KEY = "gd.paletteWidth";
const INSPECTOR_W_KEY = "gd.inspectorWidth";
const PALETTE_OPEN_KEY = "gd.paletteOpen";
const INSPECTOR_OPEN_KEY = "gd.inspectorOpen";
const PALETTE_DEFAULT = 188;
const INSPECTOR_DEFAULT = 280;
const PALETTE_MIN = 148;
const INSPECTOR_MIN = 220;
const PANEL_MAX = 560;

const paletteCache: {
  types: Partial<Record<GraphKind, NodeRegistryEntry[]>>;
  presets: Partial<Record<GraphKind, NodePreset[]>>;
} = { types: {}, presets: {} };

function storedNumber(key: string, fallback: number, min: number, max: number) {
  if (typeof window === "undefined") return fallback;
  try {
    const n = parseInt(localStorage.getItem(key) || "", 10);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  } catch {
    return fallback;
  }
}

function storedBool(key: string, fallback: boolean) {
  if (typeof window === "undefined") return fallback;
  try {
    const v = localStorage.getItem(key);
    if (v == null) return fallback;
    return v === "1" || v === "true";
  } catch {
    return fallback;
  }
}

function persist(key: string, value: number | boolean) {
  try {
    localStorage.setItem(key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
  } catch {
    /* ignore */
  }
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Math.round(n)));
}

function NodesReadyGate({ onReady }: { onReady: () => void }) {
  const ready = useNodesInitialized();
  const cb = useRef(onReady);
  cb.current = onReady;
  useEffect(() => {
    if (ready) cb.current();
  }, [ready]);
  return null;
}

export const GraphDesigner = forwardRef<DesignerHandle, DesignerMountOptions>(function GraphDesigner(
  props,
  ref,
) {
  const kind = props.kind;
  const chrome = props.chrome || "full";
  const api = useMemo(() => createApi(props.apiBase), [props.apiBase]);
  const [registry, setRegistry] = useState<NodeRegistryEntry[]>(FALLBACK_REGISTRY);
  // Host may pass empty nodes[]; keep the canvas blank (no auto End/Start).
  const initial: WorkflowGraph =
    props.graph && Array.isArray(props.graph.nodes)
      ? { ...props.graph, kind }
      : emptyGraph(kind);

  const [graphMeta, setGraphMeta] = useState<WorkflowGraph>(initial);
  const [graphId, setGraphId] = useState(props.graphId || initial.graphId || "");
  const [nodes, setNodes, onNodesChange] = useNodesState(toFlowNodes(initial, FALLBACK_REGISTRY));
  const [edges, setEdges, onEdgesChange] = useEdgesState(toFlowEdges(initial));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [issues, setIssues] = useState<any[]>([]);
  const [checklist, setChecklist] = useState<any[]>([]);
  const [panel, setPanel] = useState<"none" | "checklist" | "test">("none");
  const [viewMode, setViewMode] = useState<"canvas" | "dsl">("canvas");
  const [dslText, setDslText] = useState("");
  const [presets, setPresets] = useState<NodePreset[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(() => storedBool(PALETTE_OPEN_KEY, true));
  const [inspectorOpen, setInspectorOpen] = useState(() => storedBool(INSPECTOR_OPEN_KEY, true));
  const [paletteW, setPaletteW] = useState(() => storedNumber(PALETTE_W_KEY, PALETTE_DEFAULT, PALETTE_MIN, PANEL_MAX));
  const [inspectorW, setInspectorW] = useState(() => storedNumber(INSPECTOR_W_KEY, INSPECTOR_DEFAULT, INSPECTOR_MIN, PANEL_MAX));
  const [resizing, setResizing] = useState<"left" | "right" | null>(null);
  const [dslError, setDslError] = useState("");
  const [testInput, setTestInput] = useState(
    '{\n  "channel": "C0AKKCGEKL1",\n  "thread_ts": "",\n  "text": "Нужен BRD для нового сервиса"\n}',
  );
  const [testRunId, setTestRunId] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState("");
  const [testError, setTestError] = useState("");
  const [testCurrentNode, setTestCurrentNode] = useState<string | null>(null);
  const [testPendingNode, setTestPendingNode] = useState<string | null>(null);
  const [testReason, setTestReason] = useState("");
  const [testBusy, setTestBusy] = useState(false);
  const [scenarioStatus, setScenarioStatus] = useState<"draft" | "published" | "launched">("draft");
  const revisionRef = useRef<number | undefined>(undefined);
  const pollGenRef = useRef(0);
  const [rfInstance, setRfInstance] = useState<any>(null);
  const rfRef = useRef<any>(null);
  const canvasElRef = useRef<HTMLDivElement | null>(null);
  const pendingFitRef = useRef(true);
  const pendingAutoRef = useRef(false);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const metaRef = useRef(graphMeta);
  const graphIdRef = useRef(graphId);
  const dragRef = useRef<{ side: "left" | "right"; startX: number; startW: number } | null>(null);
  const historyRef = useRef<{ past: HistorySnap[]; future: HistorySnap[] }>({ past: [], future: [] });
  const applyingHistoryRef = useRef(false);
  const coalesceRef = useRef({ on: false, at: 0 });
  const dragHistRef = useRef(false);
  const [historyTick, setHistoryTick] = useState(0);
  nodesRef.current = nodes;
  edgesRef.current = edges;
  metaRef.current = graphMeta;
  graphIdRef.current = graphId;

  const applyScenarioCard = (card: any) => {
    if (typeof card?.revision === "number") revisionRef.current = card.revision;
    if (card?.status === "draft" || card?.status === "published" || card?.status === "launched") {
      setScenarioStatus(card.status);
    }
  };

  const bumpHistory = () => setHistoryTick((t) => t + 1);

  const scheduleFit = (duration = 0) => {
    const run = () => {
      const inst = rfRef.current;
      if (!inst?.fitView || !pendingFitRef.current) return;
      if (!nodesRef.current.length) return;
      const el = canvasElRef.current;
      if (el && (el.clientWidth < 40 || el.clientHeight < 40)) return;
      pendingFitRef.current = false;
      inst.fitView({ padding: 0.2, duration, maxZoom: 1.15, minZoom: 0.2 });
    };
    requestAnimationFrame(() => requestAnimationFrame(run));
    window.setTimeout(run, 60);
  };

  const pushHistory = (coalesce = false) => {
    if (applyingHistoryRef.current || props.readOnly) return;
    const now = Date.now();
    if (coalesce && coalesceRef.current.on && now - coalesceRef.current.at < 600) {
      coalesceRef.current.at = now;
      return;
    }
    coalesceRef.current = { on: coalesce, at: now };
    historyRef.current.past.push(cloneHistorySnap(nodesRef.current, edgesRef.current, metaRef.current));
    if (historyRef.current.past.length > 80) historyRef.current.past.shift();
    historyRef.current.future = [];
    bumpHistory();
  };

  const applySnapshot = (snap: HistorySnap) => {
    applyingHistoryRef.current = true;
    setNodes(snap.nodes);
    setEdges(snap.edges);
    nodesRef.current = snap.nodes;
    edgesRef.current = snap.edges;
    setGraphMeta(snap.meta);
    metaRef.current = snap.meta;
    applyingHistoryRef.current = false;
    props.onChange?.(
      fromFlow(kind, snap.meta.name, graphIdRef.current || snap.meta.graphId || "", snap.nodes, snap.edges, snap.meta),
    );
  };

  const undo = () => {
    if (props.readOnly || !historyRef.current.past.length) return;
    const current = cloneHistorySnap(nodesRef.current, edgesRef.current, metaRef.current);
    const prev = historyRef.current.past.pop()!;
    historyRef.current.future.push(current);
    applySnapshot(prev);
    bumpHistory();
  };

  const redo = () => {
    if (props.readOnly || !historyRef.current.future.length) return;
    const current = cloneHistorySnap(nodesRef.current, edgesRef.current, metaRef.current);
    const next = historyRef.current.future.pop()!;
    historyRef.current.past.push(current);
    applySnapshot(next);
    bumpHistory();
  };

  const undoRef = useRef(undo);
  const redoRef = useRef(redo);
  undoRef.current = undo;
  redoRef.current = redo;

  const canUndo = historyTick >= 0 && historyRef.current.past.length > 0;
  const canRedo = historyTick >= 0 && historyRef.current.future.length > 0;

  useEffect(() => {
    if (props.graphId && props.graphId !== graphIdRef.current) {
      setGraphId(props.graphId);
    }
  }, [props.graphId]);

  const palette = useMemo(() => registryForKind(registry, kind), [registry, kind]);

  useEffect(() => {
    const cached = paletteCache.types[kind];
    if (cached && cached.length) {
      setRegistry(cached);
      return;
    }
    api
      .nodeTypes(kind)
      .then((r) => {
        const types = r.node_types?.length ? r.node_types : FALLBACK_REGISTRY;
        paletteCache.types[kind] = types;
        setRegistry(types);
      })
      .catch(() => setRegistry(FALLBACK_REGISTRY));
  }, [api, kind]);

  const refreshPresets = useCallback(() => {
    api
      .listNodePresets(kind)
      .then((r) => {
        const list = Array.isArray(r.presets) ? r.presets : [];
        paletteCache.presets[kind] = list;
        setPresets(list);
      })
      .catch(() => setPresets([]));
  }, [api, kind]);

  useEffect(() => {
    const cached = paletteCache.presets[kind];
    if (cached) {
      setPresets(cached);
      return;
    }
    refreshPresets();
  }, [kind, refreshPresets]);

  const togglePalette = (open: boolean) => {
    setPaletteOpen(open);
    persist(PALETTE_OPEN_KEY, open);
  };
  const toggleInspector = (open: boolean) => {
    setInspectorOpen(open);
    persist(INSPECTOR_OPEN_KEY, open);
  };

  const onResizePointerDown = (side: "left" | "right") => (ev: ReactPointerEvent<HTMLButtonElement>) => {
    if (ev.button != null && ev.button !== 0) return;
    ev.preventDefault();
    dragRef.current = {
      side,
      startX: ev.clientX,
      startW: side === "left" ? paletteW : inspectorW,
    };
    setResizing(side);
    ev.currentTarget.setPointerCapture(ev.pointerId);
  };

  const onResizePointerMove = (ev: ReactPointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const delta = drag.side === "left" ? ev.clientX - drag.startX : drag.startX - ev.clientX;
    if (drag.side === "left") {
      setPaletteW(clamp(drag.startW + delta, PALETTE_MIN, PANEL_MAX));
    } else {
      setInspectorW(clamp(drag.startW + delta, INSPECTOR_MIN, PANEL_MAX));
    }
  };

  const onResizePointerUp = (ev: ReactPointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    dragRef.current = null;
    setResizing(null);
    try {
      ev.currentTarget.releasePointerCapture(ev.pointerId);
    } catch {
      /* ignore */
    }
    if (!drag) return;
    const delta = drag.side === "left" ? ev.clientX - drag.startX : drag.startX - ev.clientX;
    if (drag.side === "left") {
      const w = clamp(drag.startW + delta, PALETTE_MIN, PANEL_MAX);
      setPaletteW(w);
      persist(PALETTE_W_KEY, w);
    } else {
      const w = clamp(drag.startW + delta, INSPECTOR_MIN, PANEL_MAX);
      setInspectorW(w);
      persist(INSPECTOR_W_KEY, w);
    }
  };

  const resetPanelWidth = (side: "left" | "right") => {
    if (side === "left") {
      setPaletteW(PALETTE_DEFAULT);
      persist(PALETTE_W_KEY, PALETTE_DEFAULT);
    } else {
      setInspectorW(INSPECTOR_DEFAULT);
      persist(INSPECTOR_W_KEY, INSPECTOR_DEFAULT);
    }
  };

  useEffect(() => {
    if (!graphId || props.embedded) return;
    let cancelled = false;
    api
      .getGraph(graphId)
      .then((detail: any) => {
        if (cancelled) return;
        applyScenarioCard(detail);
        // The DSL is the scenario source of truth. Older/API projection
        // responses may expose only canvas IR, which is accepted as a fallback.
        const raw = detail.dsl || detail.draft?.dsl || detail.canvas || detail.draft?.graph;
        if (!raw) return;
        const g = workflowDocumentToCanvas(raw, kind);
        if (!g) return;
        applyGraph({ ...g, kind, graphId });
      })
      .catch((e) => setStatus(String(e.message || e)));
    return () => {
      cancelled = true;
    };
  }, [graphId]); // eslint-disable-line

  useEffect(() => {
    setNodes((ns) =>
      ns.map((n) => ({
        ...n,
        data: {
          ...n.data,
          entry: registry.find((e) => e.type === (n.data as any).nodeType),
        },
      })),
    );
  }, [registry, setNodes]);

  const applyGraph = useCallback(
    (g: WorkflowGraph, opts?: { resetHistory?: boolean; fit?: boolean }) => {
      // has no End node
      const nodes = (g.nodes || []).filter(
        (n) => n.type !== ("end" as any) && String(n.config?.type || "").toUpperCase() !== "END",
      );
      const keep = new Set(nodes.map((n) => n.id));
      const edges = (g.edges || []).filter((e) => keep.has(e.source) && keep.has(e.target));
      const next = { ...g, kind, nodes, edges };
      setGraphMeta(next);
      const flowNodes = toFlowNodes(next, registry);
      const flowEdges = toFlowEdges(next);
      setNodes(flowNodes);
      setEdges(flowEdges);
      nodesRef.current = flowNodes;
      edgesRef.current = flowEdges;
      setSelectedId(null);
      setSelectedEdgeIds([]);
      if (opts?.resetHistory !== false) {
        historyRef.current = { past: [], future: [] };
        coalesceRef.current = { on: false, at: 0 };
        setHistoryTick((t) => t + 1);
      }
      if (opts?.fit !== false) {
        pendingFitRef.current = true;
        pendingAutoRef.current = !hasSavedLayout(flowNodes);
        scheduleFit(0);
      }
    },
    [kind, registry, setNodes, setEdges],
  );

  const buildGraph = useCallback(() => {
    return fromFlow(
      kind,
      metaRef.current.name,
      graphIdRef.current || metaRef.current.graphId || "",
      nodesRef.current,
      edgesRef.current,
      metaRef.current,
    );
  }, [kind]);

  const emitChange = useCallback(
    (ns: Node[], es: Edge[], meta?: WorkflowGraph) => {
      if (applyingHistoryRef.current) return;
      const base = meta || metaRef.current;
      const g = fromFlow(kind, base.name, graphIdRef.current || base.graphId || "", ns, es, base);
      setGraphMeta(g);
      props.onChange?.(g);
    },
    [kind, props],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (props.readOnly) return;
      if (isEditableHotkeyTarget(e.target)) return;
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      if (e.key === "z" || e.key === "Z") {
        e.preventDefault();
        if (e.shiftKey) redoRef.current();
        else undoRef.current();
      } else if (e.key === "y" || e.key === "Y") {
        e.preventDefault();
        redoRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props.readOnly]);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      pushHistory();
      setEdges((eds) => {
        const label = humanEdgeLabel(connection.sourceHandle, null);
        const next = addEdge(
          styleEdge({
            ...connection,
            id: `e-${connection.source}-${connection.sourceHandle || "out"}-${connection.target}-${eds.length}`,
            targetHandle: connection.targetHandle || "in",
            label,
            data: {
              condition:
                connection.sourceHandle && connection.sourceHandle !== "out"
                  ? connection.sourceHandle
                  : null,
            },
          } as Edge),
          eds,
        );
        emitChange(nodesRef.current, next);
        return next;
      });
    },
    [emitChange, setEdges],
  );

  const onReconnect = useCallback(
    (oldEdge: Edge, connection: Connection) => {
      pushHistory();
      setEdges((eds) => {
        const next = eds.map((e) =>
          e.id === oldEdge.id
            ? styleEdge({
                ...e,
                source: connection.source || e.source,
                target: connection.target || e.target,
                sourceHandle: connection.sourceHandle || e.sourceHandle,
                targetHandle: connection.targetHandle || e.targetHandle || "in",
                label: humanEdgeLabel(connection.sourceHandle || e.sourceHandle, e.label as string),
                data: {
                  ...(typeof e.data === "object" && e.data ? e.data : {}),
                  condition:
                    (connection.sourceHandle || e.sourceHandle) &&
                    (connection.sourceHandle || e.sourceHandle) !== "out"
                      ? connection.sourceHandle || e.sourceHandle
                      : null,
                  waypoint: (e.data as { waypoint?: { x: number; y: number } } | undefined)?.waypoint,
                },
              })
            : e,
        );
        emitChange(nodesRef.current, next);
        return next;
      });
    },
    [emitChange, setEdges],
  );

  const setEdgeWaypoint = useCallback(
    (id: string, waypoint: { x: number; y: number } | null, persist: boolean) => {
      setEdges((eds) => {
        const next = eds.map((e) =>
          e.id === id
            ? styleEdge({
                ...e,
                data: {
                  ...(typeof e.data === "object" && e.data ? e.data : {}),
                  waypoint: waypoint || undefined,
                },
              })
            : e,
        );
        if (persist) {
          pushHistory();
          emitChange(nodesRef.current, next);
        }
        return next;
      });
    },
    [emitChange, setEdges],
  );

  const edgeEditApi = useMemo(
    () => ({ setWaypoint: setEdgeWaypoint, readOnly: !!props.readOnly }),
    [setEdgeWaypoint, props.readOnly],
  );

  const handleEdgesChange = useCallback(
    (changes: any) => {
      const removing = changes.filter((c: any) => c.type === "remove").map((c: any) => c.id as string);
      if (removing.length) {
        const lockedIds = new Set(
          edgesRef.current
            .filter((e) => {
              if (!removing.includes(e.id)) return false;
              const src = nodesRef.current.find((n) => n.id === e.source);
              const tgt = nodesRef.current.find((n) => n.id === e.target);
              return isGovernanceNode({ id: e.source, data: src?.data as any })
                || isGovernanceNode({ id: e.target, data: tgt?.data as any });
            })
            .map((e) => e.id),
        );
        const allowed = removing.filter((id: string) => !lockedIds.has(id));
        if (lockedIds.size) setStatus("Связь проверки снимается вместе с веткой");
        const rest = changes.filter((c: any) => c.type !== "remove");
        if (rest.length) onEdgesChange(rest);
        if (!allowed.length) return;
        pushHistory();
        setEdges((eds) => {
          const next = eds.filter((e) => !allowed.includes(e.id));
          edgesRef.current = next;
          emitChange(nodesRef.current, next);
          return next;
        });
        setSelectedEdgeIds((ids) => ids.filter((id) => !allowed.includes(id)));
        return;
      }
      onEdgesChange(changes);
    },
    [emitChange, onEdgesChange, setEdges],
  );

  const placeNewNode = (
    nodeType: NodeType,
    label: string,
    config: Record<string, unknown>,
    position?: { x: number; y: number },
  ) => {
    if (props.readOnly) return;
    if (nodeType === "trigger" && nodes.some((n) => (n.data as any).nodeType === "trigger")) {
      setStatus("Trigger already exists");
      return;
    }
    const id = `${nodeType}-${Date.now().toString(36)}`;
    let cx = 280;
    let cy = 180;
    if (position) {
      cx = position.x;
      cy = position.y;
    } else if (rfInstance?.screenToFlowPosition) {
      const el = document.querySelector(".gcanvas");
      const rect = el?.getBoundingClientRect();
      if (rect) {
        const p = rfInstance.screenToFlowPosition({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        });
        cx = p.x - 100;
        cy = p.y - 32;
      }
    } else if (nodes.length) {
      cx = nodes.reduce((s, n) => s + n.position.x, 0) / nodes.length + 40;
      cy = nodes.reduce((s, n) => s + n.position.y, 0) / nodes.length + 40;
    }
    const entry = palette.find((e) => e.type === nodeType) || FALLBACK_REGISTRY.find((e) => e.type === nodeType);
    const box = nodeBoxSize(nodeType, config);
    const node: Node = {
      id,
      type: "workflow",
      position: { x: cx, y: cy },
      width: box.w,
      height: box.h,
      data: {
        label,
        nodeType,
        entry,
        config,
        metadata: {},
      },
    };
    pushHistory();
    setNodes((ns) => {
      const next = [...ns, node];
      emitChange(next, edgesRef.current);
      return next;
    });
    setSelectedId(id);
    setStatus("");
  };

  const addPaletteNode = (paletteKind: PaletteKind, position?: { x: number; y: number }) => {
    let nodeType: NodeType = "webhook";
    let label = "Action";
    if (paletteKind === "trigger") {
      nodeType = "trigger";
      label = "Trigger";
    } else if (paletteKind === "condition") {
      nodeType = "condition";
      label = "Condition";
    } else if (paletteKind === "input") {
      nodeType = "input";
      label = "Input";
    } else {
      nodeType = "webhook";
      label = "Webhook";
    }
    placeNewNode(nodeType, label, defaultConfigFor(nodeType), position);
  };

  const addPresetNode = (preset: NodePreset, position?: { x: number; y: number }) => {
    const nodeType = (preset.node_type || "webhook") as NodeType;
    const config = JSON.parse(JSON.stringify(preset.config || {}));
    placeNewNode(nodeType, preset.label || preset.name || nodeType, config, position);
  };

  const saveNodeAsPreset = async (node: WorkflowNode) => {
    const suggested = (node.label || node.type || "Шаг").trim();
    const name = window.prompt("Название шаблона", suggested);
    if (!name) return;
    try {
      await api.saveNodePreset({
        name: name.trim(),
        node_type: node.type,
        label: node.label || name.trim(),
        config: node.config || {},
      });
      refreshPresets();
      setStatus(`Шаблон «${name.trim()}» сохранён`);
    } catch (e: any) {
      setStatus(String(e.message || e));
    }
  };

  const deletePreset = async (preset: NodePreset) => {
    if (!window.confirm(`Удалить шаблон «${preset.name}»?`)) return;
    try {
      await api.deleteNodePreset(preset.id);
      refreshPresets();
    } catch (e: any) {
      setStatus(String(e.message || e));
    }
  };

  const changeNodeType = (nodeId: string, nextType: NodeType, config: Record<string, unknown>, label?: string) => {
    pushHistory();
    setNodes((ns) => {
      const next = ns.map((n) => {
        if (n.id !== nodeId) return n;
        const entry = palette.find((e) => e.type === nextType) || FALLBACK_REGISTRY.find((e) => e.type === nextType);
        const box = nodeBoxSize(nextType, config);
        return {
          ...n,
          width: box.w,
          height: box.h,
          data: {
            ...n.data,
            nodeType: nextType,
            label: label || (n.data as { label?: string }).label,
            config,
            entry,
          },
        };
      });
      emitChange(next, edgesRef.current);
      return next;
    });
  };

  const selectedNode: WorkflowNode | null = useMemo(() => {
    const n = nodes.find((x) => x.id === selectedId);
    if (!n) return null;
    return {
      id: n.id,
      type: (n.data as any).nodeType,
      label: (n.data as any).label,
      position: n.position,
      config: (n.data as any).config || {},
      metadata: (n.data as any).metadata || {},
    };
  }, [nodes, selectedId]);

  const selectedEntry = palette.find((e) => e.type === selectedNode?.type);

  const autoLayout = async (opts?: { skipHistory?: boolean }) => {
    if (!opts?.skipHistory) pushHistory();
    const laid = await layoutWithElk(nodesRef.current, edgesRef.current);
    setNodes(laid);
    nodesRef.current = laid;
    setEdges((eds) => {
      const next = eds.map((e) =>
        styleEdge({
          ...e,
          data: { ...(typeof e.data === "object" && e.data ? e.data : {}), waypoint: undefined },
        }),
      );
      edgesRef.current = next;
      emitChange(laid, next);
      return next;
    });
    pendingFitRef.current = true;
    scheduleFit(opts?.skipHistory ? 0 : 200);
  };

  const openDsl = () => {
    const g = buildGraph();
    setDslText(JSON.stringify(canvasToWorkflowDsl(g), null, 2));
    setDslError("");
    setViewMode("dsl");
  };

  const applyDsl = () => {
    try {
      const parsed = JSON.parse(dslText);
      if (!isWorkflowDsl(parsed)) {
        setDslError("DSL: нужны identifier, nodes[] и connections[]");
        return;
      }
      const canvas = workflowDslToCanvas(parsed, kind);
      pushHistory();
      applyGraph(canvas, { resetHistory: false });
      setDslError("");
      setViewMode("canvas");
      setStatus("DSL применён к canvas");
      props.onChange?.(canvas);
    } catch (e: any) {
      setDslError(e.message || String(e));
    }
  };

  const copyDsl = async () => {
    try {
      const text = dslText || JSON.stringify(canvasToWorkflowDsl(buildGraph()), null, 2);
      await navigator.clipboard.writeText(text);
      setStatus("DSL скопирован в буфер");
    } catch {
      setStatus("Не удалось скопировать — выделите текст вручную");
    }
  };

  const ensureLayout = async (opts?: { silent?: boolean; force?: boolean }) => {
    const keep = !opts?.force && hasSavedLayout(nodesRef.current);
    if (keep) {
      pendingFitRef.current = true;
      scheduleFit(opts?.silent ? 0 : 200);
      return "manual" as const;
    }
    await autoLayout({ skipHistory: true });
    return "auto" as const;
  };

  useEffect(() => {
    const el = canvasElRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (!r || r.width < 40 || r.height < 40) return;
      if (pendingFitRef.current) scheduleFit(0);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const save = async () => {
    const g = buildGraph();
    const dsl = canvasToWorkflowDsl(g);
    const gid = graphIdRef.current;
    if (!gid) {
      props.onChange?.(g);
      props.onSave?.(g);
      return g;
    }
    try {
      const ver: any = await api.saveDraft(gid, dsl as any, revisionRef.current);
      applyScenarioCard(ver);
      const compiled = ver?.dsl;
      if (compiled && (compiled.nodes || compiled.connections)) {
        const canvas = { ...workflowDslToCanvas(compiled, kind), kind, graphId: gid };
        const liveById = new Map(g.nodes.map((n) => [n.id, n]));
        canvas.nodes = canvas.nodes.map((n) => ({
          ...n,
          position: liveById.get(n.id)?.position || n.position,
        }));
        const liveEdges = g.edges || [];
        canvas.edges = canvas.edges.map((e) => {
          const match = liveEdges.find(
            (le) =>
              le.source === e.source &&
              le.target === e.target &&
              String(le.sourceHandle || le.condition || "") === String(e.sourceHandle || e.condition || ""),
          );
          return match ? { ...e, id: match.id, waypoint: match.waypoint || e.waypoint } : e;
        });
        const sameIds =
          canvas.nodes.length === g.nodes.length &&
          canvas.nodes.every((n) => liveById.has(n.id));
        if (!sameIds) {
          applyGraph(canvas, { fit: false, resetHistory: false });
        }
        setStatus("Сохранено");
        props.onSave?.(sameIds ? g : canvas);
        return sameIds ? g : canvas;
      }
      setGraphMeta(g);
      props.onSave?.(g);
      return g;
    } catch (e: any) {
      setStatus(e.message || String(e));
      throw e;
    }
  };

  const validate = async () => {
    const g = buildGraph();
    const dsl = canvasToWorkflowDsl(g);
    try {
      const report: any = graphIdRef.current
        ? await api.validate(graphIdRef.current, dsl as any)
        : await api.parsePreview(dsl as any);
      const issuesList = report.issues || report.validation?.issues || [];
      setIssues(issuesList);
      setChecklist([]);
      setStatus(report.ok !== false && !issuesList.some((i: any) => i.severity !== "warning")
        ? "Проверка: ок"
        : `Проблем: ${issuesList.length}`);
      setPanel("checklist");
      return report;
    } catch (e: any) {
      setStatus(e.message || String(e));
      throw e;
    }
  };

  const runChecklist = () => void validate();

  const applyRunState = (st: any) => {
    setTestStatus(st.status || "");
    setTestError(typeof st.error === "string" ? st.error : st.error ? JSON.stringify(st.error) : "");
    const pending = st.pending_approval?.node_id || st.pending_approval?.nodeId || null;
    setTestCurrentNode(st.current_node_id || pending || null);
    setTestPendingNode(st.status === "waiting" ? pending || st.current_node_id || null : null);
  };

  const pollUntilSettled = async (runId: string) => {
    const gen = ++pollGenRef.current;
    for (let i = 0; i < 90; i++) {
      if (pollGenRef.current !== gen) return null;
      const st: any = await api.getRunState(runId);
      if (pollGenRef.current !== gen) return null;
      applyRunState(st);
      if (["completed", "failed", "waiting", "cancelled"].includes(String(st.status || ""))) {
        return st;
      }
      await new Promise((r) => setTimeout(r, 700));
    }
    setTestError((prev) => prev || "Шаг ещё выполняется. Панель обновляется — подождите или запустите снова.");
    return null;
  };

  const runTest = async () => {
    if (!graphIdRef.current) {
      setStatus("Сначала сохраните сценарий (нужен graphId)");
      setPanel("test");
      return;
    }
    let input: Record<string, unknown> = {};
    try {
      input = JSON.parse(testInput || "{}");
    } catch {
      setStatus("Test input: невалидный JSON");
      setPanel("test");
      return;
    }
    try {
      setTestBusy(true);
      setTestError("");
      setTestPendingNode(null);
      setTestCurrentNode(null);
      if (scenarioStatus === "draft") await save();
      const run: any = await api.createRun(graphIdRef.current, input, "test");
      setTestRunId(run.id);
      setTestStatus(run.status || "started");
      setPanel("test");
      setStatus(`Test run ${run.id}`);
      await pollUntilSettled(run.id);
    } catch (e: any) {
      setStatus(e.message || String(e));
      setTestError(e.message || String(e));
      setPanel("test");
    } finally {
      setTestBusy(false);
    }
  };

  const signalTest = async (decision: "approve" | "reject") => {
    if (!testRunId || !testPendingNode) return;
    try {
      setTestBusy(true);
      if (decision === "approve") {
        await api.approve(testRunId, testPendingNode, testReason || undefined);
      } else {
        await api.reject(testRunId, testPendingNode, testReason || undefined);
      }
      setTestPendingNode(null);
      setTestReason("");
      await pollUntilSettled(testRunId);
    } catch (e: any) {
      setTestError(e.message || String(e));
    } finally {
      setTestBusy(false);
    }
  };

  const testCurrentLabel = testCurrentNode
    ? String((nodes.find((n) => n.id === testCurrentNode)?.data as any)?.label || testCurrentNode)
    : "";

  const publish = async () => {
    if (!graphIdRef.current) return;
    if (scenarioStatus === "draft") await save();
    try {
      const card: any = await api.publish(graphIdRef.current, revisionRef.current);
      applyScenarioCard(card);
      setStatus("Опубликовано");
      props.onPublish?.(buildGraph());
    } catch (e: any) {
      setStatus(e.message || String(e));
      throw e;
    }
  };

  const setProductStatus = async (status: "draft" | "published" | "launched") => {
    if (!graphIdRef.current) return;
    try {
      const card: any = await api.setScenarioStatus(graphIdRef.current, status, revisionRef.current);
      applyScenarioCard(card);
      setStatus(
        status === "launched" ? "Запущено" : status === "draft" ? "Снова черновик" : "Снято с запуска",
      );
    } catch (e: any) {
      setStatus(e.message || String(e));
      throw e;
    }
  };

  const deleteSelected = () => {
    if (props.readOnly) return;
    if (selectedEdgeIds.length) {
      const ids = new Set(selectedEdgeIds);
      const locked = edgesRef.current.filter((e) => ids.has(e.id) && (
        isGovernanceNode({ id: e.source, data: nodesRef.current.find((n) => n.id === e.source)?.data as any })
        || isGovernanceNode({ id: e.target, data: nodesRef.current.find((n) => n.id === e.target)?.data as any })
      ));
      if (locked.length) {
        setStatus("Связь проверки снимается вместе с веткой");
        return;
      }
      pushHistory();
      const next = edgesRef.current.filter((e) => !ids.has(e.id));
      setEdges(next);
      edgesRef.current = next;
      setSelectedEdgeIds([]);
      emitChange(nodesRef.current, next);
      setStatus(`Удалено связей: ${ids.size}`);
      return;
    }
    const selectedNodes = nodes.filter((x) => x.selected);
    const toDelete = (selectedNodes.length ? selectedNodes : nodes.filter((x) => x.id === selectedId)).filter(
      Boolean,
    );
    if (!toDelete.length) return;
    if (toDelete.some((n) => isGovernanceNode({ id: n.id, data: n.data as any }))) {
      setStatus("Проверки ветки снимаются сами: удалите шаги ветки и сохраните");
      return;
    }
    pushHistory();
    const ids = new Set(toDelete.map((n) => n.id));
    const pruned = pruneOrphanGovernance(
      nodes.filter((x) => !ids.has(x.id)),
      edges.filter((e) => !ids.has(e.source) && !ids.has(e.target)),
    );
    setNodes(pruned.nodes);
    setEdges(pruned.edges);
    setSelectedId(null);
    emitChange(pruned.nodes, pruned.edges);
    if (pruned.removed.length) {
      setStatus(ids.size > 1 ? `Удалено блоков: ${ids.size}, проверки ветки сняты` : "Проверки ветки сняты");
    } else {
      setStatus(ids.size > 1 ? `Удалено блоков: ${ids.size}` : "");
    }
  };

  useImperativeHandle(
    ref,
    () => ({
      getGraph: buildGraph,
      setGraph: applyGraph,
      setGraphId: (id: string) => {
        setGraphId(id || "");
        setGraphMeta((m) => ({ ...m, graphId: id || "" }));
      },
      save,
      validate,
      publish,
      autoLayout,
      ensureLayout,
      deleteSelected,
    }),
    [buildGraph, applyGraph], // eslint-disable-line
  );

  // useLayoutEffect: host often calls setGraph in the same turn as mount();
  // queue-flush in embed must see the handle before paint.
  useLayoutEffect(() => {
    props.onReady?.({
      getGraph: buildGraph,
      setGraph: applyGraph,
      setGraphId: (id: string) => {
        setGraphId(id || "");
        setGraphMeta((m) => ({ ...m, graphId: id || "" }));
      },
      save,
      validate,
      publish,
      autoLayout,
      ensureLayout,
      deleteSelected,
    });
  }, [applyGraph]); // eslint-disable-line

  return (
    <div
      className={[
        "gdesigner",
        `gdesigner--${kind}`,
        chrome === "minimal" ? "gdesigner--minimal" : "",
        props.embedded ? "gdesigner--embedded" : "",
        chrome === "full" && !paletteOpen ? "gdesigner--palette-collapsed" : "",
        chrome === "full" && !inspectorOpen ? "gdesigner--inspector-collapsed" : "",
        resizing ? "is-resizing" : "",
      ].filter(Boolean).join(" ")}
      style={
        chrome === "full"
          ? ({
              ["--g-palette-w" as string]: `${paletteW}px`,
              ["--g-inspector-w" as string]: `${inspectorW}px`,
            } as CSSProperties)
          : undefined
      }
    >
      {chrome === "full" && (
        <aside className={`gpalette ${paletteOpen ? "" : "gpalette--collapsed"}`}>
          {paletteOpen ? (
            <>
              <div className="gside-head">
                <div className="gpalette__title">Шаги</div>
                <button
                  type="button"
                  className="gside-toggle"
                  title="Скрыть шаги"
                  aria-label="Скрыть шаги"
                  onClick={() => togglePalette(false)}
                >
                  ‹
                </button>
              </div>
              <div className="gpalette__body">
          {([
            ["trigger", "▶", "Trigger"],
            ["action", "⇢", "Action"],
            ["input", "✓", "Input"],
            ["condition", "◇", "Condition"],
          ] as const).map(([pk, icon, title]) => (
            <button
              key={pk}
              type="button"
              className="gpalette__item"
              disabled={!!props.readOnly}
              draggable={!props.readOnly}
              onDragStart={(e) => {
                e.dataTransfer.setData("application/x-palette-kind", pk);
                e.dataTransfer.effectAllowed = "move";
              }}
              onClick={() => addPaletteNode(pk)}
            >
              <span>{icon}</span> {title}
            </button>
          ))}
          {presets.length > 0 && (
            <>
              <div className="gpalette__cat">Шаблоны</div>
              {presets.map((p) => (
                <div key={p.id} className="gpalette__item-row">
                  <button
                    type="button"
                    className="gpalette__item gpalette__item--soft"
                    disabled={!!props.readOnly}
                    draggable={!props.readOnly}
                    title={p.node_type}
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/x-node-preset", p.id);
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    onClick={() => addPresetNode(p)}
                  >
                    <span>{PRESET_ICONS[p.node_type] || "☆"}</span> {p.name}
                  </button>
                  <button
                    type="button"
                    className="gpalette__x"
                    disabled={!!props.readOnly}
                    title="Удалить шаблон"
                    onClick={(e) => {
                      e.stopPropagation();
                      void deletePreset(p);
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </>
          )}
          <p className="gpalette__hint">
            Клик / drag блока — на холст. Перемещение поля: зажать ЛКМ на пустом месте.
            Рамка выделения: Shift+ЛКМ. Shift/⌘+клик — несколько блоков.
            Выходы condition/input — цветные точки справа: тяните стрелку.
            Связь: кружок на линии — изогнуть, концы — переподключить. Двойной клик по кружку сбрасывает изгиб.
            Отмена: ⌘Z / Ctrl+Z, повтор: ⇧⌘Z / Ctrl+Y.
          </p>
              </div>
            </>
          ) : (
            <button
              type="button"
              className="gside-rail"
              title="Показать шаги"
              onClick={() => togglePalette(true)}
            >
              Шаги
            </button>
          )}
        </aside>
      )}
      {chrome === "full" && paletteOpen && (
        <button
          type="button"
          className={`gresizer ${resizing === "left" ? "is-active" : ""}`}
          aria-label="Ширина панели шагов"
          title="Потяните, чтобы изменить ширину. Двойной клик — сброс."
          onPointerDown={onResizePointerDown("left")}
          onPointerMove={onResizePointerMove}
          onPointerUp={onResizePointerUp}
          onPointerCancel={onResizePointerUp}
          onDoubleClick={() => resetPanelWidth("left")}
        />
      )}
      <div className="gcanvas-wrap">
        {chrome !== "minimal" && (
          <div className="gtoolbar">
            <button
              type="button"
              className={paletteOpen ? "is-on" : ""}
              title={paletteOpen ? "Скрыть шаги" : "Показать шаги"}
              onClick={() => togglePalette(!paletteOpen)}
            >
              Шаги
            </button>
            <button
              type="button"
              className={inspectorOpen ? "is-on" : ""}
              title={inspectorOpen ? "Скрыть инспектор" : "Показать инспектор"}
              onClick={() => toggleInspector(!inspectorOpen)}
            >
              Инспектор
            </button>
            <div className="gview-toggle" role="tablist" aria-label="Canvas or DSL">
              <button
                type="button"
                className={viewMode === "canvas" ? "active" : ""}
                onClick={() => setViewMode("canvas")}
              >
                Canvas
              </button>
              <button type="button" className={viewMode === "dsl" ? "active" : ""} onClick={openDsl}>
                DSL
              </button>
            </div>
            {viewMode === "canvas" ? (
              <>
                <button type="button" onClick={undo} disabled={!!props.readOnly || !canUndo} title="⌘Z / Ctrl+Z">
                  Отменить
                </button>
                <button type="button" onClick={redo} disabled={!!props.readOnly || !canRedo} title="⇧⌘Z / Ctrl+Y">
                  Повторить
                </button>
                <button type="button" onClick={() => void autoLayout()}>Auto layout</button>
                <button
                  type="button"
                  onClick={deleteSelected}
                  disabled={!!props.readOnly || (!selectedId && !nodes.some((n) => n.selected) && selectedEdgeIds.length === 0)}
                >
                  Удалить
                </button>
                <button type="button" onClick={() => void runChecklist()}>Checklist</button>
                <button type="button" onClick={() => { setPanel("test"); }}>Test run</button>
              </>
            ) : (
              <>
                <button type="button" onClick={applyDsl} disabled={!!props.readOnly}>Применить DSL</button>
                <button type="button" onClick={() => void copyDsl()}>Копировать</button>
              </>
            )}
            {!props.embedded && (
              <>
                <span className="gstatus" title="Статус сценария">
                  {scenarioStatus === "draft" ? "черновик" : scenarioStatus === "published" ? "опубликован" : "запущен"}
                </span>
                <button
                  type="button"
                  onClick={() => void save()}
                  disabled={!!props.readOnly || scenarioStatus !== "draft"}
                >
                  Сохранить
                </button>
                {scenarioStatus === "draft" ? (
                  <button type="button" onClick={() => void publish()} disabled={!!props.readOnly}>
                    Опубликовать
                  </button>
                ) : null}
                {scenarioStatus === "published" && kind === "e2e" ? (
                  <button type="button" onClick={() => void setProductStatus("launched")} disabled={!!props.readOnly}>
                    Запустить
                  </button>
                ) : null}
                {scenarioStatus === "launched" ? (
                  <button type="button" onClick={() => void setProductStatus("published")} disabled={!!props.readOnly}>
                    Снять
                  </button>
                ) : null}
                {scenarioStatus !== "draft" ? (
                  <button type="button" onClick={() => void setProductStatus("draft")} disabled={!!props.readOnly}>
                    Править
                  </button>
                ) : null}
              </>
            )}
            {status ? <span className="gstatus">{status}</span> : null}
            {selectedEdgeIds.length > 0 && viewMode === "canvas" ? (
              <span className="gstatus gstatus--edge">Потяните связь, чтобы сместить изгиб · Delete</span>
            ) : null}
          </div>
        )}
        {viewMode === "dsl" ? (
          <div className="gdsl">
            <div className="gdsl__bar">
              <span className="muted">JSON DSL сценария. Canvas — графический редактор того же графа.</span>
              {dslError ? <span className="gwarn">{dslError}</span> : null}
            </div>
            <textarea
              className="gdsl__editor"
              data-de-dsl-editor="1"
              spellCheck={false}
              value={dslText}
              readOnly={!!props.readOnly}
              onChange={(e) => setDslText(e.target.value)}
            />
          </div>
        ) : (
          <>
        {panel === "checklist" && (
          <div className="gpanel">
            <div className="gpanel__head">
              <strong>Setup checklist</strong>
              <button type="button" className="gchip" onClick={() => setPanel("none")}>×</button>
            </div>
            {checklist.length === 0 && issues.length === 0 ? (
              <div className="gissue ok">Нет нерешённых зависимостей</div>
            ) : (
              <>
                {checklist.map((c, i) => (
                  <div key={i} className={`gissue ${c.severity || "error"}`}>
                    [{c.kind}] {c.label || c.node_id}: {c.message}
                  </div>
                ))}
                {issues.map((i, idx) => (
                  <div key={`i${idx}`} className={`gissue ${i.severity || "error"}`}>{i.message || i.code}</div>
                ))}
              </>
            )}
          </div>
        )}
        {panel === "test" && (
          <div className="gpanel gpanel--test">
            <div className="gpanel__head">
              <strong>Test workflow</strong>
              <button type="button" className="gchip" onClick={() => setPanel("none")}>×</button>
            </div>
            <p className="muted">
              Запускает текущий draft в этом окне (без Temporal). Для Slack укажите channel и text;
              thread_ts — если нужно подтянуть тред. Токен берётся из окружения, не из графа.
            </p>
            <label className="gfield">
              <span>Trigger input (JSON)</span>
              <textarea
                rows={5}
                placeholder={'{"channel":"C0AKKCGEKL1","thread_ts":"","text":"Нужен BRD для ..."}'}
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
              />
            </label>
            <button type="button" className="gbtn" disabled={testBusy} onClick={() => void runTest()}>
              {testBusy ? "Выполняется…" : "Execute workflow"}
            </button>
            {testRunId ? (
              <div className="gtest-status">
                <div>
                  <strong>{testStatus || "…"}</strong>
                  {testCurrentLabel ? ` · ${testCurrentLabel}` : testCurrentNode ? ` · ${testCurrentNode}` : ""}
                </div>
                <div className="muted">run {testRunId}</div>
                {testError ? <div className="gissue error">{testError}</div> : null}
                {testPendingNode ? (
                  <div className="gtest-hitl">
                    <p>Узел INPUT ждёт решение. Approve / Decline — те же выходы, что точки справа на блоке.</p>
                    <label className="gfield">
                      <span>reason (необязательно)</span>
                      <input value={testReason} onChange={(e) => setTestReason(e.target.value)} />
                    </label>
                    <div className="gtest-hitl__btns">
                      <button type="button" className="gbtn" disabled={testBusy} onClick={() => void signalTest("approve")}>
                        Approve
                      </button>
                      <button type="button" className="gbtn gbtn--inline-danger" disabled={testBusy} onClick={() => void signalTest("reject")}>
                        Decline
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
        <div className="gcanvas" ref={canvasElRef}>
          <RunHighlightContext.Provider
            value={{
              nodeId: testCurrentNode,
              mode: testCurrentNode ? (testStatus === "waiting" ? "waiting" : "current") : "",
            }}
          >
          <EdgeEditContext.Provider value={edgeEditApi}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onInit={(inst) => {
              rfRef.current = inst;
              setRfInstance(inst);
              pendingFitRef.current = true;
              scheduleFit(0);
            }}
            onNodesChange={onNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={onConnect}
            onReconnect={onReconnect}
            onConnectStart={(_, params) => {
              if (params?.handleType === "source" && params.handleId) {
                setStatus(`Связь от «${params.handleId}» — тяните к цели или кликните по входу`);
              }
            }}
            onConnectEnd={() => {
              /* status cleared on successful connect via onConnect */
            }}
            isValidConnection={(c) => !!c.source && !!c.target && c.source !== c.target}
            connectionMode={ConnectionMode.Loose}
            connectOnClick
            connectionDragThreshold={0}
            panOnDrag={[0, 1, 2]}
            noPanClassName="nopan"
            noDragClassName="nodrag"
            selectionMode={SelectionMode.Partial}
            multiSelectionKeyCode={["Meta", "Control", "Shift"]}
            selectionKeyCode="Shift"
            onNodeDragStart={() => {
              if (props.readOnly || dragHistRef.current) return;
              dragHistRef.current = true;
              pushHistory();
            }}
            onNodeDragStop={(_, __, ns) => {
              dragHistRef.current = false;
              emitChange(ns, edgesRef.current);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
            }}
            onDrop={(e) => {
              e.preventDefault();
              if (props.readOnly || !rfInstance) return;
              const pos = rfInstance.screenToFlowPosition({ x: e.clientX, y: e.clientY });
              const point = { x: pos.x - 100, y: pos.y - 32 };
              const presetId = e.dataTransfer.getData("application/x-node-preset");
              if (presetId) {
                const preset = presets.find((p) => p.id === presetId);
                if (preset) addPresetNode(preset, point);
                return;
              }
              const pk = e.dataTransfer.getData("application/x-palette-kind") as PaletteKind;
              if (!pk) return;
              addPaletteNode(pk, point);
            }}
            onSelectionChange={({ nodes: sn, edges: se }) => {
              const id = sn[0]?.id || null;
              setSelectedId((prev) => (prev === id ? prev : id));
              const nextEdgeIds = (se || []).map((e) => e.id);
              setSelectedEdgeIds((prev) => {
                if (
                  prev.length === nextEdgeIds.length &&
                  prev.every((x, i) => x === nextEdgeIds[i])
                ) {
                  return prev;
                }
                return nextEdgeIds;
              });
              if (sn.length > 1) {
                setStatus(`Выбрано блоков: ${sn.length} — перетащите любой для группового переноса`);
              }
              props.onSelect?.(id);
            }}
            onEdgeClick={(_, edge) => {
              setSelectedId(null);
              setSelectedEdgeIds([edge.id]);
              setNodes((ns) => ns.map((n) => ({ ...n, selected: false })));
              setEdges((eds) => eds.map((e) => ({ ...e, selected: e.id === edge.id })));
              setStatus("Потяните связь, чтобы сместить изгиб. Двойной клик — сбросить. Delete — удалить");
            }}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            minZoom={0.15}
            maxZoom={1.5}
            defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
            edgesFocusable={!props.readOnly}
            edgesReconnectable={!props.readOnly}
            reconnectRadius={24}
            nodesDraggable={!props.readOnly}
            nodesConnectable={!props.readOnly}
            elementsSelectable
            selectNodesOnDrag={false}
            elevateEdgesOnSelect
            deleteKeyCode={props.readOnly ? null : ["Backspace", "Delete"]}
            onNodesDelete={(deleted) => {
              pushHistory();
              const ids = new Set(deleted.map((d) => d.id));
              const pruned = pruneOrphanGovernance(
                nodesRef.current.filter((n) => !ids.has(n.id)),
                edgesRef.current.filter((e) => !ids.has(e.source) && !ids.has(e.target)),
              );
              setNodes(pruned.nodes);
              setEdges(pruned.edges);
              nodesRef.current = pruned.nodes;
              edgesRef.current = pruned.edges;
              setSelectedId(null);
              emitChange(pruned.nodes, pruned.edges);
            }}
            onEdgesDelete={(deleted) => {
              pushHistory();
              const ids = new Set(deleted.map((d) => d.id));
              setEdges((eds) => {
                const next = eds.filter((e) => !ids.has(e.id));
                edgesRef.current = next;
                emitChange(nodesRef.current, next);
                return next;
              });
              setSelectedEdgeIds([]);
            }}
          >
            <Background
              id="editor-dots"
              variant={BackgroundVariant.Dots}
              gap={18}
              size={1.2}
              color="#cbd5e1"
              bgColor="#f6f8fb"
            />
            <Controls showInteractive={!props.readOnly} />
            <NodesReadyGate
              onReady={() => {
                if (pendingAutoRef.current) {
                  pendingAutoRef.current = false;
                  void ensureLayout({ silent: true });
                  return;
                }
                if (pendingFitRef.current) scheduleFit(0);
              }}
            />
          </ReactFlow>
          </EdgeEditContext.Provider>
          </RunHighlightContext.Provider>
        </div>
          </>
        )}
      </div>
      {chrome === "full" && inspectorOpen && (
        <button
          type="button"
          className={`gresizer ${resizing === "right" ? "is-active" : ""}`}
          aria-label="Ширина инспектора"
          title="Потяните, чтобы изменить ширину. Двойной клик — сброс."
          onPointerDown={onResizePointerDown("right")}
          onPointerMove={onResizePointerMove}
          onPointerUp={onResizePointerUp}
          onPointerCancel={onResizePointerUp}
          onDoubleClick={() => resetPanelWidth("right")}
        />
      )}
      {chrome === "full" && (
        <aside className={`ginspector-wrap ${inspectorOpen ? "" : "ginspector-wrap--collapsed"}`}>
          {inspectorOpen ? (
            <>
              <div className="gside-head">
                <div className="gpalette__title">Инспектор</div>
                <button
                  type="button"
                  className="gside-toggle"
                  title="Скрыть инспектор"
                  aria-label="Скрыть инспектор"
                  onClick={() => toggleInspector(false)}
                >
                  ›
                </button>
              </div>
              <PropertyInspector
          node={selectedNode}
          entry={selectedEntry}
          kind={kind}
          graph={graphMeta}
          issues={issues}
          checklist={checklist}
          apiBase={props.apiBase}
          onChange={(node) => {
            pushHistory(true);
            setNodes((ns) => {
              const box = nodeBoxSize(node.type, node.config);
              const next = ns.map((n) =>
                n.id === node.id
                  ? {
                      ...n,
                      width: box.w,
                      height: box.h,
                      data: {
                        ...n.data,
                        label: node.label,
                        config: node.config,
                        metadata: node.metadata,
                      },
                    }
                  : n,
              );
              const allowed = outletIdSet(node.type, node.config);
              let nextEdges = edgesRef.current;
              if (allowed) {
                nextEdges = edgesRef.current.filter((e) => {
                  if (e.source !== node.id) return true;
                  const h = String(e.sourceHandle || "");
                  return !h || h === "out" || allowed.has(h);
                });
                if (nextEdges.length !== edgesRef.current.length) {
                  setEdges(nextEdges);
                  edgesRef.current = nextEdges;
                }
              }
              emitChange(next, nextEdges);
              return next;
            });
          }}
          onChangeType={changeNodeType}
          onChangeGraphMeta={(patch) => {
            pushHistory(true);
            const next = { ...graphMeta, ...patch };
            setGraphMeta(next);
            emitChange(nodesRef.current, edgesRef.current, next);
          }}
          onDeleteNode={() => deleteSelected()}
          onSavePreset={saveNodeAsPreset}
        />
            </>
          ) : (
            <button
              type="button"
              className="gside-rail"
              title="Показать инспектор"
              onClick={() => toggleInspector(true)}
            >
              Инспектор
            </button>
          )}
        </aside>
      )}
    </div>
  );
});