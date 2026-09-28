import { describe, expect, it } from "vitest";
import {
  deformContour,
  edgeClipSides,
  nearestSegment,
  pointAt,
  stripLength,
} from "./geometry";
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
  it("moves neighboring contour points with a bounded, cyclic brush", () => {
    const points: [number, number][] = [
      [10, 10],
      [20, 10],
      [30, 10],
      [30, 20],
      [20, 20],
      [10, 20],
    ];
    const moved = deformContour(points, 0, [5, 0], 25, 40, 40);
    expect(moved[0][0]).toBe(15);
    expect(moved[1][0]).toBeGreaterThan(20);
    expect(moved[5][0]).toBeGreaterThan(10);
    expect(moved[3]).toEqual(points[3]);
    expect(deformContour(points, 0, [-50, 0], 25, 40, 40)[0][0]).toBe(0);
  });
  it("does not connect or deform opposite ends of an open edge", () => {
    const points: [number, number][] = [
      [0, 10],
      [20, 10],
      [40, 10],
    ];
    expect(nearestSegment(points, [1, 10], false)).toBe(0);
    const moved = deformContour(points, 0, [0, 5], 25, 50, 30, false);
    expect(moved[0][1]).toBe(15);
    expect(moved[1][1]).toBeGreaterThan(10);
    expect(moved[2]).toEqual(points[2]);
    expect(
      edgeClipSides(
        [
          [0, 10],
          [20, 10],
          [0, 20],
        ],
        50,
        30,
        false,
      ),
    ).toEqual(["left"]);
    expect(
      edgeClipSides(
        [
          [0, 10],
          [20, 10],
          [0, 20],
        ],
        50,
        30,
        true,
      ),
    ).toEqual([]);
  });
});
