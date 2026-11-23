"""Funcții comune: județ implicit, filtre, serializare cu anonimizare GDPR."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from tro.api import schemas as S
from tro.config import get_settings
from tro.cpv import cpv_category
from tro.etl.risk import SIGNAL_TYPES
from tro.models import Authority, Company, Contract, RiskSignal
from tro.normalize import normalize_cui, strip_diacritics


def county_param(
    county: str | None = Query(
        None, description="Cod județ (ex. SB, CJ, B). 'all' = toată țara. Implicit: DEFAULT_COUNTY."
    ),
) -> str | None:
    c = (county or get_settings().default_county or "").strip().upper()
    if c in ("ALL", "*", ""):
        return None
    if not re.fullmatch(r"[A-Z]{1,2}", c):
        raise HTTPException(400, "Cod de județ invalid")
    return c


def company_key(c: Company) -> str:
    return f"pf-{c.id}" if c.is_natural_person else c.cui


def find_company(db: Session, key: str) -> Company:
    key = key.strip()
    comp: Company | None = None
    if key.lower().startswith("pf-") and key[3:].isdigit():
        comp = db.get(Company, int(key[3:]))
    else:
        cui = normalize_cui(key) or key
        comp = db.execute(select(Company).where(Company.cui == cui)).scalar_one_or_none()
        if comp and comp.is_natural_person:
            comp = None  # persoanele fizice nu se pot căuta după CUI
    if comp is None:
        raise HTTPException(404, "Firma nu a fost găsită")
    return comp


def authority_ref(a: Authority | None) -> S.AuthorityRef | None:
    if a is None:
        return None
    return S.AuthorityRef(id=a.id, name=a.name, county_code=a.county_code, is_synthetic=a.is_synthetic)


def company_ref(c: Company | None) -> S.CompanyRef | None:
    if c is None:
        return None
    return S.CompanyRef(
        key=company_key(c),
        name=c.display_name,
        is_natural_person=c.is_natural_person,
        locality=c.locality,
        is_synthetic=c.is_synthetic,
    )


def contract_item(c: Contract, signal_count: int = 0) -> S.ContractItem:
    return S.ContractItem(
        id=c.id,
        title=c.title or c.cpv_name,
        value_ron=c.value_ron,
        contract_date=c.contract_date,
        year=c.year,
        procedure_type=c.procedure_type,
        contract_type=c.contract_type,
        cpv_code=c.cpv_code,
        cpv_name=c.cpv_name,
        category=cpv_category(c.cpv_code),
        source=c.source,
        notice_number=c.notice_number,
        authority=authority_ref(c.authority),  # type: ignore[arg-type]
        company=company_ref(c.company),
        signal_count=signal_count,
        duplicate_of_id=c.duplicate_of_id,
        is_synthetic=c.is_synthetic,
    )


def signal_out(s: RiskSignal) -> S.RiskSignalOut:
    return S.RiskSignalOut(
        id=s.id,
        signal_type=s.signal_type,
        signal_label=SIGNAL_TYPES.get(s.signal_type, s.signal_type),
        score=s.score,
        target_type=s.target_type,
        title=s.title,
        explanation=s.explanation,
        details=s.details or {},
        year=s.year,
        county_code=s.county_code,
        source_url=s.source_url,
        computed_at=s.computed_at,
        authority=authority_ref(s.authority),
        company=company_ref(s.company),
        contract_id=s.contract_id,
        is_synthetic=s.is_synthetic,
    )


def signal_counts(db: Session, contract_ids: list[int]) -> dict[int, int]:
    if not contract_ids:
        return {}
    rows = db.execute(
        select(RiskSignal.contract_id, func.count())
        .where(RiskSignal.contract_id.in_(contract_ids))
        .group_by(RiskSignal.contract_id)
    ).all()
    return {int(r[0]): int(r[1]) for r in rows if r[0] is not None}


# ------------------------------------------------------------------ căutare full-text

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def tsquery_text(q: str) -> str | None:
    """'Primăria Sibiu' → 'primaria:* & sibiu:*' (prefix, fără diacritice)."""
    tokens = [t for t in _TOKEN_RE.findall(strip_diacritics(q).lower()) if t][:8]
    tokens = [t.replace("_", "") for t in tokens if t.replace("_", "")]
    if not tokens:
        return None
    return " & ".join(f"{t}:*" for t in tokens)


def ts_query(q: str):
    tq = tsquery_text(q)
    if tq is None:
        return None
    return func.to_tsquery("ro_unaccent", tq)


# ------------------------------------------------------------------ filtre contracte

SORTS: dict[str, tuple[Any, ...]] = {
    "date_desc": (Contract.contract_date.desc().nulls_last(), Contract.id.desc()),
    "date_asc": (Contract.contract_date.asc().nulls_last(), Contract.id.asc()),
    "value_desc": (Contract.value_ron.desc().nulls_last(), Contract.id.desc()),
    "value_asc": (Contract.value_ron.asc().nulls_last(), Contract.id.asc()),
}


class ContractFilters:
    def __init__(
        self,
        county: str | None = Query(None, description="Cod județ; 'all' = toată țara"),
        year: int | None = Query(None, ge=2000, le=2100),
        min_value: float | None = Query(None, ge=0),
        max_value: float | None = Query(None, ge=0),
        procedure_type: str | None = Query(None, description="Tipul procedurii (ex. 'Achiziție directă')"),
        cpv: str | None = Query(None, description="Prefix cod CPV (ex. 45 sau 45233)"),
        authority_id: int | None = Query(None),
        company: str | None = Query(None, description="CUI sau cheia firmei"),
        source: str | None = Query(None, description="ad | dan | contracte | atribuire_fara"),
        q: str | None = Query(None, max_length=200, description="Text liber (obiect, CPV, număr anunț)"),
        with_signals: bool = Query(False, description="Doar contractele cu semnale de verificat"),
        sort: str = Query("date_desc", pattern="^(date_desc|date_asc|value_desc|value_asc)$"),
    ) -> None:
        self.county = county_param(county)
        self.year = year
        self.min_value = min_value
        self.max_value = max_value
        self.procedure_type = procedure_type
        self.cpv = cpv
        self.authority_id = authority_id
        self.company = company
        self.source = source
        self.q = q
        self.with_signals = with_signals
        self.sort = sort

    def apply(self, db: Session, stmt: Select[Any]) -> Select[Any]:
        if self.county and not self.authority_id and not self.company:
            stmt = stmt.where(Contract.county_code == self.county)
        if self.year:
            stmt = stmt.where(Contract.year == self.year)
        if self.min_value is not None:
            stmt = stmt.where(Contract.value_ron >= self.min_value)
        if self.max_value is not None:
            stmt = stmt.where(Contract.value_ron <= self.max_value)
        if self.procedure_type:
            stmt = stmt.where(Contract.procedure_type == self.procedure_type)
        if self.cpv:
            digits = re.sub(r"\D", "", self.cpv)[:8]
            if digits:
                stmt = stmt.where(Contract.cpv_code.like(f"{digits}%"))
        if self.authority_id:
            stmt = stmt.where(Contract.authority_id == self.authority_id)
        if self.company:
            comp = find_company(db, self.company)
            stmt = stmt.where(Contract.company_id == comp.id)
        if self.source:
            stmt = stmt.where(Contract.source == self.source)
        if self.q:
            tq = ts_query(self.q)
            if tq is not None:
                stmt = stmt.where(Contract.search_vector.op("@@")(tq))
        if self.with_signals:
            stmt = stmt.where(select(RiskSignal.id).where(RiskSignal.contract_id == Contract.id).exists())
        return stmt

    def order(self, stmt: Select[Any]) -> Select[Any]:
        return stmt.order_by(*SORTS[self.sort])
