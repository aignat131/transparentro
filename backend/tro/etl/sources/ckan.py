"""Descoperirea rapoartelor SEAP pe data.gov.ro prin CKAN API."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from tro.etl.http import make_client, request_with_retry
from tro.normalize import simplify

log = logging.getLogger(__name__)

CKAN_API = "https://data.gov.ro/api/3/action"
SEAP_DATASET = "achizitii-publice-{year}"


@dataclass(frozen=True)
class SeapResource:
    year: int
    quarter: int | None
    kind: str  # ad | dan | contracte | atribuire_fara | initiere | modificari | sad | unknown
    name: str
    url: str
    resource_id: str
    size: int | None
    last_modified: str | None
    dataset: str

    @property
    def filename(self) -> str:
        ext = self.url.rsplit(".", 1)[-1].lower()
        if ext not in ("xlsx", "xls", "ods", "csv"):
            ext = "bin"
        return f"{self.year}_T{self.quarter or 0}_{self.kind}_{self.resource_id[:8]}.{ext}"


_KIND_RULES: list[tuple[str, str]] = [
    (r"modificare contract", "modificari"),
    (r"notificari de atribuire", "dan"),
    (r"achizitii directe", "ad"),
    (r"anunturi de atribuire la proceduri fara", "atribuire_fara"),
    (r"anunturi de in[it]*iere", "initiere"),
    (r"sad|sistemul de achizitii dinamic", "sad"),
    (r"contracte", "contracte"),
]

_QUARTER_RE = re.compile(r"(?<![a-z])t\s*[-_]?\s*(iv|iii|ii|i|[1-4])(?![a-z0-9])")
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}


def classify_name(name: str) -> str:
    s = simplify(name)
    for pat, kind in _KIND_RULES:
        if re.search(pat, s):
            return kind
    return "unknown"


def quarter_from_name(name: str) -> int | None:
    m = _QUARTER_RE.search(simplify(name))
    if not m:
        return None
    g = m.group(1)
    return int(g) if g.isdigit() else _ROMAN[g]


def list_seap_resources(year: int) -> list[SeapResource]:
    dataset = SEAP_DATASET.format(year=year)
    with make_client() as client:
        r = request_with_retry(client, "GET", f"{CKAN_API}/package_show", params={"id": dataset})
        if r.status_code == 404:
            log.warning("Setul %s nu există pe data.gov.ro", dataset)
            return []
        r.raise_for_status()
        pkg = r.json()["result"]
    out: list[SeapResource] = []
    seen_keys: set[tuple[str, int | None, int | None]] = set()
    for res in pkg.get("resources", []):
        name = res.get("name") or ""
        kind = classify_name(name)
        quarter = quarter_from_name(name) or quarter_from_name(res.get("url", ""))
        size = res.get("size")
        try:
            size = int(size) if size is not None else None
        except (TypeError, ValueError):
            size = None
        # data.gov.ro publică uneori aceeași resursă de două ori (același nume și mărime)
        key = (kind, quarter, size)
        if size and key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(
            SeapResource(
                year=year,
                quarter=quarter,
                kind=kind,
                name=name.strip(),
                url=res["url"],
                resource_id=res["id"],
                size=size,
                last_modified=res.get("last_modified") or res.get("metadata_modified"),
                dataset=dataset,
            )
        )
    return out
