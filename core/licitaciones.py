"""Procurement credibility integration for the simulation kernel.

Reads cleaned commune-level ChileCompra aggregates (`data/licitaciones/resumen_comuna_anio.csv`)
when present, and updates an executor Beta prior via Beta-Binomial updating with an effective
sample-size cap so high-volume municipalities keep realistic epistemic bands.

Used by experiments/simular.py for the municipal credibility of commune-level security policies.
"""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from core.credibilidad import BetaCredibility, Provenance

# Assumption, no source: minimum closed tenders before the award rate is used as a base rate.
MIN_SAMPLE_ASSUMPTION = 20
# Assumption, no source: cap on the effective sample size of the Beta update, so hundreds of
# tenders do not collapse the p10-p90 band of a commune's credibility.
MAX_EFFECTIVE_N_ASSUMPTION = 40.0


@dataclass(frozen=True)
class CommuneProcurementSummary:
    """Aggregated ChileCompra execution summary for one commune."""

    codigo_comuna: str
    tenders_total: int
    tenders_awarded: int
    tenders_failed: int
    tenders_closed: int
    awarded_amount_clp: float
    median_award_days: float | None
    single_bidder_share: float | None


@dataclass(frozen=True)
class ProcurementCredibilityEstimate:
    """Beta credibility estimate derived from procurement history and a prior."""

    codigo_comuna: str | None
    credibility: BetaCredibility
    provenance: Provenance
    sample_size: int
    effective_sample_size: float
    award_rate: float | None


def _opt_int(raw: str | None) -> int:
    s = (raw or "").strip()
    return int(float(s)) if s else 0


def _opt_float(raw: str | None) -> float | None:
    s = (raw or "").strip()
    return float(s) if s else None


def load_procurement_summaries(
    csv_path: Path,
    *,
    min_year: int | None = None,
) -> dict[str, CommuneProcurementSummary]:
    """Load commune-level procurement summaries from CSV; returns {} if the file is missing."""
    if not csv_path.exists():
        return {}

    grouped: dict[str, list[dict[str, str]]] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("codigo_comuna") or "").strip()
            if not code:
                continue
            year_val = _opt_int(row.get("anio"))
            if min_year is not None and year_val < min_year:
                continue
            grouped.setdefault(code, []).append(row)

    out: dict[str, CommuneProcurementSummary] = {}
    for code, rows in sorted(grouped.items()):
        total = sum(_opt_int(r.get("total_licitaciones")) for r in rows)
        awarded = sum(_opt_int(r.get("adjudicadas")) for r in rows)
        failed = sum(_opt_int(r.get("fallidas")) for r in rows)
        closed = sum(_opt_int(r.get("cerradas")) for r in rows)
        amount = sum(_opt_float(r.get("monto_adjudicado_clp")) or 0.0 for r in rows)

        days_vals = [
            v
            for r in rows
            if (v := _opt_float(r.get("mediana_dias_pub_adj"))) is not None
        ]
        single_vals = [
            v
            for r in rows
            if (v := _opt_float(r.get("proporcion_oferente_unico"))) is not None
        ]

        out[code] = CommuneProcurementSummary(
            codigo_comuna=code,
            tenders_total=total,
            tenders_awarded=awarded,
            tenders_failed=failed,
            tenders_closed=closed,
            awarded_amount_clp=round(amount, 2),
            median_award_days=(
                round(float(statistics.median(days_vals)), 3) if days_vals else None
            ),
            single_bidder_share=(
                round(float(statistics.mean(single_vals)), 6) if single_vals else None
            ),
        )
    return out


def estimate_commune_credibility(
    summary: CommuneProcurementSummary | None,
    *,
    prior: BetaCredibility,
    min_sample: int = MIN_SAMPLE_ASSUMPTION,
    max_effective_n: float = MAX_EFFECTIVE_N_ASSUMPTION,
) -> ProcurementCredibilityEstimate:
    """Update a Beta prior using observed closed tenders (awarded vs failed).

    When `tenders_closed` exceeds `max_effective_n`, awarded and failed counts are rescaled
    linearly to sum to `max_effective_n`, which keeps a realistic epistemic band width. The
    posterior mean is (alpha + s * awarded) / (alpha + beta + s * closed), so the prior shifts
    it away from the observed award rate; it does not equal that rate.

    Provenance: awarding a tender is not executing a measure, so this never returns
    "medida". With at least `min_sample` closed tenders the award rate stands as a
    municipal base rate ("tasa_base"); with fewer, or none, the result stays "supuesto".
    """
    if min_sample < 1:
        raise ValueError("min_sample must be at least 1")
    if max_effective_n <= 0:
        raise ValueError("max_effective_n must be positive")

    if summary is None or summary.tenders_closed <= 0:
        return ProcurementCredibilityEstimate(
            codigo_comuna=summary.codigo_comuna if summary is not None else None,
            credibility=prior,
            provenance="supuesto",
            sample_size=0,
            effective_sample_size=0.0,
            award_rate=None,
        )

    closed = summary.tenders_closed
    awarded = max(0, min(summary.tenders_awarded, closed))
    failed = max(0, closed - awarded)
    scale = min(1.0, max_effective_n / closed)
    eff_awarded = awarded * scale
    eff_failed = failed * scale

    posterior = BetaCredibility(prior.alpha + eff_awarded, prior.beta + eff_failed)
    provenance: Provenance = "tasa_base" if closed >= min_sample else "supuesto"
    return ProcurementCredibilityEstimate(
        codigo_comuna=summary.codigo_comuna,
        credibility=posterior,
        provenance=provenance,
        sample_size=closed,
        effective_sample_size=round(eff_awarded + eff_failed, 4),
        award_rate=round(awarded / closed, 6),
    )
