import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from tests.helpers import (
    AD_HEADER,
    CONTRACTE_CODES,
    CONTRACTE_HEADER,
    MODIF_CODES,
    MODIF_HEADER,
    seed_anaf,
    write_xlsx,
)
from tro.etl.sources import anaf as anaf_mod
from tro.etl.sources import seap
from tro.etl.sources.seap_parse import build_column_index, detect_kind, iter_report
from tro.models import (
    Authority,
    Company,
    CompanyAlias,
    Contract,
    ContractAmendment,
    ImportError_,
    SourceRecord,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """ANAF nu este apelat în teste: cache-ul e populat de `seed_anaf`."""
    monkeypatch.setattr(anaf_mod, "fetch_batch", lambda client, cuis: {c: None for c in cuis})


def ad_file(tmp_path):
    d = dt.datetime(2025, 10, 1, 6, 49)
    rows = [
        AD_HEADER,
        [
            "SPITALUL CLINIC JUDETEAN DE URGENTA SIBIU",
            4240898.0,
            "DA38982258",
            d,
            "PANANGIN FORTE",
            "33622000-6",
            "Medicamente pentru sistemul cardiovascular (Rev.2)",
            "Furnizare",
            "Nu",
            "",
            d,
            90.0,
            "BIOEEL",
            1199107.0,
        ],
        [
            "SPITALUL CLINIC JUDETEAN DE URGENTA SIBIU",
            4240898.0,
            "DA38982259",
            d,
            "Consultanță",
            "79411000-8",
            "Servicii generale de consultanta in management (Rev.2)",
            "Servicii",
            "Da",
            "PNRR",
            d,
            15000.0,
            "POPESCU ION PFA",
            "RO 31234567",
        ],
        [
            "SPITALUL CLINIC JUDETEAN DE URGENTA SIBIU",
            4240898.0,
            "DA38982260",
            d,
            "Paine",
            "15811100-7",
            "Paine (Rev.2)",
            "Furnizare",
            "Nu",
            "",
            d,
            400.0,
            "S.C. BIOEEL S.R.L.",
            "RO1199107",
        ],
        [
            "Gradinita cu Program Prelungit nr. 47",
            29170976.0,
            "DA38982261",
            d,
            "Paine 400g",
            "15811100-7",
            "Paine (Rev.2)",
            "Furnizare",
            "Nu",
            "",
            d,
            400.0,
            "THERMAL COAT",
            26067438.0,
        ],
        [
            "CUI LIPSA",
            None,
            "DA38982262",
            d,
            "x",
            "15811100-7",
            "Paine",
            "Furnizare",
            "Nu",
            "",
            d,
            1.0,
            "X",
            1.0,
        ],
    ]
    return write_xlsx(tmp_path / "ad.xlsx", rows, sheet="Sheet1")


def test_detect_kind_and_columns(tmp_path):
    pf, rows = iter_report(ad_file(tmp_path))
    assert pf.kind == "ad"
    assert pf.column_index["value"] == 11
    assert pf.column_index["supplier_cui"] == 13
    assert detect_kind(CONTRACTE_HEADER) == "contracte"
    assert detect_kind(MODIF_HEADER) == "modificari"
    idx = build_column_index("contracte", CONTRACTE_HEADER)
    # coloanele „Data publicare” repetate sunt distinse
    assert idx["initiation_date"] == 5 and idx["publication_date"] == 14


def test_import_ad_filters_county_and_anonymizes(session, tmp_path):
    seed_anaf(session, {"4240898": ("SB", "Mun. Sibiu"), "29170976": ("BV", "Mun. Brasov")})
    run = seap.import_file(session, ad_file(tmp_path))
    session.commit()
    assert run.run.status == "ok"
    contracts = list(session.execute(select(Contract).order_by(Contract.source_id)).scalars())
    # doar Sibiu (Brașov filtrat), rândul fără CUI logat ca eroare
    assert [c.source_id for c in contracts] == ["ad:DA38982258", "ad:DA38982259", "ad:DA38982260"]
    assert all(c.county_code == "SB" for c in contracts)
    assert run.run.rows_skipped == 1 and run.run.rows_failed == 1
    assert session.execute(select(func.count(ImportError_.id))).scalar() == 1
    # PFA anonimizat, fără alias-uri
    pfa = session.execute(select(Company).where(Company.cui == "31234567")).scalar_one()
    assert pfa.is_natural_person and pfa.name == "Persoană fizică autorizată"
    assert session.execute(select(func.count()).where(CompanyAlias.company_id == pfa.id)).scalar() == 0
    # deduplicare pe CUI cu alias-uri păstrate
    bio = session.execute(select(Company).where(Company.cui == "1199107")).scalar_one()
    aliases = set(session.execute(select(CompanyAlias.alias_raw).where(CompanyAlias.company_id == bio.id)).scalars())
    assert aliases == {"BIOEEL", "S.C. BIOEEL S.R.L."} or len(aliases) == 1
    auth = session.execute(select(Authority)).scalar_one()
    assert auth.locality == "Sibiu" and auth.authority_type == "Sănătate"
    c = contracts[1]
    assert c.value_ron == Decimal("15000.00") and c.eu_funded is True and c.procedure_type == "Achiziție directă"
    assert session.execute(select(func.count(SourceRecord.id))).scalar() == 3


def test_import_is_idempotent(session, tmp_path):
    seed_anaf(session, {"4240898": ("SB", "Mun. Sibiu"), "29170976": ("BV", "Mun. Brasov")})
    f = ad_file(tmp_path)
    seap.import_file(session, f)
    first = session.execute(select(func.count(Contract.id))).scalar()
    seap.import_file(session, f)
    seap.import_file(session, f)
    assert session.execute(select(func.count(Contract.id))).scalar() == first == 3
    assert session.execute(select(func.count(Company.id))).scalar() == 2
    assert session.execute(select(func.count(SourceRecord.id))).scalar() == 3


def test_import_contracts_and_amendments(session, tmp_path):
    seed_anaf(session, {"4270740": ("SB", "Mun. Sibiu")})
    d = dt.datetime(2025, 10, 1, 9, 0)
    rows = [
        CONTRACTE_HEADER,
        CONTRACTE_CODES,
        [
            "Municipiul Sibiu",
            4270740.0,
            "Anunt de atribuire",
            "Licitatie deschisa",
            "CN1000001",
            dt.datetime(2025, 6, 1),
            "Legea nr. 98/23.05.2016",
            "Un contract de achizitii publice",
            "Lucrari",
            "Pretul cel mai scazut",
            "45233140-2",
            "Lucrari de drumuri (Rev.2)",
            1.0,
            "CAN1000002",
            d,
            dt.date(2025, 9, 16),
            "123/2025",
            "Fara acord cadru",
            1000000.0,
            "DRUMURI SRL",
            "RO 999",
        ],
        [
            "Municipiul Sibiu",
            4270740.0,
            "Anunt de atribuire",
            "Licitatie deschisa",
            "CN1000001",
            dt.datetime(2025, 6, 1),
            "Legea nr. 98/23.05.2016",
            "Un contract de achizitii publice",
            "Lucrari",
            "Pretul cel mai scazut",
            "45233140-2",
            "Lucrari de drumuri (Rev.2)",
            2.0,
            "CAN1000002",
            d,
            dt.date(2025, 9, 16),
            "124/2025",
            "Fara acord cadru",
            500000.0,
            "ASFALT SA",
            "888",
        ],
    ]
    seap.import_file(session, write_xlsx(tmp_path / "c.xlsx", rows))
    cs = list(session.execute(select(Contract).order_by(Contract.value_ron.desc())).scalars())
    assert len(cs) == 2
    assert cs[0].procedure_id is not None and cs[0].procedure_id == cs[1].procedure_id
    assert cs[0].year == 2025 and cs[0].contract_type == "Lucrari"

    mrows = [
        MODIF_HEADER,
        MODIF_CODES,
        [
            "Municipiul Sibiu",
            "4270740",
            "CAN1000002",
            d,
            "123/2025",
            dt.date(2025, 9, 16),
            "Act aditional lucrari suplimentare",
            1000000.0,
            "RON",
            1300000.0,
            "RON",
        ],
        [
            "Municipiul Sibiu",
            "4270740",
            "CAN1000002",
            d,
            "124/2025",
            dt.date(2025, 9, 16),
            "Prelungire",
            500000.0,
            "RON",
            500000.0,
            "RON",
        ],
    ]
    seap.import_file(session, write_xlsx(tmp_path / "m.xlsx", mrows, sheet="Macheta", legend=True))
    seap.link_amendments(session)
    ams = list(session.execute(select(ContractAmendment).order_by(ContractAmendment.delta_pct.desc())).scalars())
    assert len(ams) == 2
    assert ams[0].delta_pct == 30.0 and ams[0].delta_ron == Decimal("300000.00")
    assert ams[0].contract_id == cs[0].id  # legat după anunț + număr contract
    assert ams[1].contract_id == cs[1].id


def test_unknown_report_is_skipped(session, tmp_path):
    f = write_xlsx(tmp_path / "x.xlsx", [["Autoritate contractanta", "CUI", "Ceva", "Altceva", "Invitatie SAD"]])
    run = seap.import_file(session, f)
    assert run.run.status == "skipped"


def test_header_variant_2026_t3(session, tmp_path):
    """În 2026 T3 antetele sunt scurtate: „CUI”, „Ofertant”, „CUI ” (a doua = furnizorul)."""
    seed_anaf(session, {"15567101": ("SB", "Mun. Sibiu")})
    header = [
        "Autoritate contractanta",
        "CUI",
        "Numar achizitie directa",
        "Data publicare",
        "Denumire achizitie",
        "Cod CPV",
        "Denumire CPV",
        "Tip contract",
        "Cu fonduri europene?",
        "Denumire program",
        "Data atribuire",
        "Valoare achizitie (RON)",
        "Ofertant",
        "CUI ",
    ]
    d = dt.datetime(2026, 7, 1, 0, 7)
    rows = [
        header,
        [
            "SERVICIUL SALVAMONT",
            15567101.0,
            "DA40735307",
            d,
            "Trasee",
            "98113000-8",
            "Servicii",
            "Servicii",
            "Da",
            "",
            dt.datetime(2026, 7, 6),
            5000.0,
            "Asociatia X",
            8772324.0,
        ],
    ]
    run = seap.import_file(session, write_xlsx(tmp_path / "ad26.xlsx", rows, sheet="Sheet1"))
    assert run.run.status == "ok" and run.run.rows_failed == 0
    c = session.execute(select(Contract)).scalar_one()
    assert c.contract_date == dt.date(2026, 7, 6) and c.eu_funded is True
    assert c.company.cui == "8772324" and c.authority.cui == "15567101"


def test_file_with_no_valid_rows_is_marked_failed(session, tmp_path):
    header = AD_HEADER[:1] + ["CUI necunoscut"] + AD_HEADER[2:]
    rows = [header, ["X", "abc", "DA1", None, "t", "1", "x", "Furnizare", "Nu", "", None, 1.0, "Y", 1.0]]
    run = seap.import_file(session, write_xlsx(tmp_path / "bad.xlsx", rows))
    assert run.run.status == "failed"


def test_repeated_contract_rows_are_counted_once(session, tmp_path):
    """Asociere (2 firme, același contract) + 2 loturi cu valoarea totală repetată → o singură valoare."""
    seed_anaf(session, {"4270740": ("SB", "Mun. Sibiu")})
    d = dt.datetime(2025, 10, 1)

    def row(lot, sup, cui, value=1000000.0, cnum="7/2025"):
        return [
            "Municipiul Sibiu",
            4270740.0,
            "Anunt de atribuire",
            "Licitatie deschisa",
            "CN9",
            d,
            "Legea nr. 98/23.05.2016",
            "Un contract",
            "Lucrari",
            "Pret",
            "45233140-2",
            "Drumuri",
            lot,
            "CAN9",
            d,
            dt.date(2025, 9, 1),
            cnum,
            "Fara acord cadru",
            value,
            sup,
            cui,
        ]

    rows = [
        CONTRACTE_HEADER,
        row(1.0, "LIDER SRL", "111"),
        row(1.0, "ASOCIAT SRL", "222"),
        row(2.0, "LIDER SRL", "111"),
        row(1.0, "ALTUL SRL", "333", 5000.0, "8/2025"),
    ]
    seap.import_file(session, write_xlsx(tmp_path / "dup.xlsx", rows))
    seap.mark_duplicate_values(session)
    cs = list(session.execute(select(Contract).order_by(Contract.id)).scalars())
    assert [c.duplicate_of_id is None for c in cs] == [True, False, False, True]
    assert [c.repeat_same_company for c in cs] == [False, False, True, False]
    total = session.execute(select(func.sum(Contract.value_ron)).where(Contract.duplicate_of_id.is_(None))).scalar()
    assert total == Decimal("1005000.00")


def test_framework_with_subsequent_contracts_counts_subsequents(session, tmp_path):
    seed_anaf(session, {"4270740": ("SB", "Mun. Sibiu")})
    d = dt.datetime(2025, 10, 1)

    def row(fw, cnum, value, notice="CAN5"):
        return [
            "Municipiul Sibiu",
            4270740.0,
            "Anunt",
            "Licitatie deschisa",
            "CN5",
            d,
            "Legea 98",
            "Acord-cadru",
            "Furnizare",
            "Pret",
            "09134100-8",
            "Motorina",
            1.0,
            notice,
            d,
            dt.date(2025, 9, 1),
            cnum,
            fw,
            value,
            "PETROL SRL",
            "555",
        ]

    rows = [
        CONTRACTE_HEADER,
        row("Cu acord cadru", "AC-1", 10_000_000.0),
        row("Cu acord cadru subsecvent", "S-1", 2_000_000.0),
        row("Cu acord cadru subsecvent", "S-2", 1_500_000.0),
        row("Cu acord cadru", "AC-2", 700_000.0, notice="CAN6"),
    ]  # fără subsecvente → rămâne
    seap.import_file(session, write_xlsx(tmp_path / "fw.xlsx", rows))
    seap.mark_duplicate_values(session)
    total = session.execute(select(func.sum(Contract.value_ron)).where(Contract.duplicate_of_id.is_(None))).scalar()
    assert total == Decimal("4200000.00")
