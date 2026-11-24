"""O propoziție de context pentru listele de firme și instituții: „pentru ce” și „de la cine / către cine”.

Pentru o pagină de rezultate (max. ~200 de rânduri) calculăm, cu aceleași filtre ca lista:
- categoria de cheltuieli cu cea mai mare valoare (din codurile CPV);
- partenerul principal: clientul principal al unei firme, furnizorul principal al unei instituții.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tro.cpv import cpv_category
from tro.domains import domain_condition
from tro.models import Authority, Company, Contract


def _filters(county: str | None, year: int | None, domain: str | None, dedupe: bool) -> list[Any]:
    # ca în liste: la instituții un contract repetat (asociere) contează o dată; la firme, pentru fiecare firmă
    f: list[Any] = [Contract.duplicate_of_id.is_(None)] if dedupe else []
    if county:
        f.append(Contract.county_code == county)
    if year:
        f.append(Contract.year == year)
    dcond = domain_condition(domain)
    if dcond is not None:
        f.append(dcond)
    return f


def _top_category(db: Session, key_col: Any, ids: list[int], filters: list[Any]) -> dict[int, str]:
    sums: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    rows = db.execute(
        select(key_col, Contract.cpv_code, func.sum(Contract.value_ron))
        .where(key_col.in_(ids), *filters)
        .group_by(key_col, Contract.cpv_code)
    ).all()
    for k, code, t in rows:
        sums[k][cpv_category(code)] += t or Decimal(0)
    return {k: max(v.items(), key=lambda kv: kv[1])[0] for k, v in sums.items() if v}


def company_context(
    db: Session, ids: list[int], county: str | None, year: int | None, domain: str | None
) -> dict[int, tuple[str | None, str | None]]:
    """id firmă → (categoria principală, clientul principal)."""
    if not ids:
        return {}
    f = _filters(county, year, domain, dedupe=False) + [Contract.repeat_same_company.is_(False)]
    cats = _top_category(db, Contract.company_id, ids, f)
    best: dict[int, tuple[Decimal, str]] = {}
    for cid, name, t in db.execute(
        select(Contract.company_id, Authority.name, func.sum(Contract.value_ron))
        .join(Authority, Authority.id == Contract.authority_id)
        .where(Contract.company_id.in_(ids), *f)
        .group_by(Contract.company_id, Authority.id)
    ).all():
        t = t or Decimal(0)
        if cid is not None and (cid not in best or t > best[cid][0]):
            best[cid] = (t, name)
    return {i: (cats.get(i), best[i][1] if i in best else None) for i in ids}


def authority_context(
    db: Session, ids: list[int], year: int | None, domain: str | None
) -> dict[int, tuple[str | None, str | None]]:
    """id instituție → (categoria principală, furnizorul principal; PFA-urile rămân anonime)."""
    if not ids:
        return {}
    f = _filters(None, year, domain, dedupe=True)
    cats = _top_category(db, Contract.authority_id, ids, f)
    best: dict[int, tuple[Decimal, str]] = {}
    for aid, name, pf, t in db.execute(
        select(Contract.authority_id, Company.name, Company.is_natural_person, func.sum(Contract.value_ron))
        .join(Company, Company.id == Contract.company_id)
        .where(Contract.authority_id.in_(ids), *f)
        .group_by(Contract.authority_id, Company.id)
    ).all():
        t = t or Decimal(0)
        if aid not in best or t > best[aid][0]:
            best[aid] = (t, "o persoană fizică autorizată" if pf else name)
    return {i: (cats.get(i), best[i][1] if i in best else None) for i in ids}
