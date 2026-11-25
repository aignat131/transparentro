"""Proceduri de achiziție (anunțuri de inițiere din SEAP): licitațiile la care firmele și ONG-urile pot participa.

Datele vin din exporturile periodice data.gov.ro, deci nu sunt în timp real: o procedură e considerată
„în curs” dacă starea ei nu e una de final (atribuită, anulată...), nu are încă un contract în date și a fost
publicată recent față de cel mai nou anunț importat. Anunțul oficial, cu termenele, e pe e-licitatie.ro.
"""

from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, not_, select
from sqlalchemy.orm import Session, selectinload

from tro.api import cache
from tro.api import schemas as S
from tro.api.common import authority_ref, county_param
from tro.cpv import cpv_category
from tro.db import get_db
from tro.domains import domain_condition
from tro.localities import authority_ids
from tro.models import Authority, Contract, Procedure

router = APIRouter(prefix="/procedures", tags=["licitații"])

# stări de final (după unaccent + lower)
CLOSED_STATUS = r"(atribuit|anulat|finalizat|incheiat|suspend|revocat|reziliat|cancel|closed|award)"
# cât de vechi poate fi un anunț față de cel mai nou anunț importat ca să-l mai socotim în curs
OPEN_WINDOW = dt.timedelta(days=120)


class ProcedureItem(BaseModel):
    id: int
    notice_number: str | None
    title: str | None
    authority: S.AuthorityRef
    authority_type: str | None
    procedure_type: str | None
    contract_type: str | None
    cpv_code: str | None
    category: str
    estimated_value_ron: Any | None
    status: str | None
    publication_date: dt.date | None
    official_url: str
    is_open: bool


def _official_url(notice: str | None) -> str:
    url = "https://www.e-licitatie.ro/pub/notices/contract-notices/list/0/0"
    return url + ("?q=" + urllib.parse.quote(notice) if notice else "")


def _open_conditions(db: Session) -> list[Any]:
    newest = db.execute(select(func.max(Procedure.publication_date))).scalar()
    status = func.lower(func.unaccent(func.coalesce(Procedure.status, "")))
    has_contract = select(Contract.id).where(Contract.procedure_id == Procedure.id).exists()
    conds: list[Any] = [not_(status.op("~", is_comparison=True)(CLOSED_STATUS)), not_(has_contract)]
    if newest:
        conds.append(Procedure.publication_date >= newest - OPEN_WINDOW)
    return conds


