"""Per-tender contribution to municipal credibility -> viz/datos/licitaciones.json.

Inputs:  data/licitaciones/licitaciones_detalle.csv (one row per deduplicated tender),
         data/licitaciones/resumen_comuna_anio.csv (the aggregates the simulation reads) and
         viz/datos/simulacion.json (politicas[].credibilidad_por_comuna).
Method:  the simulation's own prior (SECURITY_CREDIBILITY), year (PROCUREMENT_YEAR) and
         estimate_commune_credibility (core/licitaciones.py). A tender's contribution is the
         exact leave-one-out change of the posterior mean: mean with every closed tender minus
         mean without that one. Open tenders, and every tender of a commune whose credibility
         does not enter the model, contribute 0.
Checks:  per-commune counts of the detail CSV equal the aggregates, and the recomputed mean,
         closed count and award rate equal simulacion.json for every target commune. Any
         mismatch exits non-zero before writing.

Usage:  python -m experiments.licitaciones_aporte
"""
from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from core.licitaciones import (
    MAX_EFFECTIVE_N_ASSUMPTION,
    CommuneProcurementSummary,
    estimate_commune_credibility,
    load_procurement_summaries,
)
from experiments.simular import (
    OUTPUT as SIMULATION,
)
from experiments.simular import (
    PROCUREMENT,
    PROCUREMENT_YEAR,
    SECURITY_CREDIBILITY,
    municipal_credibility,
)

ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "data" / "licitaciones" / "licitaciones_detalle.csv"
OUTPUT = ROOT / "viz" / "datos" / "licitaciones.json"
CLOSED_STATES = ("adjudicada", "fallida")
STATES = (*CLOSED_STATES, "abierta")

CAVEATS = [
    ("Solo las comunas con afecta_modelo=true entran al modelo (políticas comunales de "
    "seguridad, credibilidad municipal). En las demás aporte_credibilidad=0 significa «no entra "
    "al modelo», no «no aporta»; su credibilidad_media es null."),
    ("Las licitaciones abiertas (ni adjudicadas ni fallidas; incluye cerradas sin resolver) no "
    "entran a la credibilidad: aporte_credibilidad=0."),
    ("El modelo usa solo los conteos de adjudicadas y cerradas: en cada comuna hay un único "
    "aporte para todas sus adjudicadas y otro para todas sus fallidas."),
    ("Cada aporte es exacto de a una licitación, pero no es aditivo: con más de "
    f"{MAX_EFFECTIVE_N_ASSUMPTION:g} cerradas el tamaño efectivo queda fijo en "
    f"{MAX_EFFECTIVE_N_ASSUMPTION:g}, así que adjudicadas × aporte + fallidas × aporte ≈ 0 y "
    "los aportes no suman la diferencia entre la credibilidad y el prior."),
    ("El efecto de una sola licitación sobre los delitos simulados es menor que la resolución "
    "Monte Carlo de la simulación, así que no se publica."),
    ("Adjudicar una licitación no es ejecutar una medida: la tasa de adjudicación es un proxy "
    "de capacidad operativa municipal."),
]


@dataclass
class CommuneTenders:
    rows: list[dict[str, str]] = field(default_factory=list)

    def count(self, state: str) -> int:
        return sum(1 for r in self.rows if r["estado"] == state)

    def summary(self, code: str) -> CommuneProcurementSummary:
        awarded, failed = self.count("adjudicada"), self.count("fallida")
        return _summary(code, len(self.rows), awarded, failed)


def _summary(code: str, total: int, awarded: int, failed: int) -> CommuneProcurementSummary:
    # Only the counts reach estimate_commune_credibility; amounts and days are not used.
    return CommuneProcurementSummary(code, total, awarded, failed, awarded + failed, 0.0, None,
                                     None)


def _mean(summary: CommuneProcurementSummary) -> float:
    return estimate_commune_credibility(summary, prior=SECURITY_CREDIBILITY).credibility.mean


def leave_one_out(summary: CommuneProcurementSummary) -> dict[str, float]:
    """aporte = mean with every closed tender - mean without one tender of each closed state."""
    full = _mean(summary)
    out = {}
    for state in CLOSED_STATES:
        awarded = summary.tenders_awarded - (state == "adjudicada")
        failed = summary.tenders_failed - (state == "fallida")
        if awarded < 0 or failed < 0:
            continue
        out[state] = full - _mean(_summary(summary.codigo_comuna, summary.tenders_total - 1,
                                           awarded, failed))
    return out


def load_detail(path: Path, min_year: int) -> dict[str, CommuneTenders]:
    by_commune: dict[str, CommuneTenders] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row["anio"]) < min_year:
                continue
            if row["estado"] not in STATES:
                raise SystemExit(f"Unknown estado {row['estado']!r} in {path}")
            by_commune.setdefault(row["codigo_comuna"], CommuneTenders()).rows.append(row)
    return dict(sorted(by_commune.items()))


def target_credibility(simulation: dict) -> dict[str, dict]:
    """credibilidad_por_comuna merged across policies; the same commune must agree."""
    out: dict[str, dict] = {}
    for policy in simulation.get("politicas", []):
        for code, cred in (policy.get("credibilidad_por_comuna") or {}).items():
            if code in out and out[code] != cred:
                raise SystemExit(f"credibilidad_por_comuna disagrees across policies for {code}")
            out[code] = cred
    return out


