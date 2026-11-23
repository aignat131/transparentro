"""CLI ETL: `python -m tro.etl <comanda> [opțiuni]`.

Comenzi:
  all          BNR → SEAP → ANAF firme → bilanțuri → geocodare → semnale (import REAL complet)
  bnr          cursuri BNR
  seap         rapoarte SEAP de pe data.gov.ro
  seap-file    importă un fișier SEAP local (xlsx/xls/ods)
  anaf         îmbogățește firmele din ANAF (date generale)
  bilant       bilanțuri ANAF pentru furnizorii importanți
  onrc         completează firmele din registrul ONRC (fișier mare)
  geocode      coordonate pentru localitățile autorităților
  synthetic    generează date SINTETICE (is_synthetic=true)
  risk         recalculează semnalele de verificat
  alerts       trimite alertele e-mail pentru contractele noi
  status       rezumat al bazei de date și al ultimelor importuri
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text

from tro.config import get_settings
from tro.db import session_scope


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    p = argparse.ArgumentParser(
        prog="python -m tro.etl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def seap_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--years", default=s.seap_years)
        sp.add_argument("--quarters", default=s.seap_quarters)
        sp.add_argument("--kinds", default=s.seap_kinds)
        sp.add_argument("--force", action="store_true", help="reimportă și fișierele deja importate")

    a = sub.add_parser("all")
    seap_opts(a)
    a.add_argument("--skip-bilant", action="store_true")
    a.add_argument(
        "--skip-seap", action="store_true", help="fără SEAP (ex. pe GitHub Actions, unde data.gov.ro nu răspunde)"
    )
    sub.add_parser("bnr").add_argument("--years", default=None)
    seap_opts(sub.add_parser("seap"))
    sf = sub.add_parser("seap-file")
    sf.add_argument("path")
    an = sub.add_parser("anaf")
    an.add_argument("--limit", type=int, default=None)
    sub.add_parser("bilant").add_argument("--years", default=None)
    on = sub.add_parser("onrc")
    on.add_argument("--file", default=None, help="od_firme.csv local (altfel se descarcă)")
    ge = sub.add_parser("geocode")
    ge.add_argument("--offline", action="store_true")
    sy = sub.add_parser("synthetic")
    sy.add_argument("--reset", action="store_true", help="șterge mai întâi datele sintetice existente")
    sy.add_argument("--county", default=s.default_county)
    sy.add_argument("--seed", type=int, default=42)
    sub.add_parser("risk").add_argument("--thresholds", default=None)
    al = sub.add_parser("alerts")
    al.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")

    args = p.parse_args(argv)

    from tro.etl import risk, synthetic
    from tro.etl.sources import anaf, bnr, geocode, onrc, seap

    with session_scope() as session:
        if args.cmd in ("all", "seap"):
            years = _ints(args.years)
            quarters = _ints(args.quarters)
            kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
            if args.cmd == "all":
                bnr.import_bnr(session, sorted(set(years) | {min(years) - 1}))
            if not getattr(args, "skip_seap", False):
                seap.import_seap(session, years, quarters, kinds, force=args.force)
            if args.cmd == "all":
                # fiecare etapă e independentă: o sursă indisponibilă nu oprește restul
                steps: list[tuple[str, Callable[[], object]]] = [("anaf", lambda: anaf.enrich_companies(session))]
                if not args.skip_bilant:
                    steps.append(("bilant", lambda: anaf.import_bilant(session)))
                steps += [
                    ("geocode", lambda: geocode.geocode_authorities(session)),
                    ("risk", lambda: risk.compute_all(session)),
                ]
                failed = []
                for name, step in steps:
                    try:
                        step()
                    except Exception:  # noqa: BLE001
                        session.rollback()
                        logging.exception("Etapa %s a eșuat; continui", name)
                        failed.append(name)
                if failed:
                    logging.error("Etape eșuate: %s", ", ".join(failed))
        elif args.cmd == "bnr":
            years = _ints(args.years) if args.years else [dt.date.today().year - 1, dt.date.today().year]
            bnr.import_bnr(session, years)
        elif args.cmd == "seap-file":
            seap.import_file(session, Path(args.path))
            seap.link_amendments(session)
            seap.fill_contract_titles(session)
            seap.mark_duplicate_values(session)
        elif args.cmd == "anaf":
            anaf.enrich_companies(session, limit=args.limit)
        elif args.cmd == "bilant":
            anaf.import_bilant(session, _ints(args.years) if args.years else None)
        elif args.cmd == "onrc":
            onrc.import_onrc(session, Path(args.file) if args.file else None)
        elif args.cmd == "geocode":
            geocode.geocode_authorities(session, offline=args.offline)
        elif args.cmd == "synthetic":
            if args.reset:
                synthetic.reset_synthetic(session)
            print(synthetic.generate(session, county=args.county.upper(), seed=args.seed))
        elif args.cmd == "risk":
            print(risk.compute_all(session, args.thresholds))
        elif args.cmd == "alerts":
            from tro.alerts import send_pending_alerts

            print(send_pending_alerts(session, dry_run=args.dry_run))
        elif args.cmd == "status":
            for t in [
                "authorities",
                "companies",
                "procedures",
                "contracts",
                "contract_amendments",
                "risk_signals",
                "source_records",
                "anaf_cache",
                "exchange_rates",
            ]:
                n = session.execute(text(f"SELECT count(*) FROM {t}")).scalar()  # noqa: S608
                syn = ""
                if t in ("authorities", "companies", "contracts", "risk_signals"):
                    k = session.execute(text(f"SELECT count(*) FROM {t} WHERE is_synthetic")).scalar()  # noqa: S608
                    syn = f" (sintetice: {k})"
                print(f"{t:22s} {n}{syn}")
            print("\nUltimele importuri:")
            for r in session.execute(
                text(
                    "SELECT id, source, status, rows_read, rows_upserted, rows_skipped, rows_failed, started_at "
                    "FROM import_runs ORDER BY id DESC LIMIT 15"
                )
            ):
                print(
                    f"  #{r.id} {r.source:20s} {r.status:8s} citite={r.rows_read} scrise={r.rows_upserted} "
                    f"sarite={r.rows_skipped} erori={r.rows_failed} {r.started_at:%Y-%m-%d %H:%M}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
