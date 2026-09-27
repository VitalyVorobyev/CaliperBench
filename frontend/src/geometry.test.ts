import { describe, expect, it } from "vitest";
import { nearestSegment, pointAt, stripLength } from "./geometry";
import type { Request } from "./api";

const request: Request = {
  sample_id: "test",
  strip: { start_xy: [10, 5], end_xy: [10, 25], width_px: 1, samples: 21 },
  polarities: ["either"],
};

describe("image-coordinate geometry", () => {
  it("projects scan distance to pixel-center coordinates", () => {
    expect(stripLength(request)).toBe(20);
    expect(pointAt(request, 3.25)).toEqual([10, 8.25]);
  });
  it("finds a contour segment for insertion", () => {
    expect(
      nearestSegment(
        [
          [2, 2],
          [8, 2],
          [8, 8],
          [2, 8],
        ],
        [5, 2.4],
      ),
    ).toBe(0);
  });
});
