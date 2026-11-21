"""Schema, normalization, RM commune matching, and aggregation for ChileCompra CSV dumps."""
from __future__ import annotations

import csv
import datetime as dt
import io
import math
import re
import statistics
import unicodedata
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMUNES_CSV = ROOT / "data" / "comunas_rm.csv"

CHILECOMPRA_URL_TEMPLATE = (
    "https://transparenciachc.blob.core.windows.net/lic-da/{year}-{month}.zip"
)
# Exclude extreme reporting typos (> 1 trillion CLP) documented in ChileCompra dumps.
MAX_REASONABLE_AMOUNT_CLP = 1_000_000_000_000.0

AWARDED_STATUS_CODES = frozenset({"8"})
FAILED_STATUS_CODES = frozenset({"7", "18", "19"})  # 7=Desierta, 18=Revocada, 19=Suspendida
AWARDED_STATUS_TEXTS = frozenset({"adjudicada"})
FAILED_STATUS_TEXTS = frozenset({"desierta", "revocada", "suspendida"})

SECTORS: tuple[str, ...] = (
    "agua",
    "energia",
    "aire_calefaccion",
    "seguridad",
    "infraestructura",
    "otros",
)

SECTOR_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "aire_calefaccion",
        (
            "calefac",
            "lena",
            "pellet",
            "estufa",
            "calidad del aire",
            "descontamin",
            "emision",
            "climatiz",
            "aislacion termica",
        ),
    ),
    (
        "agua",
        (
            "agua potable",
            "aguas servidas",
            "alcantarillado",
            "hidric",
            "riego",
            "apr ",
            "camion aljibe",
            "drenaje",
            "agua",
        ),
    ),
    (
        "energia",
        (
            "energia",
            "solar",
            "fotovoltaic",
            "eficiencia energetica",
            "subestacion",
            "generador",
            "electric",
        ),
    ),
    (
        "seguridad",
        (
            "seguridad",
            "camara",
            "teleproteccion",
            "vigilancia",
            "patrullaje",
            "alarma",
            "iluminacion publica",
            "alumbrado",
            "luminaria",
        ),
    ),
    (
        "infraestructura",
        (
            "construccion",
            "paviment",
            "vereda",
            "cesfam",
            "escuela",
            "hospital",
            "plaza",
            "parque",
            "obra civil",
            "infraestructura",
            "vialidad",
        ),
    ),
)

_MUNI_RE = re.compile(
    r"^(?:i\.?\s+|ilustre\s+)?municipalidad\s+(?:de\s+|del\s+)?(.+)$"
)
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
)
_MIN_VALID_DATE = dt.date(2000, 1, 1)
_MAX_VALID_DATE = dt.date(2100, 1, 1)


@dataclass(frozen=True)
class TenderLineRecord:
    """One cleaned line-item row extracted from a ChileCompra monthly CSV."""

    codigo_externo: str
    codigo_comuna: str
    anio: int
    estado: str
    adjudicada: bool
    fallida: bool
    sector: str
    monto_estimado: float | None
    monto_adjudicado: float | None
    numero_oferentes: int | None
    cantidad_reclamos: int
    dias_pub_cierre: int | None
    dias_pub_adj: int | None
    outlier_monto: bool = False


@dataclass(frozen=True)
class CommuneYearMetrics:
    """Aggregated procurement indicators for one RM commune and publication year."""

    codigo_comuna: str
    anio: int
    total_licitaciones: int
    adjudicadas: int
    fallidas: int
    cerradas: int
    tasa_adjudicacion: float | None
    mediana_dias_pub_cierre: float | None
    mediana_dias_pub_adj: float | None
    mediana_oferentes: float | None
    proporcion_oferente_unico: float | None
    monto_estimado_clp: float
    monto_adjudicado_clp: float
    total_reclamos: int


@dataclass(frozen=True)
class CommuneSectorMetrics:
    """Aggregated procurement indicators for one RM commune and domain sector."""

    codigo_comuna: str
    sector: str
    total_licitaciones: int
    adjudicadas: int
    fallidas: int
    monto_adjudicado_clp: float


def normalize_text(text: str | None) -> str:
    """Lowercase, strip accents (NFKD), and collapse whitespace."""
    if not text:
        return ""
    plain = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip().lower()


def parse_chilecompra_float(raw: str | None) -> float | None:
    """Parse Chilean- or US-formatted numbers from ChileCompra CSVs.

    Rejects empty strings, placeholders ('--'), NaN/Inf, and negative values.
    """
    if raw is None:
        return None
    s = raw.strip().replace("$", "").replace("%", "").replace(" ", "")
    if not s or s.lower() in {"--", "na", "nan", "null", "none", "n/a"}:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if s.count(",") == 1:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        val = float(s)
    except ValueError:
        return None
    if not math.isfinite(val) or val < 0:
        return None
    return val


