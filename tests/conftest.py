import pytest

from caliperbench.schema import EdgeTruth, Provenance, Request, Sample, Strip


@pytest.fixture
def request_record():
    return Request(
        sample_id="unit",
        image="unit.png",
        image_sha256="0" * 64,
        strip=Strip(start_xy=(0, 4), end_xy=(63, 4), samples=64),
        polarities=["rising", "falling"],
    )


@pytest.fixture
def sample(request_record):
    return Sample(
        request=request_record,
        split="test",
        provenance=Provenance(
            dataset_id="unit-only",
            source_url="urn:unit",
            source_version="1",
            license="MIT",
            source_image_id="unit",
            annotator="unit",
            annotation_version="1",
            derivation="unit",
            group_id="unit",
        ),
        edge_truth=EdgeTruth(
            positions_px=[15.5, 47.5],
            uncertainty_px=0,
            method="numeric fixture",
            confidence="high",
            phases=[0.5, 0.5],
        ),
    )
