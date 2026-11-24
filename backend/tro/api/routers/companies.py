from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from tro.api import cache
from tro.api import schemas as S
from tro.api.common import company_key, county_param, find_company, signal_out, ts_query
from tro.cpv import cpv_category
from tro.db import get_db
from tro.domains import domain_condition
from tro.models import Authority, Company, CompanyAlias, CompanyFinancial, Contract, RiskSignal
from tro.ngo import is_ngo_name, ngo_condition

router = APIRouter(prefix="/companies", tags=["firme"])


def companies_query(
    county: str | None,
    q: str | None,
    year: int | None,
    with_signals: bool,
    domain: str | None = None,
    ngo: bool = False,
):
    cfilter: list[Any] = [Contract.company_id.is_not(None), Contract.repeat_same_company.is_(False)]
    dcond = domain_condition(domain)
    if dcond is not None:
        cfilter.append(dcond)
    if county:
        cfilter.append(Contract.county_code == county)
    if year:
        cfilter.append(Contract.year == year)
    totals = (
        select(
            Contract.company_id.label("cid"),
            func.coalesce(func.sum(Contract.value_ron), 0).label("total"),
            func.count(Contract.id).label("n"),
        )
        .where(*cfilter)
        .group_by(Contract.company_id)
        .subquery()
    )
    sig = (
        select(RiskSignal.company_id.label("cid"), func.count().label("ns"))
        .where(RiskSignal.company_id.is_not(None))
        .group_by(RiskSignal.company_id)
        .subquery()
    )
    stmt = (
        select(Company, totals.c.total, totals.c.n, func.coalesce(sig.c.ns, 0))
        .join(totals, totals.c.cid == Company.id)
        .outerjoin(sig, sig.c.cid == Company.id)
    )
    if q:
        tq = ts_query(q)
        if tq is not None:
            stmt = stmt.where(Company.search_vector.op("@@")(tq))
    if with_signals:
        stmt = stmt.where(sig.c.ns > 0)
    if ngo:
        stmt = stmt.where(Company.is_natural_person.is_(False), ngo_condition(Company.name_normalized))
    return stmt, totals, sig


