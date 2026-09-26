# Labeling format and ground-truth status

## Current status (2026-09-26)

A local pilot has downloaded 49 weld-profile photos and 49 masks and generated 185 **automatic mask-proxy** `Sample` records under ignored `data/`. None has been independently reviewed or adjudicated. The committed `examples/annotation.jsonl` contains illustrative values and a placeholder image hash; it is not ground truth. The local pilot proxy is likewise not human-reviewed visible-edge ground truth; see `docs/pilot-weld-profiles.md`. The current `Sample`/`Request`/`Prediction` JSONL schema and generated JSON Schemas can validate benchmark tasks once labels exist. They do not yet preserve an editor's raw geometry, independent reviews, or proposal history.

| Source | Supplied reference | What CaliperBench still needs |
| --- | --- | --- |
| AmodalAppleSize RGB-D; Apple Fruitlet Sizing 2026 | Object-linked caliper diameters; images, masks and/or stereo/depth information | Confirm ID and measurement-axis mapping, calibration and uncertainty for physical tasks. Independently mark visible boundaries for edge tasks. Amodal contours are not visible edges. |
| ITODD/BOP | CAD, camera/pose information on eligible splits, industrial images | Verify available real subset and poses; CAD projections are geometric proxies, not measured image transitions or as-built dimensions. Inspect and label observed edges. |
| Weld-bead image/mask collections; MovingCables | Pixel masks/flow or processed source clips | Use masks to find candidate strips; review native images and label the actual transition. MovingCables standard clips are composited and its source clips are chroma-key processed. |
| VisA; DeepPCB | Anomaly masks or defect boxes | New edge labels. DeepPCB also needs license review and removal/flagging of artificial defects. |
| Wang et al. 2019 steel plate | Paper describes manual high-resolution edge labels | Usable image/label download and dataset rights have not been located. |

The detailed source evidence, access flags, and terms live in `registry/datasets.json`. The weld-profile entry adds a verified 49-pair pilot with binary masks but no calibrated physical measurement. An empty or `null` ground-truth field must stay empty until evidence is inspected; the registry is not a labeled release.

## Present interchange

One line in `data/annotations.jsonl` is a `Sample` (`src/caliperbench/schema.py`):

- `request`: stable sample ID, relative image path and SHA-256, source-image strip geometry, ordered transition polarities;
- `provenance`: source dataset/version/license, original image ID, annotation version/annotator, derivation, and scene/object `group_id`;
- `edge_truth`: zero to two ordered scan-distance positions in pixels, method, confidence, uncertainty, optional justified phase;
- `physical_truth`: measured value, unit, quantity, method, uncertainty and calibration reference;
- `split`: development, validation or test, assigned by original group before crops or downsampled variants.

`uv run caliperbench export ...` creates requests without truth for a black-box runner. Predictions are separate JSONL. `docs/protocol.md` defines coordinates and scoring. The current schema is a benchmark **projection**, not a sufficient working format for a labeling GUI.

## Planned editor source format

Introduce a versioned annotation document under ignored `data/annotations/` before implementing the GUI. The document should store immutable revisions keyed by original image hash and source version. Each revision should carry image dimensions and coordinate convention; task-specific strip endpoints/width/polarity; source-frame polylines, edge points or explicit no-edge regions; visible versus occluded/amodal semantics; reviewer IDs, timestamp, uncertainty, confidence, and adjudication state. Preserve imported masks/polygons as linked source evidence rather than silently converting them into edge truth. Keep physical measurement records keyed by the actual object, measurement axis, acquisition session and unit, with calibration and uncertainty, separate from edge geometry.

The conversion to benchmark `Sample` must be deterministic and versioned: intersect approved source-frame geometry with the declared strip, order crossings, reject ambiguous multiple crossings, then write scan-distance positions. Link each projected task to the immutable annotation revision and transform. A proposal can have a model name/version/checkpoint digest, prompts, score, and source-mask ID, but only an approved revision can enter the frozen test set. The editor may display the projection alongside the original geometry, yet the source document remains authoritative.

The adapter for visual-anomaly-lab documents must account for its pixel-edge coordinates: an edge-frame coordinate `(x,y)` becomes CaliperBench pixel-center coordinate `(x-0.5,y-0.5)` before strip intersection. Do not apply that shift to a record already expressed in pixel-center coordinates. Prove alignment at several zooms, on non-square images and at borders. Preserve the original source file and its convention in provenance.

High-resolution annotation plus controlled downsampling provides a **proxy** for low-resolution subpixel evaluation, with propagated and added uncertainty as described in `docs/annotation.md`. Human disagreement, optical blur, resampling and boundary definition limit accuracy. Physical ground truth can validate diameter in millimeters while remaining unable to validate a particular image-edge location.
