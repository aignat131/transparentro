"""Protecția datelor: marchează ca persoane fizice (PFA, II, IF) firmele recunoscute după oricare denumire.

La import, marcajul se pune la crearea firmei. Dacă firma a apărut întâi sub o denumire neutră
(„SARBU A. IOAN”) și abia apoi ca „... Persoană Fizică Autorizată”, ar rămâne nemarcată și numele
s-ar afișa. Pasul acesta rulează la fiecare import și repară astfel de cazuri.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from tro.models import Company, CompanyAlias
from tro.normalize import is_natural_person

log = logging.getLogger(__name__)


def mark_natural_persons(session: Session) -> int:
    aliases: dict[int, list[str]] = {}
    for cid, alias in session.execute(select(CompanyAlias.company_id, CompanyAlias.alias_raw)).all():
        aliases.setdefault(cid, []).append(alias)
    n = 0
    for c in session.execute(select(Company).where(Company.is_natural_person.is_(False))).scalars():
        names = [c.name, *aliases.get(c.id, [])]
        if any(is_natural_person(name=x) for x in names) or is_natural_person(legal_form=c.legal_form):
            c.is_natural_person = True
            n += 1
    session.commit()
    log.info("Persoane fizice marcate acum: %d", n)
    return n
