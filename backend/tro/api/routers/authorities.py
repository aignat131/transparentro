from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, func, select, true
from sqlalchemy.orm import Session, selectinload

from tro.api import cache
from tro.api import schemas as S
from tro.api.common import company_key, county_param, signal_out, ts_query
from tro.api.context import authority_context
from tro.cpv import cpv_category
from tro.db import get_db
from tro.domains import domain_condition
from tro.models import Authority, Company, Contract, RiskSignal
from tro.ngo import ngo_condition

router = APIRouter(prefix="/authorities", tags=["instituții"])

AUTH_SORTS = {"total_desc", "name_asc", "contracts_desc"}


def authorities_query(
    county: str | None,
    q: str | None,
    authority_type: str | None,
    year: int | None,
    domain: str | None = None,
    ngo: bool = False,
):
    dcond = domain_condition(domain)
    totals = (
        select(
            Contract.authority_id.label("aid"),
            func.coalesce(func.sum(Contract.value_ron), 0).label("total"),
            func.count(Contract.id).label("n"),
        )
        .where(
            (Contract.year == year) if year else true(),
            dcond if dcond is not None else true(),
            Contract.duplicate_of_id.is_(None),
        )
        .group_by(Contract.authority_id)
        .subquery()
    )
    stmt = select(Authority, totals.c.total, totals.c.n).outerjoin(totals, totals.c.aid == Authority.id)
    if dcond is not None:
        stmt = stmt.where(totals.c.n > 0)
    if ngo:
        stmt = stmt.where(ngo_condition(Authority.name_normalized), totals.c.n > 0)
    if county:
        stmt = stmt.where(Authority.county_code == county)
    if authority_type:
        stmt = stmt.where(Authority.authority_type == authority_type)
    if q:
        tq = ts_query(q)
        if tq is not None:
            stmt = stmt.where(Authority.search_vector.op("@@")(tq))
    return stmt, totals


@router.get("", response_model=S.Page[S.AuthorityItem], summary="Listă instituții (autorități contractante)")
def list_authorities(
    county: str | None = Depends(county_param),
    q: str | None = Query(None, max_length=200),
    authority_type: str | None = Query(None),
    year: int | None = Query(None),
    domain: str | None = Query(None, description="Domeniu de cheltuieli (vezi /meta → domains)"),
    ngo: bool = Query(False, description="Doar ONG-uri (asociații, fundații, federații, cluburi sportive)"),
    context: bool = Query(False, description="Adaugă categoria principală și partenerul principal"),
    sort: str = Query("total_desc", pattern="^(total_desc|name_asc|contracts_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt, totals = authorities_query(county, q, authority_type, year, domain, ngo)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    order = {
        "total_desc": (func.coalesce(totals.c.total, 0).desc(), Authority.id),
        "name_asc": (Authority.name.asc(),),
        "contracts_desc": (func.coalesce(totals.c.n, 0).desc(), Authority.id),
    }[sort]
    rows = db.execute(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    ctx = authority_context(db, [a.id for a, *_ in rows], year, domain) if context else {}
    return S.Page(
        items=[
            S.AuthorityItem(
                id=a.id,
                cui=a.cui,
                name=a.name,
                county_code=a.county_code,
                locality=a.locality,
                authority_type=a.authority_type,
                total_ron=t or Decimal(0),
                contracts=n or 0,
                is_synthetic=a.is_synthetic,
                top_category=ctx.get(a.id, (None, None))[0],
                top_supplier=ctx.get(a.id, (None, None))[1],
            )
            for a, t, n in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{authority_id}", response_model=S.AuthorityDetail, summary="Profil instituție")
def get_authority(
    authority_id: int,
    request: Request,
    response: Response,
    year: int | None = Query(None, description="Restrânge distribuțiile la un an"),
    db: Session = Depends(get_db),
):
    a = db.get(Authority, authority_id)
    if a is None:
        raise HTTPException(404, "Instituția nu a fost găsită")
    return cache.cached(request, response, lambda: _authority_detail(db, a, year))


def _authority_detail(db: Session, a: Authority, year: int | None) -> S.AuthorityDetail:
    yfilter = and_((Contract.year == year) if year else true(), Contract.duplicate_of_id.is_(None))

    by_year = db.execute(
        select(Contract.year, func.sum(Contract.value_ron), func.count())
        .where(Contract.authority_id == a.id, Contract.year.is_not(None), Contract.duplicate_of_id.is_(None))
        .group_by(Contract.year)
        .order_by(Contract.year)
    ).all()
    grand = sum((r[1] or Decimal(0)) for r in by_year if (not year or r[0] == year)) or Decimal(0)
    n_total = sum(r[2] for r in by_year if (not year or r[0] == year))

    sup = db.execute(
        select(Company, func.sum(Contract.value_ron).label("t"), func.count().label("n"))
        .join(Contract, Contract.company_id == Company.id)
        .where(Contract.authority_id == a.id, yfilter)
        .group_by(Company.id)
        .order_by(func.sum(Contract.value_ron).desc().nulls_last())
        .limit(10)
    ).all()

    cat: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
    for code, t, n in db.execute(
        select(Contract.cpv_code, func.sum(Contract.value_ron), func.count())
        .where(Contract.authority_id == a.id, yfilter)
        .group_by(Contract.cpv_code)
    ).all():
        k = cpv_category(code)
        cat[k][0] += t or Decimal(0)
        cat[k][1] += n

    proc = db.execute(
        select(Contract.procedure_type, func.sum(Contract.value_ron), func.count())
        .where(Contract.authority_id == a.id, yfilter)
        .group_by(Contract.procedure_type)
        .order_by(func.sum(Contract.value_ron).desc().nulls_last())
    ).all()

    sigs = list(
        db.execute(
            select(RiskSignal)
            .options(selectinload(RiskSignal.authority), selectinload(RiskSignal.company))
            .where(RiskSignal.authority_id == a.id)
            .order_by(RiskSignal.score.desc())
            .limit(20)
        ).scalars()
    )
    n_sig = db.execute(select(func.count()).where(RiskSignal.authority_id == a.id)).scalar_one()

    def share(t: Decimal | None) -> float | None:
        return float(t / grand) if (t and grand) else None

    return S.AuthorityDetail(
        id=a.id,
        cui=a.cui,
        name=a.name,
        county_code=a.county_code,
        county_name=a.county_name,
        locality=a.locality,
        authority_type=a.authority_type,
        address=a.address,
        lat=a.lat,
        lon=a.lon,
        total_ron=grand,
        contracts=n_total,
        is_synthetic=a.is_synthetic,
        by_year=[S.YearTotal(year=y, total_ron=t or Decimal(0), count=n) for y, t, n in by_year],
        top_suppliers=[
            S.NamedTotal(name=c.display_name, key=company_key(c), total_ron=t or Decimal(0), count=n, share=share(t))
            for c, t, n in sup
        ],
        by_category=sorted(
            [S.NamedTotal(name=k, total_ron=v[0], count=int(v[1]), share=share(v[0])) for k, v in cat.items()],
            key=lambda x: x.total_ron,
            reverse=True,
        ),
        by_procedure_type=[
            S.NamedTotal(name=p or "Necunoscut", total_ron=t or Decimal(0), count=n, share=share(t)) for p, t, n in proc
        ],
        signals=[signal_out(s) for s in sigs],
        signal_count=n_sig,
    )
