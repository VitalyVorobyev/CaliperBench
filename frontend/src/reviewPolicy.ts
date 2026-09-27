import type { ReviewDocument } from "./api";

/** UI preflight. The Python service remains the authority for contour intersections. */
export function canApproveReview(document: ReviewDocument | null): boolean {
  if (!document?.contour_reviewed || !document.reviewer.trim()) return false;
  return document.tasks.every(
    (task) =>
      task.disposition === "excluded" ||
      (task.disposition === "approved" &&
        task.crossing_px !== null &&
        task.uncertainty_px !== null &&
        task.uncertainty_px > 0),
  );
}
