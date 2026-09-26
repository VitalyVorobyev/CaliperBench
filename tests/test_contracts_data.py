import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from caliperbench.data import download, register, sha256, under_root
from caliperbench.schema import Prediction, Request, Sample, Strip


@pytest.mark.parametrize("path", ["/absolute.png", "../escape.png", "foo/../../escape", "a\\b.png"])
def test_path_contract(request_record, path):
    value = request_record.model_dump()
    value["image"] = path
    with pytest.raises(ValidationError):
        Request.model_validate(value)


def test_finite_and_cross_fields(request_record, sample):
    with pytest.raises(ValidationError):
        Strip(start_xy=(0, 0), end_xy=(0, 0))
    with pytest.raises(ValidationError):
        Strip(start_xy=(0, 0), end_xy=(float("nan"), 1))
    with pytest.raises(ValidationError):
        Prediction(sample_id="x", status="ok", edges_px=[float("nan")], runtime_ms=1)
    value = sample.model_dump()
    value["edge_truth"]["positions_px"] = [1]
    with pytest.raises(ValidationError):
        Sample.model_validate(value)


def test_symlink_escape(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        under_root(root, "escape/outside")


def test_download_checksum_and_manifest(tmp_path):
    entry = {
        "id": "unit",
        "version": "1",
        "license": {"id": "MIT"},
        "download_enabled": True,
        "download_hosts": ["example.org"],
    }
    payload = b"unit text fixture"
    source = tmp_path / "source.txt"
    source.write_bytes(payload)
    digest = sha256(source)

    def response(*args, **kwargs):
        stream = io.BytesIO(payload)
        stream.url = "https://example.org/unit"
        return stream

    with patch("urllib.request.urlopen", response):
        with pytest.raises(ValueError, match="mismatch"):
            download(tmp_path, entry, "https://example.org/unit", "0" * 64, "unit.txt")
        assert not list(tmp_path.rglob("*.part"))
        record = download(tmp_path, entry, "https://example.org/unit", digest, "unit.txt")
        assert record["sha256"] == digest
        assert json.loads((tmp_path / "manifests/unit.jsonl").read_text())["bytes"] == len(payload)
        with pytest.raises(ValueError, match="allowlist"):
            download(tmp_path, entry, "https://other.org/unit", digest, "unit.txt")
        with pytest.raises(ValueError, match="basename"):
            download(tmp_path, entry, "https://example.org/unit", digest, "../unit.txt")
    with pytest.raises(ValueError):
        register(tmp_path / "raw", entry, source, "https://example.org/unit")


def test_registry_evidence_and_schema_examples():
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / "registry/datasets.json").read_text())["datasets"]
    assert len(entries) == len({e["id"] for e in entries})
    assert {"amodal-apple", "itodd-bop", "weld-profiles-2026"} <= {e["id"] for e in entries}
    for entry in entries:
        assert entry["license"]["evidence_url"] in entry["evidence_urls"]
        assert entry["verified_on"] and entry["relabeling_strategy"]
        if entry["license"]["id"] == "unknown":
            assert not entry["download_enabled"]
    for line in (root / "examples/annotation.jsonl").read_text().splitlines():
        Sample.model_validate_json(line)
