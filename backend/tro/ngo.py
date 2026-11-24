"""Recunoașterea ONG-urilor (asociații, fundații, federații, cluburi sportive) după denumire.

SEAP nu marchează forma juridică a participanților, așa că folosim denumirea normalizată
(majuscule, fără diacritice). Excludem entitățile care se numesc „asociație”, dar nu sunt ONG-uri
în sensul obișnuit: asociațiile de dezvoltare intercomunitară (ale primăriilor), asociațiile de
proprietari și asociațiile familiale (persoane fizice).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import and_, not_

from tro.normalize import normalize_name

# Regex POSIX, valabil și în Python și în Postgres (operatorul ~)
NGO_PATTERN = (
    r"((^| )(ASOCIATIA|ASOCIATIE|ASOCIATIEI|ASOC|FUNDATIA|FUNDATIE|FUNDATIEI|FEDERATIA"
    r"|CLUBUL SPORTIV|CLUB SPORTIV)( |$)"
    r"|^(UNIUNEA|ORGANIZATIA) )"
)
NOT_NGO_PATTERN = r"(INTERCOMUNITAR|DE PROPRIETARI|PROPRIETARILOR|FAMILIALA|( |^)AF$)"

_ngo = re.compile(NGO_PATTERN)
_not_ngo = re.compile(NOT_NGO_PATTERN)


def is_ngo_name(name: str | None) -> bool:
    n = normalize_name(name)
    return bool(n and _ngo.search(n) and not _not_ngo.search(n))


def ngo_condition(column: Any) -> Any:
    """Condiție SQL pe o coloană `name_normalized`."""
    return and_(column.op("~")(NGO_PATTERN), not_(column.op("~")(NOT_NGO_PATTERN)))
