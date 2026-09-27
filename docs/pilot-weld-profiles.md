# First real-image pilot: weld profiles

**Status:** exploratory development-only mask-proxy evaluation, run 2026-09-26. It is **not** a released subpixel ground-truth benchmark. No human-reviewed edges or physical measurements are present.

## Source and reproducibility

[Conquista's Zenodo v1 release](https://zenodo.org/records/20301441) (DOI `10.5281/zenodo.20301441`, CC BY 4.0) supplies 49 real VGA-camera weld-profile photos and 49 binary weld-region masks. We verified 98 files totaling 5,779,801 bytes against Zenodo's MD5 and committed a [metadata-only pin file](../registry/weld-profiles-v1-files.json) with local SHA-256 for every file. The images and masks live under ignored `data/raw/weld-profiles-2026/`; they are not in Git. The source's fixed camera setup does not provide verified metric calibration or independent physical dimensions.

From the repository root:

```sh
uv sync --extra dev
uv run python scripts/fetch_weld_profiles.py
uv run python scripts/build_weld_proxy.py
uv run caliperbench export data/annotations_weld_proxy.jsonl --output outputs/weld_proxy_requests.jsonl
for method in gradient_integer gradient_parabolic midpoint_crossing; do
  uv run caliperbench run outputs/weld_proxy_requests.jsonl --data-root data --method "$method" --output "outputs/weld_proxy_${method}.jsonl"
  uv run caliperbench score data/annotations_weld_proxy.jsonl "outputs/weld_proxy_${method}.jsonl" --output "outputs/weld_proxy_${method}_report.json"
done
```

The builder takes four fixed x positions across each mask, keeps only columns with one continuous region and a locally coherent upper boundary, and places a 24-pixel vertical strip across that boundary. Its reference position is the half-pixel border before the first mask pixel. All 49 source images contribute; 185 candidates pass and 11 are excluded as ambiguous. The tasks are all in `development`; multiple tasks from one image share a group. The proxy truth is explicitly labeled low confidence with a 1-pixel **working** uncertainty. That number is not a measured annotator error bound.

## Textbook methods

All methods use bilinear sampling and mean projection of the same strip, then a fixed sigma-1-sample discrete Gaussian. The same requests, image hashes and intensity scaling are used for all runs.

- `gradient_integer`: strongest local finite-difference gradient above 0.01 intensity/sample; return the integer sample position.
- `gradient_parabolic`: the same peak, refined by the vertex of a three-sample parabola. This remains the default public reference.
- `midpoint_crossing`: midpoint of median endpoint intensities, with linear interpolation at the crossing nearest the strip center; require endpoint contrast at least 0.05. It currently supports a single-edge task only.

| Method | 185 valid outputs | Error >1 px | MAE to mask proxy | Bias to mask proxy | Median call time* |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gradient, integer | 185 | 63 (34.1%) | 1.046 px | −0.478 px | 0.152 ms |
| Gradient, parabola | 185 | 63 (34.1%) | 0.966 px | −0.448 px | 0.149 ms |
| Midpoint crossing | 185 | 69 (37.3%) | 0.964 px | −0.541 px | 0.153 ms |

*One local Python run on Apple Silicon; includes the predictor, excludes image decoding and file I/O. It is not a controlled speed comparison. The exact local reports and per-task predictions remain in ignored `outputs/`.

Every method returned a position on every strip; “error >1 px” is the scorer's edge-failure rate relative to the **mask boundary**, not a missing-detection rate. The MAE covers all 185 predictions. The small differences between methods are not evidence of subpixel accuracy: the mask may trace the weld region differently from the visible intensity transition, labels are pixel raster boundaries, and nearby texture can produce a stronger gradient. The strips are deliberately centered from the source mask and therefore measure localization in a supplied ROI, not object discovery. Four correlated strips per image make 185 an inappropriate independent-sample count for confidence intervals.

## Review pilot

A metadata-only [12-image selection](../registry/weld-pilot-v1.json) spans brightness, contrast, Laplacian blur response and mask-boundary contrast. The local GUI opens each real image with the source mask, a bounded classical active-contour proposal, editable contour, strip crossings and line profile. One reviewer must approve the visible contour and each usable crossing with uncertainty; ambiguous strips are excluded. No human-approved revision exists yet, so the reviewed-reference report currently has zero tasks. Once approved, compare the three methods to those frozen references and retain the 185-task mask-proxy run as an exploratory smoke test only. Add apple data separately for physical sizing once object-to-caliper matching and calibration are verified.
