"""Public, classical mask-contour proposal. This never creates ground truth."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage.filters import gaussian
from skimage.measure import find_contours
from skimage.segmentation import active_contour

PARAMETERS = {
    "method": "skimage-active-contour-v3",
    "gaussian_sigma": 1.0,
    "alpha": 0.01,
    "beta": 0.3,
    "gamma": 0.01,
    "w_edge": 1.0,
    "max_px_move": 0.5,
    "max_num_iter": 100,
    "max_displacement_px": 4.0,
    "max_vertices": 300,
}


@dataclass(frozen=True)
class Proposal:
    source_contour: list[list[float]]
    refined_contour: list[list[float]]
    flags: list[str]
    parameters: dict


def propose(image: np.ndarray, mask: np.ndarray) -> Proposal:
    """Fit a smooth closed snake from the largest mask contour; flag unsafe changes.

    Coordinates are source-image pixel centers. A failed or untrustworthy fit leaves
    the original contour as the editable proposal; it is never silently approved.
    """
    gray = np.asarray(image, dtype=float)
    binary = np.asarray(mask, dtype=bool)
    if gray.ndim != 2 or gray.shape != binary.shape or min(gray.shape) < 8:
        raise ValueError("image and mask must be matching two-dimensional arrays")
    if not np.isfinite(gray).all() or gray.min() < 0 or gray.max() > 1:
        raise ValueError("image must contain finite grayscale values in [0,1]")
    contours = find_contours(binary.astype(float), 0.5)
    if not contours:
        raise ValueError("mask has no contour")
    contour = max(contours, key=len)
    stride = max(1, int(np.ceil(len(contour) / PARAMETERS["max_vertices"])))
    start = contour[::stride].astype(float)
    source = [[round(float(x), 4), round(float(y), 4)] for y, x in start]
    flags: list[str] = []
    if len(contours) > 1:
        flags.append("multiple_source_contours")
    try:
        fit = active_contour(
            gaussian(gray, PARAMETERS["gaussian_sigma"], preserve_range=True),
            start,
            alpha=PARAMETERS["alpha"],
            beta=PARAMETERS["beta"],
            gamma=PARAMETERS["gamma"],
            w_edge=PARAMETERS["w_edge"],
            max_px_move=PARAMETERS["max_px_move"],
            max_num_iter=PARAMETERS["max_num_iter"],
            boundary_condition="periodic",
        )
        if not np.isfinite(fit).all():
            flags.append("fit_nonfinite")
            fit = start
        else:
            displacement = np.linalg.norm(fit - start, axis=1)
            limit = PARAMETERS["max_displacement_px"]
            clipped = displacement > limit
            if np.any(clipped):
                flags.append(f"vertices_clipped_to_search_band:{int(np.sum(clipped))}")
                fit = (
                    start
                    + (fit - start) * np.minimum(1, limit / np.maximum(displacement, 1e-9))[:, None]
                )
        if (
            np.any(fit[:, 0] < 0)
            or np.any(fit[:, 0] > gray.shape[0] - 1)
            or np.any(fit[:, 1] < 0)
            or np.any(fit[:, 1] > gray.shape[1] - 1)
        ):
            flags.append("fit_out_of_bounds")
            fit = start
    except (ValueError, np.linalg.LinAlgError):
        flags.append("fit_failed")
        fit = start
    refined = [[round(float(x), 4), round(float(y), 4)] for y, x in fit]
    return Proposal(source, refined, flags, dict(PARAMETERS))


def strip_crossings(
    contour: list[list[float]], start: tuple[float, float], end: tuple[float, float]
) -> list[float]:
    """Scan distances where a closed contour crosses a strip centerline."""
    if len(contour) < 3:
        return []
    a = np.asarray(start, dtype=float)
    b = np.asarray(end, dtype=float)
    d = b - a
    length = float(np.linalg.norm(d))
    if length == 0:
        raise ValueError("strip endpoints must differ")
    hits = []
    for i, p in enumerate(contour):
        q = contour[(i + 1) % len(contour)]
        e = np.asarray(q, dtype=float) - p
        cross = d[0] * e[1] - d[1] * e[0]
        if abs(cross) < 1e-9:
            continue
        delta = np.asarray(p, dtype=float) - a
        t = (delta[0] * e[1] - delta[1] * e[0]) / cross
        u = (delta[0] * d[1] - delta[1] * d[0]) / cross
        if -1e-8 <= t <= 1 + 1e-8 and -1e-8 <= u <= 1 + 1e-8:
            hits.append(float(t * length))
    ordered = sorted(hits)
    return [round(x, 4) for i, x in enumerate(ordered) if i == 0 or x - ordered[i - 1] > 1e-3]
