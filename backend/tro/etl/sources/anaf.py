"""ANAF: date generale după CUI (v9) și bilanțuri anuale.

- POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva  — max. 100 CUI/cerere, 1 cerere/s
- GET  https://webservicesp.anaf.ro/bilant?an=AAAA&cui=N
Răspunsurile se păstrează în `anaf_cache` (o singură cerere per CUI, reîmprospătare după N zile).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tro.config import get_settings
from tro.counties import county_code_from_name, county_name
from tro.etl.http import RateLimiter, make_client, request_with_retry
from tro.etl.runlog import RunLog
from tro.models import AnafCache, Company, CompanyAlias, CompanyFinancial, Contract
from tro.normalize import clean_str, is_natural_person, normalize_name, simplify, to_date

log = logging.getLogger(__name__)

ANAF_TVA_URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
ANAF_BILANT_URL = "https://webservicesp.anaf.ro/bilant"
BATCH = 100

_limiter: RateLimiter | None = None


def limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(get_settings().anaf_min_interval_s)
    return _limiter


# ------------------------------------------------------------------ parsare răspuns


def county_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("adresa_sediu_social", "adresa_domiciliu_fiscal"):
        adr = payload.get(key) or {}
        code = (adr.get("scod_JudetAuto") or adr.get("dcod_JudetAuto") or "").strip().upper()
        if code:
            return code
        name = adr.get("sdenumire_Judet") or adr.get("ddenumire_Judet")
        c = county_code_from_name(name)
        if c:
            return c
    return None


def locality_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    adr = payload.get("adresa_sediu_social") or {}
    loc = adr.get("sdenumire_Localitate") or (payload.get("adresa_domiciliu_fiscal") or {}).get("ddenumire_Localitate")
    return clean_str(loc, 120)


def general(payload: dict[str, Any] | None) -> dict[str, Any]:
    return (payload or {}).get("date_generale") or {}


def payload_is_natural_person(payload: dict[str, Any] | None) -> bool:
    g = general(payload)
    return is_natural_person(legal_form=g.get("forma_juridica")) or is_natural_person(
        legal_form=g.get("forma_organizare")
    )


def redact_natural_person(payload: dict[str, Any]) -> dict[str, Any]:
    """GDPR: pentru persoane fizice/PFA păstrăm doar județul, localitatea și datele fiscale."""
    g = dict(general(payload))
    for k in ("denumire", "adresa", "telefon", "fax", "codPostal", "iban"):
        g.pop(k, None)
    adr = payload.get("adresa_sediu_social") or {}
    keep_adr = {k: adr.get(k) for k in ("sdenumire_Judet", "scod_JudetAuto", "sdenumire_Localitate")}
    return {
        "date_generale": g,
        "adresa_sediu_social": keep_adr,
        "inregistrare_scop_Tva": {"scpTVA": (payload.get("inregistrare_scop_Tva") or {}).get("scpTVA")},
        "stare_inactiv": {"statusInactivi": (payload.get("stare_inactiv") or {}).get("statusInactivi")},
        "_redacted": True,
    }


# ------------------------------------------------------------------ cereri


def fetch_batch(client, cuis: list[str]) -> dict[str, dict[str, Any] | None]:
    today = dt.date.today().isoformat()
    body = [{"cui": int(c), "data": today} for c in cuis]
    r = request_with_retry(client, "POST", ANAF_TVA_URL, json=body, limiter=limiter())
    r.raise_for_status()
    data = r.json()
    out: dict[str, dict[str, Any] | None] = {c: None for c in cuis}
    for item in data.get("found", []) or []:
        cui = str((item.get("date_generale") or {}).get("cui", "")).strip()
        if cui:
            out[cui] = item
    return out


def ensure_cached(session: Session, cuis: Iterable[str], refresh_days: int = 60, run: RunLog | None = None) -> int:
    """Asigură că fiecare CUI are un răspuns ANAF în cache. Întoarce numărul de CUI-uri cerute."""
    wanted = sorted({c for c in cuis if c and c.isdigit() and len(c) <= 10})
    if not wanted:
        return 0
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=refresh_days)
    have: set[str] = set()
    for i in range(0, len(wanted), 5000):
        chunk = wanted[i : i + 5000]
        have.update(
            session.execute(
                select(AnafCache.cui).where(AnafCache.cui.in_(chunk), AnafCache.fetched_at >= cutoff)
            ).scalars()
        )
    missing = [c for c in wanted if c not in have]
    if not missing:
        return 0
    log.info("ANAF: interoghez %d CUI-uri (%d cereri)", len(missing), (len(missing) + BATCH - 1) // BATCH)
    with make_client() as client:
        for i in range(0, len(missing), BATCH):
            chunk = missing[i : i + BATCH]
            try:
                res = fetch_batch(client, chunk)
            except Exception as exc:  # noqa: BLE001
                if run:
                    run.error(f"anaf:{chunk[0]}..", f"Cerere ANAF eșuată: {exc}")
                else:
                    log.warning("Cerere ANAF eșuată: %s", exc)
                continue
            rows = [
                {
                    "cui": cui,
                    "found": payload is not None,
                    "payload": (
                        redact_natural_person(payload) if payload and payload_is_natural_person(payload) else payload
                    ),
                    "county_code": county_from_payload(payload),
                    "fetched_at": dt.datetime.now(dt.UTC),
                }
                for cui, payload in res.items()
            ]
            stmt = insert(AnafCache).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["cui"],
                set_={
                    "found": stmt.excluded.found,
                    "payload": stmt.excluded.payload,
                    "county_code": stmt.excluded.county_code,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            session.execute(stmt)
            session.commit()
            if (i // BATCH) % 20 == 0:
                log.info("ANAF: %d/%d", min(i + BATCH, len(missing)), len(missing))
    return len(missing)


def cached_payloads(session: Session, cuis: Iterable[str]) -> dict[str, AnafCache]:
    cuis = list(set(cuis))
    out: dict[str, AnafCache] = {}
    for i in range(0, len(cuis), 5000):
        for row in session.execute(select(AnafCache).where(AnafCache.cui.in_(cuis[i : i + 5000]))).scalars():
            out[row.cui] = row
    return out


# ------------------------------------------------------------------ îmbogățire firme


def apply_payload_to_company(company: Company, payload: dict[str, Any] | None) -> None:
    now = dt.datetime.now(dt.UTC)
    company.anaf_checked_at = now
    company.anaf_found = payload is not None
    if not payload:
        return
    g = general(payload)
    legal_form = clean_str(g.get("forma_juridica"), 120) or clean_str(g.get("forma_organizare"), 120)
    company.legal_form = legal_form
    company.registry_number = clean_str(g.get("nrRegCom"), 60)
    company.caen_code = clean_str(g.get("cod_CAEN"), 8)
    company.status = clean_str(g.get("stare_inregistrare"), 200)
    founded = to_date(g.get("data_inregistrare"))
    if founded and (company.founded_source in (None, "anaf")):
        company.founded_on = founded
        company.founded_source = "anaf"
    company.vat_payer = bool((payload.get("inregistrare_scop_Tva") or {}).get("scpTVA"))
    company.inactive = bool((payload.get("stare_inactiv") or {}).get("statusInactivi"))
    cc = county_from_payload(payload)
    company.county_code = cc
    company.county_name = county_name(cc)
    company.locality = locality_from_payload(payload)
    forma_org = clean_str(g.get("forma_organizare")) or ""
    if is_natural_person(cui=company.cui, legal_form=legal_form) or is_natural_person(legal_form=forma_org):
        company.is_natural_person = True
    if company.is_natural_person:
        company.name = "Persoană fizică autorizată"
        company.name_normalized = "PERSOANA FIZICA AUTORIZATA"
    elif g.get("denumire"):
        # denumirea oficială ANAF; variantele din SEAP rămân ca alias-uri
        official = clean_str(g.get("denumire"), 400)
        if official:
            company.name = official
            company.name_normalized = normalize_name(official)


def enrich_companies(session: Session, limit: int | None = None, refresh_days: int = 60) -> int:
    run = RunLog(session, "anaf_companies", {"limit": limit})
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=refresh_days)
    q = (
        select(Company)
        .where(Company.is_synthetic.is_(False), Company.cui.regexp_match(r"^\d{1,10}$"))
        .where((Company.anaf_checked_at.is_(None)) | (Company.anaf_checked_at < cutoff))
        .order_by(Company.id)
    )
    if limit:
        q = q.limit(limit)
    companies = list(session.execute(q).scalars())
    run.run.rows_read = len(companies)
    ensure_cached(session, [c.cui for c in companies], refresh_days=refresh_days, run=run)
    cache = cached_payloads(session, [c.cui for c in companies])
    for c in companies:
        try:
            entry = cache.get(c.cui)
            apply_payload_to_company(c, entry.payload if entry else None)
            if c.is_natural_person:
                session.query(CompanyAlias).filter(CompanyAlias.company_id == c.id).delete()
            run.run.rows_upserted += 1
        except Exception as exc:  # noqa: BLE001
            run.error(c.cui, str(exc))
    session.commit()
    run.finish()
    return len(companies)


# ------------------------------------------------------------------ bilanțuri


def parse_bilant(data: dict[str, Any]) -> dict[str, Any] | None:
    """Indicatorii se identifică după DENUMIRE (formularele diferă între tipuri de entități:
    același cod I20 poate însemna altceva la bănci, ONG-uri sau instituții)."""
    by_name: dict[str, Any] = {}
    for it in data.get("i") or []:
        name = simplify(it.get("val_den_indicator"))
        if name:
            by_name[name] = it.get("val_indicator")
    if not by_name:
        return None

    def find(*prefixes: str) -> Any:
        for pref in prefixes:
            for k, v in by_name.items():
                if k.startswith(pref):
                    return v
        return None

    def dec(v: Any) -> Decimal | None:
        return Decimal(str(v)) if v is not None else None

    turnover = dec(find("cifra de afaceri neta", "cifra de afaceri"))
    profit = dec(find("profit net"))
    loss = dec(find("pierdere neta"))
    net = None
    if profit is not None or loss is not None:
        net = (profit or Decimal(0)) - (loss or Decimal(0))
    emp = find("numar mediu de salariati", "numarul mediu de salariati")
    employees = int(emp) if emp is not None and 0 <= int(emp) < 1_000_000 else None
    if turnover is None and net is None and employees is None:
        return None
    return {"turnover_ron": turnover, "net_profit_ron": net, "employees": employees}


def import_bilant(session: Session, years: list[int] | None = None) -> int:
    """Bilanțuri pentru firmele cu încasări publice semnificative (pragul din config)."""
    s = get_settings()
    last_closed = dt.date.today().year - 1
    years = years or [y for y in (last_closed - 1, last_closed) if y >= 2015]
    run = RunLog(session, "anaf_bilant", {"years": years})
    totals = session.execute(
        select(Contract.company_id, func.sum(Contract.value_ron).label("total"))
        .join(Company, Company.id == Contract.company_id)
        .where(
            Company.is_natural_person.is_(False),
            Company.is_synthetic.is_(False),
            Company.cui.regexp_match(r"^\d{1,10}$"),
        )
        .group_by(Contract.company_id)
        .having(func.sum(Contract.value_ron) >= s.bilant_min_public_ron)
        .order_by(text("total DESC"))
        .limit(s.bilant_max_companies)
    ).all()
    company_ids = [r.company_id for r in totals]
    existing = {
        (r.company_id, r.year)
        for r in session.execute(
            select(CompanyFinancial.company_id, CompanyFinancial.year).where(
                CompanyFinancial.company_id.in_(company_ids or [-1])
            )
        )
    }
    companies = {c.id: c for c in session.execute(select(Company).where(Company.id.in_(company_ids or [-1]))).scalars()}
    with make_client() as client:
        for cid in company_ids:
            comp = companies[cid]
            for y in years:
                if (cid, y) in existing:
                    continue
                run.run.rows_read += 1
                try:
                    r = request_with_retry(
                        client, "GET", ANAF_BILANT_URL, params={"an": y, "cui": comp.cui}, limiter=limiter()
                    )
                    r.raise_for_status()
                    parsed = parse_bilant(r.json())
                except Exception as exc:  # noqa: BLE001
                    run.error(f"{comp.cui}/{y}", f"Bilanț indisponibil: {exc}")
                    continue
                vals = parsed or {"turnover_ron": None, "net_profit_ron": None, "employees": None}
                stmt = insert(CompanyFinancial).values(company_id=cid, year=y, source="anaf_bilant", **vals)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_fin_company_year",
                    set_={k: getattr(stmt.excluded, k) for k in vals},
                )
                try:
                    with session.begin_nested():
                        session.execute(stmt)
                    run.run.rows_upserted += 1
                except Exception as exc:  # noqa: BLE001
                    run.error(f"{comp.cui}/{y}", f"Bilanț nesalvat: {str(exc).splitlines()[0]}", vals)
            session.commit()
    run.finish()
    return run.run.rows_upserted
