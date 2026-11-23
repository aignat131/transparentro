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
    r = client.get("/explain/1")
    assert r.status_code == 503


def test_explain_uses_cache(client, data):
    data.add(ContractExplanation(contract_id=1, text="Explicație salvată.", model="test"))
    data.commit()
    j = client.get("/explain/1").json()
    assert j["cached"] is True and j["text"] == "Explicație salvată."
