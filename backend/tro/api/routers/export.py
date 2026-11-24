"""Export CSV pentru orice listă filtrată (aceleași filtre ca listele JSON)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from tro.api.common import ContractFilters, company_key, county_param
from tro.api.routers.authorities import authorities_query
from tro.api.routers.companies import companies_query
from tro.api.routers.contracts import contracts_query
from tro.api.routers.risk import SignalFilters, signals_query
from tro.cpv import cpv_category
from tro.db import get_db
from tro.etl.risk import SIGNAL_TYPES

router = APIRouter(prefix="/export", tags=["export"])
MAX_ROWS = 100_000


def _stream(header: list[str], rows: Iterable[list[object]]) -> Iterator[str]:
    buf = io.StringIO()
    w = csv.writer(buf)
    buf.write("﻿")  # BOM: Excel deschide corect diacriticele
    w.writerow(header)
    yield buf.getvalue()
    for i, r in enumerate(rows):
        if i >= MAX_ROWS:
            break
        buf.seek(0)
        buf.truncate()
        w.writerow(["" if v is None else v for v in r])
        yield buf.getvalue()


def _resp(name: str, gen: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@router.get("/contracts.csv", summary="Export CSV contracte (aceleași filtre ca /contracts)")
def export_contracts(f: ContractFilters = Depends(), db: Session = Depends(get_db)):
    def rows():
        for c in db.execute(contracts_query(db, f).limit(MAX_ROWS)).scalars():
            yield [
                c.id,
                c.contract_date,
                c.year,
                c.title or c.cpv_name,
                c.value_ron,
                c.procedure_type,
                c.contract_type,
                c.cpv_code,
                cpv_category(c.cpv_code),
                c.authority.name,
                c.authority.cui,
                c.company.display_name if c.company else None,
                (None if (not c.company or c.company.is_natural_person) else c.company.cui),
                c.notice_number,
                c.contract_number,
                c.source,
                "da" if c.is_synthetic else "nu",
                c.source_url,
            ]

    header = [
        "id",
        "data_contract",
        "an",
        "obiect",
        "valoare_ron",
        "tip_procedura",
        "tip_contract",
        "cpv",
        "categorie",
        "institutie",
        "cui_institutie",
        "furnizor",
        "cui_furnizor",
        "numar_anunt",
        "numar_contract",
        "sursa",
        "sintetic",
        "url_sursa",
    ]
    return _resp("contracte", _stream(header, rows()))


@router.get("/authorities.csv", summary="Export CSV instituții")
def export_authorities(
    county: str | None = Depends(county_param),
    q: str | None = None,
    authority_type: str | None = None,
    year: int | None = None,
    domain: str | None = None,
    db: Session = Depends(get_db),
):
    stmt, totals = authorities_query(county, q, authority_type, year, domain)

    def rows():
        for a, t, n in db.execute(stmt.order_by(totals.c.total.desc().nulls_last()).limit(MAX_ROWS)).all():
            yield [
                a.id,
                a.name,
                a.cui,
                a.county_code,
                a.locality,
                a.authority_type,
                t,
                n,
                "da" if a.is_synthetic else "nu",
            ]

    return _resp(
        "institutii",
        _stream(
            ["id", "denumire", "cui", "judet", "localitate", "tip", "total_ron", "contracte", "sintetic"],
            rows(),
        ),
    )


@router.get("/companies.csv", summary="Export CSV firme")
def export_companies(
    county: str | None = Depends(county_param),
    q: str | None = None,
    year: int | None = None,
    with_signals: bool = Query(False),
    domain: str | None = None,
    db: Session = Depends(get_db),
):
    stmt, totals, _ = companies_query(county, q, year, with_signals, domain)

    def rows():
        for c, t, n, ns in db.execute(stmt.order_by(totals.c.total.desc()).limit(MAX_ROWS)).all():
            yield [
                company_key(c),
                c.display_name,
                None if c.is_natural_person else c.cui,
                c.locality,
                None if c.is_natural_person else c.founded_on,
                c.caen_code,
                t,
                n,
                ns,
                "da" if c.is_synthetic else "nu",
            ]

    return _resp(
        "firme",
        _stream(
            [
                "cheie",
                "denumire",
                "cui",
                "localitate",
                "data_infiintarii",
                "caen",
                "total_ron",
                "contracte",
                "semnale",
                "sintetic",
            ],
            rows(),
        ),
    )


@router.get("/risk-signals.csv", summary="Export CSV semnale")
def export_signals(f: SignalFilters = Depends(), db: Session = Depends(get_db)):
    def rows():
        for s in db.execute(signals_query(db, f).limit(MAX_ROWS)).scalars():
            yield [
                s.id,
                SIGNAL_TYPES.get(s.signal_type, s.signal_type),
                s.score,
                s.year,
                s.title,
                s.explanation,
                s.authority.name if s.authority else None,
                s.company.display_name if s.company else None,
                s.contract_id,
                s.source_url,
                "da" if s.is_synthetic else "nu",
            ]

    return _resp(
        "semnale",
        _stream(
            [
                "id",
                "tip",
                "scor",
                "an",
                "titlu",
                "explicatie",
                "institutie",
                "firma",
                "contract_id",
                "url_sursa",
                "sintetic",
            ],
            rows(),
        ),
    )
