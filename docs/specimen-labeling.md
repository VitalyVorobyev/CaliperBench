# Visible specimen labeling on weld-profile photos

The supplied masks delineate weld regions. They are not outer-object outlines, precise optical edges, or physical dimensions. The left end of some metal specimens is outside the frame, so a complete object diameter or width cannot be recovered from those photos. A border-clipped segment must never be scored as a visible edge.

The review app offers two **proposal** starts for the visible metal silhouette:

1. **Suggest visible silhouette** converts the photo to grayscale, blurs it, applies Otsu's threshold, closes small gaps, retains the largest bright component, and extracts its contour. A frame-contact flag warns about truncation.
2. **Trace coarse outline** lets a reviewer place sparse points around the visible specimen. **Snap to visible edge** interpolates points along the outline, searches at most 1–20 pixels along each local normal, and selects a nearby smoothed-image gradient with a distance penalty. Weak-gradient vertices stay in place. The chosen radius is a search bound, not positional uncertainty.

Either route creates an editable local contour. Use the brush to correct corners, reflective areas, internal seams, and background artifacts; undo restores the prior contour. Source weld masks and the original proposal remain separate. The reviewer can freeze a revision for local investigation, but the app does not export these weld images as benchmark references.

For a later **edge-localization** subset, define which visible outer-boundary segments are in scope, exclude image-border closures and ambiguous/internal material transitions, collect independent reviewer corrections with uncertainty, and derive caliper scans normal to those accepted segments. For **physical-size** ground truth, use another dataset with a traceable measurement and calibration, such as the apple fruitlet candidate; a plausible image contour alone does not provide it.
