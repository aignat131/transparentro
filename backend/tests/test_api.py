import csv
import io

import pytest

from tro.etl import risk, synthetic


@pytest.fixture()
def data(session):
    synthetic.generate(session, county="SB", seed=7, n_auth=12, n_comp=40, years=(2024, 2025))
    risk.compute_all(session)
    return session


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_overview(client, data):
    r = client.get("/stats/overview")
    assert r.status_code == 200
    j = r.json()
    assert j["county_code"] == "SB" and j["contracts"] > 0
    assert j["data"]["has_synthetic"] is True
    assert {y["year"] for y in j["by_year"]} == {2024, 2025}
    assert len(j["latest_contracts"]) == 10
    # cache
    assert client.get("/stats/overview").headers["X-Cache"] == "HIT"


def test_other_county_is_empty(client, data):
    j = client.get("/stats/overview?county=CJ").json()
    assert j["contracts"] == 0
    assert client.get("/stats/overview?county=all").json()["contracts"] > 0
    assert client.get("/stats/overview?county=XYZ").status_code == 400


def test_contract_filters_pagination_sort(client, data):
    j = client.get("/contracts?page_size=5&sort=value_desc").json()
    vals = [float(i["value_ron"]) for i in j["items"]]
    assert vals == sorted(vals, reverse=True) and len(vals) == 5
    total = j["total"]
    j2 = client.get("/contracts?year=2025&min_value=100000&page_size=100").json()
    assert j2["total"] < total
    assert all(i["year"] == 2025 and float(i["value_ron"]) >= 100000 for i in j2["items"])
    j3 = client.get("/contracts?procedure_type=Achiziție directă&page_size=3").json()
    assert all(i["procedure_type"] == "Achiziție directă" for i in j3["items"])
    j4 = client.get("/contracts?cpv=158&page_size=50").json()
    assert all(i["cpv_code"].startswith("158") for i in j4["items"])
    p2 = client.get("/contracts?page=2&page_size=5&sort=value_desc").json()
    assert p2["items"][0]["id"] not in [i["id"] for i in j["items"]]
    assert client.get("/contracts?with_signals=true").json()["total"] > 0


def test_contract_detail(client, data):
    cid = client.get("/contracts?source=contracte&page_size=1").json()["items"][0]["id"]
    j = client.get(f"/contracts/{cid}").json()
    assert j["procedure"] is not None and "sicap_search_url" in j and j["category"]
    assert client.get("/contracts/999999").status_code == 404


def test_authority_detail(client, data):
    aid = client.get("/authorities?page_size=1").json()["items"][0]["id"]
    j = client.get(f"/authorities/{aid}").json()
    assert j["by_year"] and j["top_suppliers"] and j["by_category"] and j["by_procedure_type"]
    assert len(j["top_suppliers"]) <= 10
    shares = sum(c["share"] or 0 for c in j["by_category"])
    assert 0.99 < shares < 1.01


def test_company_detail_and_anonymization(client, data):
    items = client.get("/companies?page_size=200").json()["items"]
    legal = next(i for i in items if not i["is_natural_person"])
    j = client.get(f"/companies/{legal['key']}").json()
    assert j["cui"] == legal["key"] and j["by_year"] and j["clients"]
    pf = next(i for i in items if i["is_natural_person"])
    assert pf["key"].startswith("pf-") and pf["name"] == "Persoană fizică autorizată"
    jp = client.get(f"/companies/{pf['key']}").json()
    assert jp["cui"] is None and jp["founded_on"] is None and jp["aliases"] == [] and jp["registry_number"] is None
    assert client.get("/companies/123456789").status_code == 404


def test_search_diacritics_tolerant(client, data):
    a = client.get("/search?q=Școala gimnazială").json()
    b = client.get("/search?q=scoala gimnaziala").json()
    c = client.get("/search?q=Şcoala").json()  # sedilă
    assert a["authorities"] and [h["id"] for h in a["authorities"]] == [h["id"] for h in b["authorities"]]
    assert c["authorities"]
    assert client.get("/search?q=9900000001").json()["authorities"][0]["id"] == "1"
    assert client.get("/search?q=***").json()["authorities"] == []


def test_risk_signals_endpoint(client, data):
    j = client.get("/risk-signals?page_size=100").json()
    assert j["total"] > 0
    scores = [s["score"] for s in j["items"]]
    assert scores == sorted(scores, reverse=True)
    t = client.get("/risk-signals?signal_type=fragmentation").json()
    assert all(s["signal_type"] == "fragmentation" for s in t["items"])
    assert all(s["score"] >= 70 for s in client.get("/risk-signals?min_score=70").json()["items"])
    summary = client.get("/risk-signals/summary").json()
    assert sum(summary.values()) == j["total"]


