import { useRef, useState, type PointerEvent, type KeyboardEvent } from "react";
import { imageViewBox, useStage } from "@vitavision/stage2d";
import type { Point } from "./api";
import { nearestSegment } from "./geometry";

/** App adapter until the reusable ContourEditor lands in @vitavision/stage2d. */
export function ContourLayer({
  points,
  onChange,
  onEditStart,
  editable,
}: {
  points: Point[];
  onChange: (points: Point[]) => void;
  onEditStart: () => void;
  editable: boolean;
}) {
  const stage = useStage();
  const drag = useRef<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const outline = points.map(([x, y]) => `${x},${y}`).join(" ");
  const move = (index: number, next: Point) =>
    onChange(
      points.map((p, i) =>
        i === index
          ? [
              Math.max(0, Math.min(stage.image.width - 1, next[0])),
              Math.max(0, Math.min(stage.image.height - 1, next[1])),
            ]
          : p,
      ),
    );
  const pointerDown = (
    event: PointerEvent<SVGCircleElement>,
    index: number,
  ) => {
    if (stage.panMode || event.button !== 0) return;
    event.stopPropagation();
    onEditStart();
    drag.current = index;
    setSelected(index);
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const pointerMove = (event: PointerEvent<SVGCircleElement>) => {
    if (drag.current === null) return;
    event.stopPropagation();
    const p = stage.toImage({ x: event.clientX, y: event.clientY });
    move(drag.current, [p.x, p.y]);
  };
  const keyDown = (event: KeyboardEvent<SVGCircleElement>, index: number) => {
    const p = points[index];
    const delta = event.shiftKey ? 0.1 : 1;
    const directions: Record<string, Point> = {
      ArrowLeft: [-delta, 0],
      ArrowRight: [delta, 0],
      ArrowUp: [0, -delta],
      ArrowDown: [0, delta],
    };
    if (directions[event.key]) {
      event.preventDefault();
      event.stopPropagation();
      onEditStart();
      move(index, [
        p[0] + directions[event.key][0],
        p[1] + directions[event.key][1],
      ]);
    }
    if (
      (event.key === "Delete" || event.key === "Backspace") &&
      points.length > 3
    ) {
      event.preventDefault();
      onEditStart();
      onChange(points.filter((_, i) => i !== index));
      setSelected(null);
    }
  };
  return (
    <svg
      viewBox={imageViewBox(stage.image)}
      className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
      aria-label="Reviewed contour"
    >
      <polygon
        points={outline}
        fill="none"
        stroke="var(--signal)"
        strokeWidth={stage.imageLength(1.5)}
      />
      {editable && (
        <polygon
          points={outline}
          fill="none"
          stroke="transparent"
          strokeWidth={stage.imageLength(12)}
          className="pointer-events-auto"
          aria-label="Double click to add a contour point"
          onDoubleClick={(event) => {
            if (stage.panMode) return;
            event.stopPropagation();
            onEditStart();
            const p = stage.toImage({ x: event.clientX, y: event.clientY });
            const i = nearestSegment(points, [p.x, p.y]);
            onChange([
              ...points.slice(0, i + 1),
              [p.x, p.y],
              ...points.slice(i + 1),
            ]);
            setSelected(i + 1);
          }}
        />
      )}
      {editable &&
        points.map(([x, y], index) => (
          <circle
            key={index}
            cx={x}
            cy={y}
            r={stage.imageLength(selected === index ? 6 : 4)}
            fill="var(--surface)"
            stroke="var(--signal)"
            strokeWidth={stage.imageLength(1)}
            className="pointer-events-auto cursor-move"
            tabIndex={0}
            role="button"
            aria-label={`Contour point ${index + 1}`}
            onPointerDown={(e) => pointerDown(e, index)}
            onPointerMove={pointerMove}
            onPointerUp={() => {
              drag.current = null;
            }}
            onLostPointerCapture={() => {
              drag.current = null;
            }}
            onKeyDown={(e) => keyDown(e, index)}
            onFocus={() => setSelected(index)}
          />
        ))}
    </svg>
  );
}
