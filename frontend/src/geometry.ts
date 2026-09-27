import type { Point, Request } from "./api";

export function stripLength(request: Request): number {
  const [a, b] = [request.strip.start_xy, request.strip.end_xy];
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

export function pointAt(request: Request, distance: number): Point {
  const [a, b] = [request.strip.start_xy, request.strip.end_xy];
  const fraction = distance / stripLength(request);
  return [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction];
}

export function nearestSegment(points: Point[], point: Point): number {
  let winner = 0,
    best = Infinity;
  for (let i = 0; i < points.length; i++) {
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
