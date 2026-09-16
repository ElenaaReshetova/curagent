import type { DesignerMountOptions, GraphKind } from "../types";
import { GraphDesigner } from "../canvas/GraphDesigner";

export type BuilderShellProps = DesignerMountOptions & {
  kind: GraphKind;
};

/**
 * Builder chrome shell — IR-driven designer entry.
 * Keeps palette / canvas / inspector composition behind one mount point.
 */
export function BuilderShell(props: BuilderShellProps) {
  return (
    <div className="builder-shell" style={{ height: "100%", width: "100%" }}>
      <GraphDesigner {...props} />
    </div>
  );
}
