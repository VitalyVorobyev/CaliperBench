import { describe, expect, it } from "vitest";
import { canApproveReview } from "./reviewPolicy";
import type { ReviewDocument } from "./api";

const base = {
  contour_reviewed: true,
  reviewer: "reviewer",
  tasks: [
    {
      sample_id: "a",
      disposition: "approved",
      crossing_px: 4.25,
      uncertainty_px: 0.5,
      confidence: "medium",
      note: "",
    },
  ],
} as ReviewDocument;

describe("review approval preflight", () => {
  it("requires a named contour review and a decision for every strip", () => {
    expect(canApproveReview(base)).toBe(true);
    expect(canApproveReview({ ...base, reviewer: " " })).toBe(false);
    expect(canApproveReview({ ...base, contour_reviewed: false })).toBe(false);
    expect(
      canApproveReview({
        ...base,
        tasks: [{ ...base.tasks[0], disposition: "pending" }],
      }),
    ).toBe(false);
  });
  it("rejects missing uncertainty but permits explicit exclusions", () => {
    expect(
      canApproveReview({
        ...base,
        tasks: [{ ...base.tasks[0], uncertainty_px: null }],
      }),
    ).toBe(false);
    expect(
      canApproveReview({
        ...base,
        tasks: [
          { ...base.tasks[0], disposition: "excluded", crossing_px: null },
        ],
      }),
    ).toBe(true);
  });
});
