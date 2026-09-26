# Roadmap

## Status

The Python registry, local cache tooling, v1 benchmark JSONL, simple reference baseline, scorer, tests and CI are implemented. Ten real-data sources are registered. One local weld-profile pilot contains 49 verified real images and 185 low-confidence mask-proxy tasks; no human-adjudicated edge labels have been imported. There is no CaliperBench GUI, editor store, advanced-model adapter, or published benchmark split yet.

The GUI will be a CaliperBench-specific React app. [visual-anomaly-lab](https://github.com/VitalyVorobyev/visual-anomaly-lab) supplies a proven browser, annotation queue, zoom/pan, revision workflow, mask import, and MobileSAM-assisted draft interaction to study and reuse. [lab-ui](https://github.com/VitalyVorobyev/lab-ui) is the single source for reusable controls and canvas infrastructure: its split `@vitavision/ui`, `@vitavision/stage2d` and `@vitavision/charts` packages include `ImageStage`, image-coordinate transforms, measurement overlays and line profiles. CaliperBench owns its task-specific editor and data model. Do not introduce a competing generic canvas package.

## Phase 1 — Inspect and freeze a pilot source

**Outcome:** one legally usable, modest real-image pilot with a reproducible local manifest.

- The weld-profile subset is acquired and verified; inspect its boundary semantics with independent reviewers. Add an apple subset for the physical track after exact object and measurement mapping is checked.
- Add a source-specific conversion/inventory script after inspecting actual files. Assign group splits before creating tasks.
- Publish a metadata-only pilot inventory and the reason for each inclusion/exclusion; retain image bytes locally.

**Gate / stop condition:** every pilot image is traceable to a source version, license and SHA-256; missing dimensions/IDs are resolved or excluded. No precision claim comes from an imported mask alone.

## Phase 2 — Annotation contract and GUI foundation

**Outcome:** a person can browse pilot images, define strips and edit/review source-frame geometry.

- Specify and validate immutable annotation revisions, draft/proposal/approved states, reviewer identity, task projection and source-frame coordinate conversion. Keep physical truth separate.
- Build a React app in this repo using `@vitavision/ui` and `@vitavision/stage2d` (`ImageStage`, `MeasureOverlay`, `LineProfile`). Reuse visual-anomaly-lab's proven queue, keyboard, zoom, undo/redo, autosave/conflict and revision patterns as design inputs. Move only general 2D interaction primitives upstream to lab-ui when both apps need them; keep caliper strip tools here.
- Show image, source mask/proposal, editable visible edge geometry, strip, profile, projected crossings, uncertainty and provenance together. Support no-edge tasks, reject ambiguous crossings and display physical records without using them as edge labels.
- Persist locally; no dataset images or unfinished drafts in Git. Export approved revisions to validated benchmark `Sample` JSONL.

**Gate / stop condition:** import/edit/save/reopen/export round-trips without coordinate drift, including non-square images, borders and high zoom. A complete revision cannot be silently overwritten and an unapproved proposal cannot reach the test set.

## Phase 3 — Real-label pilot and quality study

**Outcome:** a frozen pilot split with defensible edge and physical truth tracks.

- Independently label a diverse pilot by two reviewers, adjudicate disagreements and measure uncertainty. Mark weak/occluded/ambiguous boundaries explicitly; include negative strips.
- Link physical measurements to exact object, axis and acquisition session and verify calibration. Run controlled downsampling only for images whose source resolution and reference quality justify it. Group all derived variants in one split.
- Review failures and biases by source, contrast, phase and uncertainty. Freeze annotation hashes, split IDs and task-generation version before the first published evaluation.

**Gate / stop condition:** agreement and error bounds are reported with sample counts; every scored edge has a reviewed source-frame reference; physical reports exclude unresolved object mappings.

## Phase 4 — Assisted proposals, then broader curation

**Outcome:** faster labeling without changing who decides ground truth.

- First evaluate the existing visual-anomaly-lab MobileSAM prompt-guided and bounded automatic-prompt-grid mask workflows on a held-out labeling pilot. Its proposed contours are editable drafts, not subpixel labels. Also test deterministic mask contours and the public reference baseline as low-cost candidate generators.
- If those fail, evaluate a public, openly licensed segmentation or boundary model as an optional local adapter. Pin model license, version/checkpoint digest, prompts, inference settings, runtime and proposal confidence. Keep weights out of Git. Use the same reviewer flow for every source and prevent evaluation-set training leakage.
- Measure accepted-proposal rate, reviewer time, correction distance, missed/false edges and disagreement against a manually labeled set. Add sources only after provenance and rights checks.

**Gate / stop condition:** assisted labeling saves review time at no worse final agreement, and no proposal bypasses human approval. Model scores are not declared ground truth uncertainty.

## Dependencies and open decisions

Phase 2 depends on a real pilot in Phase 1 and a stable editor document. Phase 3 depends on an end-to-end GUI and two independent reviewers. Phase 4 depends on a manual reference set; selecting an advanced model earlier would let its errors define the target. The first pilot source and release license for derived annotations are chosen only after archive/rights inspection. The exact app shell (web-only versus desktop wrapper) remains open; the React canvas, local-only data boundary and interchange do not depend on that choice. Prefer a local web app for the first pilot unless image access or deployment constraints require a wrapper.
