import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  RotateCw,
  Save,
  ScanLine,
} from "lucide-react";
import {
  Badge,
  Button,
  Checkbox,
  Input,
  NumberInput,
  Select,
  Switch,
} from "@vitavision/ui";
import { describeFields, SchemaForm, type RawValues } from "@vitavision/forms";
import { LineProfile } from "@vitavision/charts";
import {
  ImageStage,
  MeasureOverlay,
  StageReadout,
  StageToolbar,
  imageViewBox,
  useStage,
  type MeasurePrimitive,
  type StageView,
} from "@vitavision/stage2d";
import {
  getJson,
  sendJson,
  type Analysis,
  type ImageRow,
  type Point,
  type Report,
  type ReviewDocument,
  type TaskReview,
  type Workspace,
} from "./api";
import { pointAt, stripLength } from "./geometry";
import { ContourLayer } from "./ContourLayer";
import { canApproveReview } from "./reviewPolicy";

const reviewFields = describeFields({
  properties: {
    reviewer: {
      type: "string",
      title: "Reviewer",
      description: "Name recorded in every approved revision",
      "x-primary": true,
    },
    default_uncertainty: {
      type: "number",
      title: "Default uncertainty (px)",
      description:
        "Applied when approving a crossing; edit each task if needed",
      default: 1,
      exclusiveMinimum: 0,
      "x-primary": true,
    },
  },
  required: ["reviewer"],
});
const METHODS = [
  "gradient_integer",
  "gradient_parabolic",
  "midpoint_crossing",
] as const;
const methodLabel: Record<string, string> = {
  gradient_integer: "Integer gradient",
  gradient_parabolic: "Parabolic gradient",
  midpoint_crossing: "Midpoint crossing",
};

function ContourDisplay({
  points,
  color,
  dash,
  fill = false,
}: {
  points: Point[];
  color: string;
  dash?: string;
  fill?: boolean;
}) {
  const stage = useStage();
  return (
    <svg
      viewBox={imageViewBox(stage.image)}
      className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
      aria-hidden="true"
    >
      <polygon
        points={points.map(([x, y]) => `${x},${y}`).join(" ")}
        fill={fill ? color : "none"}
        fillOpacity={fill ? 0.16 : undefined}
        stroke={color}
        strokeDasharray={dash}
        strokeWidth={stage.imageLength(1.4)}
      />
    </svg>
  );
}

