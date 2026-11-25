from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from tro.api import cache
from tro.api import schemas as S
from tro.api.common import contract_item, county_param, signal_counts
from tro.counties import COUNTIES, POPULATION_2021, county_name
from tro.cpv import all_categories, cpv_category
from tro.db import get_db
from tro.domains import DOMAINS, all_domains, domain_condition, domain_of
from tro.etl.risk import SIGNAL_TYPES
from tro.localities import authority_ids, list_localities
from tro.models import Authority, Company, Contract, ImportRun, RiskSignal
from tro.ngo import ngo_condition

router = APIRouter(tags=["statistici"])


@router.get("/stats/overview", response_model=S.Overview, summary="Cifre-cheie pentru un județ")
def overview(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    year: int | None = Query(None),
    domain: str | None = Query(None, description="Domeniu de cheltuieli (vezi /meta → domains)"),
    db: Session = Depends(get_db),
):
    return cache.cached(request, response, lambda: _overview(db, county, year, domain))


def _overview(db: Session, county: str | None, year: int | None, domain: str | None = None) -> S.Overview:
    dcond = domain_condition(domain)

    def cf(stmt):
        stmt = stmt.where(Contract.duplicate_of_id.is_(None))
        if dcond is not None:
            stmt = stmt.where(dcond)
        if county:
            stmt = stmt.where(Contract.county_code == county)
        if year:
            stmt = stmt.where(Contract.year == year)
        return stmt

    total, n, n_auth, n_comp = db.execute(
        cf(
            select(
                func.coalesce(func.sum(Contract.value_ron), 0),
                func.count(Contract.id),
                func.count(distinct(Contract.authority_id)),
                func.count(distinct(Contract.company_id)),
            )
        )
    ).one()
    direct = db.execute(
        cf(select(func.coalesce(func.sum(Contract.value_ron), 0)).where(Contract.source.in_(["ad", "dan"])))
    ).scalar_one()
    by_year = db.execute(
        cf(select(Contract.year, func.sum(Contract.value_ron), func.count()).where(Contract.year.is_not(None)))
        .group_by(Contract.year)
        .order_by(Contract.year)
    ).all()
    cat: dict[str, list] = defaultdict(lambda: [Decimal(0), 0])
    for code, t, k in db.execute(
        cf(select(Contract.cpv_code, func.sum(Contract.value_ron), func.count())).group_by(Contract.cpv_code)
    ).all():
        c = cpv_category(code)
        cat[c][0] += t or Decimal(0)
        cat[c][1] += k
    sig = select(func.count(RiskSignal.id))
    if county:
        sig = sig.where(RiskSignal.county_code == county)
    if year:
        sig = sig.where(RiskSignal.year == year)
    if dcond is not None:
        sig = sig.where(select(Contract.id).where(Contract.id == RiskSignal.contract_id, dcond).exists())
    n_sig = db.execute(sig).scalar_one()
    latest = list(
        db.execute(
            cf(select(Contract).options(selectinload(Contract.authority), selectinload(Contract.company)))
            .order_by(Contract.contract_date.desc().nulls_last(), Contract.id.desc())
            .limit(10)
        ).scalars()
    )
    counts = signal_counts(db, [c.id for c in latest])
    real = db.execute(cf(select(func.count(Contract.id)).where(Contract.is_synthetic.is_(False)))).scalar_one()
    syn = db.execute(cf(select(func.count(Contract.id)).where(Contract.is_synthetic.is_(True)))).scalar_one()
    last_import = db.execute(
        select(func.max(ImportRun.finished_at)).where(ImportRun.status == "ok", ImportRun.source.like("seap_%"))
    ).scalar()
    cov_from, cov_to = db.execute(cf(select(func.min(Contract.contract_date), func.max(Contract.contract_date)))).one()
    grand = Decimal(total or 0)
    return S.Overview(
        county_code=county,
        county_name=county_name(county) if county else "România",
        total_ron=grand,
        contracts=n,
        authorities=n_auth,
        companies=n_comp,
        signals=n_sig,
        direct_awards_share=float(direct / grand) if grand else None,
        by_year=[S.YearTotal(year=y, total_ron=t or Decimal(0), count=k) for y, t, k in by_year],
        by_category=sorted(
            [
                S.NamedTotal(name=k, total_ron=v[0], count=v[1], share=float(v[0] / grand) if grand else None)
                for k, v in cat.items()
            ],
            key=lambda x: x.total_ron,
            reverse=True,
        )[:12],
        latest_contracts=[contract_item(c, counts.get(c.id, 0)) for c in latest],
        data=S.DataMode(
            real_contracts=real,
            synthetic_contracts=syn,
            has_synthetic=syn > 0,
            last_import_at=last_import,
            coverage_from=cov_from,
            coverage_to=cov_to,
        ),
    )


