import { describe, expect, it } from "vitest";

import {
  canvasToWorkflowDsl,
  workflowDocumentToCanvas,
  workflowDslToCanvas,
  type WorkflowDsl,
} from "./workflowDsl";

const dsl: WorkflowDsl = {
  identifier: "round-trip",
  title: "Round trip",
  produces: ["BUSINESS_REQUIREMENTS"],
  nodes: [
    { identifier: "trigger", title: "Trigger", config: { type: "SELF_SERVE_TRIGGER" } },
    {
      identifier: "condition",
      title: "Condition",
      config: {
        type: "CONDITION",
        options: [{ identifier: "yes", expression: "input.ready == true" }],
      },
    },
    {
      identifier: "review",
      title: "Review",
      config: {
        type: "INPUT",
        outlets: [
          { identifier: "approve" },
          { identifier: "decline" },
        ],
      },
    },
  ],
  connections: [
    { sourceIdentifier: "trigger", targetIdentifier: "condition" },
    { sourceIdentifier: "condition", targetIdentifier: "review", sourceOptionIdentifier: "yes" },
    { sourceIdentifier: "condition", targetIdentifier: "review", fallback: true },
    { sourceIdentifier: "review", targetIdentifier: "condition", sourceOutletIdentifier: "decline" },
  ],
  ui: {
    kind: "e2e",
    positions: {
      trigger: { x: 20, y: 30 },
      condition: { x: 220, y: 30 },
      review: { x: 420, y: 30 },
    },
  },
};

describe("workflow DSL canvas round trip", () => {
  it("preserves fallback, layout, produces, and HITL handles", () => {
    const roundTrip = canvasToWorkflowDsl(workflowDslToCanvas(dsl));

    expect(roundTrip.produces).toEqual(dsl.produces);
    expect(roundTrip.ui?.positions).toEqual(dsl.ui?.positions);
    expect(roundTrip.connections[1].sourceOptionIdentifier).toBe("yes");
    expect(roundTrip.connections[2].fallback).toBe(true);
    expect(roundTrip.connections[3].sourceOutletIdentifier).toBe("decline");
    expect(roundTrip.nodes.find((node) => node.identifier === "review")?.config.outlets).toEqual(
      dsl.nodes.find((node) => node.identifier === "review")?.config.outlets,
    );
  });

  it("loads both canonical DSL and canvas projections", () => {
    const canvas = workflowDslToCanvas(dsl);
    expect(workflowDocumentToCanvas(dsl)?.graphId).toBe("round-trip");
    expect(workflowDocumentToCanvas(canvas)?.edges).toEqual(canvas.edges);
    expect(workflowDocumentToCanvas({ nodes: [], connections: [] })).toBeNull();
  });
});
