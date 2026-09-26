"""Small CLI for registry, local data, request export, reference runs and offline scoring."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np
from PIL import Image

from . import __version__
from .baseline import predict
from .data import download, register, registry, sha256, under_root
from .evaluate import evaluate
from .schema import Prediction, Request, Sample


def _read(path, cls):
    rows = [
        cls.model_validate_json(line)
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]
    ids = [r.request.sample_id if isinstance(r, Sample) else r.sample_id for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate sample IDs")
    if cls is Sample:
        groups = {}
        for row in rows:
            key = (row.provenance.dataset_id, row.provenance.group_id)
            if key in groups and groups[key] != row.split:
                raise ValueError("scene/object group leaks across splits")
            groups[key] = row.split
    return rows


def _write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, allow_nan=False) + "\n" for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("registry", "download", "register"):
        p = sub.add_parser(name)
        p.add_argument("--registry", default="registry/datasets.json")
        if name != "registry":
            p.add_argument("dataset_id")
            p.add_argument("--data-root", default="data")
            p.add_argument("--url", required=True)
            p.add_argument("--sha256", required=name == "download")
            if name == "download":
                p.add_argument("--filename", required=True)
                p.add_argument("--max-bytes", type=int, default=10_000_000_000)
            else:
                p.add_argument("path")
    p = sub.add_parser("export")
    p.add_argument("annotations")
    p.add_argument("--output", required=True)
    p = sub.add_parser("run")
    p.add_argument("requests")
    p.add_argument("--data-root", default="data")
    p.add_argument("--output", required=True)
    p = sub.add_parser("score")
    p.add_argument("annotations")
    p.add_argument("predictions")
    p.add_argument("--tolerance-px", type=float, default=1)
    p.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command in {"registry", "download", "register"}:
            entries = registry(args.registry)
            if args.command == "registry":
                for e in entries.values():
                    print(
                        f"{e['id']:24} {e['priority']:3} {e['license']['id']:24} {e['access_status']}"
                    )
            elif args.command == "download":
                print(
                    json.dumps(
                        download(
                            args.data_root,
                            entries[args.dataset_id],
                            args.url,
                            args.sha256,
                            args.filename,
                            args.max_bytes,
                        ),
                        indent=2,
                    )
                )
            else:
                print(
                    json.dumps(
                        register(
                            args.data_root,
                            entries[args.dataset_id],
                            args.path,
                            args.url,
                            args.sha256,
                        ),
                        indent=2,
                    )
                )
        elif args.command == "export":
            samples = _read(args.annotations, Sample)
            _write(args.output, [s.request.model_dump() for s in samples])
        elif args.command == "run":
            predictions = []
            for request in _read(args.requests, Request):
                path = under_root(args.data_root, request.image)
                # Dataset integrity errors abort; they are not algorithm failures.
                if sha256(path) != request.image_sha256:
                    raise ValueError(f"image checksum mismatch for {request.sample_id}")
                with Image.open(path) as im:
                    if im.mode not in {"L", "RGB"}:
                        raise ValueError(
                            "baseline loader supports only 8-bit L/RGB; preprocess explicitly"
                        )
                    image = np.array(im.convert("L"), dtype=float) / 255
                predictions.append(predict(image, request).model_dump())
            _write(args.output, predictions)
            Path(str(args.output) + ".run.json").write_text(
                json.dumps(
                    {
                        "implementation": "textbook-reference-v1",
                        "caliperbench": __version__,
                        "python": platform.python_version(),
                        "platform": platform.platform(),
                        "numpy": np.__version__,
                        "requests_sha256": sha256(args.requests),
                        "runtime_scope": "predict only; includes sampling, excludes image decode and file IO",
                    },
                    indent=2,
                )
                + "\n"
            )
        else:
            result = evaluate(
                _read(args.annotations, Sample),
                _read(args.predictions, Prediction),
                args.tolerance_px,
            )
            result["annotations_sha256"] = sha256(args.annotations)
            result["predictions_sha256"] = sha256(args.predictions)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"caliperbench: {exc}\n")


if __name__ == "__main__":
    main()
