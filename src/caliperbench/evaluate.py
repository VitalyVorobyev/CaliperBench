"""Offline scoring: malformed submissions reject; missing predictions count as failures."""

import numpy as np

from .schema import Prediction, Sample


def _summary(values):
    if not values:
        return {"count": 0, "bias": None, "mae": None, "rmse": None, "p95_abs": None}
    x = np.asarray(values)
    return {
        "count": len(values),
        "bias": float(x.mean()),
        "mae": float(abs(x).mean()),
        "rmse": float(np.sqrt(np.mean(x * x))),
        "p95_abs": float(np.quantile(abs(x), 0.95)),
    }


def evaluate(samples: list[Sample], predictions: list[Prediction], tolerance_px=1.0):
    """Signed error = prediction - reference. Error summaries include valid wrong detections."""
    if not np.isfinite(tolerance_px) or tolerance_px < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    ids = [s.request.sample_id for s in samples]
    pred_ids = [p.sample_id for p in predictions]
    if len(set(ids)) != len(ids) or len(set(pred_ids)) != len(pred_ids):
        raise ValueError("duplicate sample IDs")
    if set(pred_ids) - set(ids):
        raise ValueError("unknown prediction IDs")
    by_id = {p.sample_id: p for p in predictions}
    edge, width, center, phases = [], [], [], [[] for _ in range(10)]
    physical, rows, runtimes = {}, [], []
    edge_total = edge_failed = physical_total = physical_failed = failed = 0
    for s in samples:
        p = by_id.get(s.request.sample_id)
        ok = p is not None and p.status == "ok"
        if p is not None:
            runtimes.append(p.runtime_ms)
        row = {"sample_id": s.request.sample_id, "edge_failed": None, "physical_failed": None}
        if s.edge_truth is not None:
            edge_total += 1
            truth = s.edge_truth.positions_px
            valid = (
                ok
                and len(p.edges_px) == len(truth)
                and all(0 <= x <= s.request.strip.length for x in p.edges_px)
            )
            errors = [a - b for a, b in zip(p.edges_px, truth)] if valid else []
            failure = not valid or any(abs(e) > tolerance_px for e in errors)
            edge_failed += int(failure)
            row.update(edge_failed=failure, edge_errors_px=errors if valid else None)
            if valid:
                edge.extend(errors)
                if len(errors) == 2:
                    width.append(errors[1] - errors[0])
                    center.append((errors[0] + errors[1]) / 2)
                if s.edge_truth.phases is not None:
                    for phase, error in zip(s.edge_truth.phases, errors):
                        phases[min(int(phase * 10), 9)].append(error)
        if s.physical_truth is not None:
            physical_total += 1
            gt = s.physical_truth
            valid = ok and p.physical is not None and p.physical.unit == gt.unit
            row["physical_failed"] = not valid
            physical_failed += int(not valid)
            if valid:
                error = p.physical.value - gt.value
                physical.setdefault(f"{gt.quantity} [{gt.unit}]", []).append(error)
                row["physical_error"] = error
        row["failed"] = row["edge_failed"] is True or row["physical_failed"] is True
        failed += int(row["failed"])
        rows.append(row)
    return {
        "schema_version": 1,
        "samples": len(samples),
        "tolerance_px": tolerance_px,
        "failure_rate": failed / len(samples) if samples else None,
        "edge_failure_rate": edge_failed / edge_total if edge_total else None,
        "physical_missing_rate": physical_failed / physical_total if physical_total else None,
        "edge_error_px": _summary(edge),
        "width_error_px": _summary(width),
        "center_error_px": _summary(center),
        "physical_error": {k: _summary(v) for k, v in physical.items()},
        "phase_bias_px": [{"phase_start": i / 10, **_summary(v)} for i, v in enumerate(phases)],
        "runtime_ms": {
            "count": len(runtimes),
            "median": float(np.median(runtimes)) if runtimes else None,
            "p95": float(np.quantile(runtimes, 0.95)) if runtimes else None,
        },
        "rows": rows,
    }
