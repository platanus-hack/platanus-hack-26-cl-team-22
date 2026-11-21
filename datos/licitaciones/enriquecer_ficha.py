"""Optional single-tender metadata enrichment via LicitaLab public JSON API.

Rate-limited (max 9 req/min) and cached locally for inspecting specific tender IDs
without relying on fragile ASP.NET WebForms scrapers.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from datos.licitaciones.esquema import ROOT

LICITALAB_URL_TEMPLATE = "https://api.licitalab.cl/free/tender/{tender_id}"
RATE_LIMIT_SECONDS = 60.0 / 9.0
DEFAULT_CACHE_DIR = ROOT / "data" / "raw" / "licitaciones" / "fichas"


@dataclass(frozen=True)
class TenderDetail:
    """Normalized metadata for a single tender returned by api.licitalab.cl."""

    tender_id: str
    name: str
    description: str
    status: str
    status_code: int | None
    publish_date: str | None
    close_date: str | None
    organization_name: str
    organization_tax_number: str
    unit_name: str
    unit_city: str
    unit_region: str
    criteria_count: int
    guarantees_count: int


def parse_licitalab_payload(payload: Mapping[str, Any]) -> TenderDetail:
    """Parse a JSON response from https://api.licitalab.cl/free/tender/{id}."""
    tender_id = str(payload.get("tenderId") or "").strip()
    if not tender_id:
        raise ValueError("Missing 'tenderId' in LicitaLab payload")

    dates = payload.get("TenderDate") or {}
    purchase = payload.get("tenderPurchaseData") or {}
    org = purchase.get("organization") or {}
    unit = purchase.get("orgUnit") or {}
    criteria = payload.get("TenderEvaluationCriteria") or []
    guarantees = payload.get("TenderGuarantees") or []

    status_code_raw = payload.get("statusCode")
    status_code = int(status_code_raw) if status_code_raw is not None else None

    return TenderDetail(
        tender_id=tender_id,
        name=str(payload.get("name") or "").strip(),
        description=str(payload.get("description") or "").strip(),
        status=str(payload.get("status") or "").strip(),
        status_code=status_code,
        publish_date=str(dates["publish"]) if dates.get("publish") else None,
        close_date=str(dates["close"]) if dates.get("close") else None,
        organization_name=str(org.get("name") or "").strip(),
        organization_tax_number=str(org.get("tax_number") or "").strip(),
        unit_name=str(unit.get("name") or "").strip(),
        unit_city=str(unit.get("city") or "").strip(),
        unit_region=str(unit.get("region") or "").strip(),
        criteria_count=len(criteria) if isinstance(criteria, list) else 0,
        guarantees_count=len(guarantees) if isinstance(guarantees, list) else 0,
    )


def fetch_tender_detail(
    tender_id: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    force: bool = False,
    delay_s: float = RATE_LIMIT_SECONDS,
) -> TenderDetail:
    """Fetch one tender JSON from LicitaLab with local caching."""
    clean_id = tender_id.strip()
    if not clean_id:
        raise ValueError("tender_id cannot be empty")

    cache_path = cache_dir / f"{clean_id}.json"
    if not cache_path.exists() or force:
        cache_dir.mkdir(parents=True, exist_ok=True)
        url = LICITALAB_URL_TEMPLATE.format(tender_id=clean_id)
        req = urllib.request.Request(url, headers={"User-Agent": "team22-simulation/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
        cache_path.write_bytes(body)
        if delay_s > 0:
            time.sleep(delay_s)

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    return parse_licitalab_payload(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tender_ids", nargs="+", help="One or more Mercado Publico tender IDs")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, help="Optional JSON path to write parsed details")
    parser.add_argument("--forzar-descarga", action="store_true")
    args = parser.parse_args(argv)

    details = [
        asdict(
            fetch_tender_detail(
                tid,
                args.cache_dir,
                force=args.forzar_descarga,
                delay_s=RATE_LIMIT_SECONDS if i < len(args.tender_ids) - 1 else 0.0,
            )
        )
        for i, tid in enumerate(args.tender_ids)
    ]
    serialized = json.dumps(details, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    sys.exit(main())
