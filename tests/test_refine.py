import numpy as np
import pytest
from skimage.filters import gaussian

from caliperbench.refine import snap_to_edge, specimen_silhouette


def specimen_image():
    image = np.zeros((100, 120), dtype=float)
    image[25:80, 30:95] = 1
    return gaussian(image, 1)


def test_specimen_proposal_is_a_bounded_visible_region():
    proposal = specimen_silhouette(specimen_image())
    points = np.asarray(proposal.refined_contour)
    assert proposal.flags == ["automatic_specimen_silhouette_requires_review"]
    assert 28 <= points[:, 0].min() <= 31
    assert 94 <= points[:, 0].max() <= 97
    assert 23 <= points[:, 1].min() <= 26
    assert 79 <= points[:, 1].max() <= 82
    assert proposal == specimen_silhouette(specimen_image())


def test_frame_clipped_specimen_produces_open_visible_edge():
    image = np.zeros((100, 120), dtype=float)
    image[25:80, :95] = 1
    proposal = specimen_silhouette(gaussian(image, 1))
    assert not proposal.closed
    assert "visible_edge_open_at_frame" in proposal.flags
    assert proposal.refined_contour[0][0] == 0
    assert proposal.refined_contour[-1][0] == 0
    assert proposal.refined_contour[0] != proposal.refined_contour[-1]


def test_two_frame_clipped_edges_are_not_collapsed_to_one_chain():
    image = np.zeros((100, 120), dtype=float)
    image[25:80, :] = 1
    with pytest.raises(ValueError, match="multiple substantial visible edge chains"):
        specimen_silhouette(gaussian(image, 1))


def test_snap_resamples_coarse_outline_and_moves_toward_edge():
    coarse = [[27, 22], [98, 22], [98, 83], [27, 83]]
    proposal = snap_to_edge(specimen_image(), coarse, 5)
    points = np.asarray(proposal.refined_contour)
    assert proposal.source_contour == coarse
    assert len(points) > len(coarse)
    assert 28 <= points[:, 0].min() <= 31
    assert 94 <= points[:, 0].max() <= 97
    assert proposal == snap_to_edge(specimen_image(), coarse, 5)


def test_snap_rejects_invalid_input_and_preserves_weak_regions():
    with pytest.raises(ValueError, match="radius"):
        snap_to_edge(specimen_image(), [[1, 1], [2, 1], [2, 2]], 50)
    with pytest.raises(ValueError, match="inside"):
        snap_to_edge(specimen_image(), [[-1, 1], [2, 1], [2, 2]])
    coarse = [[20, 20], [40, 20], [40, 40], [20, 40]]
    result = snap_to_edge(np.zeros((100, 120)), coarse, 5)
    assert result.refined_contour[0] == coarse[0]
    assert result.refined_contour[7] == coarse[1]
    assert "weak_gradient_at_some_vertices" in result.flags


def test_open_edge_snap_keeps_its_endpoints_and_topology():
    image = specimen_image()
    coarse = [[30, 22], [60, 22], [90, 22]]
    result = snap_to_edge(image, coarse, 5, closed=False)
    assert not result.closed
    assert result.refined_contour[0] == coarse[0]
    assert result.refined_contour[-1] == coarse[-1]
    assert len(result.refined_contour) > len(coarse)