def check_inputs(tenders: dict[str, CommuneTenders],
                 summaries: dict[str, CommuneProcurementSummary],
                 targets: dict[str, dict]) -> list[str]:
    """Every mismatch between the detail, the aggregates and simulacion.json."""
    errors = []
    for code in sorted(set(tenders) | set(summaries)):
        detail = tenders.get(code, CommuneTenders()).summary(code)
        agg = summaries.get(code)
        got = (detail.tenders_total, detail.tenders_awarded, detail.tenders_failed,
               detail.tenders_closed)
        want = ((agg.tenders_total, agg.tenders_awarded, agg.tenders_failed, agg.tenders_closed)
                if agg else (0, 0, 0, 0))
        if got != want:
            errors.append(f"{code}: detail counts {got} != aggregates {want}")
    estimates = municipal_credibility(sorted(targets), summaries)
    for code, cred in sorted(targets.items()):
        est = estimates[code]
        recomputed = _mean(tenders.get(code, CommuneTenders()).summary(code))
        if round(recomputed, 3) != cred.get("media") or round(est.credibility.mean, 3) != cred.get(
                "media"):
            errors.append(f"{code}: recomputed mean {recomputed:.6f} != media {cred.get('media')}")
        if est.sample_size != cred.get("licitaciones_cerradas"):
            errors.append(f"{code}: closed {est.sample_size} != "
                          f"licitaciones_cerradas {cred.get('licitaciones_cerradas')}")
        if est.award_rate != cred.get("tasa_adjudicacion"):
            errors.append(f"{code}: award rate {est.award_rate} != "
                          f"tasa_adjudicacion {cred.get('tasa_adjudicacion')}")
    return errors


def _num(raw: str) -> float | int | None:
    if not raw:
        return None
    val = float(raw)
    return int(val) if val.is_integer() else val


def _sig(x: float) -> float:
    return float(f"{x:.6g}")


def build(tenders: dict[str, CommuneTenders], targets: dict[str, dict],
          policies: list[str], year: int) -> dict:
    comunas = {}
    for code, group in tenders.items():
        summary = group.summary(code)
        in_model = code in targets
        aporte = leave_one_out(summary) if in_model else {}
        comunas[code] = {
            "afecta_modelo": in_model,
            "licitaciones_total": summary.tenders_total,
            "adjudicadas": summary.tenders_awarded,
            "fallidas": summary.tenders_failed,
            "cerradas": summary.tenders_closed,
            "abiertas": group.count("abierta"),
            "tasa_adjudicacion": (round(summary.tenders_awarded / summary.tenders_closed, 6)
                                  if summary.tenders_closed else None),
            "credibilidad_media": round(_mean(summary), 6) if in_model else None,
            "licitaciones": [
                {
                    "codigo_externo": r["codigo_externo"],
                    "nombre": r["nombre"],
                    "estado": r["estado"],
                    "estado_chilecompra": r["estado_chilecompra"],
                    "sector": r["sector"],
                    "monto_estimado_clp": _num(r["monto_estimado_clp"]),
                    "monto_adjudicado_clp": _num(r["monto_adjudicado_clp"]),
                    "numero_oferentes": _num(r["numero_oferentes"]),
                    "aporte_credibilidad": _sig(aporte.get(r["estado"], 0.0)),
                }
                for r in group.rows
            ],
        }
    return {
        "meta": {
            "fuente": "ChileCompra Datos Abiertos, data/licitaciones/licitaciones_detalle.csv "
                      "(una fila por licitación deduplicada por CodigoExterno)",
            "simulacion": "viz/datos/simulacion.json (politicas[].credibilidad_por_comuna)",
            "anio": year,
            "metodo": (
                "aporte_credibilidad = media_con - media_sin: media posterior de la credibilidad "
                "municipal con todas las licitaciones cerradas menos la media sin esa "
                "licitación (leave-one-out exacto). Prior Beta("
                f"{SECURITY_CREDIBILITY.alpha:g}, {SECURITY_CREDIBILITY.beta:g}) actualizado con "
                "adjudicadas y fallidas, tope de tamaño efectivo "
                f"{MAX_EFFECTIVE_N_ASSUMPTION:g} (core/licitaciones.py, "
                "estimate_commune_credibility). Positivo: la licitación sube la credibilidad."
            ),
            "prior": {"alpha": SECURITY_CREDIBILITY.alpha, "beta": SECURITY_CREDIBILITY.beta},
            "max_n_efectivo": MAX_EFFECTIVE_N_ASSUMPTION,
            "politicas": policies,
            "comunas_modelo": sorted(targets),
            "advertencias": CAVEATS,
        },
        "comunas": comunas,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--detalle", type=Path, default=DETAIL, help="per-tender detail CSV")
    ap.add_argument("--resumen", type=Path, default=PROCUREMENT,
                    help="commune-year aggregates read by the simulation")
    ap.add_argument("--simulacion", type=Path, default=SIMULATION, help="simulacion.json")
    ap.add_argument("--salida", type=Path, default=OUTPUT, help="output JSON")
    args = ap.parse_args(argv)

    simulation = json.loads(args.simulacion.read_text(encoding="utf-8"))
    targets = target_credibility(simulation)
    policies = [p["id"] for p in simulation.get("politicas", [])
                if p.get("credibilidad_por_comuna")]
    tenders = load_detail(args.detalle, PROCUREMENT_YEAR)
    summaries = load_procurement_summaries(args.resumen, min_year=PROCUREMENT_YEAR)
    errors = check_inputs(tenders, summaries, targets)
    if errors:
        raise SystemExit("licitaciones_aporte: inputs disagree, nothing written:\n  "
                         + "\n  ".join(errors))

    out = build(tenders, targets, policies, PROCUREMENT_YEAR)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    args.salida.write_text(body + "\n", encoding="utf-8")
    n = sum(len(c["licitaciones"]) for c in out["comunas"].values())
    print(f"{len(out['comunas'])} communes, {n} tenders, {len(targets)} in the model; "
          f"recomputed means match simulacion.json -> {args.salida} "
          f"({len(body.encode('utf-8')) + 1:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