def test_csv_export(client, data):
    r = client.get("/export/contracts.csv?year=2025")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
    assert rows[0][0] == "id" and len(rows) - 1 == client.get("/contracts?year=2025").json()["total"]
    for path in ("/export/authorities.csv", "/export/companies.csv", "/export/risk-signals.csv"):
        assert client.get(path).status_code == 200


def test_map_and_meta(client, data):
    pts = client.get("/map/authorities").json()
    assert pts and all(45 < p["lat"] < 47 for p in pts)
    m = client.get("/meta").json()
    assert 2025 in m["years"] and any(c["code"] == "SB" and c["has_data"] for c in m["counties"])


def test_corrections(client, session):
    r = client.post("/corrections", json={"message": "Valoarea contractului pare greșită.", "email": "a@b.ro"})
    assert r.status_code == 201
    assert client.post("/corrections", json={"message": "scurt"}).status_code == 422


def test_openapi(client):
    j = client.get("/openapi.json").json()
    for p in (
        "/authorities",
        "/companies/{key}",
        "/contracts",
        "/search",
        "/stats/overview",
        "/risk-signals",
    ):
        assert p in j["paths"]


def test_domain_filter(client, data):
    m = client.get("/meta").json()
    assert {"key": "constructii", "label": "Construcții și lucrări"} in m["domains"]
    all_ov = client.get("/stats/overview").json()
    ov = client.get("/stats/overview?domain=constructii").json()
    assert 0 < ov["contracts"] < all_ov["contracts"]
    j = client.get("/contracts?domain=constructii&page_size=100").json()
    assert j["total"] == ov["contracts"]
    assert all(i["cpv_code"][:2] in ("45", "44", "14") for i in j["items"])
    comps = client.get("/companies?domain=constructii&page_size=200").json()
    assert 0 < comps["total"] <= all_ov["companies"]
    assert sum(c["contracts"] for c in comps["items"]) <= ov["contracts"]
    auths = client.get("/authorities?domain=constructii&page_size=200").json()
    assert auths["items"] and all(a["contracts"] > 0 for a in auths["items"])
    assert client.get("/stats/overview?domain=necunoscut").json()["contracts"] == 0


def test_open_procedures(client, data):
    import datetime as dt
    from decimal import Decimal

    from sqlalchemy import func, select

    from tro.models import Authority, Procedure

    # toate cele sintetice sunt atribuite (alt URL decât mai jos: răspunsurile sunt în cache)
    assert client.get("/procedures?page_size=10").json()["total"] == 0
    auth = data.execute(select(Authority)).scalars().first()
    newest = data.execute(select(func.max(Procedure.publication_date))).scalar()
    for i, (status, value, days) in enumerate(
        [
            ("In desfasurare", "80000", 5),
            ("În desfășurare", "2500000", 10),
            ("Anulata", "50000", 5),
            ("In desfasurare", "60000", 400),  # prea veche ca să mai fie în curs
        ]
    ):
        data.add(
            Procedure(
                source_id=f"t:open{i}",
                authority_id=auth.id,
                notice_number=f"CN-T{i}",
                title=f"Servicii de test {i}",
                cpv_code="45233140-2",
                estimated_value_ron=Decimal(value),
                status=status,
                publication_date=newest - dt.timedelta(days=days),
            )
        )
    data.commit()
    j = client.get("/procedures").json()
    assert sorted(p["notice_number"] for p in j["items"]) == ["CN-T0", "CN-T1"]
    assert all(p["is_open"] and "e-licitatie.ro" in p["official_url"] for p in j["items"])
    small = client.get("/procedures?max_value=100000").json()
    assert [p["notice_number"] for p in small["items"]] == ["CN-T0"]
    assert client.get("/procedures?domain=constructii").json()["total"] == 2
    assert client.get("/procedures?domain=it").json()["total"] == 0
    assert client.get("/procedures?q=test 1").json()["total"] == 1
    every = client.get("/procedures?status=all&page_size=100").json()
    assert every["total"] > 100
    st = client.get("/procedures/statuses").json()
    assert {"status": "Anulata", "count": 1} in st["statuses"]


def test_spending_report(client, data):
    ov = client.get("/stats/overview?year=2025").json()
    r = client.get("/stats/report?year=2025").json()
    assert r["year"] == 2025 and r["contracts"] == ov["contracts"]
    assert abs(float(r["total_ron"]) - float(ov["total_ron"])) < 1
    for part in ("by_domain", "by_contract_type", "by_procedure_type", "by_authority_type", "by_month"):
        assert abs(sum(float(x["total_ron"]) for x in r[part]) - float(r["total_ron"])) < 1, part
        assert sum(x["count"] for x in r[part]) == r["contracts"], part
    assert all(x["key"] for x in r["by_domain"])
    assert r["top_authorities"] and r["top_companies"]
    assert all(m["month"].startswith("2025-") for m in r["by_month"])
    assert float(r["direct_awards_ron"]) <= float(r["total_ron"])
    assert client.get("/stats/report").json()["contracts"] >= r["contracts"]
