export type Point = [number, number];
export type TaskReview = {
  sample_id: string;
  disposition: "pending" | "approved" | "excluded";
  crossing_px: number | null;
  uncertainty_px: number | null;
  confidence: "high" | "medium" | "low";
  note: string;
  frozen_request?: Request | null;
};
export type ReviewDocument = {
  schema_version: 1 | 2;
  image_id: string;
  source_image_sha256: string;
  source_mask_sha256: string;
  coordinate_system: "pixel-center";
  proposal_method: string;
  proposal_parameters: Record<string, unknown>;
  proposal_flags: string[];
  source_contour: Point[];
  proposed_contour: Point[];
  contour: Point[];
  contour_closed: boolean;
  contour_clip_sides: ("top" | "right" | "bottom" | "left")[];
  contour_target: "weld_region" | "visible_specimen";
  contour_edits: {
    method: "specimen_silhouette" | "manual_trace" | "edge_snap";
    parameters: Record<string, unknown>;
  }[];
  contour_reviewed: boolean;
  contour_uncertainty_px: number;
  tasks: TaskReview[];
  reviewer: string;
};
export type ImageRow = {
  id: string;
  name: string;
  task_count: number;
  reviewed: boolean;
  image_url: string;
};
export type Request = {
  sample_id: string;
  strip: { start_xy: Point; end_xy: Point; width_px: number; samples: number };
  polarities: string[];
};
export type Workspace = {
  document: ReviewDocument;
  etag: string;
  width: number;
  height: number;
  requests: Record<string, Request>;
  latest_revision: number | null;
};
export type Prediction = {
  status: "ok" | "failed";
  edges_px: number[];
  runtime_ms: number;
  reason: string | null;
};
export type Analysis = {
  predictions: Record<string, Record<string, Prediction>>;
  profiles: Record<string, number[]>;
};
export type MethodReport = {
  n: number;
  detection_failures: number;
  error_over_1px: number;
  failure_rate: number | null;
  mae_px: number | null;
  bias_px: number | null;
  median_runtime_ms: number | null;
};
export type Report = {
  reference: string;
  images: number;
  approved_tasks: number;
  reviewer_uncertainty_px: {
    mean: number | null;
    min: number | null;
    max: number | null;
  };
  methods: Record<string, MethodReport>;
  mask_proxy_context: {
    status: string;
    tasks: number;
    tolerance_px: number;
    methods: Record<
      string,
      {
        mae_px: number;
        bias_px: number;
        error_over_tolerance_rate: number;
        median_runtime_ms: number;
      }
    >;
  };
};

async function responseError(response: Response): Promise<Error> {
  const body = await response.text();
  try {
    const parsed: unknown = JSON.parse(body);
    if (
      parsed &&
      typeof parsed === "object" &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
    ) {
      return new Error(parsed.detail);
    }
  } catch {
    // Preserve non-JSON service errors below.
  }
  return new Error(`${response.status}: ${body}`);
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<T>;
}

export async function sendJson<T>(
  path: string,
  method: string,
  body?: unknown,
  etag?: string,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(etag ? { "If-Match": etag } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<T>;
}
