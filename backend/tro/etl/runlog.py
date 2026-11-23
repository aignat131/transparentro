"""Jurnalizarea rulărilor de import și a erorilor per înregistrare."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy.orm import Session

from tro.models import ImportError_, ImportRun

log = logging.getLogger(__name__)

MAX_ERRORS_PER_RUN = 5000


class RunLog:
    def __init__(self, session: Session, source: str, params: dict[str, Any] | None = None) -> None:
        self.session = session
        self.run = ImportRun(source=source, params=params or {}, status="running")
        session.add(self.run)
        session.commit()
        self._errors = 0

    @property
    def id(self) -> int:
        return self.run.id

    def error(self, row_ref: str | None, message: str, raw: Any = None) -> None:
        self.run.rows_failed += 1
        self._errors += 1
        if self._errors <= MAX_ERRORS_PER_RUN:
            self.session.add(
                ImportError_(
                    run_id=self.run.id,
                    row_ref=(row_ref or "")[:200],
                    message=message[:2000],
                    raw=str(raw)[:2000] if raw is not None else None,
                )
            )
        if self._errors <= 20:
            log.warning("[%s] rând %s: %s", self.run.source, row_ref, message)

    def finish(self, status: str = "ok", message: str | None = None) -> None:
        self.run.status = status
        self.run.message = message
        self.run.finished_at = dt.datetime.now(dt.UTC)
        self.session.commit()
        log.info(
            "Import %s [%s]: citite=%d, scrise=%d, sărite=%d, erori=%d",
            self.run.source,
            status,
            self.run.rows_read,
            self.run.rows_upserted,
            self.run.rows_skipped,
            self.run.rows_failed,
        )
