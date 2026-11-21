import json

import numpy as np
import pytest

from core.credibilidad import BetaCredibility
from core.licitaciones import CommuneProcurementSummary
from experiments.simular import (
    CALIBRATION,
    SECURITY_CREDIBILITY,
    featured_communes,
    load_setup,
    mixture_summary,
    municipal_credibility,
)


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


# --- Municipal credibility from ChileCompra (docs/plan-licitaciones.md) ---


def test_municipality_with_enough_tenders_updates_the_prior_as_a_base_rate():
    data = {"13101": CommuneProcurementSummary("13101", 683, 609, 66, 675, 1.0, 30.0, 0.15)}
    est = municipal_credibility(["13101"], data)["13101"]
    assert est.provenance == "tasa_base"
    assert est.credibility.mean > SECURITY_CREDIBILITY.mean


def test_municipality_without_tenders_keeps_the_assumed_prior():
    est = municipal_credibility(["13102"], {})["13102"]
    assert est.provenance == "supuesto"
    assert est.credibility == SECURITY_CREDIBILITY


def test_mixture_summary_lies_between_its_components():
    low, high = BetaCredibility(2, 8), BetaCredibility(8, 2)
    s = mixture_summary([low, high])
    assert low.summary()["p10"] <= s["p10"] < s["media"] < s["p90"] <= high.summary()["p90"]
    assert s["media"] == pytest.approx(0.5)


def test_security_policies_publish_credibility_per_target_commune():
    data = json.loads((CALIBRATION.parents[1] / "viz/datos/simulacion.json").read_text())
    for p in (p for p in data["politicas"] if p["variable"] == "seguridad"):
        per = p["credibilidad_por_comuna"]
        assert set(per) == set(p["comunas"])
        for c in per.values():
            assert c["procedencia"] in ("tasa_base", "supuesto")
            assert 0 <= c["p10"] <= c["media"] <= c["p90"] <= 1