def parse_chilecompra_int(raw: str | None) -> int | None:
    """Parse a non-negative integer field from a ChileCompra CSV."""
    val = parse_chilecompra_float(raw)
    if val is None:
        return None
    return round(val)


def parse_chilecompra_date(raw: str | None) -> dt.date | None:
    """Parse dates from ChileCompra CSVs, rejecting invalid or sentinel dates (<2000)."""
    if raw is None:
        return None
    s = raw.strip()
    if not s or s.lower() in {"--", "na", "nan", "null", "none", "n/a"}:
        return None
    # Handle ISO timestamps with fractional seconds or timezone suffix.
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        candidate = s[:10]
        try:
            parsed = dt.date.fromisoformat(candidate)
            if _MIN_VALID_DATE <= parsed <= _MAX_VALID_DATE:
                return parsed
            return None
        except ValueError:
            pass
    for fmt in _DATE_FORMATS:
        try:
            parsed = dt.datetime.strptime(s, fmt).date()
            if _MIN_VALID_DATE <= parsed <= _MAX_VALID_DATE:
                return parsed
            return None
        except ValueError:
            continue
    return None


def load_rm_commune_index(path: Path = DEFAULT_COMMUNES_CSV) -> dict[str, str]:
    """Map normalized commune name -> 5-digit CUT codigo_comuna from data/comunas_rm.csv."""
    index: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = normalize_text(row.get("comuna"))
            code = (row.get("codigo_comuna") or "").strip()
            if name and code:
                index[name] = code
    return index


RM_COMMUNE_ALIASES: dict[str, str] = {
    "til til": "tiltil",
    "til-til": "tiltil",
}


def match_rm_commune(
    commune_field: str | None,
    org_name: str | None,
    commune_index: Mapping[str, str],
) -> str | None:
    """Resolve an RM commune CUT code conservatively without guessing.

    Checks exact normalized `commune_field` first, then `Municipalidad de <commune>`
    patterns in `org_name`. National ministries without an RM commune stay `None`.
    """
    norm_commune = normalize_text(commune_field)
    norm_commune = RM_COMMUNE_ALIASES.get(norm_commune, norm_commune)
    if norm_commune in commune_index:
        return commune_index[norm_commune]

    norm_org = normalize_text(org_name)
    if norm_org:
        match = _MUNI_RE.match(norm_org)
        if match:
            candidate = match.group(1).strip(" .,;-")
            candidate = RM_COMMUNE_ALIASES.get(candidate, candidate)
            if candidate in commune_index:
                return commune_index[candidate]
    return None


def classify_sector(name: str, description: str, product_name: str = "") -> str:
    """Classify a procurement line into one of SECTORS using normalized keywords."""
    haystack = f" {normalize_text(name)} {normalize_text(description)} {normalize_text(product_name)} "
    for sector, keywords in SECTOR_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return sector
    return "otros"


def _field_lookup(row: Mapping[str, str], *names: str) -> str:
    """Fetch the first matching column value using normalized header names."""
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    normalized_row = {normalize_text(k): v for k, v in row.items() if k is not None}
    for name in names:
        key = normalize_text(name)
        if key in normalized_row and normalized_row[key] is not None:
            return normalized_row[key]
    return ""


