"""Public geometric scan probes for reviewing a proposed image contour."""

import numpy as np

from .refine import strip_crossings


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
