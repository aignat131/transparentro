"""Explicație în limbaj simplu a unui contract, generată cu Claude (Anthropic API).

Dezactivat automat dacă ANTHROPIC_API_KEY lipsește. Rezultatul se păstrează în
`contract_explanations`, deci fiecare contract este explicat o singură dată.
Datele trimise sunt doar cele publice deja afișate pe pagină (persoanele fizice sunt anonimizate).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tro.api.routers.contracts import get_contract
from tro.config import get_settings
from tro.db import get_db
from tro.models import ContractExplanation

log = logging.getLogger(__name__)
router = APIRouter(prefix="/explain", tags=["explicații"])

SYSTEM = (
    "Ești un jurnalist de date care explică achizițiile publice din România pentru cetățeni obișnuiți. "
    "Primești datele publice ale unui contract în format JSON. Scrie în limba română, pe înțeles, 2-4 paragrafe "
    "scurte (max. 180 de cuvinte): cine a cumpărat, ce, de la cine, cât a costat, prin ce procedură și ce "
    "înseamnă acea procedură. Dacă există acte adiționale sau semnale de verificat, menționează-le NEUTRU: "
    "semnalele nu sunt acuzații și pot avea explicații legitime. Folosește doar informațiile primite; dacă "
    "lipsește ceva, spune că nu se știe. Nu face presupuneri despre intenții, nu folosi markdown, "
    "nu da sfaturi juridice."
)


def _payload(c: Any) -> dict[str, Any]:
    d = c.model_dump(mode="json")
    keep = [
        "title",
        "value_ron",
        "currency",
        "contract_date",
        "procedure_type",
        "contract_type",
        "cpv_code",
        "cpv_name",
        "category",
        "notice_number",
        "framework",
        "eu_funded",
        "eu_program",
        "duration_days",
    ]
    out = {k: d.get(k) for k in keep}
    out["institutie"] = d["authority"]["name"]
    out["furnizor"] = d["company"]["name"] if d.get("company") else None
    out["procedura"] = d.get("procedure")
    out["acte_aditionale"] = [
        {k: a.get(k) for k in ("publication_date", "description", "value_before_ron", "value_after_ron", "delta_pct")}
        for a in d.get("amendments", [])
    ]
    out["semnale"] = [{"tip": s["signal_label"], "explicatie": s["explanation"]} for s in d.get("signals", [])]
    return out


@router.get("/{contract_id}", summary="Explicație AI, în limbaj simplu, pentru un contract")
def explain(contract_id: int, db: Session = Depends(get_db)):
    s = get_settings()
    cached = db.get(ContractExplanation, contract_id)
    if cached:
        return {"contract_id": contract_id, "text": cached.text, "model": cached.model, "cached": True}
    if not s.anthropic_api_key:
        raise HTTPException(503, "Explicațiile automate nu sunt activate pe acest server.")
    detail = get_contract(contract_id, db)  # 404 dacă nu există

    import anthropic  # import local: dependența e opțională la rulare

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    try:
        response = client.beta.messages.create(
            model=s.anthropic_model,
            max_tokens=4000,
            system=SYSTEM,
            output_config={"effort": "low"},
            # la un refuz de siguranță, API-ul reîncearcă automat pe un model de rezervă
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[
                {
                    "role": "user",
                    "content": "Datele contractului:\n" + json.dumps(_payload(detail), ensure_ascii=False, indent=1),
                }
            ],
        )
    except anthropic.RateLimitError as exc:
        raise HTTPException(429, "Prea multe cereri. Încercați peste un minut.") from exc
    except anthropic.APIStatusError as exc:
        log.warning("Anthropic API %s: %s", exc.status_code, exc.message)
        raise HTTPException(502, "Serviciul de explicații nu a răspuns corect.") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(502, "Serviciul de explicații nu poate fi contactat.") from exc

    if response.stop_reason == "refusal":
        raise HTTPException(422, "Nu am putut genera o explicație pentru acest contract.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise HTTPException(502, "Explicația generată este goală.")
    db.add(ContractExplanation(contract_id=contract_id, text=text, model=response.model))
    db.commit()
    return {"contract_id": contract_id, "text": text, "model": response.model, "cached": False}
