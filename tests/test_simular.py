import json

import numpy as np
import pytest

from experiments.simular import CALIBRATION, featured_communes, load_setup


@pytest.fixture(scope="module")
def setup():
    return load_setup()


def test_communes_with_a_station_start_at_their_measured_level(setup):
    anchoring = json.loads(CALIBRATION.read_text(encoding="utf-8"))["anchoring"]["communes"]
    for i, code in enumerate(setup.communes.codes):
        if code in anchoring:
            assert setup.state.pm25[i] == pytest.approx(anchoring[code]["medido_ugm3"], abs=0.01)
    assert setup.measured.sum() == len(anchoring)


def test_communes_without_a_station_use_the_model_alone(setup):
    assert np.all(setup.air.offset[~setup.measured] == 0.0)


def test_featured_communes_are_measured_and_include_the_extremes(setup):
    featured = featured_communes(setup)
    index = {c: i for i, c in enumerate(setup.communes.codes)}
    assert all(setup.measured[index[c]] for c in featured)
    measured_levels = setup.state.pm25[setup.measured]
    levels = [setup.state.pm25[index[c]] for c in featured]
    assert max(levels) == measured_levels.max()
    assert min(levels) == measured_levels.min()
