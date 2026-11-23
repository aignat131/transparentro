import datetime as dt
from decimal import Decimal

from tro.etl.sources import anaf
from tro.etl.sources.bnr import RateLookup, parse_bnr_xml
from tro.etl.sources.onrc import parse_onrc_firme
from tro.models import Company, ExchangeRate

BNR_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<DataSet xmlns="http://www.bnr.ro/xsd"><Header><Publisher>National Bank of Romania</Publisher></Header>
<Body><Subject>Reference rates</Subject><OrigCurrency>RON</OrigCurrency>
<Cube date="2025-01-03"><Rate currency="EUR">4.9749</Rate><Rate currency="HUF" multiplier="100">1.2081</Rate></Cube>
<Cube date="2025-01-06"><Rate currency="EUR">4.9760</Rate></Cube>
</Body></DataSet>"""

ANAF_PAYLOAD = {
    "date_generale": {
        "cui": 4240600,
        "denumire": "SAPICO DISTRIBUTION SRL",
        "adresa": "JUD. BIHOR, MUN. ORADEA",
        "stare_inregistrare": "RADIERE din data 13.05.2025",
        "data_inregistrare": "1993-07-08",
        "nrRegCom": "J05/2458/1993",
        "cod_CAEN": "9609",
        "forma_juridica": "SOCIETATE COMERCIALĂ CU RĂSPUNDERE LIMITATĂ",
        "forma_organizare": "PERSOANA JURIDICA",
    },
    "inregistrare_scop_Tva": {"scpTVA": False},
    "stare_inactiv": {"statusInactivi": True},
    "adresa_sediu_social": {
        "sdenumire_Judet": "BIHOR",
        "scod_JudetAuto": "BH",
        "sdenumire_Localitate": "Mun. Oradea",
    },
}


def test_parse_bnr():
    rows = parse_bnr_xml(BNR_XML)
    assert (dt.date(2025, 1, 3), "EUR", Decimal("4.9749")) in rows
    huf = [r for r in rows if r[1] == "HUF"][0]
    assert huf[2] == Decimal("1.2081") / 100


def test_rate_lookup_uses_previous_business_day(session):
    session.add_all(
        [
            ExchangeRate(date=dt.date(2025, 1, 3), currency="EUR", rate=Decimal("4.9749")),
            ExchangeRate(date=dt.date(2025, 1, 6), currency="EUR", rate=Decimal("4.9760")),
        ]
    )
    session.commit()
    rl = RateLookup(session)
    # 5 ianuarie 2025 = duminică → cursul de vineri
    assert rl.rate(dt.date(2025, 1, 5), "EUR") == Decimal("4.9749")
    ron, rate = rl.to_ron(Decimal("100"), "EUR", dt.date(2025, 1, 6))
    assert ron == Decimal("497.60") and rate == Decimal("4.9760")
    assert rl.to_ron(Decimal("5"), "RON", None) == (Decimal("5"), Decimal(1))


def test_anaf_payload_parsing():
    assert anaf.county_from_payload(ANAF_PAYLOAD) == "BH"
    assert anaf.locality_from_payload(ANAF_PAYLOAD) == "Mun. Oradea"
    c = Company(cui="4240600", name="SAPICO", name_normalized="SAPICO", is_natural_person=False)
    anaf.apply_payload_to_company(c, ANAF_PAYLOAD)
    assert c.founded_on == dt.date(1993, 7, 8) and c.caen_code == "9609"
    assert c.inactive is True and c.vat_payer is False and c.county_code == "BH"
    assert c.name == "SAPICO DISTRIBUTION SRL" and not c.is_natural_person


def test_anaf_natural_person_redaction():
    p = {
        "date_generale": {
            "cui": 1,
            "denumire": "POPESCU ION",
            "adresa": "Str. X nr. 1",
            "telefon": "07",
            "forma_juridica": "PERSOANA FIZICA AUTORIZATA",
            "data_inregistrare": "2020-01-01",
        },
        "adresa_sediu_social": {
            "scod_JudetAuto": "SB",
            "sdenumire_Localitate": "Sat Y",
            "sdenumire_Strada": "X",
        },
    }
    assert anaf.payload_is_natural_person(p)
    r = anaf.redact_natural_person(p)
    assert "denumire" not in r["date_generale"] and "adresa" not in r["date_generale"]
    assert "sdenumire_Strada" not in r["adresa_sediu_social"]
    c = Company(cui="1", name="POPESCU ION PFA", name_normalized="X", is_natural_person=False)
    anaf.apply_payload_to_company(c, p)
    assert c.is_natural_person and c.name == "Persoană fizică autorizată"


def test_parse_bilant():
    data = {
        "i": [
            {"indicator": "I13", "val_indicator": 1000000, "val_den_indicator": "Cifra de afaceri neta"},
            {"indicator": "I18", "val_indicator": 50000, "val_den_indicator": "Profit net"},
            {"indicator": "I19", "val_indicator": 0, "val_den_indicator": "Pierdere neta"},
            {"indicator": "I20", "val_indicator": 12, "val_den_indicator": "Numar mediu de salariati"},
        ]
    }
    r = anaf.parse_bilant(data)
    assert r == {"turnover_ron": Decimal("1000000"), "net_profit_ron": Decimal("50000"), "employees": 12}
    assert anaf.parse_bilant({"i": []}) is None


def test_parse_bilant_other_form_does_not_misread_codes():
    # la alte tipuri de entități, codul I20 are alt sens (ex. o sumă în lei) — nu trebuie citit ca angajați
    data = {"i": [{"indicator": "I20", "val_indicator": 2944453922, "val_den_indicator": "Venituri din dobanzi"}]}
    assert anaf.parse_bilant(data) is None


def test_parse_onrc_fragment():
    txt = (
        "DENUMIRE^CUI^COD_INMATRICULARE^DATA_INMATRICULARE^EUID^FORMA_JURIDICA^ADR_TARA^ADR_JUDET\n"
        "AGRO COMPANY 5 SRL^1568158^J40/3606/1991^30/05/1991^ROONRC.J40/3606/1991^SRL^România^Bucureşti\n"
    )
    rows = parse_onrc_firme(txt)
    assert rows[0]["CUI"] == "1568158" and rows[0]["DATA_INMATRICULARE"] == "30/05/1991"
