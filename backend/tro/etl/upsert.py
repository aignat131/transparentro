"""Upsert în loturi (INSERT … ON CONFLICT), cu revenire rând-cu-rând la eroare."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tro.etl.runlog import RunLog

log = logging.getLogger(__name__)


def dedupe(rows: list[dict[str, Any]], key: Sequence[str]) -> list[dict[str, Any]]:
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for r in rows:
        seen[tuple(r[k] for k in key)] = r
    return list(seen.values())


def upsert(
    session: Session,
    model: Any,
    rows: list[dict[str, Any]],
    *,
    conflict: Sequence[str],
    update: Sequence[str] | None = None,
    coalesce: bool = False,
    returning: Sequence[str] | None = None,
    run: RunLog | None = None,
    batch_size: int = 1000,
) -> list[Any]:
    """Upsert idempotent. `update=None` → DO NOTHING. `coalesce=True` → nu suprascrie cu NULL."""
    if not rows:
        return []
    rows = dedupe(rows, conflict)
    out: list[Any] = []
    table = model.__table__

    def build(chunk: list[dict[str, Any]]):
        stmt: Any = insert(model).values(chunk)
        if update:
            set_ = {}
            for col in update:
                if coalesce:
                    set_[col] = func.coalesce(getattr(stmt.excluded, col), table.c[col])
                else:
                    set_[col] = getattr(stmt.excluded, col)
            stmt = stmt.on_conflict_do_update(index_elements=list(conflict), set_=set_)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=list(conflict))
        if returning:
            stmt = stmt.returning(*[table.c[c] for c in returning])
        return stmt

    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        try:
            with session.begin_nested():
                res = session.execute(build(chunk))
                if returning:
                    out.extend(res.all())
        except SQLAlchemyError as exc:
            log.warning("Lot eșuat (%s), reiau rând cu rând: %s", model.__tablename__, str(exc)[:300])
            for r in chunk:
                try:
                    with session.begin_nested():
                        res = session.execute(build([r]))
                        if returning:
                            out.extend(res.all())
                except SQLAlchemyError as exc2:
                    ref = "|".join(str(r.get(k)) for k in conflict)
                    if run:
                        run.error(ref, f"{model.__tablename__}: {str(exc2).splitlines()[0][:500]}", r)
                    else:
                        log.error("Rând eșuat %s: %s", ref, exc2)
    return out