@router.get("", response_model=S.Page[S.CompanyItem], summary="Listă firme (furnizori ai statului)")
def list_companies(
    county: str | None = Depends(county_param),
    q: str | None = Query(None, max_length=200),
    year: int | None = Query(None),
    with_signals: bool = Query(False),
    ngo: bool = Query(False, description="Doar ONG-uri (asociații, fundații, federații, cluburi sportive)"),
    domain: str | None = Query(None, description="Domeniu de cheltuieli (vezi /meta → domains)"),
    sort: str = Query("total_desc", pattern="^(total_desc|contracts_desc|signals_desc|name_asc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt, totals, sig = companies_query(county, q, year, with_signals, domain, ngo)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    order = {
        "total_desc": (totals.c.total.desc(), Company.id),
        "contracts_desc": (totals.c.n.desc(), Company.id),
        "signals_desc": (func.coalesce(sig.c.ns, 0).desc(), totals.c.total.desc()),
        "name_asc": (Company.name.asc(),),
    }[sort]
    rows = db.execute(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return S.Page(
        items=[company_item(c, t, n, ns) for c, t, n, ns in rows], total=total, page=page, page_size=page_size
    )


def company_item(c: Company, total: Decimal | None, n: int | None, ns: int | None) -> S.CompanyItem:
    return S.CompanyItem(
        key=company_key(c),
        name=c.display_name,
        is_natural_person=c.is_natural_person,
        locality=c.locality,
        county_code=c.county_code,
        total_ron=total or Decimal(0),
        contracts=n or 0,
        signal_count=ns or 0,
        is_synthetic=c.is_synthetic,
        is_ngo=not c.is_natural_person and is_ngo_name(c.name),
    )


@router.get("/{key}", response_model=S.CompanyDetail, summary="Profil firmă (după CUI)")
def get_company(key: str, request: Request, response: Response, db: Session = Depends(get_db)):
    c = find_company(db, key)
    return cache.cached(request, response, lambda: _company_detail(db, c))


def _company_detail(db: Session, c: Company) -> S.CompanyDetail:
    pf = c.is_natural_person
    by_year = db.execute(
        select(Contract.year, func.sum(Contract.value_ron), func.count())
        .where(Contract.company_id == c.id, Contract.year.is_not(None), Contract.repeat_same_company.is_(False))
        .group_by(Contract.year)
        .order_by(Contract.year)
    ).all()
    grand = sum((r[1] or Decimal(0)) for r in by_year) or Decimal(0)
    n_total = sum(r[2] for r in by_year)
    clients = db.execute(
        select(Authority, func.sum(Contract.value_ron), func.count())
        .join(Contract, Contract.authority_id == Authority.id)
        .where(Contract.company_id == c.id, Contract.repeat_same_company.is_(False))
        .group_by(Authority.id)
        .order_by(func.sum(Contract.value_ron).desc().nulls_last())
        .limit(20)
    ).all()
    cat: dict[str, list] = defaultdict(lambda: [Decimal(0), 0])
    for code, t, n in db.execute(
        select(Contract.cpv_code, func.sum(Contract.value_ron), func.count())
        .where(Contract.company_id == c.id, Contract.repeat_same_company.is_(False))
        .group_by(Contract.cpv_code)
    ).all():
        k = cpv_category(code)
        cat[k][0] += t or Decimal(0)
        cat[k][1] += n
    first = db.execute(select(func.min(Contract.contract_date)).where(Contract.company_id == c.id)).scalar()
    fins = list(
        db.execute(
            select(CompanyFinancial).where(CompanyFinancial.company_id == c.id).order_by(CompanyFinancial.year)
        ).scalars()
    )
    year_totals = {y: t for y, t, _ in by_year}
    sigs = list(
        db.execute(
            select(RiskSignal)
            .options(selectinload(RiskSignal.authority), selectinload(RiskSignal.company))
            .where(RiskSignal.company_id == c.id)
            .order_by(RiskSignal.score.desc())
        ).scalars()
    )
    aliases = (
        []
        if pf
        else [
            a
            for a in db.execute(
                select(CompanyAlias.alias_raw).where(CompanyAlias.company_id == c.id).order_by(CompanyAlias.alias_raw)
            ).scalars()
            if a != c.name
        ][:20]
    )

    def share(t: Decimal | None) -> float | None:
        return float(t / grand) if (t and grand) else None

    return S.CompanyDetail(
        key=company_key(c),
        name=c.display_name,
        is_natural_person=pf,
        locality=c.locality,
        county_code=c.county_code,
        total_ron=grand,
        contracts=n_total,
        signal_count=len(sigs),
        is_synthetic=c.is_synthetic,
        is_ngo=not pf and is_ngo_name(c.name),
        cui=None if pf else c.cui if c.cui.isdigit() else None,
        founded_on=None if pf else c.founded_on,
        founded_source=None if pf else c.founded_source,
        caen_code=c.caen_code,
        status=c.status,
        legal_form=c.legal_form,
        registry_number=None if pf else c.registry_number,
        vat_payer=c.vat_payer,
        inactive=c.inactive,
        anaf_checked_at=c.anaf_checked_at,
        aliases=aliases,
        by_year=[S.YearTotal(year=y, total_ron=t or Decimal(0), count=n) for y, t, n in by_year],
        clients=[
            S.NamedTotal(name=a.name, key=str(a.id), total_ron=t or Decimal(0), count=n, share=share(t))
            for a, t, n in clients
        ],
        by_category=sorted(
            [S.NamedTotal(name=k, total_ron=v[0], count=v[1], share=share(v[0])) for k, v in cat.items()],
            key=lambda x: x.total_ron,
            reverse=True,
        ),
        financials=[
            S.FinancialOut(
                year=f.year,
                turnover_ron=f.turnover_ron,
                net_profit_ron=f.net_profit_ron,
                employees=f.employees,
                public_total_ron=year_totals.get(f.year),
            )
            for f in fins
        ],
        signals=[signal_out(s) for s in sigs],
        first_contract_date=first,
        official_url=(
            f"https://mfinante.gov.ro/apps/infocodfiscal.html?cod={c.cui}" if (not pf and c.cui.isdigit()) else None
        ),
    )
