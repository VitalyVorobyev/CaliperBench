import { useRef, useState, type PointerEvent, type KeyboardEvent } from "react";
import { imageViewBox, useStage } from "@vitavision/stage2d";
import type { Point } from "./api";
import { deformContour, nearestSegment } from "./geometry";

/** App adapter until the reusable ContourEditor lands in @vitavision/stage2d. */
export function ContourLayer({
  points,
  onChange,
  onEditStart,
  editable,
  brushRadius,
}: {
  points: Point[];
  onChange: (points: Point[]) => void;
  onEditStart: () => void;
  editable: boolean;
  brushRadius: number;
}) {
  const stage = useStage();
  const drag = useRef<{ index: number; origin: Point; points: Point[] } | null>(
    null,
  );
  const [selected, setSelected] = useState(0);
  const outline = points.map(([x, y]) => `${x},${y}`).join(" ");
  const move = (origin: Point[], index: number, delta: Point) =>
    onChange(
      deformContour(
        origin,
        index,
        delta,
        brushRadius,
        stage.image.width,
        stage.image.height,
      ),
    );
  const pointerDown = (event: PointerEvent<SVGElement>, index: number) => {
    if (stage.panMode || event.button !== 0) return;
    event.stopPropagation();
    onEditStart();
    const p = stage.toImage({ x: event.clientX, y: event.clientY });
    drag.current = { index, origin: [p.x, p.y], points };
    setSelected(index);
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const pointerMove = (event: PointerEvent<SVGElement>) => {
    if (!drag.current) return;
    event.stopPropagation();
    const p = stage.toImage({ x: event.clientX, y: event.clientY });
    const { index, origin, points: start } = drag.current;
    move(start, index, [p.x - origin[0], p.y - origin[1]]);
  };
  const keyDown = (event: KeyboardEvent<SVGCircleElement>, index: number) => {
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
      move(points, index, directions[event.key]);
    } else if (event.key === "[" || event.key === "]") {
      event.preventDefault();
      event.stopPropagation();
      setSelected(
        (index + (event.key === "]" ? 1 : points.length - 1)) % points.length,
      );
    }
    if (
      (event.key === "Delete" || event.key === "Backspace") &&
      points.length > 3
    ) {
      event.preventDefault();
      onEditStart();
      onChange(points.filter((_, i) => i !== index));
      setSelected(Math.min(index, points.length - 2));
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
          aria-label="Drag contour to reshape; double click to add a point"
          onPointerDown={(event) => {
            const p = stage.toImage({ x: event.clientX, y: event.clientY });
            const segment = nearestSegment(points, [p.x, p.y]);
            const neighbor = (segment + 1) % points.length;
            const distance = (index: number) =>
              Math.hypot(points[index][0] - p.x, points[index][1] - p.y);
            pointerDown(
              event,
              distance(segment) <= distance(neighbor) ? segment : neighbor,
            );
          }}
          onPointerMove={pointerMove}
          onPointerUp={() => {
            drag.current = null;
          }}
          onLostPointerCapture={() => {
            drag.current = null;
          }}
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
      {editable && points[selected] && (
        <circle
          cx={points[selected][0]}
          cy={points[selected][1]}
          r={stage.imageLength(6)}
          fill="var(--surface)"
          stroke="var(--signal)"
          strokeWidth={stage.imageLength(1)}
          className="pointer-events-auto cursor-move"
          tabIndex={0}
          role="button"
          aria-label={`Contour handle ${selected + 1} of ${points.length}; arrow keys move, brackets select neighbors`}
          onPointerDown={(e) => pointerDown(e, selected)}
          onPointerMove={pointerMove}
          onPointerUp={() => {
            drag.current = null;
          }}
          onLostPointerCapture={() => {
            drag.current = null;
          }}
          onKeyDown={(e) => keyDown(e, selected)}
        />
      )}
    </svg>
  );
}
