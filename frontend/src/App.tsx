import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Check,
  ChartLine,
  Eye,
  Image as ImageIcon,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  RotateCcw,
  RotateCw,
  Save,
  ScanLine,
} from "lucide-react";
import {
  Button,
  Checkbox,
  NumberInput,
  Switch,
  Tabs,
  Tooltip,
  TooltipProvider,
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
    contour_uncertainty_px: {
      type: "number",
      title: "Contour uncertainty (px)",
      description:
        "Reviewer-assigned allowance for contour-derived crossings; not measured agreement",
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

function LayerTool({
  label,
  active,
  onClick,
  children,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip content={label}>
      <button
        type="button"
        className="cb-tool"
        aria-label={label}
        aria-pressed={active}
        data-active={active}
        onClick={onClick}
      >
        {children}
      </button>
    </Tooltip>
  );
}

function StageContent({
  workspace,
  task,
  showMask,
  showReviewedMask,
  showOriginal,
  showProposal,
  showScan,
  brushRadius,
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
  showScan: boolean;
  brushRadius: number;
  editContour: boolean;
  onContourChange: (points: Point[]) => void;
  onContourStart: () => void;
  showResults: boolean;
  analysis: Analysis | null;
}) {
  const stage = useStage();
  const fitted = useRef(false);
  useEffect(() => {
    if (!fitted.current && stage.box.width > 0 && stage.box.height > 0) {
      fitted.current = true;
      stage.fit();
    }
  }, [stage.box.width, stage.box.height, stage.fit]);
  const imageId = workspace.document.image_id;
  const request = task ? workspace.requests[task.sample_id] : undefined;
  const primitives: MeasurePrimitive[] = [];
  if (request && showScan) {
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
    if (
      showResults &&
      task?.crossing_px !== null &&
      task?.crossing_px !== undefined &&
      task?.disposition === "approved"
    ) {
      const [x, y] = pointAt(request, task.crossing_px);
      primitives.push({
        kind: "point",
        x,
        y,
        cross: true,
        tone: task.disposition === "approved" ? "normal" : "warn",
        label: "Contour reference",
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
        style={{ imageRendering: stage.view.scale >= 4 ? "pixelated" : "auto" }}
      />
      {showMask && (
        <img
          src={`/api/images/${encodeURIComponent(imageId)}/mask`}
          alt=""
          draggable={false}
          className="cb-overlay-img"
          style={{
            opacity: 0.28,
            mixBlendMode: "screen",
            imageRendering: "pixelated",
          }}
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
        brushRadius={brushRadius}
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
  const [editContour, setEditContour] = useState(true);
  const [showMask, setShowMask] = useState(false);
  const [showReviewedMask, setShowReviewedMask] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [showProposal, setShowProposal] = useState(false);
  const [brushRadius, setBrushRadius] = useState(24);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [profileOpen, setProfileOpen] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<"review" | "settings">(
    "review",
  );
  const [showResults, setShowResults] = useState(false);
  const [resultsUnlocked, setResultsUnlocked] = useState(false);
  const [reviewValues, setReviewValues] = useState<RawValues>({
    reviewer: "",
    contour_uncertainty_px: "1",
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
    setEditContour(true);
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
          contour_uncertainty_px: String(next.document.contour_uncertainty_px),
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
              (document?.tasks.filter((item) =>
                item.sample_id.includes(":contour:"),
              ).length ?? 1) - 1,
              index + (event.key === "]" ? 1 : -1),
            ),
          ),
        );
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  });

  const contourTasks =
    document?.tasks.filter((item) => item.sample_id.includes(":contour:")) ??
    [];
  const task = contourTasks[taskIndex];
  const request = task ? workspace?.requests[task.sample_id] : undefined;
  const profile = task ? analysis?.profiles[task.sample_id] : undefined;
  const marks = useMemo(() => {
    if (!task) return [];
    const result: {
      position: number;
      label: string;
      tone: "normal" | "defect" | "muted";
    }[] = [];
    if (
      showResults &&
      resultsUnlocked &&
      task.crossing_px !== null &&
      task.disposition === "approved"
    )
      result.push({
        position: task.crossing_px,
        label: "Contour reference",
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
      const [next, frozenAnalysis] = await Promise.all([
        getJson<Workspace>(
          `/api/images/${encodeURIComponent(selected)}/workspace`,
        ),
        getJson<Analysis>(
          `/api/images/${encodeURIComponent(selected)}/analysis`,
        ),
      ]);
      setWorkspace(next);
      setAnalysis(frozenAnalysis);
      setDocument(next.document);
      currentDocument.current = next.document;
      etag.current = next.etag;
      setDirty(false);
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
    <TooltipProvider>
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
        <main className="cb-main" data-sidebar-open={sidebarOpen}>
          <aside
            className="cb-sidebar"
            aria-label="Pilot images"
            data-open={sidebarOpen}
          >
            <div className="cb-sidebar-top">
              {sidebarOpen && (
                <div>
                  <p className="cb-label">Weld pilot</p>
                  <p className="text-xs text-fg-muted">
                    {images.length} real images · {report?.images ?? 0} reviewed
                  </p>
                </div>
              )}
              <Tooltip
                content={
                  sidebarOpen
                    ? "Collapse image browser"
                    : "Expand image browser"
                }
              >
                <button
                  type="button"
                  className="cb-tool"
                  aria-label={
                    sidebarOpen
                      ? "Collapse image browser"
                      : "Expand image browser"
                  }
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                >
                  {sidebarOpen ? (
                    <PanelLeftClose size={17} />
                  ) : (
                    <PanelLeftOpen size={17} />
                  )}
                </button>
              </Tooltip>
            </div>
            {sidebarOpen && (
              <>
                <div
                  className="cb-thumbnails"
                  aria-label="Pilot image previews"
                >
                  {images.map((row) => (
                    <button
                      key={row.id}
                      type="button"
                      className="cb-thumb"
                      data-active={row.id === selected}
                      onClick={() => void navigate(row.id)}
                      aria-label={`${row.name}, ${row.reviewed ? "reviewed" : "unreviewed"}`}
                    >
                      <img src={row.image_url} alt="" loading="lazy" />
                      <span className="cb-thumb-meta">
                        <span className="truncate">{row.name}</span>
                        <span
                          className={
                            row.reviewed ? "text-normal" : "text-fg-muted"
                          }
                        >
                          {row.reviewed ? "✓" : "○"}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
                <div className="cb-sidebar-footer">
                  <p className="cb-label">Current image</p>
                  <p
                    className="cb-mini truncate text-xs"
                    title={images.find((row) => row.id === selected)?.name}
                  >
                    {images.find((row) => row.id === selected)?.name ?? "—"}
                  </p>
                  <div className="mt-2 flex items-center justify-between gap-2 text-xs text-fg-muted">
                    <span>
                      {report?.approved_tasks ?? 0} approved crossings
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void exportApproved()}
                    >
                      Export
                    </Button>
                  </div>
                </div>
              </>
            )}
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
                    showScan={profileOpen}
                    brushRadius={brushRadius}
                    editContour={editContour}
                    onContourStart={checkpoint}
                    onContourChange={(points) =>
                      update(
                        {
                          ...document,
                          contour: points,
                          contour_reviewed: false,
                        },
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
            <div className="cb-profile" data-open={profileOpen}>
              <div className="cb-profile-head">
                <span className="cb-label">
                  Scan profile{" "}
                  {task ? `· ${taskIndex + 1} of ${contourTasks.length}` : ""}
                </span>
                <div className="flex items-center gap-2">
                  <span className="cb-mini text-xs text-fg-muted">
                    {request ? `${stripLength(request).toFixed(1)} px` : ""}
                  </span>
                  <Tooltip
                    content={
                      profileOpen
                        ? "Collapse scan profile"
                        : "Expand scan profile"
                    }
                  >
                    <button
                      type="button"
                      className="cb-profile-toggle"
                      onClick={() => setProfileOpen(!profileOpen)}
                      aria-label={
                        profileOpen
                          ? "Collapse scan profile"
                          : "Expand scan profile"
                      }
                      aria-expanded={profileOpen}
                    >
                      <ChartLine size={16} />
                    </button>
                  </Tooltip>
                </div>
              </div>
              {profileOpen &&
                (profile && request ? (
                  <LineProfile
                    label={`Intensity profile for ${task?.sample_id}`}
                    series={[
                      {
                        name: "Grayscale intensity",
                        points: profile.map((y, index) => ({
                          x:
                            (index * stripLength(request)) /
                            (profile.length - 1),
                          y,
                        })),
                      },
                    ]}
                    edges={marks}
                    xDomain={[0, stripLength(request)]}
                    yDomain={[0, 1]}
                    variant="wide"
                    xLabel="scan distance (px)"
                    yLabel="intensity"
                  />
                ) : (
                  <p className="px-3 pb-3 text-xs text-fg-muted">
                    No scan available for this contour.
                  </p>
                ))}
            </div>
          </section>
          <aside className="cb-inspector" aria-label="Review controls">
            <div className="cb-inspector-tabs">
              <Tabs
                items={[
                  { id: "review", label: "Review" },
                  { id: "settings", label: "Settings" },
                ]}
                active={inspectorTab}
                onSelect={setInspectorTab}
                label="Inspector views"
                idPrefix="inspector"
              />
            </div>
            {document && inspectorTab === "review" && (
              <div
                role="tabpanel"
                id="inspector-panel-review"
                aria-labelledby="inspector-tab-review"
              >
                <div className="cb-section cb-review-intro">
                  <p className="text-sm font-semibold">Weld-region boundary</p>
                  <p className="mt-2 text-xs text-fg-muted">
                    The source mask isolates a weld region, including boundaries
                    that may be visually ambiguous. Correct only defensible
                    visible transitions; leave unsuitable images unapproved.
                  </p>
                  {document.proposal_flags.length > 0 && (
                    <p className="mt-2 text-xs text-warn">
                      The automatic contour needs careful review, especially
                      near corners.
                    </p>
                  )}
                </div>
                <div className="cb-section cb-layer-section">
                  <div
                    className="cb-layer-tools"
                    role="group"
                    aria-label="Layers and editing tools"
                  >
                    <LayerTool
                      label="Source mask"
                      active={showMask}
                      onClick={() => setShowMask(!showMask)}
                    >
                      <ImageIcon size={18} />
                    </LayerTool>
                    <LayerTool
                      label="Edited mask preview"
                      active={showReviewedMask}
                      onClick={() => setShowReviewedMask(!showReviewedMask)}
                    >
                      <Layers size={18} />
                    </LayerTool>
                    <LayerTool
                      label="Original mask contour"
                      active={showOriginal}
                      onClick={() => setShowOriginal(!showOriginal)}
                    >
                      <Eye size={18} />
                    </LayerTool>
                    <LayerTool
                      label="Refined contour proposal"
                      active={showProposal}
                      onClick={() => setShowProposal(!showProposal)}
                    >
                      <ScanLine size={18} />
                    </LayerTool>
                    <LayerTool
                      label="Reshape contour"
                      active={editContour}
                      onClick={() => setEditContour(!editContour)}
                    >
                      <Pencil size={18} />
                    </LayerTool>
                  </div>
                  <div className="mt-4">
                    <label
                      className="flex items-center justify-between gap-2 text-xs font-medium"
                      htmlFor="brush-radius"
                    >
                      <span>Contour brush radius</span>
                      <span className="cb-mini">{brushRadius} px</span>
                    </label>
                    <input
                      id="brush-radius"
                      className="cb-range mt-2"
                      type="range"
                      min={2}
                      max={80}
                      step={1}
                      value={brushRadius}
                      onChange={(event) =>
                        setBrushRadius(Number(event.target.value))
                      }
                    />
                    <p className="mt-1 text-xs text-fg-muted">
                      Drag anywhere on the contour. Nearby points move smoothly
                      with it.
                    </p>
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-2">
                    <Checkbox
                      label="I reviewed the visible boundary"
                      checked={document.contour_reviewed}
                      onCheckedChange={(value) =>
                        update({ ...document, contour_reviewed: value })
                      }
                    />
                    <div className="flex gap-1">
                      <Tooltip content="Undo">
                        <button
                          type="button"
                          className="cb-tool"
                          aria-label="Undo"
                          disabled={!undo.current.length}
                          onClick={() => restore("undo")}
                        >
                          <RotateCcw size={16} />
                        </button>
                      </Tooltip>
                      <Tooltip content="Redo">
                        <button
                          type="button"
                          className="cb-tool"
                          aria-label="Redo"
                          disabled={!redo.current.length}
                          onClick={() => restore("redo")}
                        >
                          <RotateCw size={16} />
                        </button>
                      </Tooltip>
                    </div>
                  </div>
                </div>
                <div className="cb-section">
                  <p className="cb-label mb-2">Signal inspection</p>
                  <Switch
                    label="Show one normal scan"
                    description="Optional diagnostic. Approval reorients each usable scan to the reviewed contour."
                    checked={profileOpen}
                    onCheckedChange={setProfileOpen}
                  />
                  {profileOpen && contourTasks.length > 0 && (
                    <div className="mt-4">
                      <label
                        htmlFor="scan-position"
                        className="text-xs font-medium"
                      >
                        Position along contour
                      </label>
                      <div className="mt-2 flex items-center gap-2">
                        <input
                          id="scan-position"
                          className="cb-range min-w-0 flex-1"
                          type="range"
                          min={1}
                          max={contourTasks.length}
                          step={1}
                          value={taskIndex + 1}
                          onChange={(event) =>
                            setTaskIndex(Number(event.target.value) - 1)
                          }
                        />
                        <NumberInput
                          className="cb-index-input"
                          aria-label="Scan number"
                          min={1}
                          max={contourTasks.length}
                          step={1}
                          value={taskIndex + 1}
                          onChange={(event) =>
                            setTaskIndex(
                              Math.max(
                                0,
                                Math.min(
                                  contourTasks.length - 1,
                                  Number(event.target.value) - 1,
                                ),
                              ),
                            )
                          }
                        />
                      </div>
                      <p className="mt-2 text-xs text-fg-muted">
                        {taskIndex + 1} of {contourTasks.length} candidate
                        positions · diagnostic only
                      </p>
                    </div>
                  )}
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
                          <p
                            key={method}
                            className="flex justify-between gap-2"
                          >
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
                              {report.methods[method]?.mae_px?.toFixed(2) ??
                                "—"}{" "}
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
                        Exploratory mask proxy ·{" "}
                        {report.mask_proxy_context.tasks} tasks
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
              </div>
            )}
            {document && inspectorTab === "settings" && (
              <div
                role="tabpanel"
                id="inspector-panel-settings"
                aria-labelledby="inspector-tab-settings"
              >
                <div className="cb-section">
                  <p className="cb-label mb-3">Review settings</p>
                  <SchemaForm
                    fields={reviewFields}
                    values={reviewValues}
                    onChange={(next) => {
                      setReviewValues(next);
                      if (
                        next.reviewer !== reviewValues.reviewer ||
                        next.contour_uncertainty_px !==
                          reviewValues.contour_uncertainty_px
                      )
                        update({
                          ...document,
                          reviewer: String(next.reviewer ?? ""),
                          contour_uncertainty_px: Number(
                            next.contour_uncertainty_px,
                          ),
                        });
                    }}
                  />
                </div>
                <div className="cb-section text-xs text-fg-muted">
                  <p className="cb-label mb-2">Provenance</p>
                  <p>Weld profiles · Zenodo v1 · CC BY 4.0</p>
                  <p className="mt-1 cb-mini break-all">
                    Image SHA-256: {document.source_image_sha256}
                  </p>
                  <p className="mt-1">{document.proposal_method}</p>
                  {document.proposal_flags.length > 0 && (
                    <p className="mt-1">
                      Proposal diagnostics: {document.proposal_flags.join(", ")}
                    </p>
                  )}
                </div>
              </div>
            )}
          </aside>
        </main>
      </div>
    </TooltipProvider>
  );
}
