import datetime as dt
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import select

from tro.etl import risk
from tro.models import (
    Authority,
    Company,
    CompanyFinancial,
    Contract,
    ContractAmendment,
    Procedure,
    RiskSignal,
)

_n = count(1)


@pytest.fixture()
def world(session):
    a = Authority(cui="100", name="Primăria Test", name_normalized="PRIMARIA TEST", county_code="SB")
    b = Authority(cui="101", name="Școala Test", name_normalized="SCOALA TEST", county_code="SB")
    old = Company(cui="200", name="VECHE SRL", name_normalized="VECHE", founded_on=dt.date(2001, 1, 1))
    new = Company(cui="201", name="NOUA SRL", name_normalized="NOUA", founded_on=dt.date(2025, 3, 1))
    other = Company(cui="202", name="ALTA SRL", name_normalized="ALTA", founded_on=dt.date(2010, 1, 1))
    session.add_all([a, b, old, new, other])
    session.commit()
    return {"a": a, "b": b, "old": old, "new": new, "other": other}


def contract(session, auth, comp, value, day, source="ad", cpv="30192000-1", ctype="Furnizare", proc=None):
    c = Contract(
        source_id=f"t:{next(_n)}",
        source=source,
        authority_id=auth.id,
        company_id=comp.id,
        county_code="SB",
        value_ron=Decimal(str(value)),
        contract_date=day,
        year=day.year,
        cpv_code=cpv,
        contract_type=ctype,
        procedure_id=proc.id if proc else None,
        source_url="https://data.gov.ro/x",
    )
    session.add(c)
    session.commit()
    return c


def signals(session, typ):
    return list(session.execute(select(RiskSignal).where(RiskSignal.signal_type == typ)).scalars())


def test_new_company(session, world):
    contract(session, world["a"], world["old"], 1000, dt.date(2025, 1, 10))  # începutul acoperirii
    contract(session, world["a"], world["new"], 50000, dt.date(2025, 6, 1))  # 92 zile după înființare
    contract(session, world["a"], world["other"], 50000, dt.date(2025, 6, 1))
    risk.compute_all(session)
    s = signals(session, "new_company")
    assert len(s) == 1 and s[0].company_id == world["new"].id
    assert s[0].details["days"] == 92
    assert "acuz" not in s[0].explanation.lower()


def test_new_company_ignores_firms_founded_before_coverage(session, world):
    world["new"].founded_on = dt.date(2024, 12, 1)  # înainte de primul contract din date
    session.commit()
    contract(session, world["a"], world["old"], 1000, dt.date(2025, 1, 10))
    contract(session, world["a"], world["new"], 50000, dt.date(2025, 2, 1))
    risk.compute_all(session)
    assert signals(session, "new_company") == []


def test_single_bidder(session, world):
    p1 = Procedure(source_id="p:1", authority_id=world["a"].id, number_of_offers=1, procedure_type="Licitatie deschisa")
    p2 = Procedure(source_id="p:2", authority_id=world["a"].id, number_of_offers=4)
    p3 = Procedure(source_id="p:3", authority_id=world["a"].id, number_of_offers=None)
    session.add_all([p1, p2, p3])
    session.commit()
    c1 = contract(session, world["a"], world["old"], 900000, dt.date(2025, 5, 1), source="contracte", proc=p1)
    contract(session, world["a"], world["old"], 900000, dt.date(2025, 5, 1), source="contracte", proc=p2)
    contract(session, world["a"], world["old"], 900000, dt.date(2025, 5, 1), source="contracte", proc=p3)
    risk.compute_all(session)
    s = signals(session, "single_bidder")
    assert [x.contract_id for x in s] == [c1.id]


