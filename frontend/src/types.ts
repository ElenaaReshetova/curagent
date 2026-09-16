export type GraphKind = "e2e" | "stage";

export type NodeType =
  | "trigger"
  | "ai_agent"
  | "ai"
  | "webhook"
  | "condition"
  | "input"
  | "upsert_entity"
  | "kafka"
  | "integration_action"
  | "internal_service"
  | "subflow";

export type NodePreset = {
  id: string;
  name: string;
  node_type: NodeType;
  label: string;
  config: Record<string, unknown>;
  kind?: GraphKind | null;
};

export type WorkflowNode = {
  id: string;
  type: NodeType;
  label: string;
  position?: { x: number; y: number };
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type WorkflowEdge = {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  condition?: string | null;
  fallback?: boolean;
  label?: string | null;
  waypoint?: { x: number; y: number } | null;
};

export type WorkflowGraph = {
  graphId: string;
  version: string;
  name: string;
  description?: string;
  kind: GraphKind;
  produces?: string[];
  entrypoints: string[];
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables?: unknown[];
  policies?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
};

export type PortDef = { id: string; label?: string; dataType?: string };

export type NodeRegistryEntry = {
  type: NodeType;
  title: string;
  category: string;
  icon: string;
  configSchema: Record<string, unknown>;
  ports: { in?: PortDef[]; out?: PortDef[] };
  ui?: { defaultSize?: { w: number; h: number }; inspector?: string; colorToken?: string };
  colorToken?: string;
  runtime?: { temporalKind: string };
  kinds: GraphKind[];
  palette?: boolean;
};

export type DesignerHandle = {
  getGraph: () => WorkflowGraph;
  setGraph: (graph: WorkflowGraph) => void;
  setGraphId?: (id: string) => void;
  save: () => Promise<WorkflowGraph | void>;
  validate: () => Promise<any>;
  publish: () => Promise<void>;
  autoLayout: () => Promise<void>;
  /** Layout only when nodes lack valid coordinates. Returns "auto" | "manual". */
  ensureLayout?: (opts?: { silent?: boolean; force?: boolean }) => Promise<"auto" | "manual">;
  deleteSelected: () => void;
};

export type DesignerMountOptions = {
  kind: GraphKind;
  graphId?: string;
  graph?: WorkflowGraph;
  readOnly?: boolean;
  chrome?: "full" | "minimal";
  onChange?: (graph: WorkflowGraph) => void;
  onSelect?: (nodeId: string | null) => void;
  onSave?: (graph: WorkflowGraph) => void;
  onPublish?: (graph: WorkflowGraph) => void;
  onReady?: (handle: DesignerHandle) => void;
  embedded?: boolean;
  apiBase?: string;
};

export type RunStateSnapshot = {
  status: string;
  current_node_id?: string | null;
  outputs?: Record<string, unknown>;
  pending_approval?: { node_id: string } | null;
  approvals?: Record<string, { resolved?: boolean; decision?: string }>;
  run_id?: string;
  error?: string | null;
};
