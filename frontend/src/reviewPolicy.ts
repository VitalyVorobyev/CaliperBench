import type { ReviewDocument } from "./api";

/** UI preflight. The Python service remains the authority for contour intersections. */
export function canApproveReview(document: ReviewDocument | null): boolean {
  return Boolean(
    document?.contour_reviewed &&
    document.reviewer.trim() &&
    Number.isFinite(document.contour_uncertainty_px) &&
    document.contour_uncertainty_px > 0,
  );
}
