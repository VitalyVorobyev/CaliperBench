import io
import json

import numpy as np
import pytest
from PIL import Image

from caliperbench.data import sha256
from caliperbench.probes import contour_probes, normal_scan_at_crossing
from caliperbench.refine import propose, strip_crossings
from caliperbench.review import Conflict, ReviewStore, digest
from caliperbench.schema import Candidate, EdgeTruth, Provenance, Request, Sample, Strip


def test_classical_refinement_is_deterministic_and_flagged():
    image = np.zeros((36, 40), dtype=float)
    image[10:28, 9:31] = 0.8
    mask = np.zeros_like(image, dtype=bool)
    mask[11:27, 10:30] = True
    first = propose(image, mask)
    second = propose(image, mask)
    assert first == second
    assert first.parameters["method"] == "skimage-active-contour-v3"
    assert len(first.source_contour) >= 3
    assert len(first.refined_contour) == len(first.source_contour)


def test_crossing_rejects_ambiguous_geometry():
    square = [[2, 2], [8, 2], [8, 8], [2, 8]]
    assert strip_crossings(square, (5, 0), (5, 10)) == [2.0, 8.0]
    assert strip_crossings(square, (5, 0), (5, 4)) == [2.0]
    assert strip_crossings(square, (12, 0), (12, 10)) == []


def test_dense_contour_probes_have_single_crossings_and_stable_positions():
    angles = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    contour = [(50 + 25 * np.cos(t), 50 + 20 * np.sin(t)) for t in angles]
    first = contour_probes(contour, 100, 100, count=24)
    second = contour_probes(contour, 100, 100, count=24)
    np.testing.assert_allclose(
        [np.r_[center, start, end, crossing] for center, start, end, crossing in first],
        [np.r_[center, start, end, crossing] for center, start, end, crossing in second],
    )
    assert len(first) >= 20
    for _, start, end, crossing in first:
        assert len(strip_crossings(contour, tuple(start), tuple(end))) == 1
        assert abs(crossing - 12) < 3


def test_frozen_scan_turns_normal_to_reviewed_inclined_edge():
    contour = [(10 + i, 10 + i) for i in range(31)] + [(40, 60), (10, 60)]
    old = Strip(start_xy=(20, 15), end_xy=(20, 25), samples=11)
    crossing = strip_crossings(contour, old.start_xy, old.end_xy)[0]
    aligned = normal_scan_at_crossing(contour, old, crossing, 80, 80)
    assert aligned is not None
    strip, new_crossing = aligned
    vector = np.subtract(strip.end_xy, strip.start_xy)
    assert abs(vector[0] + vector[1]) < 1e-6
    assert abs(new_crossing - 5) < 1e-3


def test_review_revisions_conflicts_and_export(tmp_path):
    repository = tmp_path / "repo"
    data = tmp_path / "data"
    (repository / "registry").mkdir(parents=True)
    raw = data / "raw/weld-profiles-2026"
    raw.mkdir(parents=True)
    gray = np.zeros((36, 40), dtype=np.uint8)
    gray[10:28, 9:31] = 200
    mask = np.zeros_like(gray)
    mask[11:27, 10:30] = 255
    image_path = raw / "demo.jpg"
    mask_path = raw / "demo_mask.png"
    Image.fromarray(gray).save(image_path)
    Image.fromarray(mask).save(mask_path)
    image_sha = sha256(image_path)
    mask_sha = sha256(mask_path)
    pilot = {
        "images": [
            {
                "image": image_path.name,
                "mask": mask_path.name,
                "image_sha256": image_sha,
                "mask_sha256": mask_sha,
            }
        ]
    }
    (repository / "registry/weld-pilot-v1.json").write_text(json.dumps(pilot))
    request = Request(
        sample_id="demo:top",
        image="raw/weld-profiles-2026/demo.jpg",
        image_sha256=image_sha,
        strip=Strip(start_xy=(20, 5), end_xy=(20, 15), samples=11),
        polarities=["either"],
    )
    sample = Sample(
        request=request,
        split="development",
        provenance=Provenance(
            dataset_id="demo",
            source_url="https://example.org",
            source_version="1",
            license="CC-BY-4.0",
            source_image_id="demo.jpg",
            annotator="proxy",
            annotation_version="proxy",
            derivation="source mask",
            group_id="demo",
        ),
        edge_truth=EdgeTruth(
            positions_px=[5.5], uncertainty_px=1, method="proxy", confidence="low"
        ),
    )
    (data / "annotations_weld_proxy.jsonl").write_text(sample.model_dump_json() + "\n")
    extra_request = request.model_copy(deep=True)
    extra_request.sample_id = "demo:contour:01"
    extra = Candidate(
        request=extra_request,
        split="development",
        provenance=sample.provenance,
        proposal_crossing_px=5.5,
    )
    with pytest.raises(ValueError):
        Sample.model_validate_json(extra.model_dump_json())
    (data / "annotations_weld_contour_candidates_v2.jsonl").write_text(
        extra.model_dump_json() + "\n"
    )
    store = ReviewStore(repository, data)
    document, etag = store.read("demo")
    document.schema_version = 1
    document.contour_reviewed = True
    with store.connect() as db:
        db.execute(
            "UPDATE drafts SET body=?, etag=? WHERE image_id=?",
            (document.model_dump_json(), digest(document), "demo"),
        )
    document, etag = store.read("demo")
    assert document.schema_version == 2
    assert not document.contour_reviewed
    assert store.export_samples() == []
    assert document.tasks[0].disposition == "pending"
    document.proposal_flags.append("tampered")
    with pytest.raises(ValueError, match="evidence"):
        store.save("demo", document, etag)
    document.proposal_flags.pop()
    with pytest.raises(ValueError, match="reviewer"):
        store.approve("demo", etag)
    document.reviewer = "pilot-reviewer"
    document.contour_reviewed = True
    document.contour_uncertainty_px = 0.75
    next_etag = store.save("demo", document, etag)
    with pytest.raises(Conflict):
        store.save("demo", document, etag)
    revision = store.approve("demo", next_etag)
    assert revision["revision_id"] == 1
    assert len(revision["mask_sha256"]) == 64
    raster = np.asarray(
        Image.open(io.BytesIO(store.render_mask("demo", store.revision("demo", 1))))
    )
    assert raster.shape == (36, 40)
    assert raster[20, 20] == 255
    assert raster[0, 0] == 0
    exported = store.export_samples()
    assert len(exported) == 1
    assert exported[0].request.sample_id == "demo:contour:01"
    assert exported[0].edge_truth.method == "single-reviewer-contour-derived-edge"
    assert exported[0].edge_truth.uncertainty_px == 0.75
    document, approved_etag = store.read("demo")
    document.reviewer = "second-reviewer"
    store.save("demo", document, approved_etag)
    assert store.latest("demo")[1].reviewer == "pilot-reviewer"
    assert store.latest("demo")[1].tasks[0].disposition == "excluded"
    assert store.latest("demo")[1].tasks[1].disposition == "approved"
    assert len(store.export_samples()) == 1
