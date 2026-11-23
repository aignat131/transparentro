"""Calculul semnalelor de verificat (Faza 2).

Principii:
- formulare NEUTRĂ: „semnal de verificat”, niciodată acuzație;
- fiecare semnal are explicație în limbaj simplu, detaliile numerice și link la sursa oficială;
- pragurile sunt în `risk_thresholds.yaml` (sau fișierul din RISK_THRESHOLDS_PATH);
- recalculare completă și idempotentă (amprentă unică per semnal).
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from tro.config import get_settings
from tro.etl.runlog import RunLog
from tro.etl.upsert import upsert
from tro.models import RiskSignal

log = logging.getLogger(__name__)

SIGNAL_TYPES: dict[str, str] = {
    "new_company": "Firmă nou-înființată la primul contract",
    "single_bidder": "Procedură cu un singur ofertant",
    "fragmentation": "Achiziții directe repetate (posibilă fragmentare)",
    "amendment_increase": "Act adițional care crește valoarea cu peste 20%",
    "public_revenue_share": "Venituri majoritar din contracte publice",
    "concentration": "Furnizor dominant la o instituție",
}


def load_thresholds(path: str | None = None) -> dict[str, Any]:
    p = Path(path or get_settings().risk_thresholds_path or Path(__file__).with_name("risk_thresholds.yaml"))
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def lei(v: Any) -> str:
    if v is None:
        return "—"
    n = float(v)
    s = f"{n:,.0f}".replace(",", ".")
    return f"{s} lei"


def direct_threshold(cfg: dict[str, Any], day: dt.date | None, contract_type: str | None) -> float:
    rows = sorted(cfg["direct_award_thresholds"], key=lambda r: r["valid_from"], reverse=True)
    day = day or dt.date.today()
    chosen = rows[-1]
    for r in rows:
        if day >= dt.date.fromisoformat(str(r["valid_from"])):
            chosen = r
            break
    works = (contract_type or "").lower().startswith("lucr")
    return float(chosen["works_ron"] if works else chosen["goods_services_ron"])


def value_factor(v: float | None, cap: float = 15.0) -> float:
    """0..cap în funcție de ordinul de mărime al valorii (1.000 lei → ~0, 10 mil. → cap)."""
    if not v or v <= 0:
        return 0.0
    return max(0.0, min(cap, (math.log10(v) - 3) / 4 * cap))


def anaf_url(cui: str | None) -> str | None:
    if cui and cui.isdigit():
        return f"https://mfinante.gov.ro/apps/infocodfiscal.html?cod={cui}"
    return None


@dataclass
class Signal:
    signal_type: str
    score: float
    target_type: str
    title: str
    explanation: str
    fingerprint: str
    company_id: int | None = None
    authority_id: int | None = None
    contract_id: int | None = None
    county_code: str | None = None
    year: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    is_synthetic: bool = False

    def row(self, now: dt.datetime) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "signal_type": self.signal_type,
            "score": int(max(1, min(100, round(self.score)))),
            "target_type": self.target_type,
            "company_id": self.company_id,
            "authority_id": self.authority_id,
            "contract_id": self.contract_id,
            "county_code": self.county_code,
            "year": self.year,
            "title": self.title[:300],
            "explanation": self.explanation,
            "details": _jsonable(self.details),
            "source_url": self.source_url,
            "computed_at": now,
            "is_synthetic": self.is_synthetic,
        }


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, dt.date | dt.datetime | pd.Timestamp):
            out[k] = v.isoformat()[:10]
        elif hasattr(v, "item"):
            out[k] = v.item()
        else:
            out[k] = v
    return out


def _df(session: Session, sql: str, **params: Any) -> pd.DataFrame:
    res = session.execute(text(sql), params)
    return pd.DataFrame(res.fetchall(), columns=list(res.keys()))


# ------------------------------------------------------------------ 1. firmă nouă


def sig_new_company(session: Session, cfg: dict[str, Any]) -> list[Signal]:
    c = cfg["new_company"]
    df = _df(
        session,
        """
        WITH firsts AS (
          SELECT DISTINCT ON (ct.company_id) ct.company_id, ct.id AS contract_id, ct.contract_date,
                 ct.value_ron, ct.authority_id, ct.county_code, ct.source_url, ct.is_synthetic
          FROM contracts ct WHERE ct.company_id IS NOT NULL AND ct.contract_date IS NOT NULL
          ORDER BY ct.company_id, ct.contract_date, ct.id
        ), coverage AS (SELECT min(coalesce(publication_date, contract_date)) AS start FROM contracts)
        SELECT f.*, co.cui, co.name, co.is_natural_person, co.founded_on, co.founded_source,
               a.name AS authority_name, (SELECT start FROM coverage) AS coverage_start
        FROM firsts f JOIN companies co ON co.id = f.company_id
        JOIN authorities a ON a.id = f.authority_id
        WHERE co.founded_on IS NOT NULL
          AND f.contract_date >= co.founded_on
          AND co.founded_on >= (SELECT start FROM coverage)
          AND (f.contract_date - co.founded_on) <= :maxd
          AND coalesce(f.value_ron, 0) >= :minv
        """,
        maxd=int(c["max_days_since_founding"]),
        minv=float(c.get("min_contract_value_ron", 0)),
    )
    out: list[Signal] = []
    maxd = int(c["max_days_since_founding"])
    for r in df.itertuples():
        days = (r.contract_date - r.founded_on).days
        months = days / 30.4
        val = float(r.value_ron or 0)
        name = "O persoană fizică autorizată" if r.is_natural_person else f"Firma {r.name}"
        score = 35 + (maxd - days) / maxd * 35 + value_factor(val, 25)
        out.append(
            Signal(
                signal_type="new_company",
                score=score,
                target_type="company",
                company_id=int(r.company_id),
                authority_id=int(r.authority_id),
                contract_id=int(r.contract_id),
                county_code=r.county_code,
                year=r.contract_date.year,
                title=f"Primul contract public la {days} zile după înființare",
                explanation=(
                    f"{name} a fost înregistrată pe {r.founded_on:%d.%m.%Y} și a primit primul contract "
                    f"public cunoscut pe {r.contract_date:%d.%m.%Y} ({r.authority_name}), la aproximativ "
                    f"{months:.1f} luni după înființare, în valoare de {lei(val)}. Firmele noi pot fi perfect "
                    f"legitime; semnalul arată doar că merită verificată experiența firmei la momentul "
                    f"atribuirii."
                ),
                fingerprint=f"new_company:{r.company_id}",
                details={
                    "founded_on": r.founded_on,
                    "founded_source": r.founded_source,
                    "first_contract_date": r.contract_date,
                    "days": days,
                    "value_ron": val,
                    "threshold_days": maxd,
                },
                source_url=r.source_url or anaf_url(r.cui),
                is_synthetic=bool(r.is_synthetic),
            )
        )
    return out


# ------------------------------------------------------------------ 2. un singur ofertant


def sig_single_bidder(session: Session, cfg: dict[str, Any]) -> list[Signal]:
    mx = int(cfg["single_bidder"]["max_offers"])
    df = _df(
        session,
        """
        SELECT ct.id AS contract_id, ct.company_id, ct.authority_id, ct.county_code, ct.year, ct.value_ron,
               ct.source_url, ct.is_synthetic, ct.notice_number, p.number_of_offers, p.procedure_type,
               a.name AS authority_name
        FROM contracts ct JOIN procedures p ON p.id = ct.procedure_id
        JOIN authorities a ON a.id = ct.authority_id
        WHERE p.number_of_offers IS NOT NULL AND p.number_of_offers <= :mx AND p.number_of_offers >= 1
        """,
        mx=mx,
    )
    out = []
    for r in df.itertuples():
        val = float(r.value_ron or 0)
        out.append(
            Signal(
                signal_type="single_bidder",
                score=45 + value_factor(val, 35),
                target_type="contract",
                contract_id=int(r.contract_id),
                company_id=int(r.company_id) if pd.notna(r.company_id) else None,
                authority_id=int(r.authority_id),
                county_code=r.county_code,
                year=int(r.year) if pd.notna(r.year) else None,
                title="Procedură competitivă cu o singură ofertă",
                explanation=(
                    f"La procedura „{r.procedure_type or 'necunoscută'}” (anunț {r.notice_number}) organizată de "
                    f"{r.authority_name} s-a depus o singură ofertă, iar contractul a fost atribuit pentru "
                    f"{lei(val)}. Lipsa concurenței poate avea explicații obiective (piață mică, cerințe "
                    f"specifice), dar merită verificat dacă cerințele din documentație au fost restrictive."
                ),
                fingerprint=f"single_bidder:{r.contract_id}",
                details={"number_of_offers": int(r.number_of_offers), "value_ron": val},
                source_url=r.source_url,
                is_synthetic=bool(r.is_synthetic),
            )
        )
    return out


# ------------------------------------------------------------------ 3. fragmentare


def sig_fragmentation(session: Session, cfg: dict[str, Any]) -> list[Signal]:
    c = cfg["fragmentation"]
    n = int(c["cpv_prefix_digits"])
    df = _df(
        session,
        """
        SELECT ct.id, ct.authority_id, ct.company_id, ct.year, ct.value_ron, ct.contract_date,
               ct.contract_type, left(ct.cpv_code, :n) AS cpv_group, ct.cpv_name, ct.county_code,
               ct.source_url, ct.is_synthetic, a.name AS authority_name, co.name AS company_name,
               co.is_natural_person
        FROM contracts ct JOIN authorities a ON a.id = ct.authority_id
        JOIN companies co ON co.id = ct.company_id
        WHERE ct.source IN ('ad', 'dan', 'synthetic_ad') AND ct.company_id IS NOT NULL
          AND ct.value_ron > 0 AND ct.cpv_code IS NOT NULL AND ct.year IS NOT NULL
        """,
        n=n,
    )
    if df.empty:
        return []
    df["value"] = df["value_ron"].astype(float)
    df["threshold"] = [
        direct_threshold(cfg, d, t) for d, t in zip(df["contract_date"], df["contract_type"], strict=True)
    ]
    df = df[df["value"] < df["threshold"]]  # doar achiziții sub prag (cele legale individual)
    out = []
    for key, g in df.groupby(["authority_id", "company_id", "year", "cpv_group"]):
        auth_id, comp_id, year, cpv_group = key
        thr = float(g["threshold"].max())
        total = float(g["value"].sum())
        cnt = len(g)
        near = int((g["value"] >= thr * float(c["near_threshold_ratio"])).sum())
        by_sum = cnt >= int(c["min_count"]) and total >= thr * float(c["min_sum_ratio"])
        by_near = near >= int(c["min_near_count"])
        if not (by_sum or by_near):
            continue
        first = g.iloc[0]
        supplier = "o persoană fizică autorizată" if first.is_natural_person else first.company_name
        ratio = total / thr
        score = 35 + min(ratio, 3) / 3 * 30 + min(cnt, 20) / 20 * 15 + near * 3
        reason = (
            f"suma lor ({lei(total)}) depășește pragul legal pentru achiziție directă ({lei(thr)})"
            if by_sum
            else f"{near} dintre ele au valori de peste {int(float(c['near_threshold_ratio']) * 100)}% "
            f"din pragul legal ({lei(thr)})"
        )
        out.append(
            Signal(
                signal_type="fragmentation",
                score=score,
                target_type="pair",
                authority_id=int(auth_id),
                company_id=int(comp_id),
                contract_id=int(g.sort_values("value", ascending=False).iloc[0]["id"]),
                county_code=first.county_code,
                year=int(year),
                title=f"{cnt} achiziții directe de la același furnizor în {int(year)} (CPV {cpv_group}…)",
                explanation=(
                    f"În {int(year)}, {first.authority_name} a făcut {cnt} achiziții directe de la "
                    f"{supplier} pentru produse/servicii din aceeași categorie (cod CPV {cpv_group}…, "
                    f"ex. „{first.cpv_name or '—'}”), iar {reason}. Legea cere ca valoarea achizițiilor "
                    f"similare dintr-un an să fie estimată cumulat; repetarea poate avea explicații "
                    f"(nevoi neprevăzute, livrări eșalonate), dar merită verificat dacă nu era necesară o "
                    f"procedură competitivă."
                ),
                fingerprint=f"fragmentation:{auth_id}:{comp_id}:{year}:{cpv_group}",
                details={
                    "count": cnt,
                    "total_ron": round(total, 2),
                    "threshold_ron": thr,
                    "near_threshold_count": near,
                    "cpv_group": cpv_group,
                    "contract_ids": [int(x) for x in g["id"].tolist()[:50]],
                },
                source_url=first.source_url,
                is_synthetic=bool(g["is_synthetic"].any()),
            )
        )
    return out


# ------------------------------------------------------------------ 4. acte adiționale


def sig_amendment_increase(session: Session, cfg: dict[str, Any]) -> list[Signal]:
    pct = float(cfg["amendment_increase"]["min_increase_pct"])
    df = _df(
        session,
        """
        SELECT am.id, am.contract_id, am.authority_id, am.delta_pct, am.delta_ron, am.value_before_ron,
               am.value_after_ron, am.publication_date, am.notice_number, am.contract_number, am.source_url,
               am.is_synthetic, a.name AS authority_name, a.county_code, ct.company_id
        FROM contract_amendments am JOIN authorities a ON a.id = am.authority_id
        LEFT JOIN contracts ct ON ct.id = am.contract_id
        WHERE am.delta_pct > :pct AND am.value_before_ron > 0
        """,
        pct=pct,
    )
    out = []
    for r in df.itertuples():
        p = float(r.delta_pct)
        score = 40 + min(p, 200) / 200 * 40 + value_factor(float(r.delta_ron or 0), 20)
        out.append(
            Signal(
                signal_type="amendment_increase",
                score=score,
                target_type="contract" if pd.notna(r.contract_id) else "authority",
                contract_id=int(r.contract_id) if pd.notna(r.contract_id) else None,
                company_id=int(r.company_id) if pd.notna(r.company_id) else None,
                authority_id=int(r.authority_id),
                county_code=r.county_code,
                year=r.publication_date.year if r.publication_date else None,
                title=f"Valoarea contractului a crescut cu {p:.0f}% printr-o modificare",
                explanation=(
                    f"Contractul nr. {r.contract_number or '—'} (anunț {r.notice_number or '—'}) al "
                    f"{r.authority_name} a fost modificat"
                    f"{' pe ' + format(r.publication_date, '%d.%m.%Y') if r.publication_date else ''}: "
                    f"valoarea a trecut de la {lei(r.value_before_ron)} la {lei(r.value_after_ron)} "
                    f"(+{lei(r.delta_ron)}, +{p:.0f}%). Modificările pot fi legale (ex. clauze de ajustare "
                    f"a prețului, lucrări suplimentare neprevăzute), dar creșterile mari merită verificate."
                ),
                fingerprint=f"amendment_increase:{r.id}",
                details={
                    "amendment_id": int(r.id),
                    "value_before_ron": float(r.value_before_ron),
                    "value_after_ron": float(r.value_after_ron),
                    "delta_pct": round(p, 1),
                },
                source_url=r.source_url,
                is_synthetic=bool(r.is_synthetic),
            )
        )
    return out


# ------------------------------------------------------------------ 5. ponderea veniturilor publice


def sig_public_revenue_share(session: Session, cfg: dict[str, Any]) -> list[Signal]:
    c = cfg["public_revenue_share"]
    df = _df(
        session,
        """
        SELECT f.company_id, f.year, f.turnover_ron, co.name, co.cui, co.is_natural_person, co.is_synthetic,
               (SELECT sum(ct.value_ron) FROM contracts ct WHERE ct.company_id = f.company_id
                  AND NOT ct.repeat_same_company
                  AND ct.year = f.year) AS public_total,
               (SELECT count(*) FROM contracts ct WHERE ct.company_id = f.company_id
                  AND NOT ct.repeat_same_company
                  AND ct.year = f.year) AS n_contracts,
               (SELECT ct.county_code FROM contracts ct WHERE ct.company_id = f.company_id
                  AND ct.year = f.year LIMIT 1) AS county_code
        FROM company_financials f JOIN companies co ON co.id = f.company_id
        WHERE f.turnover_ron >= :minturn
        """,
        minturn=float(c["min_turnover_ron"]),
    )
    out = []
    for r in df.itertuples():
        if r.public_total is None or pd.isna(r.public_total):
            continue
        share = float(r.public_total) / float(r.turnover_ron)
        if share < float(c["min_share"]):
            continue
        name = "Persoana fizică autorizată" if r.is_natural_person else f"Firma {r.name}"
        out.append(
            Signal(
                signal_type="public_revenue_share",
                score=35 + min(share, 2.0) / 2.0 * 45,
                target_type="company",
                company_id=int(r.company_id),
                county_code=r.county_code,
                year=int(r.year),
                title=f"Contractele publice din {int(r.year)} ≈ {share * 100:.0f}% din cifra de afaceri",
                explanation=(
                    f"{name} a raportat la ANAF o cifră de afaceri de {lei(r.turnover_ron)} pentru "
                    f"{int(r.year)}, iar contractele publice atribuite în același an (în datele noastre) "
                    f"însumează {lei(r.public_total)} ({int(r.n_contracts)} contracte). Atenție: un contract "
                    f"se poate întinde pe mai mulți ani, deci raportul este orientativ. Dependența de "
                    f"contracte publice nu e o problemă în sine, dar e un context util."
                ),
                fingerprint=f"public_revenue_share:{r.company_id}:{r.year}",
                details={
                    "turnover_ron": float(r.turnover_ron),
                    "public_total_ron": float(r.public_total),
                    "share": round(share, 3),
                },
                source_url=f"https://webservicesp.anaf.ro/bilant?an={int(r.year)}&cui={r.cui}"
                if str(r.cui).isdigit()
                else None,
                is_synthetic=bool(r.is_synthetic),
            )
        )
    return out


# ------------------------------------------------------------------ 6. concentrare


def sig_concentration(session: Session, cfg: dict[str, Any]) -> list[Signal]:
    c = cfg["concentration"]
    df = _df(
        session,
        """
        WITH t AS (
          SELECT authority_id, year, sum(value_ron) AS total, count(*) AS n
          FROM contracts WHERE year IS NOT NULL AND value_ron > 0 AND duplicate_of_id IS NULL
          GROUP BY authority_id, year
        ), s AS (
          SELECT authority_id, year, company_id, sum(value_ron) AS supplier_total, count(*) AS n_sup,
                 bool_or(is_synthetic) AS is_synthetic, max(source_url) AS source_url
          FROM contracts WHERE year IS NOT NULL AND value_ron > 0 AND company_id IS NOT NULL
            AND duplicate_of_id IS NULL
          GROUP BY authority_id, year, company_id
        )
        SELECT s.*, t.total, t.n, a.name AS authority_name, a.county_code, co.name AS company_name,
               co.is_natural_person
        FROM s JOIN t USING (authority_id, year)
        JOIN authorities a ON a.id = s.authority_id JOIN companies co ON co.id = s.company_id
        WHERE t.total >= :mintotal AND t.n >= :minn AND s.supplier_total > t.total * :share
        """,
        mintotal=float(c["min_authority_total_ron"]),
        minn=int(c["min_authority_contracts"]),
        share=float(c["min_share"]),
    )
    out = []
    for r in df.itertuples():
        share = float(r.supplier_total) / float(r.total)
        supplier = "o persoană fizică autorizată" if r.is_natural_person else r.company_name
        out.append(
            Signal(
                signal_type="concentration",
                score=30
                + (share - float(c["min_share"])) / (1 - float(c["min_share"])) * 50
                + value_factor(float(r.supplier_total), 20),
                target_type="pair",
                authority_id=int(r.authority_id),
                company_id=int(r.company_id),
                county_code=r.county_code,
                year=int(r.year),
                title=f"Un singur furnizor a primit {share * 100:.0f}% din cheltuieli în {int(r.year)}",
                explanation=(
                    f"În {int(r.year)}, {supplier} a primit {lei(r.supplier_total)} din totalul de "
                    f"{lei(r.total)} contractat de {r.authority_name} ({share * 100:.0f}%, "
                    f"{int(r.n_sup)} din {int(r.n)} contracte). Concentrarea poate fi firească (de ex. un "
                    f"furnizor unic de utilități sau o investiție mare), dar merită privită în context."
                ),
                fingerprint=f"concentration:{r.authority_id}:{r.company_id}:{r.year}",
                details={
                    "supplier_total_ron": float(r.supplier_total),
                    "authority_total_ron": float(r.total),
                    "share": round(share, 3),
                    "supplier_contracts": int(r.n_sup),
                    "authority_contracts": int(r.n),
                },
                source_url=r.source_url,
                is_synthetic=bool(r.is_synthetic),
            )
        )
    return out


ALL = [
    sig_new_company,
    sig_single_bidder,
    sig_fragmentation,
    sig_amendment_increase,
    sig_public_revenue_share,
    sig_concentration,
]


def compute_all(session: Session, thresholds_path: str | None = None) -> dict[str, int]:
    cfg = load_thresholds(thresholds_path)
    run = RunLog(session, "risk", {"thresholds": thresholds_path or "default"})
    now = dt.datetime.now(dt.UTC)
    signals: list[Signal] = []
    counts: dict[str, int] = {}
    for fn in ALL:
        try:
            found = fn(session, cfg)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            run.error(fn.__name__, f"Eroare la calcul: {exc}")
            found = []
        counts[fn.__name__.removeprefix("sig_")] = len(found)
        signals.extend(found)
    run.run.rows_read = len(signals)
    session.execute(delete(RiskSignal))
    upsert(
        session,
        RiskSignal,
        [s.row(now) for s in signals],
        conflict=["fingerprint"],
        update=["score", "title", "explanation", "details", "computed_at"],
        run=run,
    )
    session.commit()
    run.run.rows_upserted = len(signals)
    run.finish(message=str(counts))
    log.info("Semnale calculate: %s", counts)
    return counts
