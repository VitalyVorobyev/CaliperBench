# Real-image annotation and controlled downsampling

Start with diverse real acquisitions, not a large count of similar strips. Pilot
roughly 20–50 images per source across contrast, reflection, blur, texture, occlusion,
orientation and adjacent edges. Inspect originals and licenses before selecting.
Keep a source manifest, image hashes and native dimensions. Prefer original camera
images; compressed paper screenshots, binarized exports and resized masks are poor
precision references.

1. Assign scene/object groups and development/validation/test splits first.
2. Define visible edge semantics: which material boundary, which side, and whether
   the target is a silhouette or an intensity transition. Exclude ambiguous edges
   from high-confidence localization; retain them as a labeled robustness stratum.
3. For the first weld pilot, one reviewer edits the visible contour at high zoom,
   without viewing detector outputs, then approves or excludes each crossing and assigns
   uncertainty. Record the source mask, classical proposal, reviewed contour, reviewer,
   revision and uncertainty locally. One review cannot measure inter-reviewer agreement;
   any later agreement claim requires independent duplicate annotations. Check source
   terms before publishing derived metadata.
4. Choose straight strips crossing locally near-straight boundaries. Declare whether
   the reference is the centerline intersection or a defined projected-profile
   transition. Curvature/tilt across a broad strip may make these different: narrow
   the strip or account for that uncertainty. Record no-edge strips for reliability.
5. Produce lower-resolution variants from the same high-resolution real image using
   a fixed documented antialias filter and integer factor s. Keep originals and all
   derivatives local. Record crop origin, scale, translation/phase, kernel, boundary
   handling, color space, quantization and software version.

## Coordinate transform

For pixel-center coordinates, integer area downsampling and crop origin `(cx,cy)`:

`x_low = (x_high - cx + 0.5)/s - 0.5`

and likewise for y. The first low-resolution center corresponds to high-resolution
center `cx + (s-1)/2`. Transform geometric points first, then intersect with the
new strip to obtain scan distances. Do not simply divide image coordinates by s.
Lengths scale by 1/s; offsets depend on the pixel-center convention. Rotations and
other resampling require an explicit transform, not this special-case equation.

Annotator uncertainty scales approximately by 1/s, but antialiasing, compression,
optical blur, calibration and boundary definition add uncertainty. Downsampling does
not create exact ground truth: label such data **high-resolution-derived proxy GT**.
Do not claim accuracy finer than its justified uncertainty. Blur can move the observed
intensity edge relative to the geometric silhouette; preserve this distinction.

For phase studies, vary the known sampling-grid translation of the same source and
record its component along the measurement axis and the exact resampling transform.
Only populate protocol `phases` when a one-dimensional sensor-phase interpretation
is valid. Keep all phases in one split and report correlated sample counts by source.

Physical sizing is a separate validation: match actual object/fruit IDs and acquisition
times to caliper records, document measurement axis and repeatability, and retain
camera/depth calibration and uncertainty. CAD nominal sizes and masks are not measured
as-built dimensions. No generic affine pixel-to-mm conversion is assumed.
