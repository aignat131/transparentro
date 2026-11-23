"""Fixture-uri: bază de date de test separată (tro_test), migrată cu Alembic, golită între teste."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://tro:tro@localhost:5432/tro_test")
os.environ["DATABASE_URL"] = TEST_URL
os.environ.setdefault("TARGET_COUNTIES", "SB")
os.environ.setdefault("DEFAULT_COUNTY", "SB")

from tro import db as dbmod  # noqa: E402
from tro.api import cache  # noqa: E402
from tro.config import get_settings  # noqa: E402

TABLES = [
    "contract_explanations",
    "subscriptions",
    "correction_requests",
    "risk_signals",
    "source_records",
    "import_errors",
    "import_runs",
    "contract_amendments",
    "contracts",
    "procedures",
    "company_financials",
    "company_aliases",
    "companies",
    "authorities",
    "anaf_cache",
    "exchange_rates",
    "locality_geo",
]


def _ensure_database(url: str) -> None:
    u = make_url(url)
    admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}).first()
        if not exists:
            c.execute(text(f'CREATE DATABASE "{u.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    get_settings.cache_clear()
    _ensure_database(TEST_URL)
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    command.upgrade(cfg, "head")
    dbmod.reset_engine(TEST_URL)
    yield
    dbmod.get_engine().dispose()


@pytest.fixture()
def session(database):
    eng = dbmod.get_engine()
    with eng.begin() as c:
        c.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
    cache.clear()
    s = dbmod.SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(session):
    from fastapi.testclient import TestClient

    from tro.api.main import app

    with TestClient(app) as c:
        yield c
