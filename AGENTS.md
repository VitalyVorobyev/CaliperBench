# CaliperBench contributor guidance

CaliperBench is a public benchmark for real-image edge localization and dimensional measurement. Read `README.md`, `docs/roadmap.md`, `docs/protocol.md`, and `docs/labeling-format.md` before changing the corresponding area.

## Boundaries

- Keep the public reference implementation elementary and traceable to public textbook methods. Do not add advanced, proprietary, employer-derived, or product-specific caliper techniques. Private implementations use the JSONL black-box protocol outside this repository.
- Real image files, dataset archives, local annotations in progress, predictions, model weights, caches, credentials, and generated outputs stay out of Git. Never force-add them. Stage explicit paths and run `uv run python scripts/check_repository.py` before committing.
- A public source mask, polygon, bounding box, CAD projection, or model output is a **proposal or proxy**, not automatically subpixel edge ground truth. A physical caliper reading is a separate measurement track. Do not populate `edge_truth` from either without the documented review process.
- Preserve source URL/DOI, version, license, source image ID, SHA-256, derivation, annotator/reviewer, uncertainty, and group split. Check source terms before downloading or publishing derived labels.

## UI ownership

- Build the CaliperBench browsing and labeling app here. Reuse the interaction model already implemented in `/Users/vitalyvorobyev/vision/visual-anomaly-lab`, but do not depend on that application's private state or copy its app-specific editor wholesale.
- Use `/Users/vitalyvorobyev/vision/lab-ui` as the source of reusable React controls and 2D stage features. New reusable canvas primitives belong in `@vitavision/stage2d`; CaliperBench task forms, review workflow, and persistence belong here. Use split `@vitavision/ui`, `/forms`, `/charts`, and `/stage2d`, rather than the deprecated compatibility package. The current app's small contour adapter is temporary until the upstream package releases `ContourEditor`.
- Respect coordinate frames: CaliperBench uses pixel centers (`0,0` is the first pixel center); visual-anomaly-lab region documents use pixel-edge coordinates. An import adapter must explicitly transform coordinates and retain the original document and convention.
- Generated proposals remain drafts until a human reviews them. Keep the proposal model/version/prompts and approval history; never quietly overwrite a completed reference.
- The first weld pilot uses one reviewer. Require explicit contour approval and reviewer-assigned uncertainty before deriving candidate crossings; do not describe this as inter-reviewer agreement or independently measured uncertainty. Keep physical measurements separate.

## Checks

Python tooling uses `uv`. Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, schema generation/check, and the Git content guard for relevant changes. For future frontend work, use the package manager and checks declared by that app and by lab-ui. Test pixel-center registration, annotation round trips, conflict handling, and image data exclusion when the GUI is added. Keep the README and roadmap aligned with delivered behavior.
