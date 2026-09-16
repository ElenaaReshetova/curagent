import { GraphDesigner } from "./canvas/GraphDesigner";
import { BuilderShell } from "./shells/BuilderShell";
import { RunModeShell } from "./shells/RunModeShell";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./mounts/embed";

const rootEl = document.getElementById("root");
if (rootEl && !rootEl.dataset.embedded) {
  createRoot(rootEl).render(
    <div style={{ height: "100vh" }}>
      <BuilderShell kind="stage" />
    </div>,
  );
}

export { GraphDesigner, BuilderShell, RunModeShell };