def iter_records_from_csv_stream(
    text_stream: TextIO,
    commune_index: Mapping[str, str],
    *,
    default_year: int | None = None,
    diagnostics: dict[str, int] | None = None,
) -> Iterator[TenderLineRecord]:
    """Yield cleaned RM TenderLineRecord items from a semicolon-delimited CSV stream."""
    reader = csv.DictReader(text_stream, delimiter=";")
    for row in reader:
        if diagnostics is not None:
            diagnostics["total_filas"] = diagnostics.get("total_filas", 0) + 1

        codigo_externo = _field_lookup(row, "CodigoExterno", "Codigo").strip()
        if not codigo_externo:
            continue

        commune_field = _field_lookup(row, "ComunaUnidad", "Comuna")
        org_name = _field_lookup(row, "NombreOrganismo", "Organismo")
        codigo_comuna = match_rm_commune(commune_field, org_name, commune_index)
        if codigo_comuna is None:
            if diagnostics is not None:
                diagnostics["filas_sin_comuna_rm"] = (
                    diagnostics.get("filas_sin_comuna_rm", 0) + 1
                )
            continue

        pub_date = parse_chilecompra_date(_field_lookup(row, "FechaPublicacion"))
        close_date = parse_chilecompra_date(_field_lookup(row, "FechaCierre"))
        adj_date = parse_chilecompra_date(_field_lookup(row, "FechaAdjudicacion"))
        anio = (
            pub_date.year
            if pub_date is not None
            else adj_date.year
            if adj_date is not None
            else close_date.year
            if close_date is not None
            else default_year
        )
        if anio is None:
            continue

        code_status = _field_lookup(
            row, "CodigoEstado", "CodigoEstadoLicitacion"
        ).strip()
        text_status = normalize_text(_field_lookup(row, "Estado", "EstadoLicitacion"))
        adjudicada = (
            code_status in AWARDED_STATUS_CODES or text_status in AWARDED_STATUS_TEXTS
        )
        fallida = not adjudicada and (
            code_status in FAILED_STATUS_CODES or text_status in FAILED_STATUS_TEXTS
        )
        estado_label = text_status or code_status or "desconocido"

        monto_estimado = parse_chilecompra_float(_field_lookup(row, "MontoEstimado"))
        monto_adjudicado = parse_chilecompra_float(
            _field_lookup(row, "MontoLineaAdjudica", "MontoAdjudicado")
        )
        outlier_monto = False
        if monto_estimado is not None and monto_estimado > MAX_REASONABLE_AMOUNT_CLP:
            outlier_monto = True
            monto_estimado = None
        if monto_adjudicado is not None and monto_adjudicado > MAX_REASONABLE_AMOUNT_CLP:
            outlier_monto = True
            monto_adjudicado = None
        if outlier_monto and diagnostics is not None:
            diagnostics["outliers_monto_filtrados"] = (
                diagnostics.get("outliers_monto_filtrados", 0) + 1
            )

        dias_pub_cierre = (
            (close_date - pub_date).days
            if pub_date is not None and close_date is not None and close_date >= pub_date
            else None
        )
        dias_pub_adj = (
            (adj_date - pub_date).days
            if pub_date is not None and adj_date is not None and adj_date >= pub_date
            else None
        )

        numero_oferentes = parse_chilecompra_int(_field_lookup(row, "NumeroOferentes"))
        cantidad_reclamos = (
            parse_chilecompra_int(_field_lookup(row, "CantidadReclamos")) or 0
        )

        sector = classify_sector(
            _field_lookup(row, "Nombre"),
            _field_lookup(row, "Descripcion", "Descripcion linea Adquisicion"),
            _field_lookup(
                row,
                "Nombre producto genrico",
                "Nombre producto generico",
                "NombreProductoGenerico",
            ),
        )

        if diagnostics is not None:
            diagnostics["filas_rm"] = diagnostics.get("filas_rm", 0) + 1

        yield TenderLineRecord(
            codigo_externo=codigo_externo,
            codigo_comuna=codigo_comuna,
            anio=anio,
            estado=estado_label,
            adjudicada=adjudicada,
            fallida=fallida,
            sector=sector,
            monto_estimado=monto_estimado,
            monto_adjudicado=monto_adjudicado,
            numero_oferentes=numero_oferentes,
            cantidad_reclamos=cantidad_reclamos,
            dias_pub_cierre=dias_pub_cierre,
            dias_pub_adj=dias_pub_adj,
            outlier_monto=outlier_monto,
        )


