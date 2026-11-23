"""Alerte pe e-mail: abonare cu double opt-in, confirmare, dezabonare, trimitere de rezumate.

Provider configurabil prin MAIL_PROVIDER: `console` (doar log — implicit, pentru dezvoltare) sau `smtp`.
"""

from __future__ import annotations

import datetime as dt
import logging
import secrets
import smtplib
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from tro.config import get_settings
from tro.models import Authority, Company, Contract, Subscription
from tro.normalize import normalize_cui

log = logging.getLogger(__name__)

MAX_SUBSCRIPTIONS_PER_EMAIL = 25
OUTBOX: list[EmailMessage] = []  # folosit în teste (provider console)


def send_mail(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if s.mail_provider == "smtp":
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    else:
        OUTBOX.append(msg)
        del OUTBOX[:-100]
        log.info("[e-mail console] către %s: %s\n%s", to, subject, body)


def resolve_target(db: Session, target_type: str, key: str) -> tuple[str, str] | None:
    """Întoarce (cheie canonică, nume afișat) sau None."""
    if target_type == "authority":
        if not key.isdigit():
            return None
        a = db.get(Authority, int(key))
        return (str(a.id), a.name) if a else None
    if target_type == "company":
        cui = normalize_cui(key)
        if not cui:
            return None
        c = db.execute(select(Company).where(Company.cui == cui)).scalar_one_or_none()
        if c is None or c.is_natural_person:
            return None
        return c.cui, c.name
    return None


def _target_filter(sub: Subscription, db: Session):
    if sub.target_type == "authority":
        return Contract.authority_id == int(sub.target_key)
    cid = db.execute(select(Company.id).where(Company.cui == sub.target_key)).scalar_one()
    return Contract.company_id == cid


def subscribe(db: Session, email: str, target_type: str, target_key: str) -> str:
    s = get_settings()
    email = email.strip().lower()
    target = resolve_target(db, target_type, target_key)
    if target is None:
        raise ValueError("Instituția sau firma nu există (persoanele fizice nu pot fi urmărite).")
    key, name = target
    active = db.execute(
        select(func.count()).where(Subscription.email == email, Subscription.unsubscribed_at.is_(None))
    ).scalar_one()
    if active >= MAX_SUBSCRIPTIONS_PER_EMAIL:
        raise ValueError("Ați atins numărul maxim de abonări pentru această adresă.")
    sub = db.execute(
        select(Subscription).where(
            Subscription.email == email, Subscription.target_type == target_type, Subscription.target_key == key
        )
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(email=email, target_type=target_type, target_key=key, token=secrets.token_urlsafe(32))
        db.add(sub)
    elif sub.confirmed_at and not sub.unsubscribed_at:
        db.commit()
        return "Sunteți deja abonat(ă) la aceste alerte."
    else:
        sub.token = secrets.token_urlsafe(32)
        sub.unsubscribed_at = None
        sub.confirmed_at = None
    db.commit()
    link = f"{s.api_base_url}/alerts/confirm?token={sub.token}"
    send_mail(
        email,
        f"Confirmați abonarea la alertele TransparentRO: {name}",
        f"Bună ziua,\n\nAți cerut să primiți un e-mail când apar contracte publice noi pentru:\n  {name}\n\n"
        f"Confirmați abonarea deschizând linkul:\n  {link}\n\n"
        "Dacă nu ați cerut acest lucru, ignorați mesajul — nu veți primi alte e-mailuri.\n\nTransparentRO",
    )
    return "V-am trimis un e-mail de confirmare. Abonarea devine activă după ce apăsați linkul din mesaj."


def confirm(db: Session, token: str) -> Subscription | None:
    sub = db.execute(select(Subscription).where(Subscription.token == token)).scalar_one_or_none()
    if sub is None or sub.unsubscribed_at:
        return None
    if not sub.confirmed_at:
        sub.confirmed_at = dt.datetime.now(dt.UTC)
        # trimitem doar contractele apărute DUPĂ confirmare
        sub.last_notified_contract_id = db.execute(
            select(func.coalesce(func.max(Contract.id), 0)).where(_target_filter(sub, db))
        ).scalar_one()
    db.commit()
    return sub


def unsubscribe(db: Session, token: str) -> bool:
    sub = db.execute(select(Subscription).where(Subscription.token == token)).scalar_one_or_none()
    if sub is None:
        return False
    sub.unsubscribed_at = dt.datetime.now(dt.UTC)
    db.commit()
    return True


def send_pending_alerts(db: Session, dry_run: bool = False) -> dict[str, int]:
    s = get_settings()
    subs = list(
        db.execute(
            select(Subscription).where(Subscription.confirmed_at.is_not(None), Subscription.unsubscribed_at.is_(None))
        ).scalars()
    )
    sent = 0
    for sub in subs:
        new = list(
            db.execute(
                select(Contract)
                .options(selectinload(Contract.authority), selectinload(Contract.company))
                .where(_target_filter(sub, db), Contract.id > (sub.last_notified_contract_id or 0))
                .order_by(Contract.id)
                .limit(200)
            ).scalars()
        )
        if not new:
            continue
        target = resolve_target(db, sub.target_type, sub.target_key)
        name = target[1] if target else sub.target_key
        lines = []
        for c in new[:50]:
            sup = c.company.display_name if c.company else "—"
            val = f"{float(c.value_ron or 0):,.0f} lei".replace(",", ".")
            url = f"{s.public_base_url}/contracte/{c.id}"
            lines.append(f"- {c.contract_date or ''} · {c.title or c.cpv_name} · {sup} · {val}\n  {url}")
        more = f"\n… și încă {len(new) - 50} contracte.\n" if len(new) > 50 else ""
        body = (
            f"Contracte noi pentru {name}:\n\n"
            + "\n".join(lines)
            + more
            + f"\n\nDezabonare: {s.api_base_url}/alerts/unsubscribe?token={sub.token}\n"
        )
        if not dry_run:
            send_mail(sub.email, f"TransparentRO: {len(new)} contracte noi — {name}", body)
            sub.last_notified_contract_id = new[-1].id
        sent += 1
    db.commit()
    return {"subscriptions": len(subs), "emails": sent}
