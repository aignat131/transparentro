"""Explicații și rezumate în limbaj simplu, generate cu AI (Gemini; alternativ Claude).

- /explain/{contract_id}: un contract (proiect); se păstrează în `contract_explanations`.
- /explain/company/{key}: o firmă sau un ONG care a primit bani publici.
- /explain/authority/{id}: o instituție (sau un ONG) care cumpără prin SEAP.
  Rezumatele se păstrează în `ai_summaries` și se regenerează după SUMMARY_MAX_AGE, pentru că datele se schimbă.

Dezactivat automat dacă lipsesc și GEMINI_API_KEY și ANTHROPIC_API_KEY.
Datele trimise sunt doar cele publice deja afișate pe pagină (persoanele fizice sunt anonimizate).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tro.api.common import company_key, find_company
from tro.api.routers.authorities import _authority_detail
from tro.api.routers.companies import _company_detail
from tro.api.routers.contracts import get_contract
from tro.config import get_settings
from tro.db import get_db
from tro.models import AiSummary, Authority, ContractExplanation

log = logging.getLogger(__name__)
router = APIRouter(prefix="/explain", tags=["explicații"])

SUMMARY_MAX_AGE = dt.timedelta(days=30)

SYSTEM = (
    "Ești un jurnalist de date care explică achizițiile publice din România pentru cetățeni obișnuiți. "
    "Primești datele publice ale unui contract în format JSON. Scrie în limba română, pe înțeles, 2-4 paragrafe "
    "scurte (max. 180 de cuvinte): cine a cumpărat, ce, de la cine, cât a costat, prin ce procedură și ce "
    "înseamnă acea procedură. Dacă există acte adiționale sau semnale de verificat, menționează-le NEUTRU: "
    "semnalele nu sunt acuzații și pot avea explicații legitime. Folosește doar informațiile primite; dacă "
    "lipsește ceva, spune că nu se știe. Nu face presupuneri despre intenții, nu folosi markdown, "
    "nu da sfaturi juridice."
)

SYSTEM_ENTITY = (
    "Ești un jurnalist de date care explică cetățenilor obișnuiți din România cum sunt cheltuiți banii publici. "
    "Primești în format JSON datele publice despre o {what}, extrase din achizițiile publice (SEAP) și din "
    "registrele oficiale. Scrie în limba română, pe înțeles, un rezumat de 2-3 paragrafe scurte "
    "(max. 170 de cuvinte): ce fel de entitate este, {focus}, cât și în ce ani, pentru ce fel de produse, "
    "servicii sau lucrări, și ce iese în evidență (de exemplu dacă banii vin în mare parte de la o singură "
    "instituție sau dacă există semnale de verificat). Semnalele NU sunt acuzații și pot avea explicații "
    "legitime; menționează-le neutru. Folosește doar informațiile primite, cu sumele rotunjite pe înțeles, "
    "în lei; dacă lipsește ceva, nu inventa. Nu face presupuneri despre intenții, nu folosi markdown sau "
    "liste, nu da sfaturi juridice."
)


NOT_ENABLED = "Explicațiile automate nu sunt activate pe acest server."


def _ask(system: str, content: str) -> tuple[str, str]:
    """Trimite datele la modelul AI configurat; întoarce (text, model). Ridică HTTPException la erori.

    Gemini dacă există GEMINI_API_KEY, altfel Claude dacă există ANTHROPIC_API_KEY.
    """
    s = get_settings()
    if s.gemini_api_key:
        return _ask_gemini(system, content)
    if s.anthropic_api_key:
        return _ask_claude(system, content)
    raise HTTPException(503, NOT_ENABLED)


def _ask_gemini(system: str, content: str) -> tuple[str, str]:
    s = get_settings()
    from google import genai  # import local: dependența e opțională la rulare
    from google.genai import errors

    client = genai.Client(api_key=s.gemini_api_key)
    try:
        # Vercel oprește funcția după ~60 s
        # fără stream=True răspunsul e un singur Interaction
        interaction: Any = client.interactions.create(
            model=s.gemini_model,
            system_instruction=system,
            input=content,
            generation_config={"max_output_tokens": 2000},
            timeout=50.0,
        )
    except errors.APIError as exc:
        if exc.code == 429:
            raise HTTPException(429, "Prea multe cereri. Încercați peste un minut.") from exc
        log.warning("Gemini API %s: %s", exc.code, exc.message)
        raise HTTPException(502, "Serviciul de explicații nu a răspuns corect.") from exc
    except Exception as exc:  # erori de rețea (httpx) sau de timp
        log.warning("Gemini API: %s", exc)
        raise HTTPException(502, "Serviciul de explicații nu poate fi contactat.") from exc

    if interaction.status not in ("completed", "incomplete"):
        log.warning("Gemini interaction %s: %s", interaction.status, interaction.errors)
        raise HTTPException(422, "Nu am putut genera o explicație pentru aceste date.")
    text = (interaction.output_text or "").strip()
    if not text:
        raise HTTPException(502, "Explicația generată este goală.")
    return text, str(interaction.model or s.gemini_model)


def _ask_claude(system: str, content: str) -> tuple[str, str]:
    s = get_settings()
    import anthropic  # import local: dependența e opțională la rulare

    # Vercel oprește funcția după ~60 s: un singur reîncercat, cu limită de timp
    client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=50.0, max_retries=1)
    try:
        response = client.beta.messages.create(
            model=s.anthropic_model,
            max_tokens=4000,
            system=system,
            output_config={"effort": "low"},
            # la un refuz de siguranță, API-ul reîncearcă automat pe un model de rezervă
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.RateLimitError as exc:
        raise HTTPException(429, "Prea multe cereri. Încercați peste un minut.") from exc
    except anthropic.APIStatusError as exc:
        log.warning("Anthropic API %s: %s", exc.status_code, exc.message)
        raise HTTPException(502, "Serviciul de explicații nu a răspuns corect.") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(502, "Serviciul de explicații nu poate fi contactat.") from exc

    if response.stop_reason == "refusal":
        raise HTTPException(422, "Nu am putut genera o explicație pentru aceste date.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise HTTPException(502, "Explicația generată este goală.")
    return text, response.model


def _as_json(label: str, data: dict[str, Any]) -> str:
    return f"{label}:\n" + json.dumps(data, ensure_ascii=False, indent=1, default=str)


# ---------------------------------------------------------------- contracte (proiecte)


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
    cached = db.get(ContractExplanation, contract_id)
    if cached:
        return {"contract_id": contract_id, "text": cached.text, "model": cached.model, "cached": True}
    detail = get_contract(contract_id, db)  # 404 dacă nu există
    text, model = _ask(SYSTEM, _as_json("Datele contractului", _payload(detail)))
    db.add(ContractExplanation(contract_id=contract_id, text=text, model=model))
    db.commit()
    return {"contract_id": contract_id, "text": text, "model": model, "cached": False}


# ---------------------------------------------------------------- firme, ONG-uri, instituții


def _fresh(row: AiSummary) -> bool:
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=dt.UTC)
    return dt.datetime.now(dt.UTC) - created < SUMMARY_MAX_AGE


def _summary(db: Session, kind: str, ref: str, system: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = db.get(AiSummary, (kind, ref))
    if row is not None and _fresh(row):
        return {"text": row.text, "model": row.model, "cached": True}
    text, model = _ask(system, _as_json("Datele", payload))
    if row is None:
        db.add(AiSummary(kind=kind, ref=ref, text=text, model=model))
    else:
        row.text, row.model, row.created_at = text, model, dt.datetime.now(dt.UTC)
    db.commit()
    return {"text": text, "model": model, "cached": False}


def _totals(items: list[Any], limit: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "nume": x.name,
            "total_lei": x.total_ron,
            "contracte": x.count,
            "pondere": round(x.share, 3) if x.share else None,
        }
        for x in items[:limit]
    ]


def _signals(sigs: list[Any]) -> list[dict[str, Any]]:
    return [{"tip": x.signal_label, "explicatie": x.explanation} for x in sigs[:5]]


@router.get("/company/{key}", summary="Rezumat AI pentru o firmă sau un ONG care a primit bani publici")
def summarize_company(key: str, db: Session = Depends(get_db)):
    c = find_company(db, key)  # 404 dacă nu există
    d = _company_detail(db, c)
    if d.is_natural_person:
        kind = "persoană fizică autorizată (numele nu se publică)"
    elif d.is_ngo:
        kind = "organizație neguvernamentală (ONG: asociație, fundație, club sportiv)"
    else:
        kind = "firmă"
    payload = {
        "nume": d.name,
        "tip": kind,
        "forma_juridica": d.legal_form,
        "localitate": d.locality,
        "infiintata": d.founded_on,
        "cod_caen": d.caen_code,
        "stare": d.status,
        "inactiva_anaf": d.inactive,
        "total_primit_lei": d.total_ron,
        "numar_contracte": d.contracts,
        "primul_contract": d.first_contract_date,
        "pe_ani": [{"an": y.year, "total_lei": y.total_ron, "contracte": y.count} for y in d.by_year],
        "clienti_principali": _totals(d.clients),
        "pe_categorii": _totals(d.by_category, 6),
        "date_financiare": [
            {"an": f.year, "cifra_afaceri": f.turnover_ron, "profit_net": f.net_profit_ron, "angajati": f.employees}
            for f in d.financials[-3:]
        ],
        "semnale_de_verificat": _signals(d.signals),
    }
    system = SYSTEM_ENTITY.format(
        what="firmă sau organizație care a primit bani publici",
        focus="de la ce instituții a primit bani",
    )
    key = company_key(c)
    return {"key": key, **_summary(db, "company", key, system, payload)}


@router.get("/authority/{authority_id}", summary="Rezumat AI pentru o instituție sau un ONG care cumpără")
def summarize_authority(authority_id: int, db: Session = Depends(get_db)):
    a = db.get(Authority, authority_id)
    if a is None:
        raise HTTPException(404, "Instituția nu a fost găsită")
    d = _authority_detail(db, a, None)
    payload = {
        "nume": d.name,
        "tip": d.authority_type,
        "localitate": d.locality,
        "judet": d.county_name,
        "total_cheltuit_lei": d.total_ron,
        "numar_contracte": d.contracts,
        "pe_ani": [{"an": y.year, "total_lei": y.total_ron, "contracte": y.count} for y in d.by_year],
        "furnizori_principali": _totals(d.top_suppliers),
        "pe_categorii": _totals(d.by_category, 6),
        "pe_tip_de_procedura": _totals(d.by_procedure_type, 5),
        "semnale_de_verificat": _signals(d.signals),
    }
    system = SYSTEM_ENTITY.format(
        what="instituție sau organizație care cumpără prin achiziții publice",
        focus="pe ce a cheltuit și la ce firme s-au dus banii",
    )
    return {"id": authority_id, **_summary(db, "authority", str(authority_id), system, payload)}
