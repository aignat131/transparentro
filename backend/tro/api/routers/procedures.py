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
