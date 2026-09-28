"""Public geometric scan probes for reviewing a proposed image contour."""

import numpy as np

from .refine import strip_crossings


def normal_scan_at_crossing(contour, strip, crossing, width: int, height: int):
    """Reorient a candidate scan to the local reviewed contour tangent."""
    vertices = np.asarray(contour, dtype=float)
    start = np.asarray(strip.start_xy, dtype=float)
    end = np.asarray(strip.end_xy, dtype=float)
    direction = end - start
    length = float(np.linalg.norm(direction))
    point = start + direction * (crossing / length)
    segments = np.roll(vertices, -1, axis=0) - vertices
    fractions = np.clip(
        np.sum((point - vertices) * segments, axis=1)
        / np.maximum(np.sum(segments * segments, axis=1), 1e-12),
        0,
        1,
    )
    nearest = vertices + segments * fractions[:, None]
    index = int(np.argmin(np.sum((nearest - point) ** 2, axis=1)))
    # A chord across neighboring vertices is more stable than a single polygon edge.
    tangent = vertices[(index + 3) % len(vertices)] - vertices[(index - 2) % len(vertices)]
    norm = float(np.linalg.norm(tangent))
    if norm < 1e-9:
        return None
    normal = np.array([-tangent[1], tangent[0]]) / norm
    if np.dot(normal, direction) < 0:
        normal = -normal
    a, b = point - length * normal / 2, point + length * normal / 2
    if any(not (-0.5 <= p[0] <= width - 0.5 and -0.5 <= p[1] <= height - 0.5) for p in (a, b)):
        return None
    hits = strip_crossings(contour, tuple(a), tuple(b))
    if len(hits) != 1:
        return None
    return strip.model_copy(update={"start_xy": tuple(a), "end_xy": tuple(b)}), hits[0]


def contour_probes(contour, width: int, height: int, count: int = 32):
    """Evenly sample a closed contour; retain only unambiguous in-bounds normals."""
    vertices = np.asarray(contour, dtype=float)
    closed = np.vstack([vertices, vertices[0]])
    lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    arc = np.r_[0.0, np.cumsum(lengths)]
    perimeter = float(arc[-1])
    if perimeter < 1:
        return []

    def at(distance):
        distance %= perimeter
        return np.array([np.interp(distance, arc, closed[:, axis]) for axis in (0, 1)])

    probes = []
    # More candidates than the target allows skipping corners and narrow regions.
    for ordinal in range(count * 3):
        distance = (ordinal + 0.5) * perimeter / (count * 3)
        center = at(distance)
        tangent = at(distance + 4) - at(distance - 4)
        norm = float(np.linalg.norm(tangent))
        if norm < 1:
            continue
        normal = np.array([-tangent[1], tangent[0]]) / norm
        start, end = center - 12 * normal, center + 12 * normal
        if any(
            not (-0.5 <= point[0] <= width - 0.5 and -0.5 <= point[1] <= height - 0.5)
            for point in (start, end)
        ):
            continue
        hits = strip_crossings(contour, tuple(start), tuple(end))
        if len(hits) != 1 or abs(hits[0] - 12) > 3:
            continue
        if probes and np.linalg.norm(center - probes[-1][0]) < perimeter / count * 0.7:
            continue
        probes.append((center, start, end, hits[0]))
        if len(probes) == count:
            break
    return probes
