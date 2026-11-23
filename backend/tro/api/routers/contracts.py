from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from tro.api import schemas as S
from tro.api.common import ContractFilters, contract_item, signal_counts, signal_out
from tro.db import get_db
from tro.models import Contract, ContractAmendment, RiskSignal, SourceRecord

router = APIRouter(prefix="/contracts", tags=["contracte"])


def contracts_query(db: Session, f: ContractFilters):
    stmt = select(Contract).options(selectinload(Contract.authority), selectinload(Contract.company))
    return f.order(f.apply(db, stmt))


@router.get("", response_model=S.Page[S.ContractItem], summary="Listă contracte cu filtre")
def list_contracts(
    f: ContractFilters = Depends(),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.execute(f.apply(db, select(func.count(Contract.id)))).scalar_one()
    rows = list(db.execute(contracts_query(db, f).offset((page - 1) * page_size).limit(page_size)).scalars())
    counts = signal_counts(db, [c.id for c in rows])
    return S.Page(
        items=[contract_item(c, counts.get(c.id, 0)) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{contract_id}", response_model=S.ContractDetail, summary="Detaliu contract")
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    c = db.execute(
        select(Contract)
        .options(
            selectinload(Contract.authority),
            selectinload(Contract.company),
            selectinload(Contract.procedure),
        )
        .where(Contract.id == contract_id)
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "Contractul nu a fost găsit")
    amendments = list(
        db.execute(
            select(ContractAmendment)
            .where(ContractAmendment.contract_id == c.id)
            .order_by(ContractAmendment.publication_date)
        ).scalars()
    )
    signals = list(
        db.execute(
            select(RiskSignal)
            .options(selectinload(RiskSignal.authority), selectinload(RiskSignal.company))
            .where(RiskSignal.contract_id == c.id)
            .order_by(RiskSignal.score.desc())
        ).scalars()
    )
    prov = list(
        db.execute(
            select(SourceRecord).where(SourceRecord.entity_type == "contract", SourceRecord.entity_id == c.id)
        ).scalars()
    )
    base = contract_item(c, len(signals)).model_dump()
    sicap = "https://www.e-licitatie.ro/pub/notices/ca-notices/list/0/0"
    if c.source in ("ad", "dan"):
        sicap = "https://www.e-licitatie.ro/pub/direct-acquisitions/list/1"
    if c.notice_number:
        sicap += "?q=" + urllib.parse.quote(c.notice_number)
    return S.ContractDetail(
        **base,
        original_value=c.original_value,
        currency=c.currency,
        exchange_rate=c.exchange_rate,
        publication_date=c.publication_date,
        contract_number=c.contract_number,
        lot_number=c.lot_number,
        duration_days=c.duration_days,
        framework=c.framework,
        eu_funded=c.eu_funded,
        eu_program=c.eu_program,
        source_url=c.source_url,
        source_dataset=c.source_dataset,
        sicap_search_url=sicap,
        last_updated=c.updated_at or c.last_seen_at,
        procedure=S.ProcedureOut.model_validate(c.procedure) if c.procedure else None,
        amendments=[
            S.AmendmentOut(
                id=a.id,
                publication_date=a.publication_date,
                description=a.description,
                value_before_ron=a.value_before_ron,
                value_after_ron=a.value_after_ron,
                delta_ron=a.delta_ron,
                delta_pct=a.delta_pct,
                source_url=a.source_url,
                is_synthetic=a.is_synthetic,
            )
            for a in amendments
        ],
        signals=[signal_out(s) for s in signals],
        provenance=[
            S.ProvenanceOut(
                source=p.source,
                source_url=p.source_url,
                imported_at=p.imported_at,
                first_seen_at=p.first_seen_at,
                content_hash=p.content_hash,
            )
            for p in prov
        ],
    )