def iter_records_from_zip(
    zip_path: Path,
    commune_index: Mapping[str, str],
    *,
    default_year: int | None = None,
    diagnostics: dict[str, int] | None = None,
) -> Iterator[TenderLineRecord]:
    """Read every CSV inside a ChileCompra monthly ZIP using latin-1 encoding."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith(".csv"):
                continue
            with zf.open(name) as raw_fh:
                text_fh = io.TextIOWrapper(
                    raw_fh, encoding="latin-1", errors="replace", newline=""
                )
                yield from iter_records_from_csv_stream(
                    text_fh,
                    commune_index,
                    default_year=default_year,
                    diagnostics=diagnostics,
                )


@dataclass
class _TenderAcc:
    codigo_comuna: str
    anio: int
    adjudicada: bool = False
    fallida: bool = False
    sector: str = "otros"
    monto_estimado: float | None = None
    monto_adjudicado: float = 0.0
    numero_oferentes: int | None = None
    cantidad_reclamos: int = 0
    dias_pub_cierre: int | None = None
    dias_pub_adj: int | None = None


def aggregate_records(
    records: Iterable[TenderLineRecord],
) -> tuple[list[CommuneYearMetrics], list[CommuneSectorMetrics]]:
    """Deduplicate tender-level attributes per CodigoExterno and aggregate by commune.

    ChileCompra dumps contain one row per line item (`CodigoExterno` repeats).
    Status, dates, bidder counts, complaints, and `MontoEstimado` are tender-level
    and deduplicated per `(codigo_comuna, codigo_externo)`; `MontoLineaAdjudica` is
    line-level and summed across lines.
    """
    tenders: dict[tuple[str, str], _TenderAcc] = {}
    for rec in records:
        key = (rec.codigo_comuna, rec.codigo_externo)
        acc = tenders.get(key)
        if acc is None:
            acc = _TenderAcc(codigo_comuna=rec.codigo_comuna, anio=rec.anio)
            tenders[key] = acc
        else:
            acc.anio = min(acc.anio, rec.anio)

        if rec.adjudicada:
            acc.adjudicada = True
            acc.fallida = False
        elif rec.fallida and not acc.adjudicada:
            acc.fallida = True

        if acc.sector == "otros" and rec.sector != "otros":
            acc.sector = rec.sector
        if acc.monto_estimado is None and rec.monto_estimado is not None:
            acc.monto_estimado = rec.monto_estimado
        if rec.monto_adjudicado is not None and not rec.outlier_monto:
            acc.monto_adjudicado += rec.monto_adjudicado
        if rec.numero_oferentes is not None:
            acc.numero_oferentes = (
                rec.numero_oferentes
                if acc.numero_oferentes is None
                else max(acc.numero_oferentes, rec.numero_oferentes)
            )
        acc.cantidad_reclamos = max(acc.cantidad_reclamos, rec.cantidad_reclamos)
        if acc.dias_pub_cierre is None and rec.dias_pub_cierre is not None:
            acc.dias_pub_cierre = rec.dias_pub_cierre
        if acc.dias_pub_adj is None and rec.dias_pub_adj is not None:
            acc.dias_pub_adj = rec.dias_pub_adj

    by_year: dict[tuple[str, int], list[_TenderAcc]] = defaultdict(list)
    by_sector: dict[tuple[str, str], list[_TenderAcc]] = defaultdict(list)
    for t in tenders.values():
        by_year[(t.codigo_comuna, t.anio)].append(t)
        by_sector[(t.codigo_comuna, t.sector)].append(t)

    year_metrics: list[CommuneYearMetrics] = []
    for codigo_comuna, anio in sorted(by_year):
        items = by_year[(codigo_comuna, anio)]
        adj = sum(1 for t in items if t.adjudicada)
        fal = sum(1 for t in items if t.fallida)
        closed = adj + fal
        dias_cierre = [t.dias_pub_cierre for t in items if t.dias_pub_cierre is not None]
        dias_adj = [t.dias_pub_adj for t in items if t.dias_pub_adj is not None]
        oferentes = [t.numero_oferentes for t in items if t.numero_oferentes is not None]
        year_metrics.append(
            CommuneYearMetrics(
                codigo_comuna=codigo_comuna,
                anio=anio,
                total_licitaciones=len(items),
                adjudicadas=adj,
                fallidas=fal,
                cerradas=closed,
                tasa_adjudicacion=round(adj / closed, 6) if closed > 0 else None,
                mediana_dias_pub_cierre=(
                    round(float(statistics.median(dias_cierre)), 3) if dias_cierre else None
                ),
                mediana_dias_pub_adj=(
                    round(float(statistics.median(dias_adj)), 3) if dias_adj else None
                ),
                mediana_oferentes=(
                    round(float(statistics.median(oferentes)), 3) if oferentes else None
                ),
                proporcion_oferente_unico=(
                    round(sum(1 for n in oferentes if n == 1) / len(oferentes), 6)
                    if oferentes
                    else None
                ),
                monto_estimado_clp=round(
                    sum(t.monto_estimado for t in items if t.monto_estimado is not None), 2
                ),
                monto_adjudicado_clp=round(sum(t.monto_adjudicado for t in items), 2),
                total_reclamos=sum(t.cantidad_reclamos for t in items),
            )
        )

    sector_metrics: list[CommuneSectorMetrics] = []
    for codigo_comuna, sector in sorted(by_sector):
        items = by_sector[(codigo_comuna, sector)]
        sector_metrics.append(
            CommuneSectorMetrics(
                codigo_comuna=codigo_comuna,
                sector=sector,
                total_licitaciones=len(items),
                adjudicadas=sum(1 for t in items if t.adjudicada),
                fallidas=sum(1 for t in items if t.fallida),
                monto_adjudicado_clp=round(sum(t.monto_adjudicado for t in items), 2),
            )
        )

    return year_metrics, sector_metrics
