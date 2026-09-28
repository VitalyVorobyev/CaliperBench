import type { Point, Request } from "./api";

export function edgeClipSides(
  points: Point[],
  width: number,
  height: number,
  closed: boolean,
): ("top" | "right" | "bottom" | "left")[] {
  if (closed || points.length < 2) return [];
  const ends = [points[0], points[points.length - 1]];
  return (["top", "right", "bottom", "left"] as const).filter((side) =>
    ends.some(([x, y]) => {
      if (side === "top") return y <= 0.5;
      if (side === "right") return x >= width - 1.5;
      if (side === "bottom") return y >= height - 1.5;
      return x <= 0.5;
    }),
  );
}

export function stripLength(request: Request): number {
  const [a, b] = [request.strip.start_xy, request.strip.end_xy];
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

export function pointAt(request: Request, distance: number): Point {
  const [a, b] = [request.strip.start_xy, request.strip.end_xy];
  const fraction = distance / stripLength(request);
  return [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction];
}

export function nearestSegment(
  points: Point[],
  point: Point,
  closed = true,
): number {
  let winner = 0,
    best = Infinity;
  for (let i = 0; i < points.length - (closed ? 0 : 1); i++) {
    const [a, b] = [points[i], points[(i + 1) % points.length]];
    const dx = b[0] - a[0],
      dy = b[1] - a[1];
    const t = Math.max(
      0,
      Math.min(
        1,
        ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) /
          (dx * dx + dy * dy || 1),
      ),
    );
    const distance =
      (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2;
    if (distance < best) {
      best = distance;
      winner = i;
    }
  }
  return winner;
}

/** Move a local arc with a smooth, distance-based brush. */
export function deformContour(
  points: Point[],
  anchor: number,
  delta: Point,
  radius: number,
  width: number,
  height: number,
  closed = true,
): Point[] {
  const n = points.length;
  if (!n || radius <= 0) return points;
  const arc = [0];
  for (let i = 0; i < n - (closed ? 0 : 1); i++) {
    const a = points[i],
      b = points[(i + 1) % n];
    arc.push(arc[i] + Math.hypot(b[0] - a[0], b[1] - a[1]));
  }
  const perimeter = arc[arc.length - 1];
  return points.map(([x, y], i) => {
    const direct = Math.abs(arc[i] - arc[anchor]);
    const distance = closed ? Math.min(direct, perimeter - direct) : direct;
    const weight =
      distance >= radius
        ? 0
        : (1 + Math.cos((Math.PI * distance) / radius)) / 2;
    return [
      Math.max(0, Math.min(width - 1, x + delta[0] * weight)),
      Math.max(0, Math.min(height - 1, y + delta[1] * weight)),
    ];
  });
}
