import { Handle, Position, useUpdateNodeInternals, type NodeProps } from "@xyflow/react";
import { createContext, useContext, useLayoutEffect, useRef } from "react";
import { colorFor } from "../registry/catalog";
import type { NodeRegistryEntry, PortDef } from "../types";
import { branchPorts, nodeBoxSize, sourceTopPx } from "./ports";

export const RunHighlightContext = createContext<{ nodeId: string | null; mode: "current" | "waiting" | "" }>({
  nodeId: null,
  mode: "",
});

export type GraphNodeData = {
  label: string;
  nodeType: string;
  entry?: NodeRegistryEntry;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

const HANDLE_COLORS: Record<string, string> = {
  approve: "#16a34a",
  yes: "#16a34a",
  pass: "#16a34a",
  true: "#16a34a",
  changes: "#d97706",
  clarify: "#d97706",
  reject: "#dc2626",
  decline: "#dc2626",
  no: "#dc2626",
  fail: "#dc2626",
  false: "#dc2626",
  out: "#64748b",
};

function outcomesFromConfig(
  nodeType: string,
  entry: NodeRegistryEntry | undefined,
  config?: Record<string, unknown>,
): PortDef[] {
  const branched = branchPorts(nodeType, config);
  if (branched) return branched;
  if (entry?.ports?.out?.length) {
    return entry.ports.out.map((p) => ({
      id: p.id,
      label: p.id === "out" ? "" : p.label || p.id,
    }));
  }
  return [{ id: "out", label: "" }];
}

function inputsFromEntry(entry: NodeRegistryEntry | undefined, nodeType: string): PortDef[] {
  if (nodeType === "trigger") return [];
  if (entry?.ports?.in?.length) return entry.ports.in.map((p) => ({ id: p.id, label: "" }));
  return [{ id: "in", label: "" }];
}

export function WorkflowNodeView({ id, data, selected }: NodeProps) {
  const d = data as GraphNodeData;
  const entry = d.entry;
  const color = colorFor(entry?.ui?.colorToken || (entry as { colorToken?: string } | undefined)?.colorToken || "slate");
  const outs = outcomesFromConfig(d.nodeType, entry, d.config);
  const ins = inputsFromEntry(entry, d.nodeType);
  const multi = outs.length > 1;
  const box = nodeBoxSize(d.nodeType, d.config);
  const minH = box.h;
  const updateNodeInternals = useUpdateNodeInternals();
  const outsKey = outs.map((p) => p.id).join("|");
  const rootRef = useRef<HTMLDivElement>(null);
  const highlight = useContext(RunHighlightContext);
  const runClass =
    highlight.nodeId === id
      ? highlight.mode === "waiting"
        ? "gnode--run-waiting"
        : "gnode--run-current"
      : "";

  useLayoutEffect(() => {
    updateNodeInternals(id);
    const el = rootRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => updateNodeInternals(id));
    ro.observe(el);
    const t = window.setTimeout(() => updateNodeInternals(id), 40);
    return () => {
      ro.disconnect();
      window.clearTimeout(t);
    };
  }, [id, outsKey, multi, minH, updateNodeInternals]);

  return (
    <div
      ref={rootRef}
      className={`gnode ${selected ? "gnode--selected" : ""} ${multi ? "gnode--branching" : ""} ${runClass}`}
      style={{ borderColor: color, minHeight: minH, width: box.w }}
    >
      {ins.map((p) => (
        <Handle
          key={`in-${p.id}`}
          id={p.id}
          type="target"
          position={Position.Left}
          className="gnode__handle gnode__handle--target nodrag nopan nokey"
          isConnectableStart={false}
          isConnectableEnd
          style={{ background: color, top: "50%" }}
        />
      ))}

      <div className="gnode__head" style={{ background: color }}>
        <span className="gnode__icon">{entry?.icon || "•"}</span>
        <span className="gnode__type">{entry?.title || d.nodeType}</span>
      </div>
      <div className="gnode__label">{d.label}</div>

      {outs.map((p, i) =>
        multi ? (
          <Handle
            key={`out-${p.id}`}
            id={p.id}
            type="source"
            position={Position.Right}
            className="gnode__handle gnode__handle--chip nodrag nopan nokey"
            isConnectable
            isConnectableStart
            style={{
              top: sourceTopPx(i, true),
              background: HANDLE_COLORS[p.id] || color,
            }}
            title={`${p.label || p.id}: тяните к следующему шагу`}
          >
            <span className="gnode__chip-label">{p.label || p.id}</span>
          </Handle>
        ) : (
          <Handle
            key={`out-${p.id}`}
            id={p.id}
            type="source"
            position={Position.Right}
            className="gnode__handle gnode__handle--source nodrag nopan nokey"
            isConnectable
            isConnectableStart
            style={{
              background: HANDLE_COLORS[p.id] || color,
              top: "50%",
            }}
            title={p.label || p.id}
          />
        ),
      )}
    </div>
  );
}

export const nodeTypes = { workflow: WorkflowNodeView };
