from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from tro.api import schemas as S
from tro.api.common import company_key, county_param, ts_query
from tro.db import get_db
from tro.models import Authority, Company, Contract
from tro.normalize import normalize_cui

router = APIRouter(tags=["căutare"])


@router.get("/search", response_model=S.SearchResult, summary="Căutare unificată (tolerantă la diacritice)")
def search(
    q: str = Query(..., min_length=1, max_length=200),
    county: str | None = Depends(county_param),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    tq = ts_query(q)
    cui = normalize_cui(q) if q.strip().upper().lstrip("RO").strip().isdigit() else None
    res = S.SearchResult(query=q, authorities=[], companies=[], contracts=[])
    if tq is None and not cui:
        return res

    # --- instituții
    conds: list[Any] = []
    if tq is not None:
        conds.append(Authority.search_vector.op("@@")(tq))
    if cui:
        conds.append(Authority.cui == cui)
    stmt = select(Authority).where(or_(*conds))
    if county:
        stmt = stmt.where(Authority.county_code == county)
    rank = func.ts_rank(Authority.search_vector, tq) if tq is not None else func.random()
    for a in db.execute(stmt.order_by(desc(rank)).limit(limit)).scalars():
        res.authorities.append(
            S.SearchHit(
                type="authority",
                id=str(a.id),
                title=a.name,
                subtitle=" · ".join(x for x in [a.authority_type, a.locality] if x),
                is_synthetic=a.is_synthetic,
            )
        )

    # --- firme (doar cele cu contracte în județ, dacă e filtrat)
    conds = []
    if tq is not None:
        conds.append(Company.search_vector.op("@@")(tq))
    if cui:
        conds.append((Company.cui == cui) & Company.is_natural_person.is_(False))
    tot = func.coalesce(func.sum(Contract.value_ron), 0)
    stmt2 = (
        select(Company, tot.label("t"))
        .join(Contract, Contract.company_id == Company.id)
        .where(or_(*conds), Contract.repeat_same_company.is_(False))
        .group_by(Company.id)
    )
    if county:
        stmt2 = stmt2.where(Contract.county_code == county)
    for c, t in db.execute(stmt2.order_by(desc("t")).limit(limit)).all():
        res.companies.append(
            S.SearchHit(
                type="company",
                id=company_key(c),
                title=c.display_name,
                subtitle=(f"CUI {c.cui}" if (not c.is_natural_person and c.cui.isdigit()) else c.locality),
                value_ron=t,
                is_synthetic=c.is_synthetic,
            )
        )

    # --- contracte
    if tq is not None:
        stmt3 = select(Contract).options(selectinload(Contract.authority)).where(Contract.search_vector.op("@@")(tq))
        if county:
            stmt3 = stmt3.where(Contract.county_code == county)
        stmt3 = stmt3.order_by(desc(func.ts_rank(Contract.search_vector, tq)), Contract.value_ron.desc().nulls_last())
        for k in db.execute(stmt3.limit(limit)).scalars():
            res.contracts.append(
                S.SearchHit(
                    type="contract",
                    id=str(k.id),
                    title=k.title or k.cpv_name or f"Contract {k.id}",
                    subtitle=f"{k.authority.name} · {k.contract_date or ''}",
                    value_ron=k.value_ron,
                    is_synthetic=k.is_synthetic,
                )
            )
    return res
