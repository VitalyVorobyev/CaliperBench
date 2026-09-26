import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location(
    "build_weld_proxy", Path(__file__).parents[1] / "scripts/build_weld_proxy.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
candidate = module.candidate


def test_proxy_requires_one_stable_mask_interval():
    mask = np.zeros((80, 50), dtype=bool)
    mask[30:60, 10:40] = True
    assert candidate(mask, 20) == 30
    mask[45, 20] = False
    assert candidate(mask, 20) is None
    mask[45, 20] = True
    mask[21:60, 18] = True
    assert candidate(mask, 20) is None
