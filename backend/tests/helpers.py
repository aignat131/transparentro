"""Fixture-uri de fișiere SEAP cu exact antetele rapoartelor reale (2025 T IV)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from sqlalchemy.dialects.postgresql import insert

from tro.models import AnafCache

AD_HEADER = [
    "Autoritate contractanta",
    "CUI autoritate contractanta",
    "Numar achizitie directa",
    "Data publicare",
    "Denumire achizitie",
    "Cod CPV",
    "Denumire CPV",
    "Tip contract",
    "Finantare prin fonduri comunitare?",
    "Denumire program",
    "Data finalizare",
    "Valoare achizitie (RON)",
    "Ofertant castigator",
    "CUI ofertant castigator",
]
CONTRACTE_HEADER = [
    "Autoritate contractanta",
    "CUI autoritate contractanta",
    "Tip anunt",
    "Tip procedura",
    "Numar anunt initiere",
    "Data publicare",
    "Tip legislatie",
    "Tip incheiere contract",
    "Tip contract",
    "Tip criterii de atribuire",
    "Cod CPV",
    "Denumire CPV",
    "Numar lot",
    "Numar anunt atribuire",
    "Data publicare",
    "Data contract",
    "Numar contract",
    "Incheiat prin",
    "Valoare contract (RON)",
    "Ofertant castigator",
    "CUI ofertant castigator",
]
CONTRACTE_CODES = [
    "DENUMIRE_AC",
    "CUI_AC",
    "TIP_ANUNT",
    "TIP_PROCEDURA",
    "NUMAR_ANUNT_AI",
    "DATA_PUBLICARE_AI",
    "TIP_LESIGLATIE",
    "TIP_INCHEIERE_CONTRACT",
    "TIP_CONTRACT",
    "TIP_CRITERII_ATRIBUIRE",
    "CPV_CODE",
    "DENUMIRE_CPV",
    "NUMAR_LOT",
    "NUMAR_ANUNT_ATRIBUIRE",
    "DATA_ANUNT_ATRIBUIRE",
    "DATA_CONTRACT",
    "NUMAR_CONTRACT",
    "INCHEIAT_PRIN",
    "VALOARE_CONTRACT_RON",
    "OFERTANT",
    "CUI_OF",
]
MODIF_HEADER = [
    "Autoritate contractanta",
    "CUI autoritate contractanta",
    "Numar anunt atribuire",
    "Data publicare",
    "Numar contract ",
    "Data contract",
    "Descrierea modificarilor",
    "Valoarea totala actualizata a contractului inainte de modificari",
    "Moneda",
    "Valoarea totala a contractului dupa modificari ",
    "Moneda",
]
MODIF_CODES = [
    "AC",
    "CUI_AC",
    "NUMAR_ANUNT",
    "DATA_ANUNT_MODIFICARE",
    "NUMAR_CONTRACT",
    "DATA_CONTRACT",
    "DESCRIERE_MODIFICARILOR",
    "VALOARE_INAINTE_MODIFICARI",
    "MONEDA",
    "VALOARE_DUPA_MODIFICARI",
    "MONEDA_1",
]


def write_xlsx(path: Path, rows: list[list[Any]], sheet: str = "sheet", legend: bool = False) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    if legend:
        lg = wb.create_sheet("Legenda")
        lg.append(["Legenda", ""])
    wb.save(path)
    return path


def seed_anaf(session, mapping: dict[str, tuple[str, str]]) -> None:
    """mapping: cui → (cod județ, localitate) — simulează cache-ul ANAF (fără rețea)."""
    rows = []
    for cui, (cc, loc) in mapping.items():
        rows.append(
            {
                "cui": cui,
                "found": True,
                "county_code": cc,
                "fetched_at": dt.datetime.now(dt.UTC),
                "payload": {
                    "date_generale": {
                        "cui": int(cui),
                        "denumire": f"AUTORITATE {cui}",
                        "adresa": f"{loc}, jud {cc}",
                    },
                    "adresa_sediu_social": {"scod_JudetAuto": cc, "sdenumire_Localitate": loc},
                },
            }
        )
    stmt = insert(AnafCache).values(rows).on_conflict_do_nothing()
    session.execute(stmt)
    session.commit()
