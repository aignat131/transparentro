"""ONRC — firme înregistrate (data.gov.ro, organizația `onrc`). CSV cu separator '^'.

Fișierul principal are ~660 MB; îl parcurgem în streaming și reținem doar CUI-urile
care există deja în baza noastră (furnizori ai autorităților din județele țintă).
Completează: data înmatriculării (sursă autoritativă), forma juridică, nr. de registru,
starea firmei (prin od_stare_firma + nomenclator).
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from tro.config import get_settings
from tro.etl.http import download, make_client, request_with_retry
from tro.etl.runlog import RunLog
from tro.models import Company
from tro.normalize import clean_str, is_natural_person, normalize_cui, simplify, to_date

log = logging.getLogger(__name__)

CKAN = "https://data.gov.ro/api/3/action"


def latest_onrc_dataset() -> dict:
    with make_client() as c:
        r = request_with_retry(
            c,
            "GET",
            f"{CKAN}/package_search",
            params={"fq": "organization:onrc", "q": "firme", "sort": "metadata_modified desc", "rows": 20},
        )
        r.raise_for_status()
        for pkg in r.json()["result"]["results"]:
            names = {simplify(res.get("name", "")) for res in pkg.get("resources", [])}
            if any(n.startswith("od_firme") for n in names):
                return pkg
    raise RuntimeError("Nu am găsit un set ONRC cu od_firme.csv")


def _res_url(pkg: dict, prefix: str) -> str | None:
    for res in pkg.get("resources", []):
        if simplify(res.get("name", "")).startswith(prefix):
            return res["url"]
    return None


def _reader(path: Path):
    f = open(path, encoding="utf-8-sig", errors="replace", newline="")  # noqa: SIM115
    return f, csv.DictReader(f, delimiter="^", quoting=csv.QUOTE_NONE)


def parse_onrc_firme(text: str) -> list[dict]:
    """Folosit în teste: parsează un fragment CSV ONRC."""
    rd = csv.DictReader(io.StringIO(text), delimiter="^", quoting=csv.QUOTE_NONE)
    return list(rd)


def import_onrc(session: Session, path_firme: Path | None = None) -> int:
    s = get_settings()
    run = RunLog(session, "onrc", {})
    companies = {
        c.cui: c
        for c in session.execute(
            select(Company).where(Company.is_synthetic.is_(False), Company.cui.regexp_match(r"^\d{1,10}$"))
        ).scalars()
    }
    if not companies:
        run.finish("skipped", "Nicio firmă în baza de date")
        return 0
    data_dir = Path(s.data_dir) / "onrc"
    pkg: dict = {}
    if path_firme is None:
        pkg = latest_onrc_dataset()
        url = _res_url(pkg, "od_firme")
        assert url
        run.run.params = {"dataset": pkg["name"], "url": url}
        path_firme = download(url, data_dir / f"{pkg['name']}_od_firme.csv")
    by_reg: dict[str, Company] = {}
    now = dt.datetime.now(dt.UTC)
    f, rd = _reader(path_firme)
    with f:
        for row in rd:
            run.run.rows_read += 1
            cui = normalize_cui(row.get("CUI"))
            comp = companies.get(cui or "")
            if not comp:
                continue
            try:
                d = to_date(row.get("DATA_INMATRICULARE"))
                if d:
                    comp.founded_on = d
                    comp.founded_source = "onrc"
                lf = clean_str(row.get("FORMA_JURIDICA"), 120)
                if lf:
                    comp.legal_form = lf
                    if is_natural_person(legal_form=lf):
                        comp.is_natural_person = True
                        comp.name = "Persoană fizică autorizată"
                reg = clean_str(row.get("COD_INMATRICULARE"), 60)
                if reg:
                    comp.registry_number = reg
                    by_reg[reg] = comp
                comp.onrc_checked_at = now
                run.run.rows_upserted += 1
            except Exception as exc:  # noqa: BLE001
                run.error(cui, str(exc), row)
    session.commit()
    # starea firmei (opțional)
    if pkg and by_reg:
        try:
            st_url = _res_url(pkg, "od_stare_firma")
            if st_url:
                st_path = download(st_url, data_dir / f"{pkg['name']}_od_stare_firma.csv")
                nomen = _load_state_nomenclator(data_dir)
                f2, rd2 = _reader(st_path)
                with f2:
                    for row in rd2:
                        comp = by_reg.get(row.get("COD_INMATRICULARE", ""))
                        if comp and row.get("COD"):
                            comp.status = nomen.get(row["COD"].strip(), comp.status)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            run.error("od_stare_firma", f"stare firmă indisponibilă: {exc}")
    run.finish()
    return run.run.rows_upserted


def _load_state_nomenclator(data_dir: Path) -> dict[str, str]:
    with make_client() as c:
        r = request_with_retry(
            c,
            "GET",
            f"{CKAN}/package_search",
            params={"fq": "organization:onrc", "q": "n_stare_firma", "rows": 10},
        )
        r.raise_for_status()
        for pkg in r.json()["result"]["results"]:
            url = _res_url(pkg, "n_stare_firma")
            if url:
                p = download(url, data_dir / "n_stare_firma.csv")
                f, rd = _reader(p)
                with f:
                    out = {}
                    for row in rd:
                        vals = list(row.values())
                        if len(vals) >= 2 and vals[0]:
                            out[str(vals[0]).strip()] = str(vals[1]).strip()
                    return out
    return {}
