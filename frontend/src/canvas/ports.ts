/** Branching-port helpers shared by node view, inspector, and layout. */

export type PortDef = { id: string; label: string };

const HEAD_H = 28;
const LABEL_H = 36;
const PORT_ROW_H = 30;
const PORT_PAD_TOP = 6;

export const NODE_METRICS = { HEAD_H, LABEL_H, PORT_ROW_H, PORT_PAD_TOP };

export function branchPorts(
  nodeType: string,
  config?: Record<string, unknown>,
): PortDef[] | null {
  if (nodeType === "condition" || nodeType === "branch") {
    const options = (config?.options as unknown[]) || (config?.outlets as unknown[]);
    if (Array.isArray(options) && options.length) {
      return options.map((o: any, i: number) => {
        const id = String(o?.identifier || o?.id || `opt${i + 1}`).trim() || `opt${i + 1}`;
        return { id, label: String(o?.title || o?.label || id) };
      });
    }
    return [
      { id: "yes", label: "Yes" },
      { id: "no", label: "No" },
    ];
  }
  if (nodeType === "input" || nodeType === "approval") {
    const outlets = config?.outlets;
    if (Array.isArray(outlets) && outlets.length) {
      return outlets.map((o: any, i: number) => {
        const id = String(o?.identifier || o?.id || `out${i + 1}`).trim() || `out${i + 1}`;
        return { id, label: String(o?.title || o?.label || id) };
      });
    }
    const buttons = (config?.userInputs as { buttons?: unknown[] } | undefined)?.buttons;
    if (Array.isArray(buttons) && buttons.length) {
      return buttons.map((b: any, i: number) => {
        const id = String(b?.identifier || `btn${i + 1}`).trim() || `btn${i + 1}`;
        return { id, label: String(b?.label || id) };
      });
    }
    return [
      { id: "approve", label: "Approve" },
      { id: "decline", label: "Decline" },
    ];
  }
  if (nodeType === "internal_service" && (config?.governance || config?.service === "policy.evaluate")) {
    return [
      { id: "pass", label: "Yes" },
      { id: "fail", label: "No" },
    ];
  }
  return null;
}

export function outletIdSet(nodeType: string, config?: Record<string, unknown>): Set<string> | null {
  const ports = branchPorts(nodeType, config);
  if (!ports) return null;
  return new Set(ports.map((p) => p.id));
}

export function nodeBoxSize(nodeType: string, config?: Record<string, unknown>): { w: number; h: number } {
  const ports = branchPorts(nodeType, config);
  const multi = !!ports && ports.length > 1;
  const h = multi
    ? HEAD_H + LABEL_H + PORT_PAD_TOP + ports!.length * PORT_ROW_H + 12
    : 72;
  return { w: multi ? 200 : 180, h };
}

export function sourceTopPx(index: number, multi: boolean): number {
  if (!multi) return HEAD_H + LABEL_H / 2;
  return HEAD_H + LABEL_H + PORT_PAD_TOP + index * PORT_ROW_H + PORT_ROW_H / 2;
}

export function nextPortId(existing: string[], prefix = "opt"): string {
  const used = new Set(existing.map((s) => s.trim()).filter(Boolean));
  let i = 1;
  while (used.has(`${prefix}${i}`)) i += 1;
  return `${prefix}${i}`;
}
