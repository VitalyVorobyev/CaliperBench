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
from pydantic import BaseModel, ConfigDict, Field, model_validator
from skimage.draw import polygon2mask

from .baseline import METHODS, _profile, predict
from .data import sha256
from .probes import normal_scan_at_crossing
from .refine import PARAMETERS, propose, strip_crossings
from .schema import Candidate, EdgeTruth, Provenance, Request, Sample


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TaskReview(Strict):
    sample_id: str
    disposition: Literal["pending", "approved", "excluded"] = "pending"
    crossing_px: float | None = None
    uncertainty_px: float | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    note: str = ""
    frozen_request: Request | None = None


class ContourEdit(Strict):
    method: Literal["specimen_silhouette", "manual_trace", "edge_snap"]
    parameters: dict = Field(default_factory=dict)


class ReviewDocument(Strict):
    schema_version: Literal[1, 2] = 2
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
    contour_closed: bool = True
    contour_clip_sides: list[Literal["top", "right", "bottom", "left"]] = Field(
        default_factory=list
    )
    contour_target: Literal["weld_region", "visible_specimen"] = "weld_region"
    contour_edits: list[ContourEdit] = Field(default_factory=list)
    contour_reviewed: bool = False
    contour_uncertainty_px: float = 1.0
    tasks: list[TaskReview]
    reviewer: str = ""

    @model_validator(mode="after")
    def valid_geometry(self):
        minimum = 3 if self.contour_closed else 2
        if len(self.contour) < minimum or len(self.contour) > 10000:
            raise ValueError(f"contour must have {minimum}–10000 points")
        if not self.contour_closed and self.contour_target != "visible_specimen":
            raise ValueError("an open edge must target the visible specimen")
        if len({task.sample_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate task IDs")
        if not np.isfinite(self.contour_uncertainty_px) or self.contour_uncertainty_px <= 0:
            raise ValueError("contour uncertainty must be positive")
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
        candidate_name = (
            "annotations_weld_contour_candidates_v2.jsonl"
            if (data_root / "annotations_weld_contour_candidates_v2.jsonl").exists()
            else "annotations_weld_contour_candidates.jsonl"
        )
        for name in ("annotations_weld_proxy.jsonl", candidate_name):
            path = data_root / name
            if not path.exists() and name.endswith("contour_candidates.jsonl"):
                continue
            for line in path.read_text().splitlines():
                sample = (
                    Sample.model_validate_json(line)
                    if name == "annotations_weld_proxy.jsonl"
                    or name.endswith("contour_candidates.jsonl")
                    else Candidate.model_validate_json(line)
                )
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

    @staticmethod
    def _task_from_sample(sample: Sample | Candidate, contour) -> TaskReview:
        request = sample.request
        hits = strip_crossings(contour, request.strip.start_xy, request.strip.end_xy)
        return TaskReview(
            sample_id=request.sample_id,
            crossing_px=hits[0] if len(hits) == 1 else None,
            note="multiple_or_missing_proposal_crossings" if len(hits) != 1 else "",
        )

    def _initial(self, image_id: str) -> ReviewDocument:
        self.source_verified(image_id)
        with (
            Image.open(self.image_path(image_id)) as source_image,
            Image.open(self.mask_path(image_id)) as source_mask,
        ):
            image = np.asarray(source_image.convert("L"), dtype=float) / 255
            mask = np.asarray(source_mask.convert("L")) > 0
        result = propose(image, mask)
        task_reviews = [
            self._task_from_sample(sample, result.refined_contour)
            for sample in self.samples.get(image_id, [])
        ]
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
            if document.schema_version == 1:
                # The v1 checkbox referred to contour plus per-crossing review.
                # Require a fresh explicit contour-only decision without losing edits.
                document.schema_version = 2
                document.contour_reviewed = False
                next_etag = digest(document)
                with self.connect() as db:
                    updated = db.execute(
                        "UPDATE drafts SET body=?, etag=? WHERE image_id=? AND etag=?",
                        (document.model_dump_json(), next_etag, image_id, row[1]),
                    )
                if updated.rowcount != 1:
                    raise Conflict("draft changed in another session")
                row = (document.model_dump_json(), next_etag)
            existing = {task.sample_id for task in document.tasks}
            current = {sample.request.sample_id for sample in self.samples.get(image_id, [])}
            if existing - current:
                raise ValueError(
                    "candidate registry removed draft tasks; restore the original local candidate file"
                )
            additions = [
                self._task_from_sample(sample, document.contour)
                for sample in self.samples.get(image_id, [])
                if sample.request.sample_id not in existing
            ]
            if additions:
                document.tasks.extend(additions)
                next_etag = digest(document)
                with self.connect() as db:
                    updated = db.execute(
                        "UPDATE drafts SET body=?, etag=? WHERE image_id=? AND etag=?",
                        (document.model_dump_json(), next_etag, image_id, row[1]),
                    )
                if updated.rowcount != 1:
                    raise Conflict("draft changed in another session")
                return document, next_etag
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
                "schema_version",
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

    def _validate_identity(self, image_id: str, document: ReviewDocument, *, current_tasks=True):
        row = self.row(image_id)
        if (
            document.image_id != image_id
            or document.source_image_sha256 != row["image_sha256"]
            or document.source_mask_sha256 != row["mask_sha256"]
        ):
            raise ValueError("document source identity changed")
        expected = {s.request.sample_id for s in self.samples.get(image_id, [])}
        actual = {t.sample_id for t in document.tasks}
        invalid_tasks = actual != expected if current_tasks else not actual.issubset(expected)
        if invalid_tasks:
            raise ValueError("document task identity changed")
        with Image.open(self.image_path(image_id)) as image:
            width, height = image.size
        if not document.contour_closed:
            ends = (document.contour[0], document.contour[-1])
            actual_sides = [
                side
                for side, predicate in (
                    ("top", lambda x, y: y <= 0.5),
                    ("right", lambda x, y: x >= width - 1.5),
                    ("bottom", lambda x, y: y >= height - 1.5),
                    ("left", lambda x, y: x <= 0.5),
                )
                if any(predicate(x, y) for x, y in ends)
            ]
            if document.contour_clip_sides != actual_sides:
                raise ValueError("open edge frame-contact metadata disagrees with endpoints")
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
            with Image.open(self.image_path(image_id)) as source_image:
                width, height = source_image.size
            for task in doc.tasks:
                if doc.contour_target == "visible_specimen":
                    task.disposition = "excluded"
                    task.note = "weld_scan_not_applicable_to_specimen_outline"
                    task.crossing_px = None
                    task.uncertainty_px = None
                    task.frozen_request = None
                    continue
                if ":contour:" not in task.sample_id:
                    task.disposition = "excluded"
                    task.note = "legacy_mask_proxy_only"
                    task.frozen_request = None
                    continue
                strip = by_id[task.sample_id].request.strip
                hits = strip_crossings(doc.contour, strip.start_xy, strip.end_xy)
                aligned = (
                    normal_scan_at_crossing(doc.contour, strip, hits[0], width, height)
                    if len(hits) == 1
                    else None
                )
                task.crossing_px = aligned[1] if aligned else None
                task.frozen_request = (
                    by_id[task.sample_id].request.model_copy(update={"strip": aligned[0]})
                    if aligned
                    else None
                )
                task.disposition = "approved" if aligned else "excluded"
                task.uncertainty_px = doc.contour_uncertainty_px if aligned else None
                task.confidence = "medium" if aligned else "low"
                task.note = (
                    "normal_to_reviewed_contour" if aligned else "ambiguous_or_out_of_bounds"
                )
            body = doc.model_dump_json()
            sha = hashlib.sha256(body.encode()).hexdigest()
            mask_sha = (
                hashlib.sha256(self.render_mask(image_id, doc)).hexdigest()
                if doc.contour_closed
                else None
            )
            approved_at = datetime.now(UTC).isoformat()
            cursor = db.execute(
                "INSERT INTO revisions (image_id,body,sha256,approved_at) VALUES (?,?,?,?)",
                (image_id, body, sha, approved_at),
            )
            db.execute(
                "UPDATE drafts SET body=?, etag=? WHERE image_id=? AND etag=?",
                (body, digest(doc), image_id, expected),
            )
        return {
            "revision_id": cursor.lastrowid,
            "sha256": sha,
            "mask_sha256": mask_sha,
            "approved_at": approved_at,
            "derived_crossings": sum(task.disposition == "approved" for task in doc.tasks),
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
        if not document.contour_closed:
            raise ValueError("open visible edges have no complete region mask")
        self._validate_identity(image_id, document, current_tasks=False)
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
        raise ValueError(
            "weld-region masks are not caliper ground truth; benchmark export is disabled"
        )

    def _exploratory_samples(self) -> list[Sample]:
        """Internal geometry diagnostic; never a benchmark export path."""
        exported = []
        for image_id in self.assets:
            latest = self.latest(image_id)
            if latest is None:
                continue
            self.source_verified(image_id)
            revision_id, doc = latest
            available = {
                sample.request.sample_id: sample for sample in self.samples.get(image_id, [])
            }
            for task in doc.tasks:
                if task.disposition != "approved":
                    continue
                proxy = available[task.sample_id]
                exported.append(
                    Sample(
                        request=task.frozen_request or proxy.request,
                        split="development",
                        provenance=Provenance(
                            dataset_id=proxy.provenance.dataset_id,
                            source_url=proxy.provenance.source_url,
                            source_version=proxy.provenance.source_version,
                            license=proxy.provenance.license,
                            source_image_id=proxy.provenance.source_image_id,
                            annotator=doc.reviewer,
                            annotation_version=f"review-revision-{revision_id}",
                            derivation=f"exploratory weld contour proxy, not benchmark eligible; frozen normal scan and crossing derived geometrically; revision={revision_id}; sha256={digest(doc)}",
                            group_id=proxy.provenance.group_id,
                        ),
                        edge_truth=EdgeTruth(
                            positions_px=[task.crossing_px],
                            uncertainty_px=task.uncertainty_px,
                            method="exploratory-contour-proxy-not-ground-truth",
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
        latest = self.latest(image_id)
        frozen = (
            {task.sample_id: task.frozen_request for task in latest[1].tasks if task.frozen_request}
            if latest
            else {}
        )
        for sample in self.samples.get(image_id, []):
            request = frozen.get(sample.request.sample_id) or sample.request
            profiles[request.sample_id] = _profile(image, request.strip).tolist()
            results[request.sample_id] = {
                method: predict(image, request, method).model_dump() for method in METHODS
            }
        return {"predictions": results, "profiles": profiles}
