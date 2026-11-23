"""Coordonatele localităților autorităților (Nominatim/OSM), pentru hartă.

Respectă politica Nominatim: max. 1 cerere/s, User-Agent identificabil, rezultatele
se păstrează în `locality_geo` (fiecare localitate e cerută o singură dată).
"""

from __future__ import annotations

import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tro.authority_types import locality_key
from tro.config import get_settings
from tro.counties import COUNTIES, county_name
from tro.etl.http import RateLimiter, make_client, request_with_retry
from tro.etl.runlog import RunLog
from tro.models import Authority, LocalityGeo
from tro.normalize import strip_diacritics

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"


def geocode_authorities(session: Session, offline: bool = False) -> int:
    run = RunLog(session, "geocode", {"offline": offline})
    limiter = RateLimiter(get_settings().nominatim_min_interval_s)
    auths = list(session.execute(select(Authority).where(Authority.county_code.is_not(None))).scalars())
    pairs = {(a.county_code, locality_key(a.locality)) for a in auths if a.county_code}
    known = {(g.county_code, g.locality_key): g for g in session.execute(select(LocalityGeo)).scalars()}
    missing = [p for p in pairs if p not in known or known[p].lat is None]
    run.run.rows_read = len(missing)
    if missing and not offline:
        with make_client() as client:
            for cc, lk in sorted(missing):
                lat = lon = None
                if lk:
                    cname = strip_diacritics(county_name(cc) or "")
                    attempts = [
                        {"city": lk, "county": cname, "country": "Romania"},
                        {"q": f"{lk}, {cname}, Romania"},
                    ]
                    for params in attempts:
                        try:
                            r = request_with_retry(
                                client,
                                "GET",
                                NOMINATIM,
                                params={**params, "format": "json", "limit": 1, "countrycodes": "ro"},
                                limiter=limiter,
                            )
                            r.raise_for_status()
                            js = r.json()
                            if js:
                                lat, lon = float(js[0]["lat"]), float(js[0]["lon"])
                                break
                        except Exception as exc:  # noqa: BLE001
                            run.error(f"{lk}/{cc}", f"geocodare eșuată: {exc}")
                            break
                g = LocalityGeo(
                    county_code=cc, locality_key=lk, lat=lat, lon=lon, source="nominatim" if lat else "none"
                )
                session.merge(g)
                known[(cc, lk)] = g
                run.run.rows_upserted += 1
            session.commit()
    # atribuire coordonate; fallback: centrul județului
    n = 0
    for a in auths:
        geo = known.get((a.county_code or "", locality_key(a.locality)))
        lat, lon = (geo.lat, geo.lon) if geo and geo.lat is not None else (None, None)
        if lat is None and a.county_code in COUNTIES:
            _, lat, lon = COUNTIES[a.county_code]
        if lat is not None:
            session.execute(update(Authority).where(Authority.id == a.id).values(lat=lat, lon=lon))
            n += 1
    session.commit()
    run.finish()
    return n
