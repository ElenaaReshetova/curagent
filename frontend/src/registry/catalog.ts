import type { GraphKind, NodeRegistryEntry, NodeType } from "../types";

const COLORS: Record<string, string> = {
  emerald: "#059669",
  indigo: "#4f46e5",
  sky: "#0284c7",
  cyan: "#0891b2",
  violet: "#7c3aed",
  purple: "#9333ea",
  pink: "#db2777",
  amber: "#d97706",
  orange: "#ea580c",
  teal: "#0d9488",
  slate: "#475569",
};

export function colorFor(token: string): string {
  return COLORS[token] || COLORS.slate;
}

/** Fallback registry when API is unreachable. No End — has none. */
export const FALLBACK_REGISTRY: NodeRegistryEntry[] = [
  mk("trigger", "Trigger", "Triggers", "▶", "emerald", [], ["out"]),
  mk("ai_agent", "AI Agent", "Actions", "A", "indigo", ["in"], ["out"]),
  mk("ai", "AI", "Actions", "✦", "violet", ["in"], ["out"]),
  mk("webhook", "Webhook", "Actions", "⇢", "sky", ["in"], ["out"]),
  mk("internal_service", "Internal service", "Actions", "▣", "teal", ["in"], ["out"]),
  mk("subflow", "Subflow", "Actions", "↳", "purple", ["in"], ["out"]),
  mk("condition", "Condition", "Conditions", "◇", "violet", ["in"], ["yes", "no"]),
  mk("input", "Input", "Input", "✓", "pink", ["in"], ["approve", "decline"]),
];

function mk(
  type: NodeType,
  title: string,
  category: string,
  icon: string,
  color: string,
  ins: string[],
  outs: string[],
  kinds: GraphKind[] = ["e2e", "stage"],
): NodeRegistryEntry {
  return {
    type,
    title,
    category,
    icon,
    configSchema: { type: "object", properties: {} },
    ports: {
      in: ins.map((id) => ({ id, label: id })),
      out: outs.map((id) => ({ id, label: id })),
    },
    ui: { defaultSize: { w: 200, h: 64 }, inspector: "schema-form", colorToken: color },
    runtime: { temporalKind: type === "trigger" ? "entrypoint" : type },
    kinds,
    palette: true,
  };
}

export function registryForKind(
  entries: NodeRegistryEntry[],
  kind: GraphKind,
): NodeRegistryEntry[] {
  return entries.filter((e) => e.kinds.includes(kind) && e.palette !== false);
}
