"""Create exploratory, low-confidence mask-boundary tasks; never claim edge truth."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from caliperbench.data import sha256
from caliperbench.schema import EdgeTruth, Provenance, Request, Sample, Strip

DATASET_ID = "weld-profiles-2026"
SOURCE = "https://zenodo.org/records/20301441"
FRACTIONS = (0.25, 0.4, 0.6, 0.75)
HALF_LENGTH = 12


def candidate(mask: np.ndarray, x: int):
    """One sustained mask interval and a locally coherent top boundary."""
    tops = []
    for col in range(x - 2, x + 3):
        indices = np.flatnonzero(mask[:, col])
        if len(indices) < 10 or np.any(np.diff(indices) != 1):
            return None
        tops.append(int(indices[0]))
    if max(tops) - min(tops) > 8:
        return None
    y = tops[2]
    if y < HALF_LENGTH + 2 or y + HALF_LENGTH >= mask.shape[0] - 2:
        return None
    if mask[y - HALF_LENGTH, x] or not mask[y + HALF_LENGTH, x]:
        return None
    return y


def build(data_root: Path):
    root = data_root / "raw" / DATASET_ID
    manifest = json.loads((data_root / "manifests" / f"{DATASET_ID}.json").read_text())
    assets = {f["name"]: f for f in manifest["files"]}
    samples = []
    exclusions = {
        "missing_pair": 0,
        "dimension_mismatch": 0,
        "nonbinary_mask": 0,
        "ambiguous_boundary": 0,
    }
    for image_path in sorted(root.glob("*.jpg")):
        mask_path = root / (image_path.stem + "_mask.png")
        if mask_path.name not in assets:
            exclusions["missing_pair"] += 1
            continue
        if (
            sha256(image_path) != assets[image_path.name]["sha256"]
            or sha256(mask_path) != assets[mask_path.name]["sha256"]
        ):
            raise ValueError("local source checksum mismatch")
        with Image.open(image_path) as image, Image.open(mask_path) as mask_image:
            mask_raw = np.array(mask_image.convert("L"))
            if image.size != mask_image.size:
                exclusions["dimension_mismatch"] += 1
                continue
        unique = set(np.unique(mask_raw))
        if not unique.issubset({0, 255}):
            exclusions["nonbinary_mask"] += 1
            continue
        mask = mask_raw > 0
        occupied = np.flatnonzero(mask.any(axis=0))
        if len(occupied) < 10:
            exclusions["ambiguous_boundary"] += len(FRACTIONS)
            continue
        lo, hi = int(occupied[0]), int(occupied[-1])
        for fraction in FRACTIONS:
            x = round(lo + fraction * (hi - lo))
            y = candidate(mask, x)
            if y is None:
                exclusions["ambiguous_boundary"] += 1
                continue
            key = f"{image_path.stem}:top:{fraction:g}"
            # Pixel-center convention: first inside-mask pixel y has leading boundary y-0.5.
            request = Request(
                sample_id=key,
                image=f"raw/{DATASET_ID}/{image_path.name}",
                image_sha256=assets[image_path.name]["sha256"],
                strip=Strip(start_xy=(x, y - HALF_LENGTH), end_xy=(x, y + HALF_LENGTH), samples=25),
                polarities=["either"],
            )
            provenance = Provenance(
                dataset_id=DATASET_ID,
                source_url=SOURCE,
                source_version="v1",
                license="CC-BY-4.0",
                source_image_id=image_path.name,
                annotator="automatic-mask-proxy-unreviewed",
                annotation_version="weld-proxy-v1",
                derivation=f"mask={mask_path.name}; sha256={assets[mask_path.name]['sha256']}; first-mask-pixel-top minus 0.5",
                group_id=image_path.stem,
            )
            samples.append(
                Sample(
                    request=request,
                    split="development",
                    provenance=provenance,
                    edge_truth=EdgeTruth(
                        positions_px=[HALF_LENGTH - 0.5],
                        uncertainty_px=1.0,
                        method="source binary mask boundary proxy; not visual-edge GT",
                        confidence="low",
                    ),
                )
            )
    return samples, exclusions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/annotations_weld_proxy.jsonl"))
    args = parser.parse_args()
    samples, exclusions = build(args.data_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(s.model_dump_json() + "\n" for s in samples))
    summary = {
        "source": SOURCE,
        "task_type": "exploratory_mask_proxy",
        "annotation_version": "weld-proxy-v1",
        "tasks": len(samples),
        "images_with_tasks": len({s.provenance.group_id for s in samples}),
        "excluded_candidates": exclusions,
        "annotation_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    Path(str(args.output) + ".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
