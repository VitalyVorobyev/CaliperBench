# Protocol v1

JSONL contains one UTF-8 JSON object per line. Models in `schema.py` are authoritative;
`schemas/*.schema.json` describe structure. Reject unknown fields, duplicate IDs,
nonfinite values, invalid geometry and unsupported versions. Validate through the
Python models to enforce relationships that JSON Schema cannot express.

## Coordinates and tasks

Images use x right, y down, with `(0,0)` at the top-left pixel **center**. A strip has
`start_xy`, `end_xy`, `samples`, `width_px`, `across`. Its unit direction is u and
its normal is `(-u_y,u_x)`. Returned edge positions are distances in image pixels
from start along u, not sample indices, column numbers or world coordinates.
Transverse sample centers span `[-(width_px-1)/2, +(width_px-1)/2]`. Width 1 is one
centerline; wider strips require at least two samples across. Samples include both
scan endpoints. Strip points must stay within the image for the reference baseline.

`polarities` is an ordered list of zero, one or two `rising`, `falling` or `either`
transitions. Rising means increasing intensity along the scan direction. Empty is an
explicit negative task. A two-edge task defines width `x2-x1` and center `(x1+x2)/2`
in scan coordinates; center is not necessarily an object's physical center.

An annotation `Sample` wraps a public `request`, split, provenance and at least one
of these independent tracks:

- `edge_truth`: ordered positions, uncertainty in pixels, method, confidence, optional
  per-edge experimental phases in [0,1). A negative task has empty positions.
- `physical_truth`: value, unit, quantity, uncertainty, measurement method and calibration
  reference. A caliper-measured fruit diameter is not a pixel-edge reference.

`null` means unavailable. A physical record may use `calibration_ref` to point to a
local description of missing calibration; report such samples separately until the
mapping is verified. No implicit pixels-to-mm conversion is made. Prediction units
must exactly match the physical reference; quantity comes from the task annotation.

Provenance records dataset/source/version/license, source image ID, annotation version,
annotator, derivation and a scene/object `group_id`. All requests pin image SHA-256.
The small `examples/annotation.jsonl` is a format example with a placeholder hash and
no image; it is not a runnable benchmark or a dataset record.

## Black-box integration

```sh
uv run caliperbench export data/annotations.jsonl --output outputs/requests.jsonl
# Run your implementation elsewhere using only requests + the image cache.
# Write outputs/private.jsonl using Prediction schema.
uv run caliperbench score data/annotations.jsonl outputs/private.jsonl --output outputs/report.json
```

No source-code plugin or import is required. The exported request has **no ground
truth, confidence, reference dimensions or annotator metadata**. Public requests
contain only ID, image path/hash, strip and transition types. For a physical task,
provide permitted calibration/context to the implementation as a separately versioned
input bundle without reference dimensions; record that bundle in the run manifest.
The initial runner does not orchestrate physical-sizing implementations.

A prediction has version, sample_id, `status` (`ok` or `failed`), ordered `edges_px`,
optional `{value, unit}` physical prediction, runtime_ms and optional reason.
A failure must contain no measurements. Empty successful edges mean no detection.
Do not silently discard difficult samples. Missing rows count as failures; extra IDs
or malformed rows reject the submission. Out-of-strip and wrong-count predictions
count as edge failures. Never infer outputs from ground truth during matching.

## Metrics

Signed error is prediction minus reference. Report count, bias, MAE, RMSE and 95th
percentile absolute error. Ordered edges match by index after the declared task
fixes polarity and edge count; there is no nearest-GT peak selection.

Width error is `(p2-p1)-(g2-g1)`; center error is
`(p1+p2-g1-g2)/2`. They are reported only for valid two-edge results. Error summaries
include geometrically valid wrong detections even above tolerance. Missing and
invalid results have no numerical error and remain in the failure denominator.
A successful negative has no numerical edge residual but counts in reliability.

Edge failure means missing/failed output, wrong count, out-of-strip position, or any
edge error above the declared tolerance (default 1 px). Overall failure means any
available track failed. Physical missing rate means missing/failed/unit-mismatched
physical output; physical accuracy is reported by quantity and unit without an
invented universal tolerance. Uncertainty is retained for analysis, not used to
silently relax tolerances or weight results.

Phase bias uses ten bins only for explicitly supplied, justified phases. Empty bins
are null with count zero. Rotated scan distance modulo one is not automatically a
sensor-grid phase. Runtime summaries include submitted successes and failures;
missing runtimes remain missing, never zero. An empty evaluation has null rates.

## Fair comparisons

Freeze annotations, input hashes, sample order, tolerance and split before evaluation.
Split by original scene/object/sequence before cropping/downsampling; never place
variants in different splits. Tune only on development, freeze on validation, evaluate
once on held-out test. Report per-dataset/domain/contrast/uncertainty strata separately
(run the scorer on each explicit subset); the pooled report is sample-weighted and
can be dominated by large sources. Publish included/excluded counts and reasons.

Report hardware, OS, Python/dependency versions, implementation revision/configuration,
threads, warmup, repetition count, image decode policy and timing scope. The basic
runner measures one call per image/strip with no warmup and is a functional timing
sanity check; serious speed claims need repeated runs, controlled hardware and matching
scopes. Private predictions use self-reported times; offline scoring cannot verify them.
