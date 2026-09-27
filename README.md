# CaliperBench

**A real-image benchmark for classical caliper, subpixel edge, and dimensional measurement.**

CaliperBench builds reproducible measurement tasks from public real images. It includes a dataset registry, local acquisition tools, a scorer, simple reference methods, and a local review app. **The app is ready for the 12-image weld pilot; no human-reviewed reference set has been approved yet.** Dataset images, model weights, and local labeling work stay outside Git.

## What is measured

| Track | Reference | Main outputs |
| --- | --- | --- |
| Edge localization | Reviewed visible boundaries intersecting a declared scan strip | Edge position error, detection failure, subpixel phase bias when justified |
| Paired edges | Two reviewed edge positions on one strip | Width and center error |
| Physical measurement | Object-linked caliper reading or other documented measurement, with calibration context | Error in the stated physical unit |

These tracks are independent. A physical fruit diameter does not locate its image edges. A mask, defect box, or CAD silhouette can guide annotation but does not establish subpixel edge truth.

## Data and ground-truth status

The [registry](registry/datasets.json) lists ten candidate sources, including AmodalAppleSize RGB-D, Apple Fruitlet Sizing 2026, ITODD/BOP, weld beads, MovingCables, VisA, DeepPCB and the 2019 steel-plate study. It records source links, terms, access state, expected reference types and relabeling work. Apple datasets offer physical caliper measurements; weld/cable/VisA data mainly offer masks; DeepPCB has boxes and unresolved use terms. The steel-plate images and labels have no located usable public download. A first local [weld-profile pilot](docs/pilot-weld-profiles.md) has 49 checksum-verified real photos and 185 automatically derived **mask-proxy** tasks. They are development-only and have not been visually adjudicated. No source has yet been labeled into a CaliperBench release. See [ground-truth and format details](docs/labeling-format.md).

The [12-image review pilot](registry/weld-pilot-v1.json) spans brightness, contrast, blur and mask-boundary contrast. A public [active-contour method](https://scikit-image.org/docs/stable/auto_examples/edges/plot_active_contours.html) refines each source mask within a four-pixel search band. These contours are **editable proposals**, not ground truth. A reviewer must inspect the visible contour and approve each strip crossing with an uncertainty before it enters the benchmark. This pilot records one reviewer’s judgment; it does not measure inter-reviewer agreement. High-resolution labels transformed onto controlled downsampled views remain proxy ground truth, with their transform and limits recorded.

## Review app

The local React app browses the 12 pilot images, edits the visible contour and proposed edge crossings, compares source, refined and edited masks, and shows scan profiles. Drafts autosave to a local SQLite store with revision-conflict checks. Approval freezes an immutable revision and its deterministically derived raster mask; only approved crossings export to benchmark JSONL. Textbook predictions stay hidden during review and unlock after approval. The app reuses `@vitavision/ui`, `/forms`, `/charts` and `/stage2d`, following workflow patterns from [visual-anomaly-lab](https://github.com/VitalyVorobyev/visual-anomaly-lab). General-purpose contour editing is proposed in [lab-ui PR #36](https://github.com/VitalyVorobyev/lab-ui/pull/36); the app currently carries a small adapter for its published stage package.

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
cd frontend && bun install && bun run build && cd ..
uv run uvicorn caliperbench.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. For frontend development, run `bun run dev` in `frontend/` and open its printed local URL; Vite proxies `/api` to the Python service. The review database and approved JSONL export are under ignored `data/review/`. Do not use the old `annotations_weld_proxy.jsonl` as reviewed ground truth.

After approving references, reproduce the black-box benchmark from the frozen local review store:

```sh
uv run caliperbench review-export --output outputs/reviewed_samples.jsonl
uv run caliperbench export outputs/reviewed_samples.jsonl --output outputs/reviewed_requests.jsonl
uv run caliperbench run outputs/reviewed_requests.jsonl --data-root data --output outputs/reviewed_baseline.jsonl
uv run caliperbench score outputs/reviewed_samples.jsonl outputs/reviewed_baseline.jsonl --output outputs/reviewed_report.json
```

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
