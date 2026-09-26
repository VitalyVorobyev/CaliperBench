import pytest

from caliperbench.evaluate import evaluate
from caliperbench.schema import EdgeTruth, PhysicalTruth, Prediction


def prediction(**kwargs):
    return Prediction(sample_id="unit", status="ok", runtime_ms=2, **kwargs)


def test_signed_metrics_and_phase(sample):
    result = evaluate([sample], [prediction(edges_px=[16, 49])])
    assert result["edge_error_px"]["bias"] == 1
    assert result["width_error_px"]["bias"] == 1
    assert result["center_error_px"]["bias"] == 1
    assert result["failure_rate"] == 1
    assert result["phase_bias_px"][5]["count"] == 2
    assert result["phase_bias_px"][0]["bias"] is None


def test_missing_wrong_count_outside(sample):
    for predictions in ([], [prediction(edges_px=[16])], [prediction(edges_px=[16, 70])]):
        result = evaluate([sample], predictions)
        assert result["failure_rate"] == 1
        assert result["edge_error_px"]["count"] == 0


def test_negative_false_positive(sample):
    sample.request.polarities = []
    sample.edge_truth = EdgeTruth(
        positions_px=[], uncertainty_px=0, method="unit", confidence="high"
    )
    assert evaluate([sample], [prediction(edges_px=[])])["failure_rate"] == 0
    assert evaluate([sample], [prediction(edges_px=[2])])["failure_rate"] == 1


def test_physical_separate(sample):
    sample.edge_truth = None
    sample.physical_truth = PhysicalTruth(
        value=10,
        unit="mm",
        uncertainty=0.1,
        quantity="diameter",
        method="caliper",
        calibration_ref="camera.json",
    )
    result = evaluate([sample], [prediction(physical={"value": 11, "unit": "mm"})])
    assert result["edge_error_px"]["count"] == 0
    assert result["physical_error"]["diameter [mm]"]["bias"] == 1
    assert result["physical_missing_rate"] == 0
    assert (
        evaluate([sample], [prediction(physical={"value": 0.01, "unit": "m"})])["failure_rate"] == 1
    )


def test_duplicate_unknown_and_empty(sample):
    with pytest.raises(ValueError):
        evaluate([sample, sample], [])
    p = prediction(edges_px=[])
    with pytest.raises(ValueError):
        evaluate([sample], [p, p])
    with pytest.raises(ValueError):
        evaluate([], [p])
    assert evaluate([], [])["failure_rate"] is None
    with pytest.raises(ValueError):
        evaluate([sample], [], float("nan"))
