from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from tro import alerts
from tro.api import schemas as S
from tro.config import get_settings
from tro.db import get_db

router = APIRouter(prefix="/alerts", tags=["alerte"])


def _page(title: str, text: str) -> HTMLResponse:
    site = html.escape(get_settings().public_base_url)
    return HTMLResponse(
        f"""<!doctype html><html lang="ro"><head><meta charset="utf-8"><meta name="viewport"
        content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title></head>
        <body style="font-family:system-ui,sans-serif;max-width:560px;margin:60px auto;padding:0 16px">
        <h1>{html.escape(title)}</h1><p>{html.escape(text)}</p><p><a href="{site}">Înapoi la TransparentRO</a></p>
        </body></html>"""
    )


@router.post(
    "/subscribe", response_model=S.Message, status_code=202, summary="Abonare la contracte noi (double opt-in)"
)
def subscribe(body: S.SubscribeIn, db: Session = Depends(get_db)):
    try:
        msg = alerts.subscribe(db, body.email, body.target_type, body.target_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return S.Message(message=msg)


@router.get("/confirm", response_class=HTMLResponse, summary="Confirmarea abonării (link din e-mail)")
def confirm(token: str = Query(..., min_length=10, max_length=100), db: Session = Depends(get_db)):
    sub = alerts.confirm(db, token)
    if sub is None:
        return _page("Link invalid", "Linkul de confirmare nu este valid sau abonarea a fost anulată.")
    return _page("Abonare confirmată", "Veți primi un e-mail când apar contracte noi. Vă puteți dezabona oricând.")


@router.get("/unsubscribe", response_class=HTMLResponse, summary="Dezabonare")
def unsubscribe(token: str = Query(..., min_length=10, max_length=100), db: Session = Depends(get_db)):
    ok = alerts.unsubscribe(db, token)
    return _page("Dezabonare", "V-ați dezabonat." if ok else "Linkul nu este valid.")
