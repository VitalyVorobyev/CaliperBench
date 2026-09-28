# First real-image pilot: weld profiles

**Status:** exploratory image/annotation collection. Source masks are **not caliper ground truth**; benchmark export from this pilot is disabled. The 2026-09-26 mask-proxy run below is a historical diagnostic, not a benchmark result. No physical measurements are present.

## Source and reproducibility

[Conquista's Zenodo v1 release](https://zenodo.org/records/20301441) (DOI `10.5281/zenodo.20301441`, CC BY 4.0) supplies 49 real VGA-camera weld-profile photos and 49 binary weld-region masks. We verified 98 files totaling 5,779,801 bytes against Zenodo's MD5 and committed a [metadata-only pin file](../registry/weld-profiles-v1-files.json) with local SHA-256 for every file. The images and masks live under ignored `data/raw/weld-profiles-2026/`; they are not in Git. The source's fixed camera setup does not provide verified metric calibration or independent physical dimensions.

The source labels **weld regions**, not precise optical edges. A closed mask can follow both the specimen/background silhouette and a weld/base-material boundary inside the bright metal. The latter is often weak or definition-dependent. This dataset is useful for testing difficult single-edge localization in chosen visible sections after review; it cannot support physical width error, and the full region contour should not be treated as a caliper reference by default. Images without a defensible visible boundary remain unapproved. The VGA resolution and one-reviewer pilot also limit subpixel claims.

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

A metadata-only [12-image selection](../registry/weld-pilot-v1.json) spans brightness, contrast, Laplacian blur response and mask-boundary contrast. The local GUI opens each real image with the source mask, a bounded classical active-contour proposal, editable contour, strip crossings and line profile. One reviewer may correct and approve a visible contour with stated uncertainty; normal-scan axes are aligned to that frozen contour and unique crossings are derived, while ambiguous or out-of-bounds scans are excluded. The four old vertical mask-proxy scans are only exploratory. Some mask boundaries separate weld metal from base material without a clear intensity edge, so a closed mask outline should not automatically become an edge reference. Freezing an edited contour preserves local work but does not make a benchmark reference. The closed weld-region outline can include ill-defined internal boundaries, so whole-contour-derived scans are ineligible for scoring. A later visible-edge subset would need segment-level validity and independent review. The next benchmark pilot should inspect Apple Fruitlet Sizing 2026 for matched physical caliper measurements and calibration.
