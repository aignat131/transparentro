"""Normalizare: CUI, denumiri, diacritice, detecție persoane fizice (GDPR), valori, date."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------- diacritice / text

_DIACRITICS = str.maketrans(
    {
        "ă": "a",
        "â": "a",
        "î": "i",
        "ș": "s",
        "ş": "s",
        "ț": "t",
        "ţ": "t",
        "Ă": "A",
        "Â": "A",
        "Î": "I",
        "Ș": "S",
        "Ş": "S",
        "Ț": "T",
        "Ţ": "T",
    }
)


def strip_diacritics(text: str) -> str:
    text = text.translate(_DIACRITICS)
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def simplify(text: Any) -> str:
    """lowercase, fără diacritice, spații compactate — pentru comparații de antete etc."""
    if text is None:
        return ""
    s = strip_diacritics(str(text)).lower()
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- CUI

_CNP_RE = re.compile(r"^[1-9]\d{12}$")


def normalize_cui(value: Any) -> str | None:
    """'RO 012345 ' → '12345'. Întoarce None dacă nu e un CUI plauzibil.

    Acceptă float-uri din Excel (14285773.0) și prefixe RO/R0. Un CNP (13 cifre) este
    păstrat ca atare aici; apelantul decide anonimizarea (vezi `looks_like_cnp`).
    """
    if value is None:
        return None
    if isinstance(value, float):
        if value != value or value <= 0:  # NaN
            return None
        value = str(int(value))
    s = str(value).strip().upper()
    if not s:
        return None
    s = re.sub(r"^(RO|R0)\s*", "", s)
    s = re.sub(r"[\s.\-/]", "", s)
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    if not s.isdigit():
        return None
    s = s.lstrip("0")
    if not s or len(s) > 13:
        return None
    return s


def looks_like_cnp(cui: str | None) -> bool:
    return bool(cui and _CNP_RE.match(cui))


# ---------------------------------------------------------------- denumiri firme

_LEGAL_FORMS = [
    r"S\.?\s?R\.?\s?L\.?(\s?-?\s?D)?",
    r"S\.?\s?A\.?",
    r"S\.?\s?C\.?",
    r"S\.?\s?N\.?\s?C\.?",
    r"S\.?\s?C\.?\s?S\.?",
    r"R\.?\s?A\.?",
    r"S\.?\s?C\.?\s?A\.?",
    r"S\.?\s?P\.?\s?R\.?\s?L\.?",
    r"IFN",
    r"SOCIETATE(A)? (CU RASPUNDERE LIMITATA|COMERCIALA|PE ACTIUNI)",
    r"COMPANIA",
]
_LEGAL_RE = re.compile(r"(?<![A-Z0-9])(" + "|".join(_LEGAL_FORMS) + r")(?![A-Z0-9])")


def normalize_name(name: Any) -> str:
    """'S.C. Construcții Montaj S.R.L.' → 'CONSTRUCTII MONTAJ'."""
    if name is None:
        return ""
    s = strip_diacritics(str(name)).upper()
    s = s.replace("&", " SI ")
    s = re.sub(r"[\"'`´„”“’()\[\]]", " ", s)
    s = _LEGAL_RE.sub(" ", s)
    s = re.sub(r"[.,;:]", " ", s)
    s = re.sub(r"\s*-\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------- persoane fizice (GDPR)

_PF_PATTERNS = [
    r"\bP\.?\s?F\.?\s?A\.?(?![A-Z])",
    r"PERSOANA FIZICA",
    r"\bI\.\s?I\.?(?![A-Z])",
    r"\bII$",
    r"INTREPRINDERE(A)? INDIVIDUALA",
    r"\bI\.\s?F\.?(?![A-Z])",
    r"\bIF$",
    r"INTREPRINDERE(A)? FAMILIALA",
    r"CABINET (INDIVIDUAL|MEDICAL INDIVIDUAL)",
    r"BIROU INDIVIDUAL",
    r"\bAF$",  # asociație familială
]
_PF_RE = re.compile("|".join(_PF_PATTERNS))
_PF_LEGAL_FORMS = (
    "PERSOANA FIZICA",
    "INTREPRINDERE INDIVIDUALA",
    "INTREPRINDERE FAMILIALA",
    "PFA",
    "II",
    "IF",
)


def is_natural_person(name: Any = None, cui: str | None = None, legal_form: str | None = None) -> bool:
    """True pentru persoane fizice, PFA, II, IF, cabinete individuale — se anonimizează."""
    if looks_like_cnp(cui):
        return True
    if legal_form:
        lf = strip_diacritics(legal_form).upper()
        if any(p in lf for p in ("PERSOANA FIZICA", "INTREPRINDERE INDIVIDUALA", "INTREPRINDERE FAMILIALA")):
            return True
        if lf.strip() in _PF_LEGAL_FORMS:
            return True
    if name:
        n = strip_diacritics(str(name)).upper()
        if _PF_RE.search(n):
            return True
    return False


def anonymous_key(name: str, locality: str | None = None) -> str:
    h = hashlib.sha256(f"{normalize_name(name)}|{simplify(locality)}".encode()).hexdigest()[:16]
    return f"PF-{h}"


def fallback_company_key(name: str) -> str:
    """Cheie tehnică pentru furnizori fără CUI (ex. firme străine)."""
    return "X-" + hashlib.sha256(normalize_name(name).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- valori / date


def to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        if isinstance(value, float) and value != value:
            return None
        return Decimal(str(round(float(value), 2)))
    s = str(value).strip().replace(" ", "")
    if not s:
        return None
    # format românesc 1.234.567,89
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M", "%Y/%m/%d")


def to_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, int | float):
        # număr serial Excel
        if 20000 < float(value) < 80000:
            return dt.date(1899, 12, 30) + dt.timedelta(days=int(value))
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s[:19]
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def clean_str(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        if value != value:
            return None
        if value.is_integer():
            value = int(value)
    s = re.sub(r"\s+", " ", str(value)).strip()
    if not s:
        return None
    return s[:max_len] if max_len else s


def cpv_code(value: Any) -> str | None:
    """'45233140-2' → '45233140-2'; '45233140' → '45233140'."""
    s = clean_str(value)
    if not s:
        return None
    m = re.match(r"(\d{8})(-\d)?", s)
    return m.group(0) if m else None


def to_bool_ro(value: Any) -> bool | None:
    s = simplify(value)
    if s in ("da", "yes", "true", "1"):
        return True
    if s in ("nu", "no", "false", "0"):
        return False
    return None
