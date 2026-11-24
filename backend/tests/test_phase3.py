from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from tro import alerts
from tro.etl import synthetic
from tro.models import Contract, ContractExplanation, Subscription


@pytest.fixture()
def data(session):
    synthetic.generate(session, county="SB", seed=3, n_auth=6, n_comp=20, years=(2025,))
    alerts.OUTBOX.clear()
    return session


def _token_from_last_mail() -> str:
    body = alerts.OUTBOX[-1].get_content()
    link = next(word for word in body.split() if "/alerts/confirm?token=" in word)
    return parse_qs(urlparse(link).query)["token"][0]


def test_double_opt_in_flow(client, data):
    r = client.post(
        "/alerts/subscribe", json={"email": "Ana@Exemplu.ro", "target_type": "authority", "target_key": "1"}
    )
    assert r.status_code == 202 and "confirmare" in r.json()["message"]
    sub = data.execute(select(Subscription)).scalar_one()
    assert sub.email == "ana@exemplu.ro" and sub.confirmed_at is None
    # neconfirmat → nu primește alerte
    alerts.OUTBOX.clear()
    assert alerts.send_pending_alerts(data)["emails"] == 0

    token = _token_from_last_mail() if alerts.OUTBOX else sub.token
    r = client.get(f"/alerts/confirm?token={token}")
    assert r.status_code == 200 and "confirmată" in r.text
    data.expire_all()
    assert data.get(Subscription, sub.id).confirmed_at is not None
    # după confirmare: doar contractele NOI
    assert alerts.send_pending_alerts(data)["emails"] == 0
    c = data.execute(select(Contract).where(Contract.authority_id == 1)).scalars().first()
    new = Contract(
        source_id="nou:1",
        source="ad",
        authority_id=1,
        company_id=c.company_id,
        county_code="SB",
        title="Contract nou",
        value_ron=1000,
        year=2025,
        is_synthetic=True,
    )
    data.add(new)
    data.commit()
    assert alerts.send_pending_alerts(data)["emails"] == 1
    assert "Contract nou" in alerts.OUTBOX[-1].get_content()
    assert alerts.send_pending_alerts(data)["emails"] == 0  # nu se retrimite

    r = client.get(f"/alerts/unsubscribe?token={token}")
    assert "dezabonat" in r.text


def test_subscribe_validation(client, data):
    assert (
        client.post(
            "/alerts/subscribe", json={"email": "x@y.ro", "target_type": "authority", "target_key": "99999"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/alerts/subscribe", json={"email": "nu-e-email", "target_type": "authority", "target_key": "1"}
        ).status_code
        == 422
    )
    assert client.get("/alerts/confirm?token=invalidtoken123").status_code == 200


def test_explain_disabled_without_key(client, data, monkeypatch):
    from tro.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    r = client.get("/explain/1")
    assert r.status_code == 503


def test_explain_uses_cache(client, data):
    data.add(ContractExplanation(contract_id=1, text="Explicație salvată.", model="test"))
    data.commit()
    j = client.get("/explain/1").json()
    assert j["cached"] is True and j["text"] == "Explicație salvată."


def test_summary_disabled_without_key(client, data, monkeypatch):
    from tro.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    key = client.get("/companies?page_size=1").json()["items"][0]["key"]
    assert client.get(f"/explain/company/{key}").status_code == 503
    aid = client.get("/authorities?page_size=1").json()["items"][0]["id"]
    assert client.get(f"/explain/authority/{aid}").status_code == 503
    assert client.get("/explain/company/123456789999").status_code == 404
    assert client.get("/explain/authority/999999").status_code == 404


def test_summary_cache_and_refresh(client, data, monkeypatch):
    import datetime as dt

    from tro.api.routers import explain
    from tro.models import AiSummary

    key = client.get("/companies?page_size=1").json()["items"][0]["key"]
    data.add(AiSummary(kind="company", ref=key, text="Rezumat salvat.", model="test"))
    data.commit()
    j = client.get(f"/explain/company/{key}").json()
    assert j["cached"] is True and j["text"] == "Rezumat salvat."

    # rezumatul vechi se regenerează, cu datele firmei trimise modelului
    sent: list[str] = []

    def fake_ask(system: str, content: str) -> tuple[str, str]:
        sent.append(content)
        return "Rezumat nou.", "model-test"

    monkeypatch.setattr(explain, "_ask", fake_ask)
    row = data.get(AiSummary, ("company", key))
    row.created_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=60)
    data.commit()
    j = client.get(f"/explain/company/{key}").json()
    assert j["cached"] is False and j["text"] == "Rezumat nou."
    assert "total_primit_lei" in sent[0] and "clienti_principali" in sent[0]

    aid = client.get("/authorities?page_size=1").json()["items"][0]["id"]
    j = client.get(f"/explain/authority/{aid}").json()
    assert j["text"] == "Rezumat nou." and "furnizori_principali" in sent[-1]