@router.get("/stats/report", response_model=S.SpendingReport, summary="Raport: pe ce s-au dus banii")
def report(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    year: int | None = Query(None),
    locality: str | None = Query(None, description="Localitate (slug din /localities), ex. medias"),
    db: Session = Depends(get_db),
):
    return cache.cached(request, response, lambda: _report(db, county, year, locality))


def _report(db: Session, county: str | None, year: int | None, locality: str | None = None) -> S.SpendingReport:
    loc_ids = authority_ids(db, county, locality) if locality else None

    def cf(stmt):
        stmt = stmt.where(Contract.duplicate_of_id.is_(None))
        if loc_ids is not None:
            stmt = stmt.where(Contract.authority_id.in_(loc_ids))
        if county:
            stmt = stmt.where(Contract.county_code == county)
        if year:
            stmt = stmt.where(Contract.year == year)
        return stmt

    agg = (func.coalesce(func.sum(Contract.value_ron), 0), func.count(Contract.id))
    total, n, n_auth, n_comp = db.execute(
        cf(
            select(
                *agg,
                func.count(distinct(Contract.authority_id)),
                func.count(distinct(Contract.company_id)),
            )
        )
    ).one()
    grand = Decimal(total or 0)

    def nt(name: str, t: Decimal | None, k: int, key: str | None = None) -> S.NamedTotal:
        t = Decimal(t or 0)
        return S.NamedTotal(name=name, key=key, total_ron=t, count=k, share=float(t / grand) if grand else None)

    def ranked(groups: dict[str, list[Any]], keys: dict[str, str] | None = None) -> list[S.NamedTotal]:
        out = [nt(name, v[0], v[1], (keys or {}).get(name)) for name, v in groups.items()]
        return sorted(out, key=lambda x: x.total_ron, reverse=True)

    def group_by(col: Any, label_none: str) -> list[S.NamedTotal]:
        rows = db.execute(cf(select(col, *agg)).group_by(col)).all()
        g: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
        for name, t, k in rows:
            g[name or label_none][0] += t or Decimal(0)
            g[name or label_none][1] += k
        return ranked(g)

    by_cpv = db.execute(cf(select(Contract.cpv_code, *agg)).group_by(Contract.cpv_code)).all()
    dom: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
    cat: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
    dom_keys: dict[str, str] = {}
    for code, t, k in by_cpv:
        dk = domain_of(code)
        label = DOMAINS[dk][0] if dk else "Altele / necunoscut"
        dom_keys[label] = dk or "altele"
        dom[label][0] += t or Decimal(0)
        dom[label][1] += k
        c = cpv_category(code)
        cat[c][0] += t or Decimal(0)
        cat[c][1] += k

    month = func.to_char(Contract.contract_date, "YYYY-MM")
    by_month = db.execute(
        cf(select(month, *agg).where(Contract.contract_date.is_not(None))).group_by(month).order_by(month)
    ).all()

    top_auth = db.execute(
        cf(select(Authority.id, Authority.name, *agg).join(Authority, Authority.id == Contract.authority_id))
        .group_by(Authority.id)
        .order_by(func.sum(Contract.value_ron).desc().nulls_last())
        .limit(15)
    ).all()
    top_comp = db.execute(
        cf(
            select(Company.cui, Company.id, Company.is_natural_person, Company.name, *agg)
            .join(Company, Company.id == Contract.company_id)
            .where(Contract.repeat_same_company.is_(False))
        )
        .group_by(Company.id)
        .order_by(func.sum(Contract.value_ron).desc().nulls_last())
        .limit(15)
    ).all()
    auth_types = db.execute(
        cf(select(Authority.authority_type, *agg).join(Authority, Authority.id == Contract.authority_id)).group_by(
            Authority.authority_type
        )
    ).all()
    at: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
    for name, t, k in auth_types:
        at[name or "Altă autoritate"][0] += t or Decimal(0)
        at[name or "Altă autoritate"][1] += k

    ngo_t, ngo_n = db.execute(
        cf(
            select(*agg)
            .join(Company, Company.id == Contract.company_id)
            .where(Company.is_natural_person.is_(False), ngo_condition(Company.name_normalized))
        )
    ).one()
    direct = db.execute(cf(select(agg[0]).where(Contract.source.in_(["ad", "dan"])))).scalar_one()
    eu = db.execute(cf(select(agg[0]).where(Contract.eu_funded.is_(True)))).scalar_one()

    return S.SpendingReport(
        county_code=county,
        county_name=county_name(county) if county else "România",
        year=year,
        total_ron=grand,
        contracts=n,
        authorities=n_auth,
        companies=n_comp,
        by_domain=ranked(dom, dom_keys),
        by_category=ranked(cat)[:20],
        by_contract_type=group_by(Contract.contract_type, "Nespecificat"),
        by_procedure_type=group_by(Contract.procedure_type, "Nespecificat"),
        by_authority_type=ranked(at),
        by_month=[S.MonthTotal(month=m, total_ron=t or Decimal(0), count=k) for m, t, k in by_month],
        top_authorities=[nt(name, t, k, str(aid)) for aid, name, t, k in top_auth],
        top_companies=[
            nt("Persoană fizică autorizată" if pf else name, t, k, f"pf-{cid}" if pf else cui)
            for cui, cid, pf, name, t, k in top_comp
        ],
        ngo_total_ron=Decimal(ngo_t or 0),
        ngo_contracts=ngo_n,
        direct_awards_ron=Decimal(direct or 0),
        eu_funded_ron=Decimal(eu or 0),
    )


