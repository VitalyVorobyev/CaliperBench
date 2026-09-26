import json
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

from caliperbench.cli import _read
from caliperbench.data import sha256
from caliperbench.schema import Sample


def call(*args):
    return subprocess.run(
        [sys.executable, "-m", "caliperbench.cli", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_roundtrip(tmp_path, sample):
    # Generated solely for this test; never a committed image or benchmark evidence.
    data = tmp_path / "data"
    data.mkdir()
    pixels = np.zeros((9, 64), dtype=np.uint8)
    pixels[:, 16:48] = 255
    image = data / "unit.png"
    Image.fromarray(pixels).save(image)
    sample.request.image_sha256 = sha256(image)
    annotations = data / "annotations.jsonl"
    annotations.write_text(sample.model_dump_json() + "\n")
    requests, predictions, report = [
        tmp_path / n for n in ["requests.jsonl", "pred.jsonl", "report.json"]
    ]
    result = call("export", annotations, "--output", requests)
    assert result.returncode == 0, result.stderr
    exported = json.loads(requests.read_text())
    assert set(exported) == {
        "schema_version",
        "sample_id",
        "image",
        "image_sha256",
        "strip",
        "polarities",
    }
    result = call("run", requests, "--data-root", data, "--output", predictions)
    assert result.returncode == 0, result.stderr
    result = call("score", annotations, predictions, "--output", report)
    assert result.returncode == 0, result.stderr
    summary = json.loads(report.read_text())
    assert summary["failure_rate"] == 0
    assert summary["edge_error_px"]["mae"] < 1e-8
    assert summary["annotations_sha256"] == sha256(annotations)
    assert json.loads((tmp_path / "pred.jsonl.run.json").read_text())["implementation"]
    image.write_bytes(b"corrupted")
    result = call("run", requests, "--data-root", data, "--output", predictions)
    assert result.returncode == 2 and "checksum mismatch" in result.stderr


def test_split_leakage(tmp_path, sample):
    other = sample.model_copy(deep=True)
    other.request.sample_id = "second"
    other.split = "development"
    path = tmp_path / "annotations.jsonl"
    path.write_text(sample.model_dump_json() + "\n" + other.model_dump_json() + "\n")
    with pytest.raises(ValueError, match="leaks across splits"):
        _read(path, Sample)