def test_ngo_names():
    from tro.ngo import is_ngo_name

    assert is_ngo_name("Asociația Speranță și Zâmbet")
    assert is_ngo_name("FUNDATIA COMUNITARA SIBIU")
    assert is_ngo_name("Clubul Sportiv Municipal Sibiu")
    assert not is_ngo_name("ASOCIATIA DE DEZVOLTARE INTERCOMUNITARA ECO SIBIU")
    assert not is_ngo_name("Asociatia de proprietari bloc 5")
    assert not is_ngo_name("CONSTRUCTII CS SRL")
    assert not is_ngo_name("FUNDATII SI STRUCTURI SRL")


def test_ngo_filter(client, data):
    from tro.models import Authority, Company
    from tro.normalize import normalize_name

    comp = (
        data.execute(
            select(Company)
            .join(Contract, Contract.company_id == Company.id)
            .where(Company.is_natural_person.is_(False), Contract.repeat_same_company.is_(False))
        )
        .scalars()
        .first()
    )
    comp.name = "Asociația Prietenii Naturii"
    comp.name_normalized = normalize_name(comp.name)
    auth = data.execute(select(Authority).join(Contract, Contract.authority_id == Authority.id)).scalars().first()
    auth.name = "Fundația Comunitară Test"
    auth.name_normalized = normalize_name(auth.name)
    data.commit()

    j = client.get("/companies?ngo=true").json()
    assert [c["name"] for c in j["items"]] == ["Asociația Prietenii Naturii"]
    assert j["items"][0]["is_ngo"] is True
    assert client.get(f"/companies/{comp.cui}").json()["is_ngo"] is True
    a = client.get("/authorities?ngo=true").json()
    assert [x["name"] for x in a["items"]] == ["Fundația Comunitară Test"]
    assert client.get("/companies").json()["total"] > 1


def test_gemini_is_used_when_configured(monkeypatch):
    from types import SimpleNamespace

    from google import genai

    from tro.api.routers import explain
    from tro.config import get_settings

    calls: list[dict] = []

    class FakeClient:
        def __init__(self, api_key: str):
            assert api_key == "cheie-test"
            self.interactions = SimpleNamespace(create=self.create)

        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(
                status="completed", output_text=" Rezumat Gemini. ", model="gemini-test", errors=None
            )

    monkeypatch.setattr(get_settings(), "gemini_api_key", "cheie-test")
    monkeypatch.setattr(genai, "Client", FakeClient)
    assert explain._ask("sistem", "date") == ("Rezumat Gemini.", "gemini-test")
    assert calls[0]["system_instruction"] == "sistem" and calls[0]["input"] == "date"
    assert calls[0]["model"] == get_settings().gemini_model

    def failed(**kw):
        return SimpleNamespace(status="failed", output_text=None, model=None, errors=["blocat"])

    monkeypatch.setattr(FakeClient, "create", lambda self, **kw: failed(**kw))
    import pytest as _pytest
    from fastapi import HTTPException

    with _pytest.raises(HTTPException) as e:
        explain._ask("sistem", "date")
    assert e.value.status_code == 422
