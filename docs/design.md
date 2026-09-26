# Design and public boundary

The reusable surface is a versioned request/prediction contract, annotation records,
and an offline scorer. These serve both the public reference and external executables.
`schema.py` owns coordinates and validation; `evaluate.py` owns metrics;
`baseline.py` owns the textbook pipeline; `data.py` and `cli.py` own file/network I/O.
Dataset-specific conversion scripts should live in `scripts/` until their contracts
are supported by actual inspected releases. The registry is a curation queue.

This is protocol v1 and package 0.1: an initial public contract, not a promise of
long-term API stability. Schema changes require an explicit version/migration.

## Reference baseline

The baseline uses only standard operations:

1. Equally spaced samples from `start_xy` through `end_xy`, inclusive.
2. Bilinear interpolation across a straight rectangular strip and arithmetic mean.
3. A normalized discrete Gaussian with sigma 1 sample and radius 3; edge padding.
4. Centered finite differences (`numpy.gradient`).
5. Local extrema above a fixed normalized-intensity threshold of 0.01/sample.
6. Three-point quadratic peak interpolation, clamped to half a sample.

For responses a, b, c around a peak, the offset is
`0.5 * (a - c) / (a - 2*b + c)`. This is the elementary parabola-vertex formula;
see Julius O. Smith's [quadratic interpolation derivation](https://www.dsprelated.com/freebooks/sasp/Quadratic_Interpolation_Spectral_Peaks.html).
No source code was imported from third-party caliper implementations.

The CLI also offers two deliberately plain comparators on the same sampled and
smoothed profile: `gradient_integer` omits the parabolic offset, while
`midpoint_crossing` linearly interpolates the half-intensity crossing between
median endpoint levels on a single-edge strip. Their first real-image proxy run
and its limitations are recorded in `pilot-weld-profiles.md`.

Polarity requests are processed left-to-right with greedy strongest-peak selection.
This intentionally fails on many cluttered, weak or ambiguous boundaries. There is
no robust pair search, adaptive tuning, learned component, uncertainty estimator,
optimized implementation or proprietary method. Negative tasks return a false peak
when one is detected, so false positives are measured. Smoothing is in sample units;
changing sample spacing changes the effective image-space blur. Fix sampling for a
comparison and disclose it.

Only finite grayscale arrays in [0,1] are accepted. The CLI uses Pillow conversion
from 8-bit RGB/L to L and divides by 255; gamma is unchanged. Other formats require
explicit, recorded preprocessing. Out-of-bounds strips fail rather than silently
clamping to the image. Timer scope includes sampling through prediction construction
inputs, excludes decode/file I/O, and is recorded in a run sidecar.

## Contribution rule

Contribute dataset provenance, annotations, evaluation, documentation and elementary
reference fixes. Do not contribute employer code, advanced caliper designs, private
implementations or reverse-engineered product behavior. Keep private executables and
wrappers outside this checkout and exchange only protocol files. Public source review
is mandatory before expanding the reference baseline. CI uses generated in-memory
arrays solely for numerical invariants; these are not benchmark evidence.

Current limits: no annotation GUI, no released real-image labels, no automatic
source-specific label conversion, no calibration solver, and no production runner
sandbox. Acquisition is checksum-pinned local tooling; manual source inspection is
still required. Tests cover geometry, signed metrics, failure denominators, schema
validation, local paths, checksum enforcement and the Git content guard.
