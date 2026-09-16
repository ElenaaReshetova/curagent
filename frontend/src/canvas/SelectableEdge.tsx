import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  Position,
  useReactFlow,
  type EdgeProps,
} from "@xyflow/react";
import { createContext, useContext, useEffect, useRef } from "react";

export type EdgeWaypoint = { x: number; y: number };

export const EdgeEditContext = createContext<{
  setWaypoint: (id: string, waypoint: EdgeWaypoint | null, persist: boolean) => void;
  readOnly: boolean;
}>({ setWaypoint: () => {}, readOnly: false });

function useEdgeEdit() {
  return useContext(EdgeEditContext);
}

function dist2(ax: number, ay: number, bx: number, by: number) {
  const dx = ax - bx;
  const dy = ay - by;
  return dx * dx + dy * dy;
}

const END_GUARD = 28;
const DRAG_THRESHOLD = 4;
const CORNER = 12;

function stepPath(args: {
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition?: Position;
  targetPosition?: Position;
  waypoint?: EdgeWaypoint;
}) {
  const srcPos = args.sourcePosition || Position.Right;
  const tgtPos = args.targetPosition || Position.Left;
  const backward = !args.waypoint && args.targetX < args.sourceX - 36;

  if (backward) {
    const top = Math.min(args.sourceY, args.targetY) - 40;
    const midX1 = args.sourceX + 24;
    const midX2 = args.targetX - 24;
    return {
      path: `M ${args.sourceX},${args.sourceY} L ${midX1},${args.sourceY} L ${midX1},${top} L ${midX2},${top} L ${midX2},${args.targetY} L ${args.targetX},${args.targetY}`,
      labelX: (args.sourceX + args.targetX) / 2,
      labelY: top,
      backward: true,
    };
  }

  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX: args.sourceX,
    sourceY: args.sourceY,
    targetX: args.targetX,
    targetY: args.targetY,
    sourcePosition: srcPos,
    targetPosition: tgtPos,
    borderRadius: CORNER,
    offset: 18,
    ...(args.waypoint
      ? { centerX: args.waypoint.x, centerY: args.waypoint.y }
      : {}),
  });
  return { path, labelX, labelY, backward: false };
}

/** Orthogonal connectors. Drag the line to shift the elbow; shape stays stepped. */
export function SelectableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  label,
  selected,
  data,
}: EdgeProps) {
  const { screenToFlowPosition } = useReactFlow();
  const { setWaypoint, readOnly } = useEdgeEdit();
  const toFlow = useRef(screenToFlowPosition);
  toFlow.current = screenToFlowPosition;
  const setWp = useRef(setWaypoint);
  setWp.current = setWaypoint;
  const stopDrag = useRef<(() => void) | null>(null);

  const waypoint = (data as { waypoint?: EdgeWaypoint } | undefined)?.waypoint;
  const { path, labelX, labelY, backward } = stepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    waypoint,
  });

  const baseStroke = typeof style?.stroke === "string" ? style.stroke : "#94a3b8";
  const stroke = selected ? "#2563eb" : baseStroke;
  const text = label ? String(label) : "";

  useEffect(
    () => () => {
      stopDrag.current?.();
    },
    [],
  );

  const beginDrag = (e: React.PointerEvent) => {
    if (readOnly || e.button !== 0) return;
    const origin = toFlow.current({ x: e.clientX, y: e.clientY });
    if (dist2(origin.x, origin.y, sourceX, sourceY) < END_GUARD * END_GUARD) return;
    if (dist2(origin.x, origin.y, targetX, targetY) < END_GUARD * END_GUARD) return;

    e.preventDefault();
    e.stopPropagation();

    const base = waypoint ? { x: waypoint.x, y: waypoint.y } : { x: labelX, y: labelY };
    const pointerId = e.pointerId;
    let moved = false;
    stopDrag.current?.();

    const apply = (ev: PointerEvent, persist: boolean) => {
      const now = toFlow.current({ x: ev.clientX, y: ev.clientY });
      setWp.current(
        id,
        { x: base.x + (now.x - origin.x), y: base.y + (now.y - origin.y) },
        persist,
      );
    };

    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId) return;
      const now = toFlow.current({ x: ev.clientX, y: ev.clientY });
      if (!moved && dist2(now.x, now.y, origin.x, origin.y) < DRAG_THRESHOLD * DRAG_THRESHOLD) {
        return;
      }
      moved = true;
      ev.preventDefault();
      document.body.classList.add("gedge-dragging");
      apply(ev, false);
    };
    const onUp = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId) return;
      cleanup();
      if (moved) apply(ev, true);
    };
    const cleanup = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      stopDrag.current = null;
      document.body.classList.remove("gedge-dragging");
    };
    stopDrag.current = cleanup;
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  };

  const onDoubleClick = (e: React.MouseEvent) => {
    if (readOnly) return;
    e.preventDefault();
    e.stopPropagation();
    setWp.current(id, null, true);
  };

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        interactionWidth={40}
        style={{
          ...style,
          stroke,
          strokeWidth: selected ? 3 : 2,
          strokeDasharray: backward ? "7 5" : undefined,
          cursor: readOnly ? "pointer" : "grab",
        }}
      />
      {!readOnly ? (
        <path
          d={path}
          fill="none"
          stroke="rgba(37, 99, 235, 0.001)"
          strokeWidth={28}
          className="gedge-hit nopan nodrag"
          style={{ pointerEvents: "stroke", cursor: "grab" }}
          onPointerDown={beginDrag}
          onDoubleClick={onDoubleClick}
        />
      ) : null}
      {text ? (
        <EdgeLabelRenderer>
          <div
            className={`gedge-chip nodrag nopan ${selected ? "gedge-chip--selected" : ""} ${backward ? "gedge-chip--feedback" : ""}`}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "all",
            }}
            title="Потяните, чтобы сместить изгиб. Двойной клик — сбросить. Delete — удалить."
            onPointerDown={beginDrag}
            onDoubleClick={onDoubleClick}
          >
            {text}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

export const edgeTypes = { selectable: SelectableEdge };
