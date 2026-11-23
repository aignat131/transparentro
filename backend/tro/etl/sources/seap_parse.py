"""Parsarea rapoartelor SEAP (XLSX/XLS/ODS) în dicționare normalizate.

Tipul raportului se detectează după ANTET (nu după numele resursei — pe data.gov.ro
există resurse cu etichete greșite). Coloanele se identifică după prefixul antetului
simplificat (fără diacritice, lowercase), deci micile variații între ani sunt tolerate.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from python_calamine import CalamineWorkbook

from tro.normalize import simplify

log = logging.getLogger(__name__)

# câmp intern → prefixe posibile ale antetului (simplificat). Pentru coloane repetate
# (ex. „Data publicare” de două ori în raportul de contracte) se folosește sufixul "#2".
FIELD_MAP: dict[str, dict[str, list[str]]] = {
    "ad": {
        "authority_name": ["autoritate contractanta"],
        # 2026 T3: antete scurtate („CUI”, „Ofertant”, „CUI ” — a doua coloană CUI = furnizorul)
        "authority_cui": ["cui autoritate", "cui"],
        "number": ["numar achizitie directa"],
        "publication_date": ["data publicare"],
        "title": ["denumire achizitie"],
        "cpv_code": ["cod cpv"],
        "cpv_name": ["denumire cpv"],
        "contract_type": ["tip contract"],
        "eu_funded": ["finantare prin fonduri", "cu fonduri europene"],
        "eu_program": ["denumire program", "tipul de proiect"],
        "finalized_date": ["data finalizare", "data atribuire"],
        "value": ["valoare achizitie", "valoare"],
        "supplier_name": ["ofertant castigator", "ofertant"],
        "supplier_cui": ["cui ofertant", "cui#2"],
    },
    "dan": {
        "authority_name": ["autoritate contractanta"],
        "authority_cui": ["cui autoritate", "cui"],
        "number": ["numar notificare"],
        "publication_date": ["data publicare"],
        "title": ["obiectul achizitiei"],
        "cpv_code": ["cod cpv"],
        "cpv_name": ["denumire cpv"],
        "contract_type": ["tip contract"],
        "value": ["valoare achizitie", "valoare"],
        "eu_funded": ["finantare prin fonduri", "cu fonduri europene"],
        "eu_program": ["tipul de proiect", "denumire program"],
        "finalized_date": ["data finalizare", "data atribuire"],
        "supplier_name": ["ofertant castigator", "ofertant"],
        "supplier_cui": ["cui ofertant", "cui#2"],
    },
    "contracte": {
        "authority_name": ["autoritate contractanta"],
        "authority_cui": ["cui autoritate"],
        "notice_type": ["tip anunt"],
        "procedure_type": ["tip procedura"],
        "initiation_notice": ["numar anunt initiere"],
        "initiation_date": ["data publicare"],
        "legislation": ["tip legislatie"],
        "assignment_type": ["tip incheiere contract"],
        "contract_type": ["tip contract"],
        "award_criteria": ["tip criterii", "criteriu de atribuire"],
        "cpv_code": ["cod cpv"],
        "cpv_name": ["denumire cpv"],
        "lot": ["numar lot"],
        "award_notice": ["numar anunt atribuire"],
        "publication_date": ["data publicare#2"],
        "contract_date": ["data contract"],
        "contract_number": ["numar contract"],
        "framework": ["incheiat prin"],
        "value": ["valoare contract"],
        "supplier_name": ["ofertant castigator"],
        "supplier_cui": ["cui ofertant"],
        "title": ["denumire contract", "obiect contract"],
    },
    "atribuire_fara": {
        "authority_name": ["autoritate contractanta"],
        "authority_cui": ["cui autoritate"],
        "notice_type": ["tip anunt"],
        "procedure_type": ["tip procedura"],
        "award_notice": ["numar anunt atribuire"],
        "publication_date": ["data publicare"],
        "legislation": ["tip legislatie"],
        "framework": ["incheiat prin"],
        "contract_type": ["tip contract"],
        "award_criteria": ["criteriu de atribuire", "tip criterii"],
        "cpv_code": ["cod cpv"],
        "cpv_name": ["denumire cpv"],
        "contract_date": ["data contract"],
        "contract_number": ["numar contract"],
        "title": ["denumire contract"],
        "value": ["valoare atribuita", "valoare contract"],
        "supplier_name": ["ofertant castigator"],
        "supplier_cui": ["cui ofertant"],
    },
    "initiere": {
        "authority_name": ["autoritate contractanta"],
        "authority_cui": ["cui autoritate"],
        "notice_type": ["tip anunt"],
        "procedure_type": ["tip procedura"],
        "status": ["stare procedura"],
        "initiation_notice": ["numar anunt initiere"],
        "publication_date": ["data publicare"],
        "contract_type": ["tip contract"],
        "assignment_type": ["modalitate de atribuire"],
        "title": ["denumire procedura"],
        "cpv_code": ["cod cpv"],
        "cpv_name": ["denumire cpv"],
        "estimated_value": ["valoare estimata"],
        "currency": ["moneda"],
    },
    "modificari": {
        "authority_name": ["autoritate contractanta"],
        "authority_cui": ["cui autoritate"],
        "award_notice": ["numar anunt"],
        "publication_date": ["data publicare"],
        "contract_number": ["numar contract"],
        "contract_date": ["data contract"],
        "description": ["descrierea modificarilor"],
        "value_before": [
            "valoarea totala actualizata",
            "valoarea totala a contractului inainte",
            "valoare inainte",
        ],
        "currency_before": ["moneda"],
        "value_after": ["valoarea totala a contractului dupa", "valoare dupa"],
        "currency_after": ["moneda#2"],
    },
}


def detect_kind(headers: list[str]) -> str | None:
    h = [simplify(x) for x in headers]
    joined = " | ".join(h)
    if "descrierea modificarilor" in joined:
        return "modificari"
    if "numar achizitie directa" in joined:
        return "ad"
    if "numar notificare" in joined:
        return "dan"
    if "valoare estimata" in joined and "stare procedura" in joined:
        return "initiere"
    if "numar lot" in joined and "valoare contract" in joined:
        return "contracte"
    if "valoare atribuita" in joined or ("denumire contract" in joined and "numar anunt atribuire" in joined):
        return "atribuire_fara"
    if "invitati" in joined or "sad" in joined:
        return "sad"
    return None


@dataclass
class ParsedFile:
    kind: str | None
    headers: list[str]
    column_index: dict[str, int] = field(default_factory=dict)
    sheet: str = ""


def build_column_index(kind: str, headers: list[str]) -> dict[str, int]:
    simple = [simplify(x) for x in headers]
    # numerotăm aparițiile repetate: "data publicare", "data publicare#2"
    keyed: list[str] = []
    counts: dict[str, int] = {}
    for s in simple:
        counts[s] = counts.get(s, 0) + 1
        keyed.append(s if counts[s] == 1 else f"{s}#{counts[s]}")
    idx: dict[str, int] = {}
    for fld, prefixes in FIELD_MAP[kind].items():
        for pref in prefixes:
            base, _, nth = pref.partition("#")
            found = None
            for i, k in enumerate(keyed):
                kbase, _, knth = k.partition("#")
                if kbase.startswith(base) and (knth == nth):
                    found = i
                    break
            if found is not None and found not in idx.values():
                idx[fld] = found
                break
    return idx


def _is_header_row(row: list[Any]) -> bool:
    cells = [simplify(c) for c in row if c not in (None, "")]
    return len(cells) >= 4 and any(c.startswith("autoritate contractanta") or c == "ac" for c in cells)


def _is_code_row(row: list[Any]) -> bool:
    """Al doilea rând din unele rapoarte: DENUMIRE_AC, CUI_AC, ..."""
    cells = [str(c) for c in row if c not in (None, "")]
    return len(cells) >= 4 and sum(1 for c in cells if c.isupper() and "_" in c) >= len(cells) // 2


def row_hash(row: list[Any]) -> str:
    return hashlib.sha256("\x1f".join("" if c is None else str(c) for c in row).encode()).hexdigest()


def iter_report(path: Path) -> tuple[ParsedFile, Iterator[tuple[int, list[Any]]]]:
    """Deschide raportul, găsește foaia de date și antetul; întoarce un iterator de rânduri."""
    wb = CalamineWorkbook.from_path(str(path))
    sheet_names = [s for s in wb.sheet_names if simplify(s) not in ("legenda",)]
    for sn in sheet_names:
        sheet = wb.get_sheet_by_name(sn)
        rows_iter = iter(sheet.iter_rows())
        header: list[Any] | None = None
        line_no = 0
        for _ in range(15):
            try:
                r = next(rows_iter)
            except StopIteration:
                break
            line_no += 1
            if _is_header_row(r):
                header = [("" if c is None else str(c)) for c in r]
                break
        if header is None:
            continue
        kind = detect_kind(header)
        pf = ParsedFile(kind=kind, headers=header, sheet=sn)
        if kind and kind in FIELD_MAP:
            pf.column_index = build_column_index(kind, header)

        def gen(it=rows_iter, start=line_no) -> Iterator[tuple[int, list[Any]]]:
            n = start
            for r in it:
                n += 1
                if not any(c not in (None, "") for c in r):
                    continue
                if _is_code_row(r):
                    continue
                yield n, list(r)

        return pf, gen()
    return ParsedFile(kind=None, headers=[]), iter(())


def extract(pf: ParsedFile, row: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fld, i in pf.column_index.items():
        out[fld] = row[i] if i < len(row) else None
    return out
