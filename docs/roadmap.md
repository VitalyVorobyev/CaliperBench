# Roadmap

## Status

The Python registry, cache tooling, v1 benchmark JSONL, three textbook baselines, scorer, tests and CI are implemented. Ten real-data sources are registered. The local weld collection has 49 verified images and 185 low-confidence mask-proxy tasks. A deterministic 12-image subset, classical contour proposals, a local React review app, SQLite drafts and immutable approvals are implemented. **No human-reviewed edge reference or published benchmark split exists yet.**

The GUI is a CaliperBench-specific local web app using `@vitavision/ui`, `/forms`, `/charts`, and `/stage2d`; reusable contour interaction is contributed upstream to lab-ui. [visual-anomaly-lab](https://github.com/VitalyVorobyev/visual-anomaly-lab) informed browsing and revision behavior. CaliperBench owns its review workflow, persistence and benchmark projection.

## Delivered — real-data pilot and review foundation

The weld source is checksum verified under ignored `data/`, with a metadata-only 12-image selection. The selection spans brightness, contrast, blur and source-mask boundary contrast. Imported masks are proposals; the Python active-contour refinement is bounded and preserves source and algorithm provenance.

The local app browses images, displays source/refined/reviewed contours and masks, edits contour vertices and strip crossings, shows line profiles, autosaves drafts, detects conflicting saves and freezes approvals. Predictions unlock after approval. An approved-revision exporter preserves the existing black-box JSONL protocol. No approval is generated automatically.

The current CI covers deterministic refinement, crossings, revision conflicts, approved-only export, coordinate projection and no-image frontend geometry. Images, masks, drafts, predictions and database remain local.

## Next — human review and visual acceptance

Have one reviewer inspect all 12 images, edit the visible contour, approve or exclude every strip crossing, assign uncertainty and confidence, and freeze revisions. An external reviewer must still verify the app’s visual alignment and interaction quality at normal and high zoom, on a narrow window and with keyboard navigation. Record failures and any needed refinements before calling the pilot ready.

Compare approved references against all three existing baselines. Report edge MAE, bias, detection failures, runtime, reviewer-assigned uncertainty and image-group counts. Keep the 185 mask-proxy tasks as exploratory diagnostics, never substitute them for reviewed references. Do not report width/center or physical error until those truth tracks have real observations.

**Gate:** user confirms overlay alignment, contour editing, review decisions and reproducible report on the 12 images. A one-reviewer pilot does not establish inter-reviewer agreement.

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
