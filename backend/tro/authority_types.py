"""Clasificarea simplă a autorităților după denumire (euristică, documentată în Metodologie)."""

from __future__ import annotations

import re

from tro.normalize import simplify

_RULES: list[tuple[str, str]] = [
    (r"consiliul judetean|judetul ", "Consiliu județean"),
    (
        r"primari|comuna |orasul |municipiul |unitatea administrativ|^uat |^u\.a\.t",
        "Primărie / administrație locală",
    ),
    (
        r"spital|sanatori|ambulant|dispensar|centrul medical|institutul (regional|national) de|policlinic|dsp ",
        "Sănătate",
    ),
    (r"universitat|academia", "Universitate"),
    (
        r"scoal|liceu|colegiu|gradinit|palatul copiilor|clubul copiilor|seminar|inspectoratul scolar|creșa|cresa",
        "Educație",
    ),
    (
        r"directia generala de asistenta|asistenta sociala|dgaspc|centrul de ingrijire|camin|protectia copilului",
        "Asistență socială",
    ),
    (
        r"politi|jandarm|inspectoratul (pentru situatii|general)|isu |penitenciar"
        r"|unitatea militara|ministerul apararii",
        "Ordine publică și apărare",
    ),
    (
        r"muzeu|biblioteca|teatr|filarmonic|centrul (judetean|cultural)|casa de cultura|cultural|ansamblul",
        "Cultură",
    ),
    (
        r"apa |apa-|apa canal|salubri|termoficare|transport public|tursib|drumuri|aeroport"
        r"|regia|compania|s\.?a\.?$|srl",
        "Companie / regie publică",
    ),
    (
        r"directia|agentia|oficiul|administratia|autoritatea|institutia prefectului|prefectur|garda|inspectoratul",
        "Instituție publică",
    ),
    (r"parohi|biserica|manastir", "Culte"),
]


def classify_authority(name: str | None) -> str:
    s = simplify(name)
    for pat, typ in _RULES:
        if re.search(pat, s):
            return typ
    return "Altă autoritate"


_LOCALITY_PREFIX = re.compile(
    r"^(mun\.?|municipiul|oras(ul)?\.?|ors\.?|com\.?|comuna|sat(ul)?\.?|loc\.?)\s+", re.IGNORECASE
)


def locality_key(locality: str | None) -> str:
    """'Mun. Sibiu' → 'sibiu'; 'Com. Şura Mică' → 'sura mica' (cheie pentru geocodare/grupare)."""
    if not locality:
        return ""
    s = simplify(locality)
    # ANAF: „Sat Alma Com. Alma” → satul „alma”
    s = re.split(r"\s+(com|oras|mun)\.?\s+", s)[0]
    s = _LOCALITY_PREFIX.sub("", s)
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)
    return s.strip()


def locality_display(locality: str | None) -> str | None:
    if not locality:
        return None
    s = _LOCALITY_PREFIX.sub("", locality.strip())
    return s.strip().title() if s.isupper() else s.strip()
