import { describe, expect, it } from "vitest";
import { canApproveReview } from "./reviewPolicy";
import type { ReviewDocument } from "./api";

const base = {
  contour_reviewed: true,
  contour_uncertainty_px: 1,
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
  it("requires a named contour review with positive uncertainty", () => {
    expect(canApproveReview(base)).toBe(true);
    expect(canApproveReview({ ...base, reviewer: " " })).toBe(false);
    expect(canApproveReview({ ...base, contour_reviewed: false })).toBe(false);
    expect(canApproveReview({ ...base, contour_uncertainty_px: 0 })).toBe(
      false,
    );
  });
  it("does not require individual scan decisions", () => {
    expect(
      canApproveReview({
        ...base,
        tasks: [
          { ...base.tasks[0], disposition: "pending", crossing_px: null },
        ],
      }),
    ).toBe(true);
  });
});
