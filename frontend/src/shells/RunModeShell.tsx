import type { ReactNode } from "react";
import type { RunStateSnapshot, WorkflowGraph } from "../types";

export type RunModeShellProps = {
  graph: WorkflowGraph;
  runState?: RunStateSnapshot | null;
  readOnly?: boolean;
  onApprove?: (nodeId: string) => void | Promise<void>;
  onReject?: (nodeId: string) => void | Promise<void>;
  onResume?: (nodeId?: string) => void | Promise<void>;
  canvas?: ReactNode;
};

/** Run view: graph + status. No debug JSON dumps. */
export function RunModeShell({
  graph,
  runState,
  readOnly = true,
  onApprove,
  onReject,
  onResume,
  canvas,
}: RunModeShellProps) {
  const pendingId = runState?.pending_approval?.node_id;
  const currentId = runState?.current_node_id;
  const status = runState?.status || "pending";

  return (
    <div className="run-mode-shell" data-status={status}>
      <header className="run-mode-shell__bar">
        <strong>{graph.name || "Запуск"}</strong>
        <span className="run-mode-shell__meta">{status}</span>
        {currentId ? <span className="run-mode-shell__meta">→ {currentId}</span> : null}
        {!readOnly && pendingId ? (
          <div className="run-mode-shell__actions">
            <button type="button" onClick={() => onApprove?.(pendingId)}>Утвердить</button>
            <button type="button" onClick={() => onReject?.(pendingId)}>Отклонить</button>
            <button type="button" onClick={() => onResume?.(pendingId)}>Продолжить</button>
          </div>
        ) : null}
      </header>
      <div className="run-mode-shell__canvas">{canvas}</div>
      {runState?.error ? <div className="run-mode-shell__error">{runState.error}</div> : null}
    </div>
  );
}
