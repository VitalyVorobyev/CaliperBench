import numpy as np
import pytest

from caliperbench.baseline import _profile, predict
from caliperbench.schema import Strip


def test_pair_and_reverse(request_record):
    image = np.zeros((9, 64))
    image[:, 16:48] = 1
    p = predict(image, request_record)
    assert p.status == "ok"
    assert p.edges_px == pytest.approx([15.5, 47.5], abs=1e-8)
    reverse = request_record.model_copy(
        update={"strip": Strip(start_xy=(63, 4), end_xy=(0, 4), samples=64)}
    )
    assert predict(image, reverse).edges_px == pytest.approx([15.5, 47.5], abs=1e-8)


def test_transverse_bilinear_geometry():
    y, x = np.mgrid[:30, :30]
    strip = Strip(start_xy=(5, 5), end_xy=(20, 20), width_px=3, across=3, samples=16)
    assert _profile(2 * x + 3 * y, strip) == pytest.approx(np.linspace(25, 100, 16))


def test_spacing_is_image_pixels(request_record):
    image = np.zeros((9, 64))
    image[:, 16:48] = 1
    req = request_record.model_copy(
        update={"strip": Strip(start_xy=(0, 4), end_xy=(63, 4), samples=127)}
    )
    assert predict(image, req).edges_px == pytest.approx([15.5, 47.5], abs=1e-8)


def test_missing_and_negative(request_record):
    flat = np.zeros((9, 64))
    assert predict(flat, request_record).status == "failed"
    negative = request_record.model_copy(update={"polarities": []})
    assert predict(flat, negative).edges_px == []
    flat[:, 32:] = 1
    assert len(predict(flat, negative).edges_px) == 1


@pytest.mark.parametrize(
    "bad", [np.full((9, 64), np.nan), np.ones((9, 64)) * 255, np.zeros((2, 2, 3))]
)
def test_invalid_images(request_record, bad):
    assert predict(bad, request_record).status == "failed"


def test_out_of_bounds(request_record):
    p = predict(np.zeros((3, 64)), request_record)
    assert p.status == "failed" and p.reason == "strip_out_of_bounds"
