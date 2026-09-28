# Roadmap

## Status

The Python registry, cache tooling, v1 benchmark JSONL, three textbook baselines, scorer, tests and CI are implemented. Ten real-data sources are registered. The local weld collection has 49 verified images and 185 low-confidence mask-proxy tasks. A deterministic 12-image subset, classical contour proposals, a local React review app, SQLite drafts and immutable approvals are implemented. **Weld is exploratory only; its source masks are not caliper ground truth and benchmark export is blocked. No eligible benchmark split exists yet.**

The GUI is a CaliperBench-specific local web app using `@vitavision/ui`, `/forms`, `/charts`, and `/stage2d`; reusable contour and raster-mask interaction is proposed upstream in [lab-ui PR #36](https://github.com/VitalyVorobyev/lab-ui/pull/36). The current app edits contour-derived masks; freehand raster painting remains an optional later workflow. [visual-anomaly-lab](https://github.com/VitalyVorobyev/visual-anomaly-lab) informed browsing and revision behavior. CaliperBench owns its review workflow, persistence and benchmark projection.

## Delivered — real-data pilot and review foundation

The weld source is checksum verified under ignored `data/`, with a metadata-only 12-image selection. The selection spans brightness, contrast, blur and source-mask boundary contrast. Imported masks are proposals; the Python active-contour refinement is bounded and preserves source and algorithm provenance. A deterministic local generator adds 291 normal scan candidates along those proposals; the original mask-proxy samples remain separately identified. Active-contour refinement itself does not use caliper strips.

The local app browses image thumbnails in a foldable panel, displays source/refined/reviewed contours and masks, reshapes neighboring contour vertices with an adjustable brush, offers a single optional normal scan and collapsible profile overlay, autosaves drafts, detects conflicting saves and freezes exploratory contours. It can suggest a visible-specimen silhouette or accept a coarse hand-traced closed outline, then snap that outline toward nearby gradients within a reviewer-chosen radius. Reviewer settings sit in a separate tab. No weld-derived benchmark export is available.

The current CI covers deterministic refinement, crossings, revision conflicts, weld-export blocking, coordinate projection and no-image frontend geometry. Images, masks, drafts, predictions and database remain local.

## Next — physically grounded pilot

Start with [Apple Fruitlet Sizing 2026](https://data.mendeley.com/datasets/k45nnfjydt/1), whose public description lists rectified stereo images, stereo calibration and ground-truth caliper measurements. First inspect the archive and verify source rights, image-to-fruit IDs, measurement axes, camera parameters and units. Select a small, diverse set with unambiguous object-to-measurement matching; keep all files local. Implement the physical truth track before claiming millimeter accuracy. Visible edge localization remains a separate annotation task.

Keep the weld browser as an exploratory annotation and difficult-image tool. Do not review all 12 masks as if a closed weld-region contour were a visible edge. Visible specimen edges remain open where metal exits the frame; their frame-contact sides are recorded, and no artificial closing segment is treated as an optical edge. Open and closed paths can both be edited and snapped. The current editor stores one active path; a photo with multiple substantial visible chains is rejected by the automatic single-path proposer until multi-chain annotation is implemented. A future weld edge subset requires an explicit visible-boundary definition, segment-level inclusion/exclusion, and independent review before eligibility changes. The next geometry stage will keep a region mask separate from optical edge chains, derive a trimmed provisional centerline, and admit orthogonal sections only when both visible sides are present.

**Gate:** a source image, object ID, calibration record and physical caliper reading are traceably linked for each physical sample. No proxy mask is substituted for that measurement.

## Later — broaden truth tracks and supported app

Add paired-edge tasks and calibrated physical datasets after source-object mapping is verified. Introduce independent duplicate review if a release requires measured annotation reliability; current uncertainty values are reviewer judgments. Extend the app to dataset-level review management and versioned migrations, test more screen sizes and accessibility states, and replace the small local contour adapter when the upstream lab-ui package releases its component.

Preserve an explicit visible-edge versus geometric-outline distinction for every new source. Controlled downsampling remains a separately labeled high-resolution-derived proxy track, with transforms and uncertainty recorded.

**Gate:** each published score uses an approved reference or matched physical measurement, plus source license and immutable derivation.

## Later — model-assisted proposals

**Outcome:** faster labeling without changing who decides ground truth.

- Measure reviewer time and correction distance on the classical pilot first. Then evaluate visual-anomaly-lab's MobileSAM proposal workflow or another openly licensed model on a held-out labeling set. Its outputs remain editable drafts, not subpixel labels.
- If those fail, evaluate a public, openly licensed segmentation or boundary model as an optional local adapter. Pin model license, version/checkpoint digest, prompts, inference settings, runtime and proposal confidence. Keep weights out of Git. Use the same reviewer flow for every source and prevent evaluation-set training leakage.
- Measure accepted-proposal rate, reviewer time, correction distance, missed/false edges and disagreement against a manually labeled set. Add sources only after provenance and rights checks.

**Gate / stop condition:** assisted labeling saves review time at no worse final agreement, and no proposal bypasses human approval. Model scores are not declared ground truth uncertainty.

The pilot is a local web app. A desktop wrapper is a distribution choice for a later release, not a prerequisite for reviewing the initial real-image set.
