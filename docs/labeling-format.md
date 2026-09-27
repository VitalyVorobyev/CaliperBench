# Labeling format and ground-truth status

## Current status

A local pilot has downloaded 49 weld-profile photos and 49 masks and generated 185 **automatic mask-proxy** tasks under ignored `data/`. The committed 12-image pilot selection has editable classical contour proposals and a local review app. No crossing is yet approved. The `examples/annotation.jsonl` values and old mask-proxy file are not reviewed ground truth. `Sample`/`Request`/`Prediction` JSONL remains the evaluation contract; the separate local review document retains raw geometry and approval history.

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

## Local editor source format

The editor stores JSON documents in ignored `data/review/reviews.sqlite3`, keyed by original image and mask hashes. Each document has the source contour, refined proposal, editable visible contour, algorithm parameters and rejection flags, reviewer, and per-strip crossing, confidence, uncertainty and disposition. Drafts use ETags to prevent stale overwrites; approval inserts an immutable revision. The edited contour is the mask source; its deterministic source-resolution raster is available from the approved-revision mask endpoint, while the original imported mask remains linked evidence. The first pilot supports one visible-edge crossing per strip; broader no-edge, paired-edge and physical review workflows are future work. Physical measurements remain separate from edge geometry.

Approval validates exactly one contour crossing on each approved strip and checks that the reviewer-marked crossing agrees with it within the stated uncertainty (at least a two-pixel editing allowance). Ambiguous tasks can be explicitly excluded. Export reads only the latest approved revision per image, creates deterministic `Sample` JSONL under `data/review/`, and links the revision ID and hash in provenance. The app hides baseline predictions until approval to limit anchoring. A future model adapter may populate proposals but cannot approve them.

The adapter for visual-anomaly-lab documents must account for its pixel-edge coordinates: an edge-frame coordinate `(x,y)` becomes CaliperBench pixel-center coordinate `(x-0.5,y-0.5)` before strip intersection. Do not apply that shift to a record already expressed in pixel-center coordinates. Prove alignment at several zooms, on non-square images and at borders. Preserve the original source file and its convention in provenance.

High-resolution annotation plus controlled downsampling provides a **proxy** for low-resolution subpixel evaluation, with propagated and added uncertainty as described in `docs/annotation.md`. Human disagreement, optical blur, resampling and boundary definition limit accuracy. Physical ground truth can validate diameter in millimeters while remaining unable to validate a particular image-edge location.
