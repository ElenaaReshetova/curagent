import type { GraphKind, NodePreset, NodeRegistryEntry, RunStateSnapshot, WorkflowGraph } from "../types";

const defaultBase = () =>
  (typeof window !== "undefined" && (window as any).__GRAPH_API_BASE__) || "/api/v1";

export async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const parsed = JSON.parse(text);
      message =
        parsed?.error?.message ||
        parsed?.detail?.error?.message ||
        (typeof parsed?.detail === "string" ? parsed.detail : message);
    } catch {
      /* keep text */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function createApi(apiBase = defaultBase()) {
  return {
    nodeTypes: (kind?: GraphKind) =>
      fetchJSON<{ node_types: NodeRegistryEntry[] }>(
        `${apiBase}/schemas/node-types${kind ? `?kind=${kind}` : ""}`,
      ),
    listScenarios: (kind?: GraphKind) =>
      fetchJSON<{ items: any[]; total: number }>(
        `${apiBase}/scenarios${kind ? `?kind=${kind}` : ""}`,
      ),
    getScenario: (id: string) => fetchJSON<any>(`${apiBase}/scenarios/${id}`),
    getGraph: async (id: string) => {
      const s: any = await fetchJSON(`${apiBase}/scenarios/${id}`);
      return {
        ...s,
        graph: s,
        draft: { dsl: s.dsl, graph: s.canvas, revision: s.revision },
        canvas: s.canvas,
        published: s.status === "draft" ? null : { dsl: s.dsl, graph: s.canvas },
      };
    },
    resolveGraph: (kind: GraphKind, key: string, name?: string) =>
      fetchJSON<{ id: string; key: string; kind: string; name: string }>(
        `${apiBase}/graphs/resolve?kind=${kind}&key=${encodeURIComponent(key)}${name ? `&name=${encodeURIComponent(name)}` : ""}`,
      ),
    saveDraft: (id: string, dsl: Record<string, unknown> | WorkflowGraph, revision?: number) =>
      fetchJSON(`${apiBase}/scenarios/${id}`, {
        method: "PUT",
        body: JSON.stringify({ dsl, revision }),
      }),
    publish: (id: string, revision?: number) =>
      fetchJSON(`${apiBase}/scenarios/${id}`, {
        method: "POST",
        body: JSON.stringify({ status: "published", revision }),
      }),
    setScenarioStatus: (id: string, status: "draft" | "published" | "launched", revision?: number) =>
      fetchJSON(`${apiBase}/scenarios/${id}`, {
        method: "POST",
        body: JSON.stringify({ status, revision }),
      }),
    validate: (id: string, dsl: Record<string, unknown> | WorkflowGraph) =>
      fetchJSON(`${apiBase}/graphs/${id}/validate`, {
        method: "POST",
        body: JSON.stringify({ dsl }),
      }),
    createRun: (
      scenarioId: string,
      input: Record<string, unknown> = {},
      mode?: "test" | "live",
    ) => {
      const inferred =
        mode || (String(input._source || "").toUpperCase() === "TEST" ? "test" : "live");
      return fetchJSON(`${apiBase}/runs`, {
        method: "POST",
        body: JSON.stringify({
          scenario_id: scenarioId,
          mode: inferred,
          input,
        }),
      });
    },
    parsePreview: (dsl: Record<string, unknown>) =>
      fetchJSON<{
        ok: boolean;
        validation: { ok: boolean; issues: any[] };
        plan: Record<string, unknown>;
        dsl: Record<string, unknown>;
      }>(`${apiBase}/graphs/parse`, {
        method: "POST",
        body: JSON.stringify({ dsl }),
      }),
    normalize: (dsl: Record<string, unknown>) =>
      fetchJSON<{ ok: boolean; dsl: Record<string, unknown> }>(`${apiBase}/graphs/normalize`, {
        method: "POST",
        body: JSON.stringify({ dsl }),
      }),
    listGraphs: async (kind?: GraphKind) => {
      const data = await fetchJSON<{ items: any[]; total: number }>(
        `${apiBase}/scenarios${kind ? `?kind=${kind}` : ""}`,
      );
      return { graphs: data.items || [], items: data.items || [], total: data.total || 0 };
    },
    listSkills: (query = "") =>
      fetchJSON<{ skills: { id: string; key: string; name: string; description?: string; status?: string }[] }>(
        `${apiBase}/skills${query ? `?query=${encodeURIComponent(query)}` : ""}`,
      ),
    listNodePresets: (kind?: GraphKind) =>
      fetchJSON<{ presets: NodePreset[] }>(
        `${apiBase}/node-presets${kind ? `?kind=${kind}` : ""}`,
      ),
    saveNodePreset: (payload: {
      name: string;
      node_type: string;
      label?: string;
      config?: Record<string, unknown>;
      kind?: GraphKind | null;
      id?: string;
    }) =>
      fetchJSON<NodePreset>(`${apiBase}/node-presets`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteNodePreset: (id: string) =>
      fetchJSON<{ ok: boolean }>(`${apiBase}/node-presets/${id}`, { method: "DELETE" }),
    getRunState: (runId: string) =>
      fetchJSON<RunStateSnapshot>(`${apiBase}/runs/${runId}/state`),
    getRunViewer: (runId: string) =>
      fetchJSON<{
        run: Record<string, unknown>;
        dsl: Record<string, unknown>;
        plan: Record<string, unknown>;
        state: RunStateSnapshot;
        graph_id: string;
        version_id: string;
      }>(`${apiBase}/runs/${runId}/viewer`),
    getWorkflowSchema: () => fetchJSON<Record<string, unknown>>(`${apiBase}/schemas/workflow-graph`),
    signal: (runId: string, body: Record<string, unknown>) =>
      fetchJSON(`${apiBase}/runs/${runId}/signal`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    approve: (runId: string, nodeId: string, comment?: string) =>
      fetchJSON(`${apiBase}/runs/${runId}/signal`, {
        method: "POST",
        body: JSON.stringify({ decision: "approve", node_id: nodeId, comment }),
      }),
    reject: (runId: string, nodeId: string, reason?: string) =>
      fetchJSON(`${apiBase}/runs/${runId}/signal`, {
        method: "POST",
        body: JSON.stringify({ decision: "reject", node_id: nodeId, reason }),
      }),
    resume: (runId: string, nodeId?: string, payload: Record<string, unknown> = {}) =>
      fetchJSON(`${apiBase}/runs/${runId}/signal`, {
        method: "POST",
        body: JSON.stringify({ decision: "resume", node_id: nodeId, payload }),
      }),
  };
}
