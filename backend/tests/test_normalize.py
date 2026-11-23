import datetime as dt
from decimal import Decimal

import pytest

from tro.authority_types import classify_authority, locality_key
from tro.cpv import UNKNOWN, cpv_category
from tro.etl.sources.ckan import classify_name, quarter_from_name
from tro.normalize import (
    is_natural_person,
    looks_like_cnp,
    normalize_cui,
    normalize_name,
    strip_diacritics,
    to_date,
    to_decimal,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("RO 13795308", "13795308"),
        ("RO13795308", "13795308"),
        ("ro 0012345", "12345"),
        (14285773.0, "14285773"),
        (" 4240898 ", "4240898"),
        ("R0 960322", "960322"),
        ("", None),
        (None, None),
        ("CUI_AC", None),
        ("abc123", None),
        (float("nan"), None),
        ("000", None),
    ],
)
def test_normalize_cui(raw, expected):
    assert normalize_cui(raw) == expected


def test_cnp_detection():
    assert looks_like_cnp("1850101123456")
    assert not looks_like_cnp("13795308")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("S.C. Construcții Montaj S.R.L.", "CONSTRUCTII MONTAJ"),
        ("SC ALFA SRL", "ALFA"),
        ("Beta S.A.", "BETA"),
        ("ŞTEFĂNEŞTI-ŢARA SRL", "STEFANESTI TARA"),
        ("DRUMURI SI PODURI SA SIBIU", "DRUMURI SI PODURI SIBIU"),
        ("SALUBRIS S.R.L.-D", "SALUBRIS"),
        ("SAPICO DISTRIBUTION", "SAPICO DISTRIBUTION"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_normalize_name_keeps_words_containing_legal_forms():
    # „SA” în interiorul unui cuvânt nu trebuie eliminat
    assert normalize_name("SANATATEA SRL") == "SANATATEA"
    assert normalize_name("CASA VERDE SRL") == "CASA VERDE"


@pytest.mark.parametrize(
    "name,cui,lf,expected",
    [
        ("POPESCU ION PFA", "123", None, True),
        ("Popescu Ion Persoană Fizică Autorizată", None, None, True),
        ("IONESCU MARIA I.I.", None, None, True),
        ("CABINET MEDICAL INDIVIDUAL DR. X", None, None, True),
        ("ALFA SRL", "123", None, False),
        ("LOT II CONSTRUCT SRL", None, None, False),
        (None, "1850101123456", None, True),
        ("X", "123", "INTREPRINDERE INDIVIDUALA", True),
        ("X", "123", "SOCIETATE COMERCIALĂ CU RĂSPUNDERE LIMITATĂ", False),
    ],
)
def test_natural_person(name, cui, lf, expected):
    assert is_natural_person(name, cui, lf) is expected


def test_decimal_and_date_parsing():
    assert to_decimal(64120.0) == Decimal("64120.00")
    assert to_decimal("1.234.567,89") == Decimal("1234567.89")
    assert to_decimal("1234.5") == Decimal("1234.50")
    assert to_decimal("") is None
    assert to_date("15.03.2025") == dt.date(2025, 3, 15)
    assert to_date(dt.datetime(2025, 10, 1, 8, 54)) == dt.date(2025, 10, 1)
    assert to_date("04/12/1991") == dt.date(1991, 12, 4)
    assert to_date(45000) == dt.date(2023, 3, 15)
    assert to_date("nu e data") is None


def test_strip_diacritics_both_variants():
    assert strip_diacritics("Șș Țț Şş Ţţ ĂăÂâÎî") == "Ss Tt Ss Tt AaAaIi"


def test_cpv_categories():
    assert cpv_category("45233140-2") == "Construcții drumuri"
    assert cpv_category("72212000-4").startswith("IT")
    assert cpv_category("15811100-7") == "Alimente"
    assert cpv_category("45000000-7") == "Lucrări de construcții"
    assert cpv_category(None) == UNKNOWN
    assert cpv_category("99999999") == UNKNOWN


def test_authority_classification_and_locality():
    assert classify_authority("Municipiul Sibiu") == "Primărie / administrație locală"
    assert classify_authority("SPITALUL CLINIC JUDETEAN DE URGENTA SIBIU") == "Sănătate"
    assert classify_authority("Scoala Gimnaziala nr. 2 Cisnadie") == "Educație"
    assert classify_authority('UNIVERSITATEA "LUCIAN BLAGA" DIN SIBIU') == "Universitate"
    assert locality_key("Mun. Sibiu") == "sibiu"
    assert locality_key("Com. Şura Mică") == "sura mica"
    assert locality_key("Oraş Avrig") == "avrig"
    assert locality_key("Sat Alma Com. Alma") == "alma"
    assert locality_key("Sat Apoldu de Jos Com. Apoldu de Jos") == "apoldu de jos"


@pytest.mark.parametrize(
    "name,kind,quarter",
    [
        ("Achiziții directe T IV 2025", "ad", 4),
        ("Achizitii directe TII 2026", "ad", 2),
        ("Achizitii directe TI 2026", "ad", 1),
        ("Achiziții directe TIII 2025", "ad", 3),
        ("Notificări de atribuire la cumpărarea directa T1 2025", "dan", 1),
        ("Contracte T IV 2025", "contracte", 4),
        ("Raport Contracte publicate T II 2024", "contracte", 2),
        ("Anunturi de atribuire la proceduri fara anunt de initiere TIII 2026", "atribuire_fara", 3),
        ("Anunturi de intiere publicate TII 2026", "initiere", 2),
        ("Date din modificare contract T IV 2025", "modificari", 4),
        ("Invitații de depunere SAD cu anunț aferent T IV 2025", "sad", 4),
    ],
)
def test_ckan_classification(name, kind, quarter):
    assert classify_name(name) == kind
    assert quarter_from_name(name) == quarter


def test_quarter_from_url():
    assert quarter_from_name("datagov-raport-contracte-t-iv_2024.xlsx") == 4
    assert quarter_from_name("datagov_raport_contracte_t1_2025.xlsx") == 1
    assert quarter_from_name("datagov-raport-achizitii-directe-tiii.xls") == 3
