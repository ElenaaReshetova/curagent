import { createRoot, type Root } from "react-dom/client";
import { GraphDesigner } from "../canvas/GraphDesigner";
import { RunModeShell } from "../shells/RunModeShell";
import type { DesignerHandle, DesignerMountOptions, RunStateSnapshot, WorkflowGraph } from "../types";
import { createApi } from "../api/client";
import "../styles.css";

const roots = new WeakMap<Element, Root>();
const handles = new WeakMap<Element, { current: DesignerHandle | null }>();

type Pending = {
  graph?: WorkflowGraph;
  graphId?: string;
};

function wrapHandle(
  el: Element,
  root: Root,
  handleBox: { current: DesignerHandle | null },
  pending: Pending,
): DesignerHandle & { unmount: () => void } {
  const flush = (h: DesignerHandle) => {
    if (pending.graph) {
      h.setGraph(pending.graph);
      pending.graph = undefined;
    }
    if (pending.graphId != null) {
      h.setGraphId?.(pending.graphId);
      pending.graphId = undefined;
    }
  };

  // If React already reported ready, apply any leftover queue now.
  if (handleBox.current) flush(handleBox.current);

  return {
    getGraph: () => {
      if (!handleBox.current) {
        // Fall back to last queued / mounted graph so hosts don't wipe state.
        if (pending.graph) return pending.graph;
        throw new Error("Designer not ready");
      }
      return handleBox.current.getGraph();
    },
    setGraph: (g) => {
      if (handleBox.current) {
        handleBox.current.setGraph(g);
        pending.graph = undefined;
      } else {
        pending.graph = g;
      }
    },
    setGraphId: (id: string) => {
      if (handleBox.current) {
        handleBox.current.setGraphId?.(id);
        pending.graphId = undefined;
      } else {
        pending.graphId = id;
      }
    },
    save: async () => handleBox.current!.save(),
    validate: async () => handleBox.current!.validate(),
    publish: async () => handleBox.current!.publish(),
    autoLayout: async () => handleBox.current!.autoLayout(),
    ensureLayout: async (opts) => {
      if (!handleBox.current?.ensureLayout) return "manual";
      // Apply queued graph before layout so ELK sees real nodes.
      flush(handleBox.current);
      return handleBox.current.ensureLayout(opts);
    },
    deleteSelected: () => handleBox.current?.deleteSelected(),
    unmount() {
      root.unmount();
      roots.delete(el);
      handles.delete(el);
    },
  };
}

export function mount(el: Element, options: DesignerMountOptions) {
  let root = roots.get(el);
  let handleBox = handles.get(el);

  // If host wiped the DOM (innerHTML='') the fiber root is dead — remount cleanly.
  const domEmpty = !(el as HTMLElement).childElementCount;
  if (root && domEmpty) {
    try {
      root.unmount();
    } catch {
      /* ignore */
    }
    roots.delete(el);
    handles.delete(el);
    root = undefined;
    handleBox = undefined;
  }

  const pending: Pending = {
    graph: options.graph,
    graphId: options.graphId,
  };

  // Already mounted: push graph/options via imperative API — do not remount (keeps edges).
  if (root && handleBox?.current) {
    if (options.graph) handleBox.current.setGraph(options.graph);
    if (options.graphId) handleBox.current.setGraphId?.(options.graphId);
    if (options.onReady) options.onReady(handleBox.current);
    return wrapHandle(el, root, handleBox, pending);
  }

  if (!root) {
    root = createRoot(el);
    roots.set(el, root);
  }
  handleBox = { current: null };
  handles.set(el, handleBox);

  const wrapped = wrapHandle(el, root, handleBox, pending);

  root.render(
    <GraphDesigner
      {...options}
      chrome={options.chrome || "full"}
      onReady={(h) => {
        handleBox!.current = h;
        // Apply any setGraph/setGraphId that raced ahead of first paint.
        if (pending.graph) {
          h.setGraph(pending.graph);
          pending.graph = undefined;
        }
        if (pending.graphId != null) {
          h.setGraphId?.(pending.graphId);
          pending.graphId = undefined;
        }
        options.onReady?.(h);
      }}
    />,
  );

  return wrapped;
}

export type RunModeMountOptions = {
  graph: WorkflowGraph;
  runId?: string;
  runState?: RunStateSnapshot | null;
  apiBase?: string;
  readOnly?: boolean;
  pollMs?: number;
  onState?: (state: RunStateSnapshot) => void;
};

/** Mount IR-driven run mode: readonly canvas + optional HITL actions. */
export function mountRunMode(el: Element, options: RunModeMountOptions) {
  let root = roots.get(el);
  if (!root) {
    root = createRoot(el);
    roots.set(el, root);
  }

  const api = createApi(options.apiBase);
  let disposed = false;
  let runState = options.runState || null;
  let timer: ReturnType<typeof setInterval> | null = null;

  const render = () => {
    root!.render(
      <RunModeShell
        graph={options.graph}
        runState={runState}
        readOnly={options.readOnly === true}
        onApprove={async (nodeId) => {
          if (!options.runId) return;
          await api.approve(options.runId, nodeId);
          await refresh();
        }}
        onReject={async (nodeId) => {
          if (!options.runId) return;
          await api.reject(options.runId, nodeId);
          await refresh();
        }}
        onResume={async (nodeId) => {
          if (!options.runId) return;
          await api.resume(options.runId, nodeId);
          await refresh();
        }}
        canvas={
          <GraphDesigner
            kind={options.graph.kind}
            graph={options.graph}
            readOnly
            chrome="minimal"
            embedded
          />
        }
      />,
    );
  };

  const refresh = async () => {
    if (!options.runId || disposed) return;
    try {
      const state = await api.getRunState(options.runId);
      runState = state;
      options.onState?.(state);
      render();
    } catch {
      /* keep last known state */
    }
  };

  render();
  if (options.runId) {
    void refresh();
    timer = setInterval(() => void refresh(), options.pollMs || 2000);
  }

  return {
    setRunState(state: RunStateSnapshot | null) {
      runState = state;
      render();
    },
    refresh,
    unmount() {
      disposed = true;
      if (timer) clearInterval(timer);
      root?.unmount();
      roots.delete(el);
    },
  };
}

declare global {
  interface Window {
    ReactFlowDesigner?: {
      mount: typeof mount;
      mountRunMode: typeof mountRunMode;
    };
  }
}

window.ReactFlowDesigner = { mount, mountRunMode };

export default { mount, mountRunMode };
