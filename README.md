# CaliperBench

A real-image benchmark for subpixel edge and dimensional measurement.

CaliperBench curates public image sources, defines measurement tasks and evaluates
predictions. It is an initial benchmark toolkit, **not yet a labeled benchmark release**.
Real images are the focus; tiny generated arrays exist only to test the tooling.

The public baseline is deliberately elementary: bilinear strip sampling → mean
projection → Gaussian smoothing → finite differences → peak selection → three-point
parabolic refinement. No advanced, proprietary or employer-derived methods belong here.
External implementations can submit predictions without releasing source code.

## Start

Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra dev
uv run caliperbench registry
uv run pytest
uv run python scripts/check_repository.py
```

Use the repository root as the working directory. Dataset files stay in ignored
`data/`; annotations under development, predictions and reports stay in `outputs/`.
No image archives are downloaded by installation or CI.

```sh
# After preparing local annotations using docs/protocol.md:
uv run caliperbench export data/annotations.jsonl --output outputs/requests.jsonl
uv run caliperbench run outputs/requests.jsonl --data-root data --output outputs/baseline.jsonl
uv run caliperbench score data/annotations.jsonl outputs/baseline.jsonl --output outputs/report.json
```

## Contents

- [Candidate dataset registry](registry/datasets.json): nine sources, evidence URLs,
  licenses, access limitations, priorities and relabeling plans.
- [Data acquisition](docs/datasets.md): local cache, hashes and provenance.
- [Protocol and metrics](docs/protocol.md): independent image-edge and physical tracks.
- [Annotation guide](docs/annotation.md): high-resolution labels, uncertainty and downsampling.
- [Design and IP boundary](docs/design.md): intentionally narrow reference implementation.
- `schemas/`: generated JSON Schemas; Python validation also enforces cross-field invariants.
- `tests/`: small deterministic numeric fixtures; no committed image files.

Start curation with apples for physical sizing, ITODD for industrial geometry, and
MovingCables for paired edges. Native masks and CAD projections are candidate-label
sources, not verified subpixel truth. DeepPCB has conflicting terms and artificial
defects; steel-plate data remains inaccessible. Unknown registry values are explicit
`null`s, not inferred facts. Source terms were checked on 2026-09-26; archive contents
have not yet been inspected.

Code and original documentation: [MIT](LICENSE). Dataset licenses remain independent.
