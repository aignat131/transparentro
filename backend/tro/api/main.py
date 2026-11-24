"""TransparentRO API — date despre achizițiile publice, pentru cetățeni."""

from __future__ import annotations

import importlib
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from tro.api.routers import (
    authorities,
    companies,
    contracts,
    export,
    feedback,
    procedures,
    risk,
    search,
    stats,
)
from tro.config import get_settings
from tro.db import get_db

logging.basicConfig(level=logging.INFO)

DESCRIPTION = """
API-ul TransparentRO expune achizițiile publice (SEAP/SICAP), datele firmelor (ANAF/ONRC) și
**semnale de verificat** calculate automat.

* Valorile sunt în **RON**; conversiile valutare folosesc cursul BNR din ziua contractului.
* Persoanele fizice și PFA-urile sunt **anonimizate** („Persoană fizică autorizată” + localitate).
* Semnalele **nu sunt acuzații** — sunt indicii care merită o privire mai atentă.
* Parametrul `county` (ex. `SB`, `CJ`, `B`, `all`) este acceptat de toate listele; implicit: județul configurat.
* Înregistrările cu `is_synthetic = true` sunt date SINTETICE, generate pentru dezvoltare.
"""

app = FastAPI(
    title="TransparentRO API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=[
        {"name": "contracte"},
        {"name": "instituții"},
        {"name": "firme"},
        {"name": "căutare"},
        {"name": "statistici"},
        {"name": "semnale"},
        {"name": "export"},
        {"name": "alerte"},
        {"name": "explicații"},
        {"name": "corecții"},
    ],
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

for r in (contracts, authorities, companies, procedures, search, stats, risk, export, feedback):
    app.include_router(r.router)

# Faza 3 (module opționale): alerte e-mail și explicații AI
for _name in ("alerts", "explain"):
    try:
        _mod = importlib.import_module(f"tro.api.routers.{_name}")
        app.include_router(_mod.router)
    except ImportError:  # pragma: no cover
        pass


@app.get("/health", tags=["statistici"], summary="Stare serviciu")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
