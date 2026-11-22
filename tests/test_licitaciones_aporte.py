"""Per-tender contribution to municipal credibility (experiments/licitaciones_aporte.py)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.licitaciones import CommuneProcurementSummary, estimate_commune_credibility
from experiments.licitaciones_aporte import main
from experiments.simular import SECURITY_CREDIBILITY

DETAIL_FIELDS = ["codigo_comuna", "anio", "codigo_externo", "nombre", "estado",
                 "estado_chilecompra", "sector", "monto_estimado_clp", "monto_adjudicado_clp",
                 "numero_oferentes", "dias_pub_cierre", "dias_pub_adj"]
SUMMARY_FIELDS = ["codigo_comuna", "anio", "total_licitaciones", "adjudicadas", "fallidas",
                  "cerradas", "tasa_adjudicacion", "mediana_dias_pub_cierre",
                  "mediana_dias_pub_adj", "mediana_oferentes", "proporcion_oferente_unico",
                  "monto_estimado_clp", "monto_adjudicado_clp"]
# Target commune: 50 awarded, 10 failed, 3 open -> 60 closed, above the effective-n cap of 40.
TARGET, OTHER = "13101", "13119"
COUNTS = {TARGET: (50, 10, 3), OTHER: (4, 1, 2)}


def _summary(code: str, awarded: int, failed: int) -> CommuneProcurementSummary:
    return CommuneProcurementSummary(code, awarded + failed, awarded, failed, awarded + failed,
                                     0.0, None, None)


def _mean(awarded: int, failed: int) -> float:
    est = estimate_commune_credibility(_summary(TARGET, awarded, failed),
                                       prior=SECURITY_CREDIBILITY)
    return est.credibility.mean


def _write_inputs(tmp_path: Path, *, media_shift: float = 0.0,
                  summary_shift: int = 0) -> list[str]:
    detail = tmp_path / "licitaciones_detalle.csv"
    with detail.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DETAIL_FIELDS)
        w.writeheader()
        for code, (a, f, o) in COUNTS.items():
            states = ["adjudicada"] * a + ["fallida"] * f + ["abierta"] * o
            for i, estado in enumerate(states):
                w.writerow({"codigo_comuna": code, "anio": 2024,
                            "codigo_externo": f"{code}-{i}-LE24", "nombre": f"Obra {i}",
                            "estado": estado, "estado_chilecompra": estado, "sector": "otros",
                            "monto_estimado_clp": 1000.0, "monto_adjudicado_clp": "",
                            "numero_oferentes": 2, "dias_pub_cierre": "", "dias_pub_adj": ""})
    summary = tmp_path / "resumen_comuna_anio.csv"
    with summary.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for code, (a, f, o) in COUNTS.items():
            w.writerow({"codigo_comuna": code, "anio": 2024,
                        "total_licitaciones": a + f + o + summary_shift, "adjudicadas": a,
                        "fallidas": f, "cerradas": a + f})
    a, f, _ = COUNTS[TARGET]
    est = estimate_commune_credibility(_summary(TARGET, a, f), prior=SECURITY_CREDIBILITY)
    cred = {TARGET: {"p10": 0.5, "media": round(est.credibility.mean + media_shift, 3),
                     "p90": 0.9, "procedencia": est.provenance,
                     "tasa_adjudicacion": est.award_rate, "licitaciones_cerradas": a + f}}
    sim = tmp_path / "simulacion.json"
    sim.write_text(json.dumps({"politicas": [
        {"id": "aire", "credibilidad": {"media": 0.3}},
        {"id": "ilustrativa-camaras", "credibilidad_por_comuna": cred},
        {"id": "ilustrativa-iluminacion", "credibilidad_por_comuna": cred},
    ]}), encoding="utf-8")
    return ["--detalle", str(detail), "--resumen", str(summary), "--simulacion", str(sim),
            "--salida", str(tmp_path / "licitaciones.json")]


def _run(tmp_path: Path) -> dict:
    assert main(_write_inputs(tmp_path)) == 0
    return json.loads((tmp_path / "licitaciones.json").read_text(encoding="utf-8"))


def test_contribution_is_the_exact_leave_one_out_change_of_the_mean(tmp_path: Path):
    out = _run(tmp_path)
    comuna = out["comunas"][TARGET]
    a, f, o = COUNTS[TARGET]
    assert comuna["afecta_modelo"] is True
    assert (comuna["licitaciones_total"], comuna["adjudicadas"], comuna["fallidas"],
            comuna["cerradas"], comuna["abiertas"]) == (a + f + o, a, f, a + f, o)
    assert comuna["credibilidad_media"] == pytest.approx(_mean(a, f))

    by_state = {}
    for t in comuna["licitaciones"]:
        by_state.setdefault(t["estado"], set()).add(t["aporte_credibilidad"])
    # aporte = mean with every tender - mean without this one.
    (awarded,), (failed,) = by_state["adjudicada"], by_state["fallida"]
    assert awarded == pytest.approx(_mean(a, f) - _mean(a - 1, f), rel=1e-5)
    assert failed == pytest.approx(_mean(a, f) - _mean(a, f - 1), rel=1e-5)
    assert by_state["abierta"] == {0}
    assert awarded > 0 > failed
    # Under the effective-sample cap the leave-one-out changes cancel out.
    assert a * awarded + f * failed == pytest.approx(0.0, abs=1e-6)


def test_commune_outside_the_model_lists_tenders_with_zero_contribution(tmp_path: Path):
    out = _run(tmp_path)
    comuna = out["comunas"][OTHER]
    assert comuna["afecta_modelo"] is False
    assert comuna["credibilidad_media"] is None
    assert len(comuna["licitaciones"]) == sum(COUNTS[OTHER])
    assert {t["aporte_credibilidad"] for t in comuna["licitaciones"]} == {0}
    assert {"codigo_externo", "nombre", "estado", "estado_chilecompra", "sector",
            "monto_estimado_clp", "monto_adjudicado_clp", "numero_oferentes",
            "aporte_credibilidad"} <= set(comuna["licitaciones"][0])
    assert out["meta"]["anio"] == 2024
    assert out["meta"]["advertencias"]


def test_builder_fails_without_output_when_the_recomputed_mean_mismatches(tmp_path: Path):
    argv = _write_inputs(tmp_path, media_shift=0.01)
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code not in (0, None)
    assert not (tmp_path / "licitaciones.json").exists()


def test_builder_fails_when_detail_counts_disagree_with_the_aggregates(tmp_path: Path):
    argv = _write_inputs(tmp_path, summary_shift=1)
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code not in (0, None)
    assert not (tmp_path / "licitaciones.json").exists()
