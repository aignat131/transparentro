"""Generator de date SINTETICE pentru dezvoltare și demonstrații.

- Toate înregistrările au `is_synthetic = true`; interfața afișează un banner.
- Numele instituțiilor și firmelor sunt fictive și conțin marcajul „(SINTETIC)”.
- CUI-urile sintetice sunt de 10 cifre, începând cu „99” — imposibil de confundat cu CUI-uri reale.
- Coordonatele sunt puncte aleatoare în interiorul județului, NU sediile unor instituții reale.
- Include intenționat situații care declanșează fiecare tip de semnal, pentru testare.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
from decimal import Decimal

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from tro.counties import COUNTIES, county_name
from tro.etl.runlog import RunLog
from tro.models import (
    Authority,
    Company,
    CompanyAlias,
    CompanyFinancial,
    Contract,
    ContractAmendment,
    Procedure,
    RiskSignal,
)
from tro.normalize import normalize_name

log = logging.getLogger(__name__)

TAG = " (SINTETIC)"

AUTH_TEMPLATES = [
    ("Primăria Comunei Valea Fictivă {n}", "Primărie / administrație locală"),
    ("Primăria Orașului Exemplu {n}", "Primărie / administrație locală"),
    ("Școala Gimnazială Demonstrativă nr. {n}", "Educație"),
    ("Liceul Teoretic de Test nr. {n}", "Educație"),
    ("Spitalul Orășenesc Model {n}", "Sănătate"),
    ("Direcția de Asistență Socială Demo {n}", "Asistență socială"),
    ("Muzeul Imaginar {n}", "Cultură"),
    ("Serviciul Public de Drumuri Fictive {n}", "Companie / regie publică"),
]
COMPANY_WORDS = [
    "Alfa",
    "Beta",
    "Gama",
    "Delta",
    "Orion",
    "Vega",
    "Nova",
    "Carpat",
    "Olt",
    "Cibin",
    "Dacic",
    "Logos",
    "Sigma",
    "Atlas",
    "Terra",
    "Lumen",
    "Rapid",
    "Vertex",
    "Nord",
    "Sud",
]
COMPANY_SUFFIX = [
    "Construct",
    "Trade",
    "Med",
    "Soft",
    "Serv",
    "Distribution",
    "Prest",
    "Consult",
    "Food",
    "Instal",
    "Auto",
    "Print",
    "Clean",
    "Energy",
    "Proiect",
]
CPV_SAMPLES = [
    ("45233140-2", "Lucrari de drumuri (Rev.2)", "Lucrari"),
    ("45453000-7", "Lucrari de reparatii generale si de renovare (Rev.2)", "Lucrari"),
    ("45214200-2", "Lucrari de constructii de cladiri scolare (Rev.2)", "Lucrari"),
    ("72212000-4", "Servicii de programare de aplicatii software (Rev.2)", "Servicii"),
    ("30213100-6", "Computere portabile (Rev.2)", "Furnizare"),
    ("15811100-7", "Paine (Rev.2)", "Furnizare"),
    ("15800000-6", "Diverse produse alimentare (Rev.2)", "Furnizare"),
    ("33600000-6", "Produse farmaceutice (Rev.2)", "Furnizare"),
    ("33140000-3", "Consumabile medicale (Rev.2)", "Furnizare"),
    ("09134100-8", "Motorina (Rev.2)", "Furnizare"),
    ("90511000-2", "Servicii de colectare a gunoiului (Rev.2)", "Servicii"),
    ("90620000-9", "Servicii de deszapezire (Rev.2)", "Servicii"),
    ("79341000-6", "Servicii de publicitate (Rev.2)", "Servicii"),
    ("79952000-2", "Servicii de organizare de evenimente (Rev.2)", "Servicii"),
    ("71320000-7", "Servicii de proiectare tehnica (Rev.2)", "Servicii"),
    ("30192000-1", "Accesorii de birou (Rev.2)", "Furnizare"),
    ("39130000-2", "Mobilier de birou (Rev.2)", "Furnizare"),
    ("50700000-2", "Servicii de reparare si de intretinere a instalatiilor (Rev.2)", "Servicii"),
]
PROC_TYPES = ["Licitatie deschisa", "Procedura simplificata", "Negociere fara publicare prealabila"]

# casete aproximative pentru puncte aleatoare în județ (doar pentru hartă)
BOX = {"SB": (45.55, 46.20, 23.60, 24.85)}


def _cui(i: int) -> str:
    return str(9900000000 + i)


def reset_synthetic(session: Session) -> None:
    session.execute(delete(RiskSignal).where(RiskSignal.is_synthetic.is_(True)))
    session.execute(delete(ContractAmendment).where(ContractAmendment.is_synthetic.is_(True)))
    session.execute(delete(Contract).where(Contract.is_synthetic.is_(True)))
    session.execute(delete(Procedure).where(Procedure.is_synthetic.is_(True)))
    syn_companies = select(Company.id).where(Company.is_synthetic.is_(True))
    session.execute(delete(CompanyFinancial).where(CompanyFinancial.company_id.in_(syn_companies)))
    session.execute(delete(CompanyAlias).where(CompanyAlias.company_id.in_(syn_companies)))
    session.execute(delete(Company).where(Company.is_synthetic.is_(True)))
    session.execute(delete(Authority).where(Authority.is_synthetic.is_(True)))
    session.commit()


def generate(
    session: Session,
    county: str = "SB",
    seed: int = 42,
    n_auth: int = 36,
    n_comp: int = 140,
    years: tuple[int, ...] = (2024, 2025, 2026),
) -> dict[str, int]:
    rnd = random.Random(seed)
    run = RunLog(session, "synthetic", {"county": county, "seed": seed})
    box = BOX.get(county)
    if box is None:
        _, lat0, lon0 = COUNTIES[county]
        box = (lat0 - 0.3, lat0 + 0.3, lon0 - 0.4, lon0 + 0.4)
    today = dt.date.today()

    # ---- autorități
    auths: list[Authority] = []
    for i in range(n_auth):
        tpl, typ = AUTH_TEMPLATES[i % len(AUTH_TEMPLATES)]
        name = tpl.format(n=i + 1) + TAG
        a = Authority(
            cui=_cui(i + 1),
            name=name,
            name_normalized=normalize_name(name),
            county_code=county,
            county_name=county_name(county),
            locality=f"Localitatea Fictivă {i % 12 + 1}",
            authority_type=typ,
            lat=rnd.uniform(box[0], box[1]),
            lon=rnd.uniform(box[2], box[3]),
            is_synthetic=True,
            address="Adresă fictivă",
        )
        auths.append(a)
    session.add_all(auths)

    # ---- firme
    comps: list[Company] = []
    for i in range(n_comp):
        pf = i % 23 == 0
        if pf:
            name = "Persoană fizică autorizată"
        else:
            name = f"{rnd.choice(COMPANY_WORDS)} {rnd.choice(COMPANY_SUFFIX)} {i + 1} SRL{TAG}"
        founded = today - dt.timedelta(days=rnd.randint(400, 9000))
        c = Company(
            cui=_cui(10000 + i),
            name=name,
            name_normalized=normalize_name(name),
            is_natural_person=pf,
            county_code=county,
            county_name=county_name(county),
            locality=f"Localitatea Fictivă {i % 12 + 1}",
            founded_on=founded,
            founded_source="synthetic",
            caen_code=rnd.choice(["4120", "4211", "6201", "4646", "1071", "8121", "7311"]),
            status="INREGISTRAT",
            legal_form="SRL" if not pf else "PFA",
            vat_payer=not pf,
            inactive=False,
            is_synthetic=True,
        )
        comps.append(c)
    # firme „nou-înființate” pentru semnalul 1 (înființate în anul primelor contracte)
    for c in comps[1:6]:
        c.founded_on = dt.date(years[0], 1, 1) + dt.timedelta(days=rnd.randint(30, 300))
    session.add_all(comps)
    session.flush()
    for c in comps:
        if not c.is_natural_person:
            session.add(
                CompanyAlias(company_id=c.id, alias_normalized=c.name_normalized, alias_raw=c.name, source="synthetic")
            )

    def rdate(y: int, after: dt.date | None = None) -> dt.date:
        start = dt.date(y, 1, 1)
        end = min(dt.date(y, 12, 31), today)
        if after and after > start:
            start = after
        if start > end:
            start = end
        return start + dt.timedelta(days=rnd.randint(0, max(0, (end - start).days)))

    contracts: list[Contract] = []
    n_contract = 0

    def add_contract(
        auth: Authority,
        comp: Company,
        y: int,
        value: float,
        *,
        source: str = "ad",
        proc: Procedure | None = None,
        cpv: tuple[str, str, str] | None = None,
        when: dt.date | None = None,
    ) -> Contract:
        nonlocal n_contract
        n_contract += 1
        cpv = cpv or rnd.choice(CPV_SAMPLES)
        d = when or rdate(y, comp.founded_on + dt.timedelta(days=1) if comp.founded_on else None)
        number = f"SIN-DA{n_contract:07d}" if source == "ad" else f"SIN-CAN{n_contract:07d}"
        c = Contract(
            source_id=f"synthetic:{n_contract}",
            source=source,
            authority_id=auth.id,
            company_id=comp.id,
            county_code=county,
            title=f"{cpv[1].replace(' (Rev.2)', '')} — achiziție demonstrativă",
            cpv_code=cpv[0],
            cpv_name=cpv[1],
            contract_type=cpv[2],
            procedure_type="Achiziție directă" if source == "ad" else (proc.procedure_type if proc else None),
            procedure_id=proc.id if proc else None,
            value_ron=Decimal(str(round(value, 2))),
            original_value=Decimal(str(round(value, 2))),
            currency="RON",
            exchange_rate=Decimal(1),
            contract_date=d,
            publication_date=d,
            year=d.year,
            contract_number=f"{rnd.randint(100, 9999)}/{d:%d.%m.%Y}",
            notice_number=number,
            source_url=None,
            source_dataset="Date SINTETICE generate local",
            is_synthetic=True,
            duration_days=rnd.choice([None, 30, 90, 180, 365]),
        )
        contracts.append(c)
        return c

    # achiziții directe obișnuite
    for y in years:
        for _ in range(700):
            a = rnd.choice(auths)
            comp = rnd.choice(comps)
            value = min(rnd.lognormvariate(8.6, 1.4), 250_000)
            add_contract(a, comp, y, value)
    # proceduri competitive (unele cu un singur ofertant)
    procs: list[Procedure] = []
    for i in range(160):
        y = rnd.choice(years)
        a = rnd.choice(auths)
        cpv = rnd.choice(CPV_SAMPLES)
        est = rnd.lognormvariate(13.2, 1.0)
        p = Procedure(
            source_id=f"synthetic:p{i}",
            authority_id=a.id,
            notice_number=f"SIN-CN{i:06d}",
            title=f"{cpv[1].replace(' (Rev.2)', '')} — procedură demonstrativă",
            procedure_type=rnd.choice(PROC_TYPES),
            contract_type=cpv[2],
            cpv_code=cpv[0],
            estimated_value_ron=Decimal(str(round(est, 2))),
            number_of_offers=1 if i % 5 == 0 else rnd.randint(2, 7),
            award_criteria="Pretul cel mai scazut",
            legislation="Legea nr. 98/23.05.2016",
            status="Atribuita",
            publication_date=rdate(y),
            is_synthetic=True,
        )
        procs.append(p)
    session.add_all(procs)
    session.flush()
    for p in procs:
        a = next(x for x in auths if x.id == p.authority_id)
        comp = rnd.choice(comps[6:])
        cpv = next(c for c in CPV_SAMPLES if c[0] == p.cpv_code)
        assert p.publication_date and p.estimated_value_ron
        add_contract(
            a,
            comp,
            p.publication_date.year,
            float(p.estimated_value_ron) * rnd.uniform(0.75, 1.0),
            source="contracte",
            proc=p,
            cpv=cpv,
        )

    # semnal 1: firme noi cu contract la câteva luni de la înființare
    for c in comps[1:6]:
        assert c.founded_on
        add_contract(
            rnd.choice(auths),
            c,
            c.founded_on.year,
            rnd.uniform(60_000, 900_000),
            source="contracte",
            when=c.founded_on + dt.timedelta(days=rnd.randint(20, 150)),
        )
    # semnal 3: fragmentare (multe achiziții directe aproape de prag)
    frag_cpv = ("30192000-1", "Accesorii de birou (Rev.2)", "Furnizare")
    for k in range(4):
        a, comp = auths[k % len(auths)], comps[(20 + k) % len(comps)]
        y = years[min(1, len(years) - 1)]
        for _ in range(rnd.randint(3, 6)):
            add_contract(a, comp, y, rnd.uniform(200_000, 265_000), cpv=frag_cpv)
    # semnal 6: concentrare (un furnizor dominant)
    for k in range(3):
        a, comp = auths[(10 + k) % len(auths)], comps[(30 + k) % len(comps)]
        for y in years[:2]:
            for _ in range(8):
                add_contract(a, comp, y, rnd.uniform(150_000, 240_000))

    session.add_all(contracts)
    session.flush()

    # semnal 4: acte adiționale
    big = [c for c in contracts if c.source == "contracte"]
    amendments = []
    for i, ct in enumerate(rnd.sample(big, min(40, len(big)))):
        before = ct.value_ron or Decimal(0)
        pct = rnd.choice([3, 5, 8, 12, 15, 25, 35, 60, 110]) if i % 2 == 0 else rnd.choice([2, 4, 10])
        after = (before * (Decimal(100 + pct) / 100)).quantize(Decimal("0.01"))
        assert ct.contract_date
        amendments.append(
            ContractAmendment(
                source_id=f"synthetic:m{i}",
                contract_id=ct.id,
                authority_id=ct.authority_id,
                notice_number=ct.notice_number,
                contract_number=ct.contract_number,
                contract_date=ct.contract_date,
                publication_date=min(ct.contract_date + dt.timedelta(days=rnd.randint(30, 300)), today),
                description="Act adițional demonstrativ: suplimentare cantități / prelungire durată (SINTETIC)",
                value_before_ron=before,
                value_after_ron=after,
                delta_ron=after - before,
                delta_pct=float(pct),
                currency="RON",
                is_synthetic=True,
            )
        )
    session.add_all(amendments)

    # semnal 5: date financiare (cifră de afaceri) pe ani
    totals: dict[tuple[int, int], float] = {}
    for ct in contracts:
        if ct.company_id and ct.year:
            totals[(ct.company_id, ct.year)] = totals.get((ct.company_id, ct.year), 0) + float(ct.value_ron or 0)
    for comp in comps:
        if comp.is_natural_person:
            continue
        for y in years[:-1]:
            pub = totals.get((comp.id, y), 0)
            factor = rnd.choice([0.6, 1.1, 3, 5, 10, 25]) if pub else rnd.uniform(1, 50)
            turnover = max(pub * factor, rnd.uniform(50_000, 3_000_000) if not pub else pub * factor)
            session.add(
                CompanyFinancial(
                    company_id=comp.id,
                    year=y,
                    turnover_ron=Decimal(str(round(turnover, 2))),
                    net_profit_ron=Decimal(str(round(turnover * rnd.uniform(-0.05, 0.15), 2))),
                    employees=rnd.randint(1, 120),
                    source="synthetic",
                    is_synthetic=True,
                )
            )
    session.commit()
    stats = {
        "authorities": len(auths),
        "companies": len(comps),
        "procedures": len(procs),
        "contracts": len(contracts),
        "amendments": len(amendments),
    }
    run.run.rows_upserted = sum(stats.values())
    run.finish(message=str(stats))
    session.execute(text("ANALYZE"))
    return stats
