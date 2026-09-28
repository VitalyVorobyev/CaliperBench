# CaliperBench

**A real-image benchmark for classical caliper, subpixel edge, and dimensional measurement.**

CaliperBench builds reproducible measurement tasks from public real images. It includes a dataset registry, local acquisition tools, a scorer, simple reference methods, and a local review app. **The weld collection is now exploratory only: its region masks are not caliper ground truth, and benchmark export is disabled.** Dataset images, model weights, and local labeling work stay outside Git.

## What is measured

| Track | Reference | Main outputs |
| --- | --- | --- |
| Edge localization | Reviewed visible boundaries intersecting a declared scan strip | Edge position error, detection failure, subpixel phase bias when justified |
| Paired edges | Two reviewed edge positions on one strip | Width and center error |
| Physical measurement | Object-linked caliper reading or other documented measurement, with calibration context | Error in the stated physical unit |

These tracks are independent. A physical fruit diameter does not locate its image edges. A mask, defect box, or CAD silhouette can guide annotation but does not establish subpixel edge truth.

## Data and ground-truth status

The [registry](registry/datasets.json) lists ten candidate sources, including AmodalAppleSize RGB-D, Apple Fruitlet Sizing 2026, ITODD/BOP, weld beads, MovingCables, VisA, DeepPCB and the 2019 steel-plate study. It records source links, terms, access state, expected reference types and relabeling work. Apple datasets offer physical caliper measurements; weld/cable/VisA data mainly offer masks; DeepPCB has boxes and unresolved use terms. The steel-plate images and labels have no located usable public download. A first local [weld-profile pilot](docs/pilot-weld-profiles.md) has 49 checksum-verified real photos and 185 automatically derived **mask-proxy** tasks. They are development-only and have not been visually adjudicated. No source has yet been labeled into a CaliperBench release. See [ground-truth and format details](docs/labeling-format.md).

The [12-image review pilot](registry/weld-pilot-v1.json) spans brightness, contrast, blur and mask-boundary contrast. A public [active-contour method](https://scikit-image.org/docs/stable/auto_examples/edges/plot_active_contours.html) refines each source mask within a four-pixel search band. Active-contour refinement uses image gradients, not caliper strips. The review app adds deterministic normal scan probes along the proposal: 291 local candidates across the pilot, alongside the original 3–4 mask-proxy strips per image. Candidate records carry no ground-truth track and cannot be scored as reviewed samples. These contours and crossings are **editable proposals**, not ground truth. A reviewer may correct and freeze a contour as an annotation exercise; it does not enter the benchmark. A future visible-edge subset would need an explicit edge definition, segment-level validity, and independent review. No physical measurement is supplied. High-resolution labels transformed onto controlled downsampled views remain proxy ground truth, with their transform and limits recorded.

## Review app

The local React app has a foldable thumbnail browser, a smooth contour brush with adjustable radius, compact layer tools, one optional normal-scan diagnostic with a slider, a collapsible scan-profile overlay, and a separate settings tab. It edits the visible contour and compares source, refined and edited masks. The reviewed raster mask is derived from the contour; the app does not yet expose freehand mask painting. Drafts autosave to a local SQLite store with revision-conflict checks. Freezing stores an immutable contour revision and deterministic raster mask for local investigation. Geometric scans may be derived internally, but this dataset cannot export benchmark samples. The original vertical mask-proxy tasks and their historical scores are diagnostic only. The app reuses `@vitavision/ui`, `/forms`, `/charts` and `/stage2d`, following workflow patterns from [visual-anomaly-lab](https://github.com/VitalyVorobyev/visual-anomaly-lab). General-purpose contour and mask editing components are proposed in [lab-ui PR #36](https://github.com/VitalyVorobyev/lab-ui/pull/36); the app currently carries a small contour adapter for its published stage package.

The editor now offers a [visible-specimen proposal and local edge snap](docs/specimen-labeling.md). You can also trace a coarse closed outline, snap it within a bounded radius, then correct it with the contour brush. These operations create proposals only; frame-truncated specimen sides cannot become physical-size truth.

Learned model assistance is a later, optional proposal source after this classical pilot measures review effort. The public benchmark baseline remains a textbook pipeline; private implementations can use the [black-box JSONL protocol](docs/protocol.md) without publishing code.

## Run the current toolkit

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv sync --extra dev
uv run caliperbench registry
uv run pytest
```

To prepare and open the real-image review pilot (the download stores files only under ignored `data/`):

```sh
uv run python scripts/fetch_weld_profiles.py
uv run python scripts/build_weld_proxy.py
uv run python scripts/select_weld_pilot.py  # reproduces the committed metadata-only selection
uv run python scripts/build_contour_candidates.py  # local-only review probes
cd frontend && bun install && bun run build && cd ..
uv run uvicorn caliperbench.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. For frontend development, run `bun run dev` in `frontend/` and open its printed local URL; Vite proxies `/api` to the Python service. The review database is under ignored `data/review/`. Weld benchmark export is blocked; do not use `annotations_weld_proxy.jsonl` as ground truth.

The next acquisition target is [Apple Fruitlet Sizing 2026](https://data.mendeley.com/datasets/k45nnfjydt/1), which lists real caliper measurements, rectified stereo images and calibration. Its object IDs, measured axes and files must be checked before it becomes a physical-measurement benchmark. Visible-edge references would still need separate review.

Once a local `data/annotations.jsonl` and its images exist:

```sh
uv run caliperbench export data/annotations.jsonl --output outputs/requests.jsonl
uv run caliperbench run outputs/requests.jsonl --data-root data --output outputs/baseline.jsonl
uv run caliperbench score data/annotations.jsonl outputs/baseline.jsonl --output outputs/report.json
```

The default baseline uses bilinear strip sampling, mean projection, fixed Gaussian smoothing, finite differences, peak selection and three-point parabolic refinement. `--method` also selects integer-gradient and midpoint-crossing textbook comparators. The [pilot report](docs/pilot-weld-profiles.md) gives their first real-image mask-proxy results. These methods are functional lower bars, not production calipers. The committed [format example](examples/annotation.jsonl) has a placeholder hash and no image.

## Project files

- [First real-image pilot](docs/pilot-weld-profiles.md) — verified local data, proxy task construction and first baseline numbers.
- [Roadmap](docs/roadmap.md) — delivered pilot and remaining review/release gates.
- [Labeling format and ground-truth status](docs/labeling-format.md) — current JSONL and planned editor document.
- [Dataset acquisition](docs/datasets.md) — local cache, checksums, provenance and rights.
- [Annotation guide](docs/annotation.md) — review and controlled downsampling.
- [Protocol and metrics](docs/protocol.md) — coordinates, black-box predictions and scoring.
- [Design boundary](docs/design.md) and [contributor guidance](AGENTS.md).

Code and original documentation are [MIT licensed](LICENSE). Source datasets retain their own terms. CI tests generated numeric fixtures; no real image data is checked in.
