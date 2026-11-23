"""Import SEAP: descoperire (CKAN) → descărcare → parsare → filtrare pe județ (via ANAF) → upsert.

Idempotent: fiecare înregistrare are un `source_id` stabil derivat din identificatorii SEAP
(număr DA/DAN, număr anunț + lot + contract + furnizor) și se scrie cu INSERT … ON CONFLICT.
Incremental: fișierele deja importate cu succes (aceeași resursă CKAN, aceeași dată de
modificare) sunt sărite, cu excepția `--force`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tro.authority_types import classify_authority, locality_display
from tro.config import get_settings
from tro.counties import county_name
from tro.etl.http import download, make_client
from tro.etl.runlog import RunLog
from tro.etl.sources import anaf
from tro.etl.sources.bnr import RateLookup
from tro.etl.sources.ckan import SeapResource, list_seap_resources
from tro.etl.sources.seap_parse import FIELD_MAP, ParsedFile, extract, iter_report, row_hash
from tro.etl.upsert import upsert
from tro.models import (
    Authority,
    Company,
    CompanyAlias,
    Contract,
    ContractAmendment,
    Procedure,
    SourceRecord,
)
from tro.normalize import (
    anonymous_key,
    clean_str,
    cpv_code,
    fallback_company_key,
    is_natural_person,
    looks_like_cnp,
    normalize_cui,
    normalize_name,
    to_bool_ro,
    to_date,
    to_decimal,
)

log = logging.getLogger(__name__)

KIND_ORDER = ["initiere", "contracte", "atribuire_fara", "ad", "dan", "modificari"]
PROCEDURE_LABEL = {
    "ad": "Achiziție directă",
    "dan": "Achiziție directă (notificare)",
}


def _h(*parts: Any) -> str:
    return hashlib.sha256("\x1f".join("" if p is None else str(p) for p in parts).encode()).hexdigest()


# ------------------------------------------------------------------ orchestrare


def already_imported(session: Session, res: SeapResource) -> bool:
    row = session.execute(
        text(
            "SELECT 1 FROM import_runs WHERE source LIKE 'seap_%' AND status = 'ok' "
            "AND params->>'resource_id' = :rid AND coalesce(params->>'last_modified','') = :lm "
            "AND coalesce(params->>'counties','') = :ct LIMIT 1"
        ),
        {"rid": res.resource_id, "lm": res.last_modified or "", "ct": get_settings().target_counties},
    ).first()
    return row is not None


def import_seap(
    session: Session,
    years: list[int],
    quarters: list[int],
    kinds: list[str],
    *,
    force: bool = False,
) -> None:
    s = get_settings()
    data_dir = Path(s.data_dir) / "seap"
    with make_client() as client:
        for year in years:
            resources = [
                r for r in list_seap_resources(year) if r.kind in kinds and (r.quarter in quarters or r.quarter is None)
            ]
            resources.sort(key=lambda r: (r.quarter or 0, KIND_ORDER.index(r.kind)))
            log.info("SEAP %d: %d resurse de importat", year, len(resources))
            for res in resources:
                if not force and already_imported(session, res):
                    log.info("Sar peste %s (deja importat)", res.name)
                    continue
                try:
                    path = download(res.url, data_dir / res.filename, client=client)
                except Exception as exc:  # noqa: BLE001
                    run = RunLog(session, f"seap_{res.kind}", _params(res))
                    run.finish("failed", f"Descărcare eșuată: {exc}")
                    continue
                import_file(session, path, res)
    link_amendments(session)
    fill_contract_titles(session)
    mark_duplicate_values(session)


def _params(res: SeapResource | None, path: Path | None = None) -> dict[str, Any]:
    p: dict[str, Any] = {"counties": get_settings().target_counties}
    if res:
        p.update(
            resource_id=res.resource_id,
            name=res.name,
            url=res.url,
            year=res.year,
            quarter=res.quarter,
            last_modified=res.last_modified or "",
        )
    if path:
        p["file"] = path.name
    return p


def import_file(session: Session, path: Path, res: SeapResource | None = None) -> RunLog:
    """Importă un singur raport SEAP (oricare tip). Poate fi folosit și pe fișiere locale."""
    pf, rows = iter_report(path)
    kind = pf.kind or "unknown"
    run = RunLog(session, f"seap_{kind}", _params(res, path))
    if pf.kind not in FIELD_MAP:
        run.finish("skipped", f"Tip de raport nerecunoscut/neimportat: {pf.kind} ({path.name})")
        return run
    if res and res.kind != pf.kind:
        log.warning("Resursa '%s' e etichetată %s dar antetul indică %s", res.name, res.kind, pf.kind)

    records: list[tuple[int, list[Any], dict[str, Any], str]] = []
    for line, row in rows:
        run.run.rows_read += 1
        d = extract(pf, row)
        cui = normalize_cui(d.get("authority_cui"))
        if not cui:
            run.error(f"{path.name}:{line}", "CUI autoritate lipsă/invalid", d.get("authority_cui"))
            continue
        records.append((line, row, d, cui))
    log.info("%s: %d rânduri citite (%s)", path.name, len(records), pf.kind)

    # 1) rezolvarea județului autorităților prin ANAF (cache)
    s = get_settings()
    auth_cuis = {r[3] for r in records}
    anaf.ensure_cached(session, auth_cuis, run=run)
    cache = anaf.cached_payloads(session, auth_cuis)
    if s.all_counties:
        keep = records
    else:
        targets = set(s.target_county_list)
        keep = [r for r in records if (cache.get(r[3]) and cache[r[3]].county_code in targets)]
    run.run.rows_skipped = len(records) - len(keep)
    log.info("%s: %d rânduri în județele țintă (%s)", path.name, len(keep), s.target_counties)

    if run.run.rows_read > 0 and not records:
        run.finish("failed", f"Niciun rând valid în {path.name}: antet necunoscut? {pf.headers[:20]}")
        return run

    loader = _Loader(session, run, pf, res, path, cache)
    for i in range(0, len(keep), 2000):
        loader.load(keep[i : i + 2000])
        session.commit()
    run.finish("ok")
    return run


# ------------------------------------------------------------------ încărcare


class _Loader:
    def __init__(
        self,
        session: Session,
        run: RunLog,
        pf: ParsedFile,
        res: SeapResource | None,
        path: Path,
        anaf_cache: dict[str, Any],
    ) -> None:
        self.session = session
        self.run = run
        self.kind = pf.kind
        self.res = res
        self.path = path
        self.anaf_cache = anaf_cache
        self.rates = RateLookup(session)
        self.source_url = res.url if res else None
        self.dataset = f"data.gov.ro/dataset/{res.dataset} — {res.name}" if res else path.name
        self.now = dt.datetime.now(dt.UTC)

    # ---------------- autorități
    def authorities(self, batch: list[tuple[int, list[Any], dict[str, Any], str]]) -> dict[str, int]:
        rows: dict[str, dict[str, Any]] = {}
        for _, _, d, cui in batch:
            if cui in rows:
                continue
            entry = self.anaf_cache.get(cui)
            payload = entry.payload if entry else None
            name = clean_str(d.get("authority_name"), 400) or clean_str(anaf.general(payload).get("denumire"), 400)
            name = name or f"Autoritate CUI {cui}"
            cc = entry.county_code if entry else None
            rows[cui] = {
                "cui": cui,
                "name": name,
                "name_normalized": normalize_name(name),
                "county_code": cc,
                "county_name": county_name(cc),
                "locality": locality_display(anaf.locality_from_payload(payload)),
                "address": clean_str(anaf.general(payload).get("adresa")),
                "authority_type": classify_authority(name),
                "is_synthetic": False,
            }
        res = upsert(
            self.session,
            Authority,
            list(rows.values()),
            conflict=["cui"],
            update=["county_code", "county_name", "locality", "address"],
            coalesce=True,
            returning=["id", "cui"],
            run=self.run,
        )
        return {r.cui: r.id for r in res}

    # ---------------- firme
    def supplier_key(self, d: dict[str, Any]) -> tuple[str, str, bool] | None:
        name = clean_str(d.get("supplier_name"), 400)
        raw_cui = d.get("supplier_cui")
        cui = normalize_cui(raw_cui)
        if not name and not cui:
            return None
        pf = is_natural_person(name, cui)
        if pf:
            key = cui if (cui and not looks_like_cnp(cui)) else anonymous_key(name or "", None)
            return key, "Persoană fizică autorizată", True
        if cui:
            return cui, name or f"CUI {cui}", False
        assert name is not None
        return fallback_company_key(name), name, False

    def companies(self, batch) -> dict[str, int]:
        rows: dict[str, dict[str, Any]] = {}
        aliases: list[tuple[str, str]] = []
        for _, _, d, _ in batch:
            k = self.supplier_key(d)
            if not k:
                continue
            key, name, pf = k
            if key not in rows:
                rows[key] = {
                    "cui": key,
                    "name": name,
                    "name_normalized": normalize_name(name),
                    "is_natural_person": pf,
                    "is_synthetic": False,
                }
            if not pf:
                aliases.append((key, name))
        upsert(self.session, Company, list(rows.values()), conflict=["cui"], update=None, run=self.run)
        ids = {
            r.cui: r.id
            for r in self.session.execute(select(Company.id, Company.cui).where(Company.cui.in_(list(rows))))
        }
        alias_rows = [
            {
                "company_id": ids[k],
                "alias_normalized": normalize_name(n),
                "alias_raw": n,
                "source": "seap",
            }
            for k, n in aliases
            if k in ids and normalize_name(n)
        ]
        upsert(self.session, CompanyAlias, alias_rows, conflict=["company_id", "alias_normalized"], run=self.run)
        return ids

    # ---------------- proceduri
    def procedures(self, batch, auth_ids: dict[str, int]) -> dict[str, int]:
        rows: list[dict[str, Any]] = []
        for line, _, d, cui in batch:
            try:
                p = self.procedure_row(d, auth_ids[cui])
            except Exception as exc:  # noqa: BLE001
                self.run.error(f"{self.path.name}:{line}", f"procedură: {exc}")
                continue
            if p:
                rows.append(p)
        cols = [
            "authority_id",
            "notice_number",
            "title",
            "procedure_type",
            "contract_type",
            "cpv_code",
            "estimated_value_ron",
            "award_criteria",
            "legislation",
            "status",
            "publication_date",
        ]
        res = upsert(
            self.session,
            Procedure,
            rows,
            conflict=["source_id"],
            update=cols,
            coalesce=True,
            returning=["id", "source_id"],
            run=self.run,
        )
        return {r.source_id: r.id for r in res}

    def procedure_row(self, d: dict[str, Any], authority_id: int) -> dict[str, Any] | None:
        if self.kind == "initiere":
            notice = clean_str(d.get("initiation_notice"), 60)
            if not notice:
                return None
            pub = to_date(d.get("publication_date"))
            est = to_decimal(d.get("estimated_value"))
            cur = (clean_str(d.get("currency")) or "RON").upper()
            est_ron, _ = self.rates.to_ron(est, cur, pub)
            return {
                "source_id": f"p:{notice}",
                "authority_id": authority_id,
                "notice_number": notice,
                "title": clean_str(d.get("title")),
                "procedure_type": clean_str(d.get("procedure_type"), 120),
                "contract_type": clean_str(d.get("contract_type"), 40),
                "cpv_code": cpv_code(d.get("cpv_code")),
                "estimated_value_ron": est_ron,
                "award_criteria": None,
                "legislation": None,
                "status": clean_str(d.get("status"), 60),
                "publication_date": pub,
                "is_synthetic": False,
            }
        if self.kind in ("contracte", "atribuire_fara"):
            notice = clean_str(d.get("initiation_notice"), 60) or clean_str(d.get("award_notice"), 60)
            if not notice:
                return None
            return {
                "source_id": f"p:{notice}",
                "authority_id": authority_id,
                "notice_number": notice,
                "title": None,
                "procedure_type": clean_str(d.get("procedure_type"), 120),
                "contract_type": clean_str(d.get("contract_type"), 40),
                "cpv_code": cpv_code(d.get("cpv_code")),
                "estimated_value_ron": None,
                "award_criteria": clean_str(d.get("award_criteria"), 120),
                "legislation": clean_str(d.get("legislation"), 80),
                "status": None,
                "publication_date": to_date(d.get("initiation_date")) or to_date(d.get("publication_date")),
                "is_synthetic": False,
            }
        return None

    # ---------------- contracte
    def contract_row(
        self,
        d: dict[str, Any],
        authority_id: int,
        county: str | None,
        company_id: int | None,
        proc_ids: dict[str, int],
        supplier_cui: str | None,
    ) -> dict[str, Any] | None:
        kind = self.kind
        value = to_decimal(d.get("value"))
        pub = to_date(d.get("publication_date"))
        common: dict[str, Any] = {
            "source": kind,
            "authority_id": authority_id,
            "company_id": company_id,
            "county_code": county,
            "cpv_code": cpv_code(d.get("cpv_code")),
            "cpv_name": clean_str(d.get("cpv_name"), 300),
            "contract_type": clean_str(d.get("contract_type"), 40),
            "value_ron": value,
            "original_value": value,
            "currency": "RON",
            "exchange_rate": Decimal(1),
            "publication_date": pub,
            "source_url": self.source_url,
            "source_dataset": self.dataset[:300],
            "last_seen_at": self.now,
            "is_synthetic": False,
            "framework": clean_str(d.get("framework"), 80),
            "eu_funded": to_bool_ro(d.get("eu_funded")),
            "eu_program": clean_str(d.get("eu_program"), 300),
            "lot_number": None,
            "contract_number": None,
            "procedure_id": None,
            "duration_days": None,
        }
        if kind in ("ad", "dan"):
            number = clean_str(d.get("number"), 60)
            if not number:
                raise ValueError("număr achiziție directă lipsă")
            cdate = to_date(d.get("finalized_date")) or pub
            common.update(
                source_id=f"{kind}:{number}",
                notice_number=number,
                title=clean_str(d.get("title")),
                procedure_type=PROCEDURE_LABEL[kind],
                contract_date=cdate,
                year=cdate.year if cdate else None,
            )
            return common
        if kind in ("contracte", "atribuire_fara"):
            award = clean_str(d.get("award_notice"), 60)
            if not award:
                raise ValueError("număr anunț de atribuire lipsă")
            lot = clean_str(d.get("lot"), 20)
            cnum = clean_str(d.get("contract_number"), 160)
            cdate = to_date(d.get("contract_date")) or pub
            notice_for_proc = clean_str(d.get("initiation_notice"), 60) or award
            prefix = "c" if kind == "contracte" else "af"
            common.update(
                source_id=f"{prefix}:{award}:{_h(lot, cnum, supplier_cui, d.get('supplier_name'))[:24]}",
                notice_number=award,
                title=clean_str(d.get("title")),
                procedure_type=clean_str(d.get("procedure_type"), 120),
                contract_date=cdate,
                year=cdate.year if cdate else None,
                lot_number=lot,
                contract_number=cnum,
                procedure_id=proc_ids.get(f"p:{notice_for_proc}"),
            )
            return common
        return None

    def amendment_row(self, d: dict[str, Any], authority_id: int) -> dict[str, Any]:
        pub = to_date(d.get("publication_date"))
        cdate = to_date(d.get("contract_date"))
        before = to_decimal(d.get("value_before"))
        after = to_decimal(d.get("value_after"))
        cur_b = (clean_str(d.get("currency_before")) or "RON").upper()[:3]
        cur_a = (clean_str(d.get("currency_after")) or cur_b).upper()[:3]
        day = cdate or pub
        before_ron, _ = self.rates.to_ron(before, cur_b, day)
        after_ron, _ = self.rates.to_ron(after, cur_a, day)
        delta = (after_ron - before_ron) if (after_ron is not None and before_ron is not None) else None
        pct = float(delta / before_ron * 100) if (delta is not None and before_ron) else None
        notice = clean_str(d.get("award_notice"), 60)
        cnum = clean_str(d.get("contract_number"), 160)
        desc = clean_str(d.get("description"))
        return {
            "source_id": "m:" + _h(authority_id, notice, cnum, pub, before, after, (desc or "")[:200])[:40],
            "authority_id": authority_id,
            "notice_number": notice,
            "contract_number": cnum,
            "contract_date": cdate,
            "publication_date": pub,
            "description": desc,
            "value_before_ron": before_ron,
            "value_after_ron": after_ron,
            "delta_ron": delta,
            "delta_pct": round(pct, 2) if pct is not None else None,
            "currency": cur_a if cur_a == cur_b else "RON",
            "source_url": self.source_url,
            "is_synthetic": False,
        }

    # ---------------- lot
    def load(self, batch) -> None:
        auth_ids = self.authorities(batch)
        provenance: list[dict[str, Any]] = []

        if self.kind == "initiere":
            proc = self.procedures(batch, auth_ids)
            self.run.run.rows_upserted += len(proc)
            for _line, row, d, _ in batch:
                n = clean_str(d.get("initiation_notice"), 60)
                if n and f"p:{n}" in proc:
                    provenance.append(self._prov("procedure", f"p:{n}", proc[f"p:{n}"], row))
            self._provenance(provenance)
            return

        if self.kind == "modificari":
            rows = []
            for line, row, d, cui in batch:
                try:
                    r = self.amendment_row(d, auth_ids[cui])
                    rows.append(r)
                    provenance.append(self._prov("amendment", r["source_id"], None, row))
                except Exception as exc:  # noqa: BLE001
                    self.run.error(f"{self.path.name}:{line}", f"modificare: {exc}", d)
            cols = [c for c in rows[0] if c != "source_id"] if rows else []
            res = upsert(
                self.session,
                ContractAmendment,
                rows,
                conflict=["source_id"],
                update=cols,
                returning=["id", "source_id"],
                run=self.run,
            )
            self.run.run.rows_upserted += len(res)
            ids = {r.source_id: r.id for r in res}
            for p in provenance:
                p["entity_id"] = ids.get(p["source_key"])
            self._provenance(provenance)
            return

        comp_ids = self.companies(batch)
        proc_ids = self.procedures(batch, auth_ids) if self.kind in ("contracte", "atribuire_fara") else {}
        rows = []
        for line, row, d, cui in batch:
            try:
                k = self.supplier_key(d)
                company_id = comp_ids.get(k[0]) if k else None
                entry = self.anaf_cache.get(cui)
                rec = self.contract_row(
                    d,
                    auth_ids[cui],
                    entry.county_code if entry else None,
                    company_id,
                    proc_ids,
                    normalize_cui(d.get("supplier_cui")),
                )
                if rec:
                    rows.append(rec)
                    provenance.append(self._prov("contract", rec["source_id"], None, row))
            except Exception as exc:  # noqa: BLE001
                self.run.error(f"{self.path.name}:{line}", f"contract: {exc}", d)
        cols = [c for c in rows[0] if c not in ("source_id",)] if rows else []
        res = upsert(
            self.session,
            Contract,
            rows,
            conflict=["source_id"],
            update=cols,
            returning=["id", "source_id"],
            run=self.run,
        )
        self.run.run.rows_upserted += len(res)
        ids = {r.source_id: r.id for r in res}
        for p in provenance:
            p["entity_id"] = ids.get(p["source_key"])
        self._provenance(provenance)

    def _prov(self, entity_type: str, key: str, entity_id: int | None, row: list[Any]) -> dict[str, Any]:
        return {
            "source": f"seap_{self.kind}",
            "source_key": key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_url": self.source_url,
            "content_hash": row_hash(row),
            "imported_at": self.now,
            "first_seen_at": self.now,
            "run_id": self.run.id,
        }

    def _provenance(self, rows: list[dict[str, Any]]) -> None:
        upsert(
            self.session,
            SourceRecord,
            rows,
            conflict=["source", "source_key"],
            update=["entity_id", "source_url", "content_hash", "imported_at", "run_id"],
            run=self.run,
        )


# ------------------------------------------------------------------ post-procesare


def link_amendments(session: Session) -> int:
    """Leagă actele adiționale de contracte (același anunț de atribuire + aceeași autoritate)."""
    res = session.execute(
        text(
            """
            UPDATE contract_amendments a SET contract_id = (
                SELECT c.id FROM contracts c
                WHERE c.authority_id = a.authority_id AND c.notice_number = a.notice_number
                ORDER BY (c.contract_number = a.contract_number) DESC NULLS LAST, c.id
                LIMIT 1
            )
            WHERE a.contract_id IS NULL AND a.notice_number IS NOT NULL
            """
        )
    )
    session.commit()
    return getattr(res, "rowcount", 0) or 0


def mark_duplicate_values(session: Session) -> int:
    """Același contract pe mai multe rânduri SEAP (membrii unei asocieri, sau loturi cu valoarea totală
    repetată): păstrăm primul rând ca principal, celelalte indică spre el și nu intră în totaluri."""
    session.execute(
        text(
            "UPDATE contracts SET duplicate_of_id = NULL, repeat_same_company = false "
            "WHERE duplicate_of_id IS NOT NULL OR repeat_same_company"
        )
    )
    # 1) acord-cadru + contracte subsecvente sub același anunț: numărăm subsecventele (cheltuiala efectivă),
    #    nu valoarea maximă a acordului-cadru; acordurile fără subsecvente raportate rămân în totaluri.
    session.execute(
        text(
            """
            UPDATE contracts f SET duplicate_of_id = s.first_sub, repeat_same_company = true
            FROM (
              SELECT authority_id, notice_number, min(id) AS first_sub FROM contracts
              WHERE lower(framework) LIKE '%subsecvent%' AND notice_number IS NOT NULL
              GROUP BY authority_id, notice_number
            ) s
            WHERE lower(f.framework) = 'cu acord cadru'
              AND f.authority_id = s.authority_id AND f.notice_number = s.notice_number
            """
        )
    )
    # 2) același contract pe mai multe rânduri (asociere / loturi cu valoarea totală repetată)
    res = session.execute(
        text(
            """
            UPDATE contracts c SET duplicate_of_id = d.first_id
            FROM (
              SELECT id, first_value(id) OVER (
                PARTITION BY authority_id, notice_number, coalesce(contract_number, ''), value_ron ORDER BY id
              ) AS first_id
              FROM contracts
              WHERE source IN ('contracte', 'atribuire_fara') AND notice_number IS NOT NULL
                AND value_ron IS NOT NULL AND duplicate_of_id IS NULL
            ) d
            WHERE c.id = d.id AND d.first_id <> d.id
            """
        )
    )
    session.execute(
        text(
            """
            UPDATE contracts c SET repeat_same_company = true
            FROM contracts m
            WHERE c.duplicate_of_id = m.id AND c.company_id IS NOT DISTINCT FROM m.company_id
            """
        )
    )
    session.commit()
    return getattr(res, "rowcount", 0) or 0


def fill_contract_titles(session: Session) -> int:
    res = session.execute(
        text(
            """
            UPDATE contracts c SET title = p.title
            FROM procedures p
            WHERE c.procedure_id = p.id AND c.title IS NULL AND p.title IS NOT NULL
            """
        )
    )
    session.commit()
    return getattr(res, "rowcount", 0) or 0
