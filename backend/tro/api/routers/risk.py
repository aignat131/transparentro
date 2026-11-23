from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from tro.api import schemas as S
from tro.api.common import county_param, find_company, signal_out
from tro.db import get_db
from tro.models import RiskSignal

router = APIRouter(tags=["semnale"])


class SignalFilters:
    def __init__(
        self,
        county: str | None = Query(None, description="Cod județ; 'all' = toată țara"),
        signal_type: str | None = Query(None),
        min_score: int = Query(0, ge=0, le=100),
        year: int | None = Query(None),
        authority_id: int | None = Query(None),
        company: str | None = Query(None),
        sort: str = Query("score_desc", pattern="^(score_desc|recent|year_desc)$"),
    ) -> None:
        self.county = county_param(county)
        self.signal_type = signal_type
        self.min_score = min_score
        self.year = year
        self.authority_id = authority_id
        self.company = company
        self.sort = sort

    def apply(self, db: Session, stmt):
        if self.county and not self.authority_id and not self.company:
            stmt = stmt.where(RiskSignal.county_code == self.county)
        if self.signal_type:
            stmt = stmt.where(RiskSignal.signal_type == self.signal_type)
        if self.min_score:
            stmt = stmt.where(RiskSignal.score >= self.min_score)
        if self.year:
            stmt = stmt.where(RiskSignal.year == self.year)
        if self.authority_id:
            stmt = stmt.where(RiskSignal.authority_id == self.authority_id)
        if self.company:
            stmt = stmt.where(RiskSignal.company_id == find_company(db, self.company).id)
        return stmt

    def order(self, stmt):
        return stmt.order_by(
            *{
                "score_desc": (RiskSignal.score.desc(), RiskSignal.id),
                "recent": (RiskSignal.computed_at.desc(), RiskSignal.id),
                "year_desc": (RiskSignal.year.desc().nulls_last(), RiskSignal.score.desc()),
            }[self.sort]
        )


def signals_query(db: Session, f: SignalFilters):
    stmt = select(RiskSignal).options(selectinload(RiskSignal.authority), selectinload(RiskSignal.company))
    return f.order(f.apply(db, stmt))


@router.get("/risk-signals", response_model=S.Page[S.RiskSignalOut], summary="Semnale de verificat (cu filtre)")
def list_signals(
    f: SignalFilters = Depends(),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.execute(f.apply(db, select(func.count(RiskSignal.id)))).scalar_one()
    rows = db.execute(signals_query(db, f).offset((page - 1) * page_size).limit(page_size)).scalars()
    return S.Page(items=[signal_out(s) for s in rows], total=total, page=page, page_size=page_size)


@router.get("/risk-signals/summary", summary="Număr de semnale pe tip")
def signals_summary(county: str | None = Depends(county_param), db: Session = Depends(get_db)):
    stmt = select(RiskSignal.signal_type, func.count()).group_by(RiskSignal.signal_type)
    if county:
        stmt = stmt.where(RiskSignal.county_code == county)
    return {t: n for t, n in db.execute(stmt).all()}