function StageContent({
  workspace,
  task,
  showMask,
  showReviewedMask,
  showOriginal,
  showProposal,
  editContour,
  onContourChange,
  onContourStart,
  showResults,
  analysis,
}: {
  workspace: Workspace;
  task: TaskReview | undefined;
  showMask: boolean;
  showReviewedMask: boolean;
  showOriginal: boolean;
  showProposal: boolean;
  editContour: boolean;
  onContourChange: (points: Point[]) => void;
  onContourStart: () => void;
  showResults: boolean;
  analysis: Analysis | null;
}) {
  const stage = useStage();
  const imageId = workspace.document.image_id;
  const request = task ? workspace.requests[task.sample_id] : undefined;
  const primitives: MeasurePrimitive[] = [];
  if (request) {
    const [a, b] = [request.strip.start_xy, request.strip.end_xy];
    primitives.push({
      kind: "caliper",
      cx: (a[0] + b[0]) / 2,
      cy: (a[1] + b[1]) / 2,
      width: stripLength(request),
      height: Math.max(2, request.strip.width_px),
      angle: Math.atan2(b[1] - a[1], b[0] - a[0]),
      tone: "signal",
    });
    if (task?.crossing_px !== null && task?.crossing_px !== undefined) {
      const [x, y] = pointAt(request, task.crossing_px);
      primitives.push({
        kind: "point",
        x,
        y,
        cross: true,
        tone: task.disposition === "approved" ? "normal" : "warn",
        label: "Reference",
      });
    }
    if (showResults && analysis) {
      METHODS.forEach((method) => {
        const result = analysis.predictions[task!.sample_id]?.[method];
        if (result?.status === "ok" && result.edges_px[0] !== undefined) {
          const [x, y] = pointAt(request, result.edges_px[0]);
          primitives.push({
            kind: "point",
            x,
            y,
            tone: method === "gradient_parabolic" ? "defect" : "muted",
            label: methodLabel[method],
          });
        }
      });
    }
  }
  return (
    <>
      <img
        src={`/api/images/${encodeURIComponent(imageId)}/source`}
        alt={`Weld profile ${imageId}`}
        draggable={false}
        className="cb-overlay-img"
      />
      {showMask && (
        <img
          src={`/api/images/${encodeURIComponent(imageId)}/mask`}
          alt=""
          draggable={false}
          className="cb-overlay-img"
          style={{ opacity: 0.28, mixBlendMode: "screen" }}
        />
      )}
      {showOriginal && (
        <ContourDisplay
          points={workspace.document.source_contour}
          color="var(--warn)"
          dash="5 4"
        />
      )}
      {showProposal && (
        <ContourDisplay
          points={workspace.document.proposed_contour}
          color="var(--defect)"
          dash="3 3"
        />
      )}
      {showReviewedMask && (
        <ContourDisplay
          points={workspace.document.contour}
          color="var(--signal)"
          fill
        />
      )}
      <ContourLayer
        points={workspace.document.contour}
        onChange={onContourChange}
        onEditStart={onContourStart}
        editable={editContour}
      />
      <MeasureOverlay
        nativeWidth={workspace.width}
        nativeHeight={workspace.height}
        primitives={primitives}
        strokeScale={stage.view.scale}
      />
    </>
  );
}

