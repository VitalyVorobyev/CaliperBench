"""Build local-only caliper review probes along each pilot contour proposal."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from caliperbench.data import sha256
from caliperbench.probes import contour_probes
from caliperbench.refine import propose
from caliperbench.schema import Candidate, Provenance, Request, Strip

DATASET_ID = "weld-profiles-2026"
SOURCE = "https://zenodo.org/records/20301441"
HALF_LENGTH = 12.0
TARGET_COUNT = 32


def build(repository: Path, data_root: Path):
    pilot = json.loads((repository / "registry/weld-pilot-v1.json").read_text())
    root = data_root / "raw" / DATASET_ID
    samples = []
    counts = {}
    for row in pilot["images"]:
        image_path, mask_path = root / row["image"], root / row["mask"]
        if sha256(image_path) != row["image_sha256"] or sha256(mask_path) != row["mask_sha256"]:
            raise ValueError(f"source checksum mismatch: {row['image']}")
        with Image.open(image_path) as image_source, Image.open(mask_path) as mask_source:
            width, height = image_source.size
            image = np.asarray(image_source.convert("L"), dtype=float) / 255
            mask = np.asarray(mask_source.convert("L")) > 0
        contour = propose(image, mask).refined_contour
        image_id = image_path.stem
        probes = contour_probes(contour, width, height, TARGET_COUNT)
        counts[image_id] = len(probes)
        for ordinal, (_, start, end, crossing) in enumerate(probes, 1):
            samples.append(
                Candidate(
                    request=Request(
                        sample_id=f"{image_id}:contour:{ordinal:02d}",
                        image=f"raw/{DATASET_ID}/{image_path.name}",
                        image_sha256=row["image_sha256"],
                        strip=Strip(
                            start_xy=(float(start[0]), float(start[1])),
                            end_xy=(float(end[0]), float(end[1])),
                            samples=25,
                        ),
                        polarities=["either"],
                    ),
                    split="development",
                    provenance=Provenance(
                        dataset_id=DATASET_ID,
                        source_url=SOURCE,
                        source_version="v1",
                        license="CC-BY-4.0",
                        source_image_id=image_path.name,
                        annotator="automatic-active-contour-proposal-unreviewed",
                        annotation_version="contour-probes-v1",
                        derivation="bounded active contour; uniform arc sampling; normal scan; single proposal crossing; not visible-edge ground truth",
                        group_id=image_id,
                    ),
                    proposal_crossing_px=float(crossing),
                )
            )
    return samples, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/annotations_weld_contour_candidates_v2.jsonl")
    )
    args = parser.parse_args()
    samples, counts = build(Path(__file__).resolve().parents[1], args.data_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(sample.model_dump_json() + "\n" for sample in samples)
    if args.output.exists() and args.output.read_text() != body:
        raise ValueError("existing candidate file differs; preserve reviewed strip geometry")
    args.output.write_text(body)
    print(json.dumps({"candidate_probes": len(samples), "per_image": counts}, indent=2))


if __name__ == "__main__":
    main()
