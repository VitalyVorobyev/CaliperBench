"""Choose a deterministic, varied 12-image review pilot; write metadata only."""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import laplace

from caliperbench.data import sha256


def main():
    root = Path("data/raw/weld-profiles-2026")
    manifest = json.loads(Path("data/manifests/weld-profiles-2026.json").read_text())
    assets = {item["name"]: item for item in manifest["files"]}
    rows = []
    for path in sorted(root.glob("*.jpg")):
        mask = root / f"{path.stem}_mask.png"
        if mask.name not in assets:
            continue
        if (
            sha256(path) != assets[path.name]["sha256"]
            or sha256(mask) != assets[mask.name]["sha256"]
        ):
            raise ValueError(f"checksum mismatch: {path.name}")
        with Image.open(path) as image:
            gray = np.asarray(image.convert("L"), dtype=float) / 255
        with Image.open(mask) as source_mask:
            binary = np.asarray(source_mask.convert("L")) > 0
        boundary = binary ^ np.roll(binary, 1, axis=0)
        ys, xs = np.where(boundary)
        local = np.abs(
            gray[np.clip(ys + 2, 0, gray.shape[0] - 1), xs]
            - gray[np.clip(ys - 2, 0, gray.shape[0] - 1), xs]
        )
        features = [
            float(gray.mean()),
            float(gray.std()),
            float(laplace(gray).var()),
            float(np.median(local)),
        ]
        rows.append(
            {
                "image": path.name,
                "mask": mask.name,
                "image_sha256": assets[path.name]["sha256"],
                "mask_sha256": assets[mask.name]["sha256"],
                "features": features,
            }
        )
    values = np.array([row["features"] for row in rows])
    scaled = (values - values.mean(axis=0)) / np.maximum(values.std(axis=0), 1e-9)
    selected = []
    for column in range(scaled.shape[1]):
        for index in (int(np.argmin(scaled[:, column])), int(np.argmax(scaled[:, column]))):
            if index not in selected:
                selected.append(index)
    while len(selected) < 12:
        distances = np.min(
            np.linalg.norm(scaled[:, None, :] - scaled[selected][None, :, :], axis=2), axis=1
        )
        distances[selected] = -1
        selected.append(int(np.argmax(distances)))
    selected = sorted(selected[:12], key=lambda index: rows[index]["image"])
    output = {
        "schema_version": 1,
        "source": "https://doi.org/10.5281/zenodo.20301441",
        "selection": "extrema plus farthest-point sampling of brightness, contrast, Laplacian variance, and source-mask boundary contrast",
        "images": [rows[index] for index in selected],
    }
    destination = Path("registry/weld-pilot-v1.json")
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(
        f"Selected {len(selected)} images: {', '.join(rows[index]['image'] for index in selected)}"
    )


if __name__ == "__main__":
    main()
