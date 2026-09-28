"""Public, classical mask-contour proposal. This never creates ground truth."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import map_coordinates, median_filter
from skimage.filters import gaussian, threshold_otsu
from skimage.measure import find_contours, label
from skimage.morphology import closing, disk
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
    closed: bool = True
    clip_sides: tuple[str, ...] = ()


def specimen_silhouette(image: np.ndarray) -> Proposal:
    """Propose the largest bright specimen against a dark backdrop.

    This is a segmentation *proposal*, never an optical-edge or dimension label.
    Border contact and weak foreground separation are explicitly flagged.
    """
    gray = np.asarray(image, dtype=float)
    if gray.ndim != 2 or min(gray.shape) < 8 or not np.isfinite(gray).all():
        raise ValueError("image must be a finite two-dimensional array")
    smooth = gaussian(gray, 1.5, preserve_range=True)
    threshold = float(threshold_otsu(smooth))
    binary = closing(smooth > threshold, disk(3))
    components = label(binary)
    counts = np.bincount(components.ravel())
    if len(counts) < 2:
        raise ValueError("no bright specimen could be separated from the background")
    counts[0] = 0
    mask = components == int(np.argmax(counts))
    if mask.sum() < gray.size * 0.03:
        raise ValueError("foreground proposal is too small")
    contours = find_contours(mask.astype(float), 0.5)
    if not contours:
        raise ValueError("foreground has no usable contour")
    ranked = sorted(contours, key=len, reverse=True)
    if len(ranked) > 1 and len(ranked[1]) >= 0.25 * len(ranked[0]):
        raise ValueError("multiple substantial visible edge chains; trace an edge manually")
    contour = ranked[0]
    closed = bool(np.allclose(contour[0], contour[-1]))
    stride = max(1, int(np.ceil(len(contour) / PARAMETERS["max_vertices"])))
    sampled = contour[::stride]
    if not closed and not np.array_equal(sampled[-1], contour[-1]):
        sampled = np.vstack((sampled, contour[-1]))
    source = [[round(float(x), 4), round(float(y), 4)] for y, x in sampled]
    flags = ["automatic_specimen_silhouette_requires_review"]
    clip_sides = tuple(
        side
        for side, contact in (
            ("top", np.any(mask[0])),
            ("right", np.any(mask[:, -1])),
            ("bottom", np.any(mask[-1])),
            ("left", np.any(mask[:, 0])),
        )
        if contact
    )
    if clip_sides:
        flags.append("specimen_touches_frame")
    if not closed:
        flags.append("visible_edge_open_at_frame")
    return Proposal(
        source,
        source,
        flags,
        {
            "method": "otsu-largest-bright-component-v1",
            "gaussian_sigma": 1.5,
            "closing_radius_px": 3,
            "threshold": threshold,
        },
        closed,
        clip_sides,
    )


def snap_to_edge(
    image: np.ndarray,
    contour: list[list[float]],
    radius_px: float = 5.0,
    *,
    closed: bool = True,
) -> Proposal:
    """Locally attach a coarse open edge or closed contour to nearby gradients.

    Search is only along each vertex normal; a displacement penalty prevents
    distant texture from winning. No global snake regularizer rounds corners.
    """
    gray = np.asarray(image, dtype=float)
    points = np.asarray(contour, dtype=float)
    if gray.ndim != 2 or not np.isfinite(gray).all():
        raise ValueError("image must be finite grayscale")
    minimum = 3 if closed else 2
    if points.ndim != 2 or points.shape[1] != 2 or not minimum <= len(points) <= 10000:
        raise ValueError(f"contour needs {minimum}–10000 xy points")
    if not np.isfinite(points).all() or not 1 <= radius_px <= 20:
        raise ValueError("contour and radius must be finite; radius must be 1–20 px")
    height, width = gray.shape
    if (
        np.any(points[:, 0] < 0)
        or np.any(points[:, 0] > width - 1)
        or np.any(points[:, 1] < 0)
        or np.any(points[:, 1] > height - 1)
    ):
        raise ValueError("contour must lie inside the image")
    source = [[round(float(x), 4), round(float(y), 4)] for x, y in points]
    # A reviewer may place just a few anchors; distribute samples along each
    # segment so the snap works between anchors as well as at them.
    if len(points) < 300:
        pieces = []
        ends = np.roll(points, -1, axis=0) if closed else points[1:]
        for start, end in zip(points if closed else points[:-1], ends, strict=True):
            count = max(1, int(np.ceil(np.linalg.norm(end - start) / 3)))
            pieces.extend(start + (end - start) * (j / count) for j in range(count))
        if not closed:
            pieces.append(points[-1])
        if len(pieces) <= 10000:
            points = np.asarray(pieces)
    smooth = gaussian(gray, 1.0, preserve_range=True)
    gy, gx = np.gradient(smooth)
    tangent = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
    if not closed:
        tangent[0] = points[1] - points[0]
        tangent[-1] = points[-1] - points[-2]
    norm = np.linalg.norm(tangent, axis=1)
    valid = norm > 1e-6
    normal = np.zeros_like(tangent)
    normal[valid, 0] = -tangent[valid, 1] / norm[valid]
    normal[valid, 1] = tangent[valid, 0] / norm[valid]
    offsets = np.arange(-radius_px, radius_px + 0.01, 0.25)
    candidates = points[:, None, :] + normal[:, None, :] * offsets[None, :, None]
    x, y = candidates[..., 0], candidates[..., 1]
    in_bounds = (x >= 0) & (x <= width - 1) & (y >= 0) & (y <= height - 1)
    coordinates = np.stack((y.ravel(), x.ravel()))
    sampled_gx = map_coordinates(gx, coordinates, order=1, mode="nearest").reshape(x.shape)
    sampled_gy = map_coordinates(gy, coordinates, order=1, mode="nearest").reshape(x.shape)
    strength = np.abs(sampled_gx * normal[:, 0, None] + sampled_gy * normal[:, 1, None])
    # The local image gradient must dominate a modest distance preference.
    local_peak = np.max(np.where(in_bounds, strength, 0), axis=1)
    score = strength - 0.12 * local_peak[:, None] * np.abs(offsets)[None, :] / radius_px
    score[~in_bounds] = -np.inf
    choice = np.argmax(score, axis=1)
    displacement = offsets[choice]
    displacement[~valid | (local_peak < 0.015)] = 0
    displacement = median_filter(displacement, size=3, mode="wrap" if closed else "nearest")
    if not closed:
        displacement[[0, -1]] = 0
    result = points + normal * displacement[:, None]
    flags = []
    if np.count_nonzero(np.abs(displacement) >= radius_px - 0.25):
        flags.append("some_vertices_reached_search_limit")
    if np.count_nonzero(local_peak < 0.015):
        flags.append("weak_gradient_at_some_vertices")
    return Proposal(
        source,
        [[round(float(x), 4), round(float(y), 4)] for x, y in result],
        flags,
        {"method": "normal-gradient-snap-v1", "gaussian_sigma": 1.0, "radius_px": radius_px},
        closed,
    )


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
