"""Local review documents and immutable approved benchmark references."""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, model_validator
from skimage.draw import polygon2mask

from .baseline import METHODS, _profile, predict
from .data import sha256
from .refine import PARAMETERS, propose, strip_crossings
from .schema import EdgeTruth, Provenance, Sample


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TaskReview(Strict):
    sample_id: str
    disposition: Literal["pending", "approved", "excluded"] = "pending"
    crossing_px: float | None = None
    uncertainty_px: float | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    note: str = ""


class ReviewDocument(Strict):
    schema_version: Literal[1] = 1
    image_id: str
    source_image_sha256: str
    source_mask_sha256: str
    coordinate_system: Literal["pixel-center"] = "pixel-center"
    proposal_method: str
    proposal_parameters: dict
    proposal_flags: list[str]
    source_contour: list[tuple[float, float]]
    proposed_contour: list[tuple[float, float]]
    contour: list[tuple[float, float]]
    contour_reviewed: bool = False
    tasks: list[TaskReview]
    reviewer: str = ""

    @model_validator(mode="after")
    def valid_geometry(self):
        if len(self.contour) < 3 or len(self.contour) > 10000:
            raise ValueError("contour must have 3–10000 points")
        if len({task.sample_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate task IDs")
        return self


def digest(document: ReviewDocument) -> str:
    return hashlib.sha256(document.model_dump_json().encode()).hexdigest()


class Conflict(Exception):
    pass


class ReviewStore:
    def __init__(self, repository: Path, data_root: Path):
        self.repository = repository
        self.data_root = data_root
        self.database = data_root / "review" / "reviews.sqlite3"
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.pilot = json.loads((repository / "registry/weld-pilot-v1.json").read_text())
        self.assets = {row["image"].removesuffix(".jpg"): row for row in self.pilot["images"]}
        self.samples = {}
        for line in (data_root / "annotations_weld_proxy.jsonl").read_text().splitlines():
            sample = Sample.model_validate_json(line)
            image_id = Path(sample.request.image).stem
            self.samples.setdefault(image_id, []).append(sample)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS drafts (image_id TEXT PRIMARY KEY, body TEXT NOT NULL, etag TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY, image_id TEXT NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL, approved_at TEXT NOT NULL)"
            )

    def connect(self):
        return sqlite3.connect(self.database)

    def row(self, image_id: str) -> dict:
        if image_id not in self.assets:
            raise KeyError(image_id)
        return self.assets[image_id]

    def image_path(self, image_id: str) -> Path:
        return self.data_root / "raw/weld-profiles-2026" / self.row(image_id)["image"]

    def mask_path(self, image_id: str) -> Path:
        return self.data_root / "raw/weld-profiles-2026" / self.row(image_id)["mask"]

    def source_verified(self, image_id: str):
        row = self.row(image_id)
        if (
            sha256(self.image_path(image_id)) != row["image_sha256"]
            or sha256(self.mask_path(image_id)) != row["mask_sha256"]
        ):
            raise ValueError("source checksum mismatch")

    def _initial(self, image_id: str) -> ReviewDocument:
        self.source_verified(image_id)
        with (
            Image.open(self.image_path(image_id)) as source_image,
            Image.open(self.mask_path(image_id)) as source_mask,
        ):
            image = np.asarray(source_image.convert("L"), dtype=float) / 255
            mask = np.asarray(source_mask.convert("L")) > 0
        result = propose(image, mask)
        task_reviews = []
        for sample in self.samples.get(image_id, []):
            request = sample.request
            hits = strip_crossings(
                result.refined_contour, request.strip.start_xy, request.strip.end_xy
            )
            task_reviews.append(
                TaskReview(
                    sample_id=request.sample_id,
                    crossing_px=hits[0] if len(hits) == 1 else None,
                    note="multiple_or_missing_proposal_crossings" if len(hits) != 1 else "",
                )
            )
        row = self.row(image_id)
        return ReviewDocument(
            image_id=image_id,
            source_image_sha256=row["image_sha256"],
            source_mask_sha256=row["mask_sha256"],
            proposal_method=result.parameters["method"],
            proposal_parameters=result.parameters,
            proposal_flags=result.flags,
            source_contour=result.source_contour,
            proposed_contour=result.refined_contour,
            contour=result.refined_contour,
            tasks=task_reviews,
        )

    def read(self, image_id: str) -> tuple[ReviewDocument, str]:
        self.row(image_id)
        with self.connect() as db:
            row = db.execute(
                "SELECT body, etag FROM drafts WHERE image_id=?", (image_id,)
            ).fetchone()
        if row:
            document = ReviewDocument.model_validate_json(row[0])
            # Refresh only an untouched proposal from an older algorithm version.
            # Human edits and approved revisions are never replaced.
            if (
                document.proposal_method != PARAMETERS["method"]
                and document.contour == document.proposed_contour
                and not document.contour_reviewed
                and not document.reviewer
                and all(task.disposition == "pending" for task in document.tasks)
            ):
                replacement = self._initial(image_id)
                replacement_etag = digest(replacement)
                with self.connect() as db:
                    updated = db.execute(
                        "UPDATE drafts SET body=?, etag=? WHERE image_id=? AND etag=?",
                        (replacement.model_dump_json(), replacement_etag, image_id, row[1]),
                    )
                if updated.rowcount:
                    return replacement, replacement_etag
            return document, row[1]
        document = self._initial(image_id)
        etag = digest(document)
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO drafts VALUES (?,?,?)",
                (image_id, document.model_dump_json(), etag),
            )
        return document, etag

    def save(self, image_id: str, document: ReviewDocument, expected: str) -> str:
        self._validate_identity(image_id, document)
        new_etag = digest(document)
        with self.connect() as db:
            current = db.execute(
                "SELECT body FROM drafts WHERE image_id=? AND etag=?", (image_id, expected)
            ).fetchone()
            if current is None:
                raise Conflict("draft changed in another session")
            previous = ReviewDocument.model_validate_json(current[0])
            immutable = (
                "source_image_sha256",
                "source_mask_sha256",
                "coordinate_system",
                "proposal_method",
                "proposal_parameters",
                "proposal_flags",
                "source_contour",
                "proposed_contour",
            )
            if any(getattr(document, name) != getattr(previous, name) for name in immutable):
                raise ValueError("source and proposal evidence cannot be edited")
            updated = db.execute(
                "UPDATE drafts SET body=?, etag=? WHERE image_id=? AND etag=?",
                (document.model_dump_json(), new_etag, image_id, expected),
            )
            if updated.rowcount != 1:
                raise Conflict("draft changed in another session")
        return new_etag

    def _validate_identity(self, image_id: str, document: ReviewDocument):
        row = self.row(image_id)
        if (
            document.image_id != image_id
            or document.source_image_sha256 != row["image_sha256"]
            or document.source_mask_sha256 != row["mask_sha256"]
        ):
            raise ValueError("document source identity changed")
        expected = {s.request.sample_id for s in self.samples.get(image_id, [])}
        if {t.sample_id for t in document.tasks} != expected:
            raise ValueError("document task identity changed")
        with Image.open(self.image_path(image_id)) as image:
            width, height = image.size
        if any(
            not (-0.5 <= x <= width - 0.5 and -0.5 <= y <= height - 0.5)
            for x, y in document.contour
        ):
            raise ValueError("contour point outside image")

    def approve(self, image_id: str, expected: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT body, etag FROM drafts WHERE image_id=?", (image_id,)
            ).fetchone()
            if row is None or row[1] != expected:
                raise Conflict("draft changed in another session")
            doc = ReviewDocument.model_validate_json(row[0])
            self._validate_identity(image_id, doc)
            if not doc.contour_reviewed or not doc.reviewer.strip():
                raise ValueError("reviewer and contour approval are required")
            by_id = {sample.request.sample_id: sample for sample in self.samples.get(image_id, [])}
            for task in doc.tasks:
                if task.disposition == "pending":
                    raise ValueError(f"task {task.sample_id} is still pending")
                if task.disposition == "approved":
                    if (
                        task.crossing_px is None
                        or task.uncertainty_px is None
                        or task.uncertainty_px <= 0
                    ):
                        raise ValueError(
                            f"task {task.sample_id} needs crossing and positive uncertainty"
                        )
                    strip = by_id[task.sample_id].request.strip
                    if not 0 <= task.crossing_px <= strip.length:
                        raise ValueError("approved crossing is outside strip")
                    hits = strip_crossings(doc.contour, strip.start_xy, strip.end_xy)
                    if len(hits) != 1 or abs(hits[0] - task.crossing_px) > max(
                        2, task.uncertainty_px
                    ):
                        raise ValueError(f"task {task.sample_id} disagrees with reviewed contour")
            body = doc.model_dump_json()
            sha = hashlib.sha256(body.encode()).hexdigest()
            mask_sha = hashlib.sha256(self.render_mask(image_id, doc)).hexdigest()
            approved_at = datetime.now(UTC).isoformat()
            cursor = db.execute(
                "INSERT INTO revisions (image_id,body,sha256,approved_at) VALUES (?,?,?,?)",
                (image_id, body, sha, approved_at),
            )
        return {
            "revision_id": cursor.lastrowid,
            "sha256": sha,
            "mask_sha256": mask_sha,
            "approved_at": approved_at,
        }

    def revision(self, image_id: str, revision_id: int) -> ReviewDocument:
        self.row(image_id)
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM revisions WHERE image_id=? AND id=?", (image_id, revision_id)
            ).fetchone()
        if row is None:
            raise KeyError(revision_id)
        return ReviewDocument.model_validate_json(row[0])

    def render_mask(self, image_id: str, document: ReviewDocument) -> bytes:
        """Deterministically rasterize a contour revision at source-image pixel centers."""
        self._validate_identity(image_id, document)
        with Image.open(self.image_path(image_id)) as image:
            width, height = image.size
        vertices_yx = np.asarray([(y, x) for x, y in document.contour], dtype=float)
        mask = polygon2mask((height, width), vertices_yx)
        buffer = io.BytesIO()
        Image.fromarray(mask.astype(np.uint8) * 255).save(buffer, format="PNG", optimize=False)
        return buffer.getvalue()

    def latest(self, image_id: str) -> tuple[int, ReviewDocument] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT id,body FROM revisions WHERE image_id=? ORDER BY id DESC LIMIT 1",
                (image_id,),
            ).fetchone()
        return (row[0], ReviewDocument.model_validate_json(row[1])) if row else None

    def export_samples(self) -> list[Sample]:
        exported = []
        for image_id in self.assets:
            latest = self.latest(image_id)
            if latest is None:
                continue
            self.source_verified(image_id)
            revision_id, doc = latest
            reviews = {task.sample_id: task for task in doc.tasks}
            for proxy in self.samples.get(image_id, []):
                task = reviews[proxy.request.sample_id]
                if task.disposition != "approved":
                    continue
                exported.append(
                    Sample(
                        request=proxy.request,
                        split="development",
                        provenance=Provenance(
                            dataset_id=proxy.provenance.dataset_id,
                            source_url=proxy.provenance.source_url,
                            source_version=proxy.provenance.source_version,
                            license=proxy.provenance.license,
                            source_image_id=proxy.provenance.source_image_id,
                            annotator=doc.reviewer,
                            annotation_version=f"review-revision-{revision_id}",
                            derivation=f"human-reviewed contour and crossing; revision={revision_id}; sha256={digest(doc)}",
                            group_id=proxy.provenance.group_id,
                        ),
                        edge_truth=EdgeTruth(
                            positions_px=[task.crossing_px],
                            uncertainty_px=task.uncertainty_px,
                            method="single-reviewer-visible-edge",
                            confidence=task.confidence,
                        ),
                    )
                )
        return exported

    def predictions(self, image_id: str) -> dict:
        self.source_verified(image_id)
        with Image.open(self.image_path(image_id)) as source_image:
            image = np.asarray(source_image.convert("L"), dtype=float) / 255
        results = {}
        profiles = {}
        for sample in self.samples.get(image_id, []):
            request = sample.request
            profiles[request.sample_id] = _profile(image, request.strip).tolist()
            results[request.sample_id] = {
                method: predict(image, request, method).model_dump() for method in METHODS
            }
        return {"predictions": results, "profiles": profiles}