export function App() {
  const [images, setImages] = useState<ImageRow[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [document, setDocument] = useState<ReviewDocument | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [taskIndex, setTaskIndex] = useState(0);
  const [view, setView] = useState<StageView | null>(null);
  const [status, setStatus] = useState("Loading pilot…");
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [editContour, setEditContour] = useState(false);
  const [showMask, setShowMask] = useState(false);
  const [showReviewedMask, setShowReviewedMask] = useState(false);
  const [showOriginal, setShowOriginal] = useState(true);
  const [showProposal, setShowProposal] = useState(true);
  const [showResults, setShowResults] = useState(false);
  const [resultsUnlocked, setResultsUnlocked] = useState(false);
  const [reviewValues, setReviewValues] = useState<RawValues>({
    reviewer: "",
    default_uncertainty: "1",
  });
  const etag = useRef("");
  const currentDocument = useRef<ReviewDocument | null>(null);
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const undo = useRef<ReviewDocument[]>([]);
  const redo = useRef<ReviewDocument[]>([]);

  const refreshIndex = useCallback(async () => {
    const [rows, summary] = await Promise.all([
      getJson<ImageRow[]>("/api/images"),
      getJson<Report>("/api/report"),
    ]);
    setImages(rows);
    setReport(summary);
    return rows;
  }, []);

  useEffect(() => {
    refreshIndex()
      .then((rows) => setSelected(rows[0]?.id ?? null))
      .catch((e) => {
        setError(String(e));
        setStatus("Could not load pilot");
      });
  }, [refreshIndex]);
  useEffect(() => {
    if (!selected) return;
    let live = true;
    setWorkspace(null);
    setAnalysis(null);
    setStatus("Opening image…");
    setError("");
    setTaskIndex(0);
    setView(null);
    setShowResults(false);
    setEditContour(false);
    Promise.all([
      getJson<Workspace>(
        `/api/images/${encodeURIComponent(selected)}/workspace`,
      ),
      getJson<Analysis>(`/api/images/${encodeURIComponent(selected)}/analysis`),
    ])
      .then(([next, predictions]) => {
        if (!live) return;
        setWorkspace(next);
        setDocument(next.document);
        currentDocument.current = next.document;
        etag.current = next.etag;
        setReviewValues({
          reviewer: next.document.reviewer,
          default_uncertainty: "1",
        });
        setAnalysis(predictions);
        setResultsUnlocked(next.latest_revision !== null);
        setDirty(false);
        undo.current = [];
        redo.current = [];
        setStatus(
          next.latest_revision
            ? `Approved revision ${next.latest_revision}`
            : "Draft · unreviewed",
        );
      })
      .catch((e) => {
        if (live) {
          setError(String(e));
          setStatus("Could not open image");
        }
      });
    return () => {
      live = false;
    };
  }, [selected]);

  const checkpoint = useCallback(() => {
    if (currentDocument.current) {
      undo.current = [
        ...undo.current.slice(-79),
        structuredClone(currentDocument.current),
      ];
      redo.current = [];
    }
  }, []);
  const update = useCallback(
    (next: ReviewDocument, record = true) => {
      if (record) checkpoint();
      currentDocument.current = next;
      setDocument(next);
      setDirty(true);
      setStatus("Unsaved changes");
      setResultsUnlocked(false);
      setShowResults(false);
    },
    [checkpoint],
  );
  const saveNow = useCallback(async () => {
    const snapshot = currentDocument.current;
    if (!selected || !snapshot || !dirty) return;
    saveQueue.current = saveQueue.current
      .catch(() => undefined)
      .then(async () => {
        const result = await sendJson<{ etag: string }>(
          `/api/images/${encodeURIComponent(selected)}/draft`,
          "PUT",
          snapshot,
          etag.current,
        );
        etag.current = result.etag;
        if (currentDocument.current === snapshot) {
          setDirty(false);
          setStatus("Draft saved");
        }
      });
    try {
      await saveQueue.current;
      setError("");
    } catch (e) {
      setError(String(e));
      setStatus("Save failed — review before leaving");
      throw e;
    }
  }, [selected, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(() => {
      void saveNow().catch(() => undefined);
    }, 900);
    return () => window.clearTimeout(timer);
  }, [document, dirty, saveNow]);

  const navigate = useCallback(
    async (imageId: string) => {
      if (imageId === selected) return;
      if (dirty) {
        try {
          await saveNow();
        } catch {
          return;
        }
      }
      setSelected(imageId);
    },
    [dirty, saveNow, selected],
  );
  const restore = (direction: "undo" | "redo") => {
    const from = direction === "undo" ? undo.current : redo.current;
    const to = direction === "undo" ? redo.current : undo.current;
    const previous = from.pop();
    if (!previous || !currentDocument.current) return;
    to.push(structuredClone(currentDocument.current));
    update(previous, false);
  };
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (
        event.target instanceof HTMLElement &&
        event.target.closest(
          "input, textarea, [role=dialog], [contenteditable=true]",
        )
      )
        return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        restore(event.shiftKey ? "redo" : "undo");
      } else if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "y"
      ) {
        event.preventDefault();
        restore("redo");
      } else if (event.key === "j" || event.key === "k") {
        const index = images.findIndex((row) => row.id === selected);
        const target = images[index + (event.key === "j" ? 1 : -1)];
        if (target) void navigate(target.id);
      } else if (event.key === "[" || event.key === "]")
        setTaskIndex((index) =>
          Math.max(
            0,
            Math.min(
              (document?.tasks.length ?? 1) - 1,
              index + (event.key === "]" ? 1 : -1),
            ),
          ),
        );
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  });

  const task = document?.tasks[taskIndex];
  const request = task ? workspace?.requests[task.sample_id] : undefined;
  const profile = task ? analysis?.profiles[task.sample_id] : undefined;
  const marks = useMemo(() => {
    if (!task) return [];
    const result: {
      position: number;
      label: string;
      tone: "normal" | "defect" | "muted";
    }[] = [];
    if (task.crossing_px !== null)
      result.push({
        position: task.crossing_px,
        label: task.disposition === "approved" ? "Reviewed" : "Draft",
        tone: "normal",
      });
    if (showResults && resultsUnlocked && analysis)
      METHODS.forEach((method) => {
        const prediction = analysis.predictions[task.sample_id]?.[method];
        if (prediction?.status === "ok" && prediction.edges_px[0] !== undefined)
          result.push({
            position: prediction.edges_px[0],
            label: methodLabel[method],
            tone: method === "gradient_parabolic" ? "defect" : "muted",
          });
      });
    return result;
  }, [task, showResults, resultsUnlocked, analysis]);

  const setTask = (patch: Partial<TaskReview>) => {
    if (!document || !task) return;
    update({
      ...document,
      tasks: document.tasks.map((item, index) =>
        index === taskIndex ? { ...item, ...patch } : item,
      ),
    });
  };
  const approve = async () => {
    if (!selected || !document) return;
    try {
      if (dirty) await saveNow();
      const result = await sendJson<{ revision_id: number }>(
        `/api/images/${encodeURIComponent(selected)}/approve`,
        "POST",
        undefined,
        etag.current,
      );
      setWorkspace((current) =>
        current ? { ...current, latest_revision: result.revision_id } : current,
      );
      setResultsUnlocked(true);
      setStatus(`Approved revision ${result.revision_id}`);
      setError("");
      await refreshIndex();
    } catch (e) {
      setError(String(e));
    }
  };
  const exportApproved = async () => {
    try {
      const result = await sendJson<{ count: number; path: string }>(
        "/api/export",
        "POST",
      );
      setStatus(`Exported ${result.count} approved tasks to ${result.path}`);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="cb-shell">
      <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-4">
        <div className="flex items-center gap-2">
          <ScanLine className="h-5 w-5 text-signal" aria-hidden />
          <strong className="text-sm tracking-tight">CaliperBench</strong>
          <span className="text-xs text-fg-muted">/ Review studio</span>
        </div>
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={`cb-status truncate ${error ? "cb-error" : ""}`}
            role="status"
          >
            {error || status}
          </span>
          <Button
            size="sm"
            icon={<Save />}
            disabled={!dirty}
            onClick={() => void saveNow().catch(() => undefined)}
          >
            Save draft
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<Check />}
            disabled={!canApproveReview(document)}
            onClick={() => void approve()}
          >
            Approve revision
          </Button>
        </div>
      </header>
      <main className="cb-main">
        <aside className="cb-sidebar" aria-label="Pilot images">
          <div className="cb-section">
            <p className="cb-label">Weld pilot · 12 images</p>
            <p className="mt-2 text-xs text-fg-muted">
              Real images, source masks and classical contour proposals.
              Approval is per image and crossing.
            </p>
          </div>
          {images.map((row) => (
            <button
              key={row.id}
              className="cb-file"
              data-active={row.id === selected}
              onClick={() => void navigate(row.id)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{row.name}</span>
                <span
                  className={row.reviewed ? "text-normal" : "text-fg-subtle"}
                  aria-label={row.reviewed ? "Reviewed" : "Unreviewed"}
                >
                  {row.reviewed ? "✓" : "○"}
                </span>
              </div>
              <span className="text-xs text-fg-muted">
                {row.task_count} strips
              </span>
            </button>
          ))}
          <div className="cb-section">
            <p className="cb-label">Reviewed reference</p>
            <p className="mt-1 text-sm">
              {report?.images ?? 0} / {images.length} images
            </p>
            <p className="text-xs text-fg-muted">
              {report?.approved_tasks ?? 0} approved crossings
            </p>
            <Button
              size="sm"
              className="mt-3"
              onClick={() => void exportApproved()}
            >
              Export JSONL
            </Button>
          </div>
        </aside>
        <section className="cb-stage" aria-label="Image and measurements">
          <div className="cb-stage-frame">
            {workspace && document ? (
              <ImageStage
                image={{ width: workspace.width, height: workspace.height }}
                view={view}
                onView={setView}
                label="Weld image review canvas"
                toolbar={<StageToolbar />}
                readout={<StageReadout cursor={null} />}
                panKeys={!editContour}
              >
                <StageContent
                  workspace={{ ...workspace, document }}
                  task={task}
                  showMask={showMask}
                  showReviewedMask={showReviewedMask}
                  showOriginal={showOriginal}
                  showProposal={showProposal}
                  editContour={editContour}
                  onContourStart={checkpoint}
                  onContourChange={(points) =>
                    update(
                      { ...document, contour: points, contour_reviewed: false },
                      false,
                    )
                  }
                  showResults={showResults && resultsUnlocked}
                  analysis={analysis}
                />
              </ImageStage>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-white/70">
                {status}
              </div>
            )}
          </div>
          <div className="cb-profile p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="cb-label">
                Scan profile {task ? `· ${task.sample_id}` : ""}
              </span>
              <span className="cb-mini text-xs text-fg-muted">
                {request ? `${stripLength(request).toFixed(1)} px` : ""}
              </span>
            </div>
            {profile && request ? (
              <LineProfile
                label={`Intensity profile for ${task?.sample_id}`}
                series={[
                  {
                    name: "Grayscale intensity",
                    points: profile.map((y, index) => ({
                      x: (index * stripLength(request)) / (profile.length - 1),
                      y,
                    })),
                  },
                ]}
                edges={marks}
                xDomain={[0, stripLength(request)]}
                yDomain={[0, 1]}
                variant="wide"
              />
            ) : (
              <p className="text-xs text-fg-muted">
                Select a strip to inspect its image signal.
              </p>
            )}
          </div>
        </section>
        <aside className="cb-inspector" aria-label="Review controls">
          <div className="cb-section">
            <p className="cb-label">
              {selected ? `Image ${selected}` : "Select an image"}
            </p>
            <p className="mt-1 text-sm font-medium">Visible edge review</p>
            <p className="mt-1 text-xs text-fg-muted">
              Source mask → classical refinement → your contour and crossings.
              Only an approved revision enters the benchmark.
            </p>
            {document?.proposal_flags.length ? (
              <div className="mt-3 rounded border border-warn/40 bg-warn/10 p-2 text-xs text-warn">
                Proposal flags: {document.proposal_flags.join(", ")}
              </div>
            ) : null}
          </div>
          {document && (
            <>
              <div className="cb-section space-y-3">
                <p className="cb-label">Layers &amp; editing</p>
                <Switch
                  label="Source mask"
                  checked={showMask}
                  onCheckedChange={setShowMask}
                />
                <Switch
                  label="Edited mask preview"
                  checked={showReviewedMask}
                  onCheckedChange={setShowReviewedMask}
                />
                <Switch
                  label="Original mask contour"
                  checked={showOriginal}
                  onCheckedChange={setShowOriginal}
                />
                <Switch
                  label="Refined proposal"
                  checked={showProposal}
                  onCheckedChange={setShowProposal}
                />
                <Switch
                  label="Edit reviewed contour"
                  checked={editContour}
                  onCheckedChange={setEditContour}
                />
                <Checkbox
                  label="I reviewed the visible contour"
                  checked={document.contour_reviewed}
                  onCheckedChange={(value) =>
                    update({ ...document, contour_reviewed: value })
                  }
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    icon={<RotateCcw />}
                    disabled={!undo.current.length}
                    onClick={() => restore("undo")}
                  >
                    Undo
                  </Button>
                  <Button
                    size="sm"
                    icon={<RotateCw />}
                    disabled={!redo.current.length}
                    onClick={() => restore("redo")}
                  >
                    Redo
                  </Button>
                </div>
                <p className="text-xs text-fg-muted">
                  Drag points, double click the outline to add one, or focus a
                  point and use arrow keys. Shift + arrow moves 0.1 px.
                </p>
              </div>
              <div className="cb-section">
                <div className="mb-3 flex items-center justify-between">
                  <p className="cb-label">Caliper strips</p>
                  <span className="text-xs text-fg-muted">
                    {taskIndex + 1} / {document.tasks.length}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {document.tasks.map((item, index) => (
                    <button
                      key={item.sample_id}
                      className={`rounded px-2 py-1 text-xs ${index === taskIndex ? "bg-signal text-signal-fg" : "bg-raised text-fg-muted"}`}
                      onClick={() => setTaskIndex(index)}
                      aria-label={`Strip ${index + 1}: ${item.disposition}`}
                    >
                      {index + 1}
                      {item.disposition === "approved"
                        ? " ✓"
                        : item.disposition === "excluded"
                          ? " ×"
                          : ""}
                    </button>
                  ))}
                </div>
                {task && request && (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="cb-mini text-xs">{task.sample_id}</span>
                      <Badge
                        tone={
                          task.disposition === "approved" ? "normal" : "neutral"
                        }
                      >
                        {task.disposition}
                      </Badge>
                    </div>
                    <label className="block text-xs font-medium">
                      Reference crossing · scan distance (px)
                      <NumberInput
                        className="mt-1"
                        value={task.crossing_px ?? ""}
                        min={0}
                        max={stripLength(request)}
                        step="any"
                        onChange={(e) =>
                          setTask({
                            crossing_px:
                              e.target.value === ""
                                ? null
                                : Number(e.target.value),
                            disposition: "pending",
                          })
                        }
                      />
                    </label>
                    <label className="block text-xs font-medium">
                      Uncertainty (px)
                      <NumberInput
                        className="mt-1"
                        value={task.uncertainty_px ?? ""}
                        min={0.001}
                        step="any"
                        onChange={(e) =>
                          setTask({
                            uncertainty_px:
                              e.target.value === ""
                                ? null
                                : Number(e.target.value),
                            disposition: "pending",
                          })
                        }
                      />
                    </label>
                    <label className="block text-xs font-medium">
                      Confidence
                      <Select
                        className="mt-1"
                        value={task.confidence}
                        onValueChange={(value) =>
                          setTask({
                            confidence: value as TaskReview["confidence"],
                          })
                        }
                        options={[
                          { value: "high", label: "High" },
                          { value: "medium", label: "Medium" },
                          { value: "low", label: "Low" },
                        ]}
                      />
                    </label>
                    <label className="block text-xs font-medium">
                      Review note
                      <Input
                        className="mt-1"
                        value={task.note}
                        onChange={(e) => setTask({ note: e.target.value })}
                      />
                    </label>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={task.crossing_px === null}
                        onClick={() =>
                          setTask({
                            disposition: "approved",
                            uncertainty_px:
                              task.uncertainty_px ??
                              Number(reviewValues.default_uncertainty || 1),
                          })
                        }
                      >
                        Approve crossing
                      </Button>
                      <Button
                        size="sm"
                        onClick={() =>
                          setTask({
                            disposition: "excluded",
                            note: task.note || "ambiguous_visible_edge",
                          })
                        }
                      >
                        Exclude
                      </Button>
                    </div>
                    <div className="flex justify-between">
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<ChevronLeft />}
                        disabled={taskIndex === 0}
                        onClick={() => setTaskIndex((index) => index - 1)}
                      >
                        Previous
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<ChevronRight />}
                        disabled={taskIndex === document.tasks.length - 1}
                        onClick={() => setTaskIndex((index) => index + 1)}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
              <div className="cb-section">
                <p className="cb-label mb-3">Review identity</p>
                <SchemaForm
                  fields={reviewFields}
                  values={reviewValues}
                  onChange={(next) => {
                    setReviewValues(next);
                    if (next.reviewer !== reviewValues.reviewer)
                      update({
                        ...document,
                        reviewer: String(next.reviewer ?? ""),
                      });
                  }}
                />
              </div>
              <div className="cb-section space-y-3">
                <p className="cb-label">Baseline comparison</p>
                <Switch
                  label="Show textbook predictions"
                  description={
                    resultsUnlocked
                      ? "Available after approval; hidden during editing"
                      : "Approve this revision to unlock comparison"
                  }
                  checked={showResults && resultsUnlocked}
                  disabled={!resultsUnlocked}
                  onCheckedChange={setShowResults}
                />
                {showResults && resultsUnlocked && task && analysis && (
                  <div className="rounded border border-line bg-raised p-2 text-xs">
                    <p className="mb-1 font-medium">
                      Selected strip · {task.sample_id}
                    </p>
                    {METHODS.map((method) => {
                      const prediction =
                        analysis.predictions[task.sample_id]?.[method];
                      const error =
                        prediction?.status === "ok" &&
                        prediction.edges_px[0] !== undefined &&
                        task.crossing_px !== null
                          ? prediction.edges_px[0] - task.crossing_px
                          : null;
                      return (
                        <p key={method} className="flex justify-between gap-2">
                          <span>{methodLabel[method]}</span>
                          <span className="cb-mini">
                            {error === null
                              ? "failed"
                              : `${error >= 0 ? "+" : ""}${error.toFixed(2)} px`}
                          </span>
                        </p>
                      );
                    })}
                  </div>
                )}
                {report && report.approved_tasks > 0 && (
                  <div className="space-y-2 text-xs">
                    <p className="font-medium">
                      Reviewed reference · {report.approved_tasks} crossings
                    </p>
                    {METHODS.map((method) => (
                      <div key={method} className="border-b border-line pb-1">
                        <div className="flex justify-between gap-2">
                          <span>{methodLabel[method]}</span>
                          <span className="cb-mini">
                            {report.methods[method]?.mae_px?.toFixed(2) ?? "—"}{" "}
                            px MAE
                          </span>
                        </div>
                        <p className="text-fg-muted">
                          Bias{" "}
                          {report.methods[method]?.bias_px?.toFixed(2) ?? "—"}{" "}
                          px · failure{" "}
                          {(
                            (report.methods[method]?.failure_rate ?? 0) * 100
                          ).toFixed(1)}
                          % ·{" "}
                          {report.methods[method]?.median_runtime_ms?.toFixed(
                            2,
                          ) ?? "—"}{" "}
                          ms
                        </p>
                      </div>
                    ))}
                    <p className="text-fg-muted">
                      Reviewer-assigned uncertainty: mean{" "}
                      {report.reviewer_uncertainty_px.mean?.toFixed(2) ?? "—"}{" "}
                      px. This is not measured agreement.
                    </p>
                  </div>
                )}
                {report && (
                  <div className="border-t border-line pt-2 text-xs text-fg-muted">
                    <p className="font-medium">
                      Exploratory mask proxy · {report.mask_proxy_context.tasks}{" "}
                      tasks
                    </p>
                    {METHODS.map((method) => (
                      <p key={method}>
                        {methodLabel[method]}:{" "}
                        {report.mask_proxy_context.methods[
                          method
                        ]?.mae_px.toFixed(2)}{" "}
                        px MAE
                      </p>
                    ))}
                    <p>
                      Different, unreviewed reference and sample count; for
                      context only.
                    </p>
                  </div>
                )}
              </div>
              <div className="cb-section text-xs text-fg-muted">
                <p className="cb-label mb-2">Provenance</p>
                <p>Weld profiles · Zenodo v1 · CC BY 4.0</p>
                <p className="mt-1 cb-mini break-all">
                  Image SHA-256: {document.source_image_sha256}
                </p>
                <p className="mt-1">{document.proposal_method}</p>
              </div>
            </>
          )}
        </aside>
      </main>
    </div>
  );
}
