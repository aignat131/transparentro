"""Domenii largi de cheltuieli, pentru filtrul de pe site.

Fiecare domeniu grupează diviziuni CPV (primele 2 cifre ale codului). Categoriile fine din
`tro.cpv` rămân pentru detalii; domeniile sunt puține, ca cetățeanul să aleagă ușor.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import false, or_

from tro.models import Contract

# cheie → (etichetă, diviziuni CPV)
DOMAINS: dict[str, tuple[str, tuple[str, ...]]] = {
    "constructii": ("Construcții și lucrări", ("45", "44", "14")),
    "utilitati": ("Energie, apă și utilități", ("09", "41", "65", "76")),
    "sanatate": ("Sănătate", ("33", "85")),
    "transport": ("Transport și vehicule", ("34", "60", "63")),
    "it": ("IT și comunicații", ("30", "32", "48", "64", "72")),
    "salubritate": ("Salubritate, curățenie, spații verzi", ("90", "77")),
    "echipamente": ("Echipamente, utilaje și reparații", ("16", "31", "35", "38", "42", "43", "50", "51")),
    "proiectare": ("Proiectare, consultanță și servicii", ("66", "70", "71", "73", "75", "79", "98")),
    "educatie": ("Educație, cultură și sport", ("37", "55", "80", "92")),
    "bunuri": ("Alimente, mobilier și alte bunuri", ("03", "15", "18", "19", "22", "24", "39")),
}


def all_domains() -> list[dict[str, str]]:
    return [{"key": k, "label": v[0]} for k, v in DOMAINS.items()]


def domain_condition(key: str | None) -> Any:
    """Condiția SQL pentru contractele dintr-un domeniu; None dacă nu e cerut niciun domeniu."""
    if not key:
        return None
    d = DOMAINS.get(key)
    if d is None:
        return false()
    return or_(*(Contract.cpv_code.like(f"{p}%") for p in d[1]))
