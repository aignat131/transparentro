"""Nomenclatorul județelor (cod auto, denumire, centru aproximativ pentru hartă)."""

from __future__ import annotations

from tro.normalize import simplify

# cod: (denumire, lat, lon) — centrul aproximativ al reședinței de județ
COUNTIES: dict[str, tuple[str, float, float]] = {
    "AB": ("Alba", 46.07, 23.58),
    "AR": ("Arad", 46.18, 21.31),
    "AG": ("Argeș", 44.86, 24.87),
    "BC": ("Bacău", 46.57, 26.91),
    "BH": ("Bihor", 47.05, 21.93),
    "BN": ("Bistrița-Năsăud", 47.13, 24.49),
    "BT": ("Botoșani", 47.75, 26.67),
    "BV": ("Brașov", 45.65, 25.61),
    "BR": ("Brăila", 45.27, 27.96),
    "B": ("București", 44.43, 26.10),
    "BZ": ("Buzău", 45.15, 26.82),
    "CS": ("Caraș-Severin", 45.30, 21.89),
    "CL": ("Călărași", 44.20, 27.33),
    "CJ": ("Cluj", 46.77, 23.60),
    "CT": ("Constanța", 44.18, 28.63),
    "CV": ("Covasna", 45.86, 25.79),
    "DB": ("Dâmbovița", 44.93, 25.46),
    "DJ": ("Dolj", 44.32, 23.80),
    "GL": ("Galați", 45.44, 28.05),
    "GR": ("Giurgiu", 43.90, 25.97),
    "GJ": ("Gorj", 45.04, 23.27),
    "HR": ("Harghita", 46.36, 25.80),
    "HD": ("Hunedoara", 45.88, 22.91),
    "IL": ("Ialomița", 44.56, 27.37),
    "IS": ("Iași", 47.16, 27.59),
    "IF": ("Ilfov", 44.50, 26.08),
    "MM": ("Maramureș", 47.66, 23.58),
    "MH": ("Mehedinți", 44.63, 22.66),
    "MS": ("Mureș", 46.54, 24.56),
    "NT": ("Neamț", 46.93, 26.37),
    "OT": ("Olt", 44.43, 24.37),
    "PH": ("Prahova", 44.94, 26.02),
    "SM": ("Satu Mare", 47.79, 22.89),
    "SJ": ("Sălaj", 47.18, 23.06),
    "SB": ("Sibiu", 45.79, 24.15),
    "SV": ("Suceava", 47.65, 26.26),
    "TR": ("Teleorman", 43.97, 25.33),
    "TM": ("Timiș", 45.75, 21.23),
    "TL": ("Tulcea", 45.18, 28.80),
    "VS": ("Vaslui", 46.64, 27.73),
    "VL": ("Vâlcea", 45.10, 24.37),
    "VN": ("Vrancea", 45.70, 27.18),
}

_BY_NAME = {simplify(v[0]): k for k, v in COUNTIES.items()}
_BY_NAME.update({"municipiul bucuresti": "B", "bucuresti": "B"})


def county_code_from_name(name: str | None) -> str | None:
    if not name:
        return None
    s = simplify(name).replace("judetul ", "").replace("jud. ", "").strip()
    if s.startswith("municipiul bucuresti") or s.startswith("bucuresti"):
        return "B"
    return _BY_NAME.get(s)


def county_name(code: str | None) -> str | None:
    if not code:
        return None
    c = COUNTIES.get(code.upper())
    return c[0] if c else None


# Populația rezidentă la recensământul din 2021 (INS), pentru calculul „lei pe locuitor”.
POPULATION_2021: dict[str, int] = {
    "SB": 388_325,
}