def test_fragmentation(session, world):
    for m in (2, 4, 6):
        contract(session, world["a"], world["old"], 100000, dt.date(2025, m, 1))  # 3 × 100k = 300k > 270.120
    # sub prag cumulat → fără semnal
    for m in (2, 4, 6):
        contract(session, world["b"], world["old"], 10000, dt.date(2025, m, 1))
    # același furnizor, altă categorie CPV → nu se cumulează
    contract(session, world["b"], world["old"], 260000, dt.date(2025, 7, 1), cpv="45000000-7", ctype="Lucrari")
    risk.compute_all(session)
    s = signals(session, "fragmentation")
    assert len(s) == 1 and s[0].authority_id == world["a"].id
    assert s[0].details["count"] == 3 and s[0].details["threshold_ron"] == 270120


def test_fragmentation_near_threshold(session, world):
    contract(session, world["a"], world["other"], 250000, dt.date(2025, 3, 1))
    contract(session, world["a"], world["other"], 240000, dt.date(2025, 9, 1))
    risk.compute_all(session)
    s = signals(session, "fragmentation")
    assert len(s) == 1 and s[0].details["near_threshold_count"] == 2


def test_amendment_increase(session, world):
    c = contract(session, world["a"], world["old"], 100000, dt.date(2025, 1, 1), source="contracte")
    for i, (before, after) in enumerate([(100000, 125000), (100000, 115000), (100000, 100000)]):
        session.add(
            ContractAmendment(
                source_id=f"m{i}",
                contract_id=c.id,
                authority_id=world["a"].id,
                value_before_ron=Decimal(before),
                value_after_ron=Decimal(after),
                delta_ron=Decimal(after - before),
                delta_pct=(after - before) / before * 100,
                publication_date=dt.date(2025, 6, 1),
            )
        )
    session.commit()
    risk.compute_all(session)
    s = signals(session, "amendment_increase")
    assert len(s) == 1 and s[0].details["delta_pct"] == 25.0 and s[0].contract_id == c.id


def test_public_revenue_share(session, world):
    contract(session, world["a"], world["old"], 600000, dt.date(2024, 5, 1), source="contracte")
    contract(session, world["a"], world["other"], 100000, dt.date(2024, 5, 1), source="contracte")
    session.add_all(
        [
            CompanyFinancial(company_id=world["old"].id, year=2024, turnover_ron=Decimal(1000000)),
            CompanyFinancial(company_id=world["other"].id, year=2024, turnover_ron=Decimal(5000000)),
        ]
    )
    session.commit()
    risk.compute_all(session)
    s = signals(session, "public_revenue_share")
    assert len(s) == 1 and s[0].company_id == world["old"].id and s[0].details["share"] == 0.6


def test_concentration(session, world):
    for i in range(5):
        contract(session, world["a"], world["other"], 20000, dt.date(2025, 1 + i, 1))
    contract(session, world["a"], world["old"], 400000, dt.date(2025, 8, 1), source="contracte")
    # autoritate mică (sub pragul de 200.000 lei) → ignorată
    for i in range(5):
        contract(session, world["b"], world["old"], 1000, dt.date(2025, 1 + i, 1))
    risk.compute_all(session)
    s = signals(session, "concentration")
    assert len(s) == 1 and s[0].company_id == world["old"].id and s[0].authority_id == world["a"].id
    assert s[0].details["share"] == 0.8


def test_recompute_is_idempotent(session, world):
    for m in (2, 4, 6):
        contract(session, world["a"], world["old"], 100000, dt.date(2025, m, 1))
    first = risk.compute_all(session)
    second = risk.compute_all(session)
    assert first == second
    assert len(list(session.execute(select(RiskSignal)).scalars())) == sum(first.values())


def test_direct_threshold_selection():
    cfg = risk.load_thresholds()
    assert risk.direct_threshold(cfg, dt.date(2025, 1, 1), "Furnizare") == 270120
    assert risk.direct_threshold(cfg, dt.date(2025, 1, 1), "Lucrari") == 900400
    assert risk.direct_threshold(cfg, dt.date(2019, 1, 1), "Servicii") == 135060
