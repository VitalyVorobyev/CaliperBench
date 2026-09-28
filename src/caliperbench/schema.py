"""Versioned, strict contracts. All image coordinates use integer pixel centers."""

from math import hypot
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Strip(Contract):
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    width_px: float = Field(default=1, ge=1)
    samples: int = Field(default=101, ge=5, le=100000)
    across: int = Field(default=1, ge=1, le=1000)

    @property
    def length(self) -> float:
        return hypot(self.end_xy[0] - self.start_xy[0], self.end_xy[1] - self.start_xy[1])

    @model_validator(mode="after")
    def geometry(self):
        if self.length == 0:
            raise ValueError("strip endpoints must differ")
        if self.width_px > 1 and self.across < 2:
            raise ValueError("a wide strip requires at least two transverse samples")
        if self.samples * self.across > 2_000_000:
            raise ValueError("strip exceeds reference sampling budget")
        return self


class Request(Contract):
    schema_version: Literal[1] = 1
    sample_id: str = Field(min_length=1)
    image: str
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    strip: Strip
    # Sequence is ordered along the scan; [] means a negative/no-edge task.
    polarities: list[Literal["rising", "falling", "either"]] = Field(max_length=2)

    @model_validator(mode="after")
    def relative_image(self):
        path = PurePosixPath(self.image)
        if not self.image or path.is_absolute() or ".." in path.parts or "\\" in self.image:
            raise ValueError("image must be a relative POSIX path under the data root")
        return self


class EdgeTruth(Contract):
    positions_px: list[float] = Field(max_length=2)
    uncertainty_px: float = Field(ge=0)
    method: str = Field(min_length=1)
    confidence: Literal["high", "medium", "low"]
    # Explicit experimental phase, not inferred from arbitrary scan coordinates.
    phases: list[float] | None = None


class PhysicalTruth(Contract):
    value: float = Field(gt=0)
    unit: Literal["mm", "um", "m"]
    uncertainty: float = Field(ge=0)
    quantity: str = Field(min_length=1)
    method: str = Field(min_length=1)
    calibration_ref: str = Field(min_length=1)


class Provenance(Contract):
    dataset_id: str
    source_url: str
    source_version: str
    license: str
    source_image_id: str
    annotator: str
    annotation_version: str
    derivation: str
    group_id: str  # Original scene/object; all derived crops stay in the same split.


class Sample(Contract):
    request: Request
    split: Literal["development", "validation", "test"]
    provenance: Provenance
    edge_truth: EdgeTruth | None = None
    physical_truth: PhysicalTruth | None = None

    @model_validator(mode="after")
    def truth(self):
        if self.edge_truth is None and self.physical_truth is None:
            raise ValueError("at least one ground-truth track is required")
        if self.edge_truth is not None:
            x = self.edge_truth.positions_px
            if len(x) != len(self.request.polarities):
                raise ValueError("truth count must match task")
            if x != sorted(set(x)) or any(v < 0 or v > self.request.strip.length for v in x):
                raise ValueError("truth positions must be ordered, unique and inside strip")
            phases = self.edge_truth.phases
            if phases is not None and (
                len(phases) != len(x) or any(p < 0 or p >= 1 for p in phases)
            ):
                raise ValueError("phases must match edges and lie in [0, 1)")
        return self


class Candidate(Contract):
    """An unreviewed local proposal; deliberately has no truth track."""

    request: Request
    split: Literal["development", "validation", "test"]
    provenance: Provenance
    proposal_crossing_px: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def crossing_within_strip(self):
        if (
            self.proposal_crossing_px is not None
            and self.proposal_crossing_px > self.request.strip.length
        ):
            raise ValueError("proposal crossing is outside strip")
        return self


class PhysicalPrediction(Contract):
    value: float = Field(gt=0)
    unit: Literal["mm", "um", "m"]


class Prediction(Contract):
    schema_version: Literal[1] = 1
    sample_id: str = Field(min_length=1)
    status: Literal["ok", "failed"]
    edges_px: list[float] = Field(default_factory=list, max_length=2)
    physical: PhysicalPrediction | None = None
    runtime_ms: float = Field(ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def result(self):
        if self.edges_px != sorted(set(self.edges_px)):
            raise ValueError("predicted edges must be unique and scan-ordered")
        if self.status == "failed" and (self.edges_px or self.physical is not None):
            raise ValueError("failed predictions cannot contain measurements")
        return self
