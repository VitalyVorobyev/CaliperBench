"""Textbook bilinear sampling, projection, finite differences and parabola fitting."""

from time import perf_counter
from typing import Literal

import numpy as np

from .schema import Prediction, Request


def _profile(image, strip):
    start, end = np.array(strip.start_xy), np.array(strip.end_xy)
    direction = (end - start) / strip.length
    normal = np.array([-direction[1], direction[0]])
    t = np.linspace(0, strip.length, strip.samples)
    offsets = np.linspace(-(strip.width_px - 1) / 2, (strip.width_px - 1) / 2, strip.across)
    xy = start + t[:, None, None] * direction + offsets[None, :, None] * normal
    x, y = xy[..., 0], xy[..., 1]
    h, w = image.shape
    if x.min() < 0 or y.min() < 0 or x.max() > w - 1 or y.max() > h - 1:
        raise ValueError("strip_out_of_bounds")
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    dx, dy = x - x0, y - y0
    sampled = (
        (1 - dx) * (1 - dy) * image[y0, x0]
        + dx * (1 - dy) * image[y0, x1]
        + (1 - dx) * dy * image[y1, x0]
        + dx * dy * image[y1, x1]
    )
    return sampled.mean(axis=1)


Method = Literal["gradient_parabolic", "gradient_integer", "midpoint_crossing"]
METHODS = ("gradient_parabolic", "gradient_integer", "midpoint_crossing")


def predict(
    image: np.ndarray, request: Request, method: Method = "gradient_parabolic"
) -> Prediction:
    """Accept a finite grayscale float image in [0,1]; positions are scan-distance pixels."""
    started = perf_counter()
    edges, reason = [], None
    try:
        image = np.asarray(image, dtype=float)
        if image.ndim != 2 or min(image.shape) < 2 or not np.isfinite(image).all():
            raise ValueError("invalid_grayscale_image")
        if image.min() < 0 or image.max() > 1:
            raise ValueError("expected_intensity_range_0_1")
        profile = _profile(image, request.strip)
        # Fixed sigma=1 sample, radius=3 Gaussian. No adaptive or learned logic.
        k = np.exp(-0.5 * np.arange(-3, 4, dtype=float) ** 2)
        smooth = np.convolve(np.pad(profile, 3, mode="edge"), k / k.sum(), mode="valid")
        step = request.strip.length / (request.strip.samples - 1)
        if method == "midpoint_crossing":
            if len(request.polarities) != 1:
                raise ValueError("midpoint_crossing_requires_one_edge")
            before, after = float(np.median(smooth[:3])), float(np.median(smooth[-3:]))
            if abs(after - before) < 0.05:
                raise ValueError("insufficient_endpoint_contrast")
            polarity = "rising" if after > before else "falling"
            if request.polarities[0] not in ("either", polarity):
                raise ValueError("wrong_polarity")
            threshold = (before + after) / 2
            crossings = []
            for i in range(len(smooth) - 1):
                a, b = smooth[i], smooth[i + 1]
                if a <= threshold < b if polarity == "rising" else a >= threshold > b:
                    crossings.append((i + (threshold - a) / (b - a)) * step)
            if not crossings:
                raise ValueError("missing_crossing")
            edges = [min(crossings, key=lambda x: abs(x - request.strip.length / 2))]
        elif method in {"gradient_parabolic", "gradient_integer"}:
            gradient = np.gradient(smooth)
            candidates = []
            for sign in (1, -1):
                response = sign * gradient
                for i in range(1, len(response) - 1):
                    if (
                        response[i] > 0.01
                        and response[i] >= response[i - 1]
                        and response[i] > response[i + 1]
                    ):
                        denom = response[i - 1] - 2 * response[i] + response[i + 1]
                        delta = (
                            0
                            if method == "gradient_integer" or denom == 0
                            else 0.5 * (response[i - 1] - response[i + 1]) / denom
                        )
                        x = (i + float(np.clip(delta, -0.5, 0.5))) * step
                        candidates.append(
                            (float(response[i]), x, "rising" if sign == 1 else "falling")
                        )
            # Greedy strongest peak per requested polarity, with increasing scan position.
            for polarity in request.polarities:
                eligible = [
                    c
                    for c in candidates
                    if (polarity == "either" or c[2] == polarity)
                    and (not edges or c[1] > edges[-1])
                ]
                if not eligible:
                    raise ValueError("missing_peak")
                edges.append(max(eligible, key=lambda c: (c[0], -c[1]))[1])
            if not request.polarities and candidates:
                # Preserve an actual false detection for negative-task evaluation.
                edges = [max(candidates)[1]]
        else:
            raise ValueError("unknown_method")
    except ValueError as exc:
        reason, edges = str(exc), []
    return Prediction(
        sample_id=request.sample_id,
        status="failed" if reason else "ok",
        edges_px=edges,
        reason=reason,
        runtime_ms=(perf_counter() - started) * 1000,
    )