@router.get("", response_model=S.Page[ProcedureItem], summary="Licitații (proceduri de achiziție)")
def list_procedures(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    status: str = Query("open", pattern="^(open|all)$", description="open = doar cele aflate (probabil) în curs"),
    max_value: float | None = Query(None, ge=0, description="Valoare estimată maximă (lei)"),
    authority_type: str | None = Query(None),
    domain: str | None = Query(None),
    locality: str | None = Query(None, description="Localitate (slug din /localities)"),
    q: str | None = Query(None, max_length=200),
    sort: str = Query("recent", pattern="^(recent|value_desc|value_asc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    def compute() -> S.Page[ProcedureItem]:
        stmt = select(Procedure).join(Authority, Authority.id == Procedure.authority_id)
        open_conds = _open_conditions(db)
        if status == "open":
            stmt = stmt.where(*open_conds)
        if county:
            stmt = stmt.where(Authority.county_code == county)
        if max_value is not None:
            stmt = stmt.where(Procedure.estimated_value_ron <= max_value)
        if authority_type:
            stmt = stmt.where(Authority.authority_type == authority_type)
        if locality:
            stmt = stmt.where(Authority.id.in_(authority_ids(db, county, locality)))
        dcond = domain_condition(domain, Procedure.cpv_code)
        if dcond is not None:
            stmt = stmt.where(dcond)
        if q:
            words = [w for w in q.split() if w]
            if words:
                stmt = stmt.where(*[func.unaccent(Procedure.title).ilike(func.unaccent(f"%{w}%")) for w in words])
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        order: tuple[Any, ...] = {
            "recent": (Procedure.publication_date.desc().nulls_last(), Procedure.id.desc()),
            "value_desc": (Procedure.estimated_value_ron.desc().nulls_last(), Procedure.id.desc()),
            "value_asc": (Procedure.estimated_value_ron.asc().nulls_last(), Procedure.id.desc()),
        }[sort]
        rows = list(
            db.execute(
                stmt.options(selectinload(Procedure.authority))
                .order_by(*order)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars()
        )
        open_ids = set()
        if rows and status == "all":
            open_ids = set(
                db.execute(select(Procedure.id).where(Procedure.id.in_([p.id for p in rows]), *open_conds)).scalars()
            )
        items = [
            ProcedureItem(
                id=p.id,
                notice_number=p.notice_number,
                title=p.title,
                authority=authority_ref(p.authority),  # type: ignore[arg-type]  # mereu există
                authority_type=p.authority.authority_type,
                procedure_type=p.procedure_type,
                contract_type=p.contract_type,
                cpv_code=p.cpv_code,
                category=cpv_category(p.cpv_code),
                estimated_value_ron=p.estimated_value_ron,
                status=p.status,
                publication_date=p.publication_date,
                official_url=_official_url(p.notice_number),
                is_open=status == "open" or p.id in open_ids,
            )
            for p in rows
        ]
        return S.Page(items=items, total=total, page=page, page_size=page_size)

    return cache.cached(request, response, compute)


@router.get("/statuses", summary="Câte proceduri sunt în fiecare stare (din ultimul import)")
def statuses(county: str | None = Depends(county_param), db: Session = Depends(get_db)):
    stmt = select(Procedure.status, func.count()).join(Authority, Authority.id == Procedure.authority_id)
    if county:
        stmt = stmt.where(Authority.county_code == county)
    rows = db.execute(stmt.group_by(Procedure.status).order_by(func.count().desc())).all()
    newest = db.execute(select(func.max(Procedure.publication_date))).scalar()
    return {"newest_publication": newest, "statuses": [{"status": s, "count": n} for s, n in rows]}


MONTHS_RO = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]  # fmt: skip


class UpcomingItem(BaseModel):
    authority: S.AuthorityRef
    category: str
    cpv_prefix: str
    month: int
    month_name: str
    years: list[int]
    typical_value_ron: Any
    last_title: str | None


@router.get("/upcoming", response_model=list[UpcomingItem], summary="Ce urmează probabil: cumpărături care se repetă")
def upcoming(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    locality: str | None = Query(None),
    months: int = Query(3, ge=1, le=12, description="Câte luni înainte"),
    min_value: float = Query(20_000, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Instituțiile cumpără multe lucruri în fiecare an, cam în aceeași lună (deszăpezire, rechizite,
    întreținerea parcurilor). Căutăm grupele CPV (3 cifre) cumpărate de aceeași instituție, în aceeași
    lună, în cel puțin doi ani diferiți, pentru lunile care urmează."""

    def compute() -> list[UpcomingItem]:
        today = dt.date.today()
        wanted = [((today.month - 1 + i) % 12) + 1 for i in range(1, months + 1)]
        month = func.extract("month", Contract.contract_date)
        prefix = func.substr(Contract.cpv_code, 1, 3)
        stmt = (
            select(
                Contract.authority_id,
                prefix.label("pfx"),
                month.label("m"),
                func.array_agg(func.distinct(Contract.year)).label("years"),
                func.avg(Contract.value_ron).label("avg"),
                func.max(Contract.contract_date).label("last"),
            )
            .where(
                Contract.duplicate_of_id.is_(None),
                Contract.contract_date.is_not(None),
                Contract.cpv_code.is_not(None),
                Contract.value_ron >= min_value,
                month.in_(wanted),
            )
            .group_by(Contract.authority_id, prefix, month)
            .having(func.count(func.distinct(Contract.year)) >= 2)
        )
        if county:
            stmt = stmt.where(Contract.county_code == county)
        if locality:
            stmt = stmt.where(Contract.authority_id.in_(authority_ids(db, county, locality)))
        rows = list(db.execute(stmt).all())
        # cele mai apropiate luni întâi, apoi după valoare
        rows.sort(key=lambda r: (wanted.index(int(r.m)), -(r.avg or 0)))
        rows = rows[:limit]
        ids = {r.authority_id for r in rows}
        auths = {a.id: a for a in db.execute(select(Authority).where(Authority.id.in_(ids))).scalars()}
        out = []
        for r in rows:
            title = db.execute(
                select(Contract.title)
                .where(
                    Contract.authority_id == r.authority_id,
                    Contract.cpv_code.like(f"{r.pfx}%"),
                    Contract.contract_date == r.last,
                )
                .limit(1)
            ).scalar()
            out.append(
                UpcomingItem(
                    authority=authority_ref(auths[r.authority_id]),  # type: ignore[arg-type]
                    category=cpv_category(f"{r.pfx}00000"),
                    cpv_prefix=r.pfx,
                    month=int(r.m),
                    month_name=MONTHS_RO[int(r.m) - 1],
                    years=sorted(y for y in r.years if y),
                    typical_value_ron=r.avg,
                    last_title=title,
                )
            )
        return out

    return cache.cached(request, response, compute)
