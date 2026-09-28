# Labeling format and ground-truth status

## Current status

A local pilot has downloaded 49 weld-profile photos and 49 masks and generated 185 **automatic mask-proxy** tasks under ignored `data/`. The committed 12-image pilot selection has editable classical contour proposals and a local review app. A separate ignored v2 file contains 291 deterministic normal-scan **review candidates** along those proposals. Its `Candidate` records have `proposal_crossing_px` and deliberately no `edge_truth` field; they cannot be scored as reviewed samples. Active-contour refinement uses image gradients and no caliper strips; these scans are evaluation candidates, not its internal steps. No weld crossing is eligible for benchmark scoring. The `examples/annotation.jsonl`, mask-proxy file, and contour-candidate file are not reviewed ground truth. `Sample`/`Request`/`Prediction` JSONL remains the evaluation contract; the separate local review document retains raw geometry and approval history.

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

The exploratory weld editor stores JSON documents in ignored `data/review/reviews.sqlite3`, keyed by original image and mask hashes. Each document has the source contour, refined proposal, editable contour, `contour_target` (`weld_region` by default or `visible_specimen` after starting a new outline), a `contour_edits` operation log with snap parameters, original algorithm parameters and rejection flags, reviewer, contour uncertainty, and derived per-strip crossing status. Drafts use ETags to prevent stale overwrites; freezing inserts an immutable exploratory revision. The edited contour is the mask source; its deterministic source-resolution raster is available from the approved-revision mask endpoint, while the original imported mask remains linked evidence. The first pilot supports one visible-edge crossing per strip; broader no-edge, paired-edge and physical review workflows are future work. Physical measurements remain separate from edge geometry.

Version 2 separates contour-only approval from the earlier per-crossing workflow. Opening a version-1 draft preserves its geometry and reviewer but clears its old review checkbox, requiring a fresh explicit decision. Previously frozen revisions remain immutable.

Freezing requires a named reviewer, inspected contour, and positive reviewer-assigned contour uncertainty. Candidate scans are reoriented normal to the frozen contour at their intersections; unique crossings are derived geometrically, while ambiguous or out-of-bounds scans are excluded automatically. The frozen request geometry is stored in each approved task. The old vertical mask-proxy scans are never promoted by this flow. The weld exporter is blocked: whole weld-region contours contain internal, sometimes visually ambiguous boundaries and must not become scored edge references. The old mask-proxy results remain historical diagnostics. A future source-specific annotation protocol must first select valid visible boundary segments and assess review agreement. A future model adapter may populate proposals but cannot approve them.

The adapter for visual-anomaly-lab documents must account for its pixel-edge coordinates: an edge-frame coordinate `(x,y)` becomes CaliperBench pixel-center coordinate `(x-0.5,y-0.5)` before strip intersection. Do not apply that shift to a record already expressed in pixel-center coordinates. Prove alignment at several zooms, on non-square images and at borders. Preserve the original source file and its convention in provenance.

High-resolution annotation plus controlled downsampling provides a **proxy** for low-resolution subpixel evaluation, with propagated and added uncertainty as described in `docs/annotation.md`. Human disagreement, optical blur, resampling and boundary definition limit accuracy. Physical ground truth can validate diameter in millimeters while remaining unable to validate a particular image-edge location.
