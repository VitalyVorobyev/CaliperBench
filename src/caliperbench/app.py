"""Local-only review API. Run with `uv run uvicorn caliperbench.app:app`."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from .refine import snap_to_edge, specimen_silhouette
from .review import Conflict, ReviewDocument, ReviewStore

REPOSITORY = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("CALIPERBENCH_DATA_ROOT", REPOSITORY / "data")).resolve()
store = ReviewStore(REPOSITORY, DATA_ROOT)
app = FastAPI(title="CaliperBench local review", version="0.1.0")


@app.get("/api/images")
def images():
    result = []
    for image_id, row in store.assets.items():
        latest = store.latest(image_id)
        result.append(
            {
                "id": image_id,
                "name": row["image"],
                "task_count": len(store.samples.get(image_id, [])),
                "reviewed": latest is not None,
                "image_url": f"/api/images/{image_id}/source",
            }
        )
    return result


@app.get("/api/images/{image_id}/source")
def source(image_id: str):
    try:
        store.source_verified(image_id)
        return FileResponse(store.image_path(image_id), media_type="image/jpeg")
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None


@app.get("/api/images/{image_id}/mask")
def mask(image_id: str):
    try:
        store.source_verified(image_id)
        return FileResponse(store.mask_path(image_id), media_type="image/png")
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None


@app.get("/api/images/{image_id}/workspace")
def workspace(image_id: str):
    try:
        doc, etag = store.read(image_id)
        with Image.open(store.image_path(image_id)) as image:
            width, height = image.size
        latest = store.latest(image_id)
        frozen = (
            {task.sample_id: task.frozen_request for task in latest[1].tasks if task.frozen_request}
            if latest
            else {}
        )
        return {
            "document": doc,
            "etag": etag,
            "width": width,
            "height": height,
            "requests": {
                s.request.sample_id: (frozen.get(s.request.sample_id) or s.request).model_dump()
                for s in store.samples.get(image_id, [])
            },
            "latest_revision": latest[0] if latest else None,
        }
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None


@app.put("/api/images/{image_id}/draft")
def save_draft(image_id: str, document: ReviewDocument, if_match: str = Header(...)):
    try:
        return {"etag": store.save(image_id, document, if_match)}
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.post("/api/images/{image_id}/approve")
def approve(image_id: str, if_match: str = Header(...)):
    try:
        return store.approve(image_id, if_match)
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.get("/api/images/{image_id}/analysis")
def analysis(image_id: str):
    try:
        return store.predictions(image_id)
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None


@app.get("/api/images/{image_id}/revisions/{revision_id}/mask")
def reviewed_mask(image_id: str, revision_id: int):
    try:
        document = store.revision(image_id, revision_id)
        return Response(store.render_mask(image_id, document), media_type="image/png")
    except KeyError:
        raise HTTPException(404, "unknown approved revision") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class SnapRequest(BaseModel):
    contour: list[tuple[float, float]]
    radius_px: float = Field(default=5, ge=1, le=20)
    closed: bool = True


def _gray_source(image_id: str) -> np.ndarray:
    store.source_verified(image_id)
    with Image.open(store.image_path(image_id)) as image:
        return np.asarray(image.convert("L"), dtype=float) / 255


@app.get("/api/images/{image_id}/specimen-proposal")
def specimen_proposal(image_id: str):
    try:
        return specimen_silhouette(_gray_source(image_id))
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.post("/api/images/{image_id}/snap")
def snap(image_id: str, request: SnapRequest):
    try:
        return snap_to_edge(
            _gray_source(image_id), request.contour, request.radius_px, closed=request.closed
        )
    except KeyError:
        raise HTTPException(404, "unknown pilot image") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.get("/api/report")
def report():
    # The weld collection is an annotation experiment, not a scored benchmark.
    samples = []
    by_image = {}
    for sample in samples:
        image_id = Path(sample.request.image).stem
        by_image.setdefault(image_id, []).append(sample)
    methods = {}
    uncertainties = [sample.edge_truth.uncertainty_px for sample in samples]
    for method in ("gradient_integer", "gradient_parabolic", "midpoint_crossing"):
        errors = []
        detection_failures = 0
        runtimes = []
        for image_id, group in by_image.items():
            predictions = store.predictions(image_id)["predictions"]
            for sample in group:
                prediction = predictions[sample.request.sample_id][method]
                runtimes.append(prediction["runtime_ms"])
                if prediction["status"] != "ok" or len(prediction["edges_px"]) != 1:
                    detection_failures += 1
                else:
                    errors.append(prediction["edges_px"][0] - sample.edge_truth.positions_px[0])
        over_tolerance = detection_failures + sum(abs(error) > 1 for error in errors)
        methods[method] = {
            "n": len(errors),
            "detection_failures": detection_failures,
            "error_over_1px": over_tolerance,
            "failure_rate": over_tolerance / len(samples) if samples else None,
            "mae_px": sum(abs(x) for x in errors) / len(errors) if errors else None,
            "bias_px": sum(errors) / len(errors) if errors else None,
            "median_runtime_ms": sorted(runtimes)[len(runtimes) // 2] if runtimes else None,
        }
    proxy = json.loads((REPOSITORY / "registry/weld-mask-proxy-summary.json").read_text())
    return {
        "reference": "none-weld-exploratory",
        "images": len(by_image),
        "approved_tasks": len(samples),
        "reviewer_uncertainty_px": {
            "mean": sum(uncertainties) / len(uncertainties) if uncertainties else None,
            "min": min(uncertainties) if uncertainties else None,
            "max": max(uncertainties) if uncertainties else None,
        },
        "methods": methods,
        "mask_proxy_context": proxy,
    }


@app.post("/api/export")
def export():
    raise HTTPException(409, "weld masks are proposals; benchmark export is disabled")


frontend = REPOSITORY / "frontend/dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