@router.get("/localities", summary="Localitățile din județ (după sediul instituțiilor), cu totaluri")
def localities(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return cache.cached(request, response, lambda: list_localities(db, county, year))


@router.get("/map/authorities", response_model=list[S.MapPoint], summary="Instituții cu coordonate (hartă)")
def map_authorities(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    def compute() -> list[S.MapPoint]:
        stmt = select(Authority, func.coalesce(func.sum(Contract.value_ron), 0), func.count(Contract.id)).join(
            Contract, Contract.authority_id == Authority.id
        )
        if year:
            stmt = stmt.where(Contract.year == year)
        stmt = stmt.where(Authority.lat.is_not(None), Contract.duplicate_of_id.is_(None)).group_by(Authority.id)
        if county:
            stmt = stmt.where(Authority.county_code == county)
        return [
            S.MapPoint(
                id=a.id,
                name=a.name,
                lat=a.lat,
                lon=a.lon,
                locality=a.locality,
                authority_type=a.authority_type,
                total_ron=t,
                contracts=k,
                is_synthetic=a.is_synthetic,
            )
            for a, t, k in db.execute(stmt).all()
        ]

    return cache.cached(request, response, compute)


@router.get("/meta", summary="Nomenclatoare: județe, ani, tipuri de procedură, categorii, semnale")
def meta(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    db: Session = Depends(get_db),
):
    def compute():
        yq = select(Contract.year).distinct().where(Contract.year.is_not(None))
        pq = select(Contract.procedure_type, func.count()).where(Contract.procedure_type.is_not(None))
        if county:
            yq = yq.where(Contract.county_code == county)
            pq = pq.where(Contract.county_code == county)
        years = sorted([y for y in db.execute(yq).scalars() if y is not None], reverse=True)
        procs = [p for p, _ in db.execute(pq.group_by(Contract.procedure_type).order_by(func.count().desc())).all()]
        counties_with_data = set(db.execute(select(Contract.county_code).distinct()).scalars())
        atypes = [t for t in db.execute(select(Authority.authority_type).distinct()).scalars() if t]
        return {
            "default_county": county,
            "counties": [
                {"code": k, "name": v[0], "has_data": k in counties_with_data, "lat": v[1], "lon": v[2]}
                for k, v in sorted(COUNTIES.items(), key=lambda kv: kv[1][0])
            ],
            "years": years,
            "procedure_types": procs,
            "authority_types": sorted(atypes),
            "categories": all_categories(),
            "domains": all_domains(),
            "signal_types": [{"code": k, "label": v} for k, v in SIGNAL_TYPES.items()],
            "population": POPULATION_2021.get(county or ""),
        }

    return cache.cached(request, response, compute)
