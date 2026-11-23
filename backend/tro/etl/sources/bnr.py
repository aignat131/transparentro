"""Cursuri BNR (XML public). Conversii valutare la cursul din ziua contractului."""

from __future__ import annotations

import datetime as dt
import logging
import xml.etree.ElementTree as ET
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tro.etl.http import make_client, request_with_retry
from tro.etl.runlog import RunLog
from tro.models import ExchangeRate

log = logging.getLogger(__name__)

BNR_YEAR_URL = "https://curs.bnr.ro/files/xml/years/nbrfxrates{year}.xml"
BNR_DAILY_URL = "https://curs.bnr.ro/nbrfxrates.xml"
NS = {"b": "http://www.bnr.ro/xsd"}


def parse_bnr_xml(content: bytes) -> list[tuple[dt.date, str, Decimal]]:
    root = ET.fromstring(content)
    out: list[tuple[dt.date, str, Decimal]] = []
    for cube in root.iterfind(".//b:Cube", NS):
        day = dt.date.fromisoformat(cube.attrib["date"])
        for rate in cube.iterfind("b:Rate", NS):
            mult = Decimal(rate.attrib.get("multiplier", "1"))
            if not rate.text:
                continue
            out.append((day, rate.attrib["currency"], Decimal(rate.text.strip()) / mult))
    return out


def import_bnr(session: Session, years: list[int]) -> int:
    run = RunLog(session, "bnr", {"years": years})
    total = 0
    with make_client() as client:
        urls = [BNR_YEAR_URL.format(year=y) for y in years] + [BNR_DAILY_URL]
        for url in urls:
            try:
                r = request_with_retry(client, "GET", url)
                r.raise_for_status()
                if b"<DataSet" not in r.content[:500]:
                    run.error(url, "Răspunsul nu este XML BNR (posibil redirect)")
                    continue
                rows = parse_bnr_xml(r.content)
            except Exception as exc:  # noqa: BLE001
                run.error(url, f"Eroare la descărcare/parsare: {exc}")
                continue
            run.run.rows_read += len(rows)
            for i in range(0, len(rows), 2000):
                chunk = rows[i : i + 2000]
                stmt = insert(ExchangeRate).values([{"date": d, "currency": c, "rate": v} for d, c, v in chunk])
                stmt = stmt.on_conflict_do_update(
                    index_elements=["date", "currency"], set_={"rate": stmt.excluded.rate}
                )
                session.execute(stmt)
            session.commit()
            total += len(rows)
            run.run.rows_upserted += len(rows)
    run.finish()
    return total


class RateLookup:
    """Caută cursul pentru o zi; dacă lipsește (weekend/sărbătoare), ultimul curs anterior."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._cache: dict[tuple[dt.date, str], Decimal | None] = {}

    def rate(self, day: dt.date | None, currency: str) -> Decimal | None:
        currency = (currency or "RON").upper().strip()
        if currency == "RON":
            return Decimal(1)
        if day is None:
            day = dt.date.today()
        key = (day, currency)
        if key not in self._cache:
            row = self.session.execute(
                select(ExchangeRate.rate)
                .where(ExchangeRate.currency == currency, ExchangeRate.date <= day)
                .order_by(ExchangeRate.date.desc())
                .limit(1)
            ).scalar_one_or_none()
            self._cache[key] = row
        return self._cache[key]

    def to_ron(
        self, amount: Decimal | None, currency: str, day: dt.date | None
    ) -> tuple[Decimal | None, Decimal | None]:
        if amount is None:
            return None, None
        r = self.rate(day, currency)
        if r is None:
            return None, None
        return (amount * r).quantize(Decimal("0.01")), r
