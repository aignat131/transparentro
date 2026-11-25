"""Localitățile unui județ, după sediul instituțiilor publice.

SEAP scrie localitatea în mai multe feluri: „Sibiu”, „Orş. Cisnădie”, „Şelimbăr Com. Şelimbăr”,
„Richiş Com. Biertan” (satul Richiș din comuna Biertan). Grupăm pe oraș / comună, ca un locuitor să
găsească tot ce ține de primăria lui.
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tro.models import Authority, Contract
from tro.normalize import strip_diacritics

_PREFIX = re.compile(r"^(orş\.|ors\.|oraş|oras|mun\.|municipiul|com\.|comuna|sat)\s+", re.I)


def locality_name(raw: str | None) -> str | None:
    """„Richiş Com. Biertan” → „Biertan”; „Orş. Agnita” → „Agnita”."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    m = re.search(r"\bCom\.\s*(.+)$", s, re.I)
    if m:
        s = m.group(1)
    s = _PREFIX.sub("", s).strip(" ,.")
    s = s.replace("ş", "ș").replace("Ş", "Ș").replace("ţ", "ț").replace("Ţ", "Ț")
    return s or None


def slugify(name: str) -> str:
    s = strip_diacritics(name).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _authorities(db: Session, county: str | None) -> list[tuple[int, str | None]]:
    stmt = select(Authority.id, Authority.locality)
    if county:
        stmt = stmt.where(Authority.county_code == county)
    return [(i, loc) for i, loc in db.execute(stmt).all()]


def authority_ids(db: Session, county: str | None, slug: str) -> list[int]:
    """Instituțiile cu sediul în localitatea dată (după slug)."""
    out = []
    for aid, raw in _authorities(db, county):
        name = locality_name(raw)
        if name and slugify(name) == slug:
            out.append(aid)
    return out


def list_localities(db: Session, county: str | None, year: int | None) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    by_auth: dict[int, str] = {}
    for aid, raw in _authorities(db, county):
        name = locality_name(raw)
        if not name:
            continue
        slug = slugify(name)
        by_auth[aid] = slug
        groups.setdefault(slug, {"slug": slug, "name": name, "authorities": 0})
        groups[slug]["authorities"] += 1
    totals: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
    stmt = (
        select(Contract.authority_id, func.coalesce(func.sum(Contract.value_ron), 0), func.count(Contract.id))
        .where(Contract.duplicate_of_id.is_(None), Contract.authority_id.in_(list(by_auth)))
        .group_by(Contract.authority_id)
    )
    if year:
        stmt = stmt.where(Contract.year == year)
    for aid, t, n in db.execute(stmt).all():
        totals[by_auth[aid]][0] += Decimal(t or 0)
        totals[by_auth[aid]][1] += n
    out = []
    for slug, g in groups.items():
        t, n = totals.get(slug, [Decimal(0), 0])
        out.append({**g, "total_ron": t, "contracts": n})
    return sorted(out, key=lambda x: x["total_ron"], reverse=True)
