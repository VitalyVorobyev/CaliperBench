# CaliperBench

**A real-image benchmark for classical caliper, subpixel edge, and dimensional measurement.**

CaliperBench is building a reproducible collection of small measurement tasks drawn from public real images. The repository already has a candidate dataset registry, annotation and prediction schemas, local acquisition tools, a scorer, and a deliberately simple reference algorithm. **There is no released real-image labeled test set or GUI yet.** Dataset images, model weights, and local labeling work stay outside Git.

## What is measured

| Track | Reference | Main outputs |
| --- | --- | --- |
| Edge localization | Reviewed visible boundaries intersecting a declared scan strip | Edge position error, detection failure, subpixel phase bias when justified |
| Paired edges | Two reviewed edge positions on one strip | Width and center error |
| Physical measurement | Object-linked caliper reading or other documented measurement, with calibration context | Error in the stated physical unit |

These tracks are independent. A physical fruit diameter does not locate its image edges. A mask, defect box, or CAD silhouette can guide annotation but does not establish subpixel edge truth.

## Data and ground-truth status

The [registry](registry/datasets.json) lists nine candidate sources, including AmodalAppleSize RGB-D, Apple Fruitlet Sizing 2026, ITODD/BOP, weld beads, MovingCables, VisA, DeepPCB and the 2019 steel-plate study. It records source links, terms, access state, expected reference types and relabeling work. Apple datasets offer physical caliper measurements; weld/cable/VisA data mainly offer masks; DeepPCB has boxes and unresolved use terms. The steel-plate images and labels have no located usable public download. **No source has yet been inspected and labeled into a CaliperBench release.** See [ground-truth and format details](docs/labeling-format.md).

The first pilot will inspect actual source files, label visible edges at native resolution, quantify reviewer disagreement and preserve uncertainty. High-resolution labels transformed onto controlled downsampled views are proxy ground truth, with the transform and its limits recorded. Source images and raw archives will not be committed.

## Labeling app plan

A CaliperBench React app will let reviewers browse local datasets, draw scan strips and edge geometry, view a line profile, compare imported masks and model proposals, record physical measurements, and approve immutable annotation revisions. It will follow the proven browsing and labeling workflow in [visual-anomaly-lab](https://github.com/VitalyVorobyev/visual-anomaly-lab). Reusable controls and the 2D canvas come from [lab-ui](https://github.com/VitalyVorobyev/lab-ui), especially `@vitavision/stage2d` and its `ImageStage`; CaliperBench keeps measurement-specific tools and storage here. The [roadmap](docs/roadmap.md) gives phases and acceptance gates.

visual-anomaly-lab already has prompt-guided and automatic-prompt-grid MobileSAM mask proposals. We will test that workflow on manually labeled CaliperBench images before choosing any further public model. Proposals remain editable drafts until reviewed; they never become ground truth automatically. The public benchmark baseline stays a textbook pipeline and private implementations may be evaluated through the [black-box JSONL protocol](docs/protocol.md) without publishing code.

## Run the current toolkit

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv sync --extra dev
uv run caliperbench registry
uv run pytest
```

Once a local `data/annotations.jsonl` and its images exist:

```sh
uv run caliperbench export data/annotations.jsonl --output outputs/requests.jsonl
uv run caliperbench run outputs/requests.jsonl --data-root data --output outputs/baseline.jsonl
uv run caliperbench score data/annotations.jsonl outputs/baseline.jsonl --output outputs/report.json
```

The baseline uses bilinear strip sampling, mean projection, fixed Gaussian smoothing, finite differences, peak selection and three-point parabolic refinement. It is a functional lower bar, not a production caliper. The committed [format example](examples/annotation.jsonl) has a placeholder hash and no image.

## Project files

- [Roadmap](docs/roadmap.md) — GUI, data, review and model-assistance phases.
- [Labeling format and ground-truth status](docs/labeling-format.md) — current JSONL and planned editor document.
- [Dataset acquisition](docs/datasets.md) — local cache, checksums, provenance and rights.
- [Annotation guide](docs/annotation.md) — review and controlled downsampling.
- [Protocol and metrics](docs/protocol.md) — coordinates, black-box predictions and scoring.
- [Design boundary](docs/design.md) and [contributor guidance](AGENTS.md).

Code and original documentation are [MIT licensed](LICENSE). Source datasets retain their own terms. CI tests generated numeric fixtures; no real image data is checked in.
