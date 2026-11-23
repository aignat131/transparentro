from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from tro.api import cache
from tro.api import schemas as S
from tro.api.common import contract_item, county_param, signal_counts
from tro.counties import COUNTIES, county_name
from tro.cpv import all_categories, cpv_category
from tro.db import get_db
from tro.etl.risk import SIGNAL_TYPES
from tro.models import Authority, Contract, ImportRun, RiskSignal

router = APIRouter(tags=["statistici"])


@router.get("/stats/overview", response_model=S.Overview, summary="Cifre-cheie pentru un județ")
def overview(
    request: Request,
    response: Response,
    county: str | None = Depends(county_param),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return cache.cached(request, response, lambda: _overview(db, county, year))


def _overview(db: Session, county: str | None, year: int | None) -> S.Overview:
    def cf(stmt):
        stmt = stmt.where(Contract.duplicate_of_id.is_(None))
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
        yq = select(distinct(Contract.year)).where(Contract.year.is_not(None))
        pq = select(Contract.procedure_type, func.count()).where(Contract.procedure_type.is_not(None))
        if county:
            yq = yq.where(Contract.county_code == county)
            pq = pq.where(Contract.county_code == county)
        years = sorted([y for y in db.execute(yq).scalars() if y is not None], reverse=True)
        procs = [p for p, _ in db.execute(pq.group_by(Contract.procedure_type).order_by(func.count().desc())).all()]
        counties_with_data = set(db.execute(select(distinct(Contract.county_code))).scalars())
        atypes = [t for t in db.execute(select(distinct(Authority.authority_type))).scalars() if t]
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
            "signal_types": [{"code": k, "label": v} for k, v in SIGNAL_TYPES.items()],
        }

    return cache.cached(request, response, compute)
