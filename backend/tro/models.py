"""Modelul de date (inspirat din OCDS: buyer → Authority, supplier → Company,
tender → Procedure, contract/award → Contract, amendment → ContractAmendment).

Cheia de legătură dintre surse este CUI-ul normalizat (fără „RO”, spații, zerouri la început).
Valorile monetare sunt în RON (Numeric/Decimal). Fiecare tabel principal are `is_synthetic`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tro.db import Base

Money = Numeric(18, 2)
JsonType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Authority(TimestampMixin, Base):
    """Autoritate contractantă (OCDS: buyer)."""

    __tablename__ = "authorities"

    id: Mapped[int] = mapped_column(primary_key=True)
    cui: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(400))
    name_normalized: Mapped[str] = mapped_column(String(400), index=True)
    county_code: Mapped[str | None] = mapped_column(String(3), index=True)
    county_name: Mapped[str | None] = mapped_column(String(60))
    locality: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text)
    authority_type: Mapped[str | None] = mapped_column(String(60), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('ro_unaccent', coalesce(name,'') || ' ' || coalesce(locality,'') || ' ' || cui)",
            persisted=True,
        ),
    )

    contracts: Mapped[list[Contract]] = relationship(back_populates="authority")

    __table_args__ = (Index("ix_authorities_search", "search_vector", postgresql_using="gin"),)


class Company(TimestampMixin, Base):
    """Operator economic (OCDS: supplier / tenderer)."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    # CUI normalizat; pentru furnizori fără CUI valid: "X-<hash>" (cheie tehnică)
    cui: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(400))
    name_normalized: Mapped[str] = mapped_column(String(400), index=True)
    # GDPR: persoane fizice / PFA / II / IF → numele nu se afișează
    is_natural_person: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    county_code: Mapped[str | None] = mapped_column(String(3))
    county_name: Mapped[str | None] = mapped_column(String(60))
    locality: Mapped[str | None] = mapped_column(String(120))
    founded_on: Mapped[dt.date | None] = mapped_column(Date)
    founded_source: Mapped[str | None] = mapped_column(String(20))
    caen_code: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str | None] = mapped_column(String(200))
    legal_form: Mapped[str | None] = mapped_column(String(120))
    registry_number: Mapped[str | None] = mapped_column(String(60))
    vat_payer: Mapped[bool | None] = mapped_column(Boolean)
    inactive: Mapped[bool | None] = mapped_column(Boolean)
    anaf_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    anaf_found: Mapped[bool | None] = mapped_column(Boolean)
    onrc_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('ro_unaccent', CASE WHEN is_natural_person THEN 'persoana fizica autorizata' "
            "ELSE coalesce(name,'') END || ' ' || cui)",
            persisted=True,
        ),
    )

    aliases: Mapped[list[CompanyAlias]] = relationship(back_populates="company", cascade="all, delete-orphan")
    financials: Mapped[list[CompanyFinancial]] = relationship(back_populates="company", cascade="all, delete-orphan")
    contracts: Mapped[list[Contract]] = relationship(back_populates="company")

    __table_args__ = (Index("ix_companies_search", "search_vector", postgresql_using="gin"),)

    @property
    def pf(self) -> bool:
        """Persoană fizică (se anonimizează). Verificăm și denumirea, nu doar marcajul din import:
        o firmă văzută întâi sub alt nume poate să nu fi fost marcată la creare."""
        from tro.normalize import is_natural_person

        return bool(self.is_natural_person) or is_natural_person(name=self.name)

    @property
    def display_name(self) -> str:
        return "Persoană fizică autorizată" if self.pf else self.name


class CompanyAlias(Base):
    """Denumirile diferite sub care apare aceeași firmă (același CUI) în surse."""

    __tablename__ = "company_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    alias_normalized: Mapped[str] = mapped_column(String(400))
    alias_raw: Mapped[str] = mapped_column(String(400))
    source: Mapped[str] = mapped_column(String(40))

    company: Mapped[Company] = relationship(back_populates="aliases")

    __table_args__ = (UniqueConstraint("company_id", "alias_normalized", name="uq_alias"),)


class CompanyFinancial(Base):
    """Indicatori din bilanț pe ani (ANAF /bilant)."""

    __tablename__ = "company_financials"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    turnover_ron: Mapped[Decimal | None] = mapped_column(Money)
    net_profit_ron: Mapped[Decimal | None] = mapped_column(Money)
    employees: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40), default="anaf_bilant")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="financials")

    __table_args__ = (UniqueConstraint("company_id", "year", name="uq_fin_company_year"),)


class Procedure(TimestampMixin, Base):
    """Procedură de atribuire (OCDS: tender)."""

    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), unique=True)
    authority_id: Mapped[int] = mapped_column(ForeignKey("authorities.id"), index=True)
    notice_number: Mapped[str | None] = mapped_column(String(60), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    procedure_type: Mapped[str | None] = mapped_column(String(120), index=True)
    contract_type: Mapped[str | None] = mapped_column(String(40))
    cpv_code: Mapped[str | None] = mapped_column(String(16), index=True)
    estimated_value_ron: Mapped[Decimal | None] = mapped_column(Money)
    number_of_offers: Mapped[int | None] = mapped_column(Integer)
    award_criteria: Mapped[str | None] = mapped_column(String(120))
    legislation: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str | None] = mapped_column(String(60))
    publication_date: Mapped[dt.date | None] = mapped_column(Date)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    authority: Mapped[Authority] = relationship()


class Contract(TimestampMixin, Base):
    """Contract / achiziție directă (OCDS: award + contract)."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(160), unique=True)
    source: Mapped[str] = mapped_column(String(30), index=True)  # ad | dan | contracte | atribuire_fara | synthetic
    procedure_id: Mapped[int | None] = mapped_column(ForeignKey("procedures.id"), index=True)
    authority_id: Mapped[int] = mapped_column(ForeignKey("authorities.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    # Același contract raportat pe mai multe rânduri (asociere de firme / mai multe loturi cu valoarea
    # totală repetată): rândurile suplimentare indică rândul principal și NU intră în totaluri.
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id", ondelete="SET NULL"), index=True)
    # rând repetat al aceluiași contract pentru ACEEAȘI firmă (loturi) → exclus și din totalurile firmei
    repeat_same_company: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    county_code: Mapped[str | None] = mapped_column(String(3), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    cpv_code: Mapped[str | None] = mapped_column(String(16), index=True)
    cpv_name: Mapped[str | None] = mapped_column(String(300))
    contract_type: Mapped[str | None] = mapped_column(String(40))  # Furnizare | Servicii | Lucrari
    procedure_type: Mapped[str | None] = mapped_column(String(120), index=True)
    value_ron: Mapped[Decimal | None] = mapped_column(Money, index=True)
    original_value: Mapped[Decimal | None] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="RON")
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    contract_date: Mapped[dt.date | None] = mapped_column(Date, index=True)
    publication_date: Mapped[dt.date | None] = mapped_column(Date)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    contract_number: Mapped[str | None] = mapped_column(String(160))
    notice_number: Mapped[str | None] = mapped_column(String(60), index=True)
    lot_number: Mapped[str | None] = mapped_column(String(20))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    framework: Mapped[str | None] = mapped_column(String(80))
    eu_funded: Mapped[bool | None] = mapped_column(Boolean)
    eu_program: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_dataset: Mapped[str | None] = mapped_column(String(300))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('ro_unaccent', coalesce(title,'') || ' ' || coalesce(cpv_name,'') || ' ' || "
            "coalesce(notice_number,'') || ' ' || coalesce(contract_number,''))",
            persisted=True,
        ),
    )

    authority: Mapped[Authority] = relationship(back_populates="contracts")
    company: Mapped[Company | None] = relationship(back_populates="contracts")
    procedure: Mapped[Procedure | None] = relationship()
    amendments: Mapped[list[ContractAmendment]] = relationship(back_populates="contract")

    __table_args__ = (
        Index("ix_contracts_search", "search_vector", postgresql_using="gin"),
        Index("ix_contracts_auth_year", "authority_id", "year"),
        Index("ix_contracts_company_year", "company_id", "year"),
    )


class ContractAmendment(TimestampMixin, Base):
    """Act adițional / modificare de contract (OCDS: amendment)."""

    __tablename__ = "contract_amendments"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(200), unique=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    authority_id: Mapped[int] = mapped_column(ForeignKey("authorities.id"), index=True)
    notice_number: Mapped[str | None] = mapped_column(String(60))
    contract_number: Mapped[str | None] = mapped_column(String(160))
    contract_date: Mapped[dt.date | None] = mapped_column(Date)
    publication_date: Mapped[dt.date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    value_before_ron: Mapped[Decimal | None] = mapped_column(Money)
    value_after_ron: Mapped[Decimal | None] = mapped_column(Money)
    delta_ron: Mapped[Decimal | None] = mapped_column(Money)
    delta_pct: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="RON")
    source_url: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    contract: Mapped[Contract | None] = relationship(back_populates="amendments")
    authority: Mapped[Authority] = relationship()


class RiskSignal(Base):
    """Semnal de verificat (NU acuzație). Calculat în ETL."""

    __tablename__ = "risk_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(200), unique=True)
    signal_type: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[int] = mapped_column(Integer, index=True)  # 0–100
    target_type: Mapped[str] = mapped_column(String(20))  # company | contract | authority | pair
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    authority_id: Mapped[int | None] = mapped_column(ForeignKey("authorities.id", ondelete="CASCADE"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    county_code: Mapped[str | None] = mapped_column(String(3), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(300))
    explanation: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    source_url: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    company: Mapped[Company | None] = relationship()
    authority: Mapped[Authority | None] = relationship()
    contract: Mapped[Contract | None] = relationship()


class SourceRecord(Base):
    """Proveniența fiecărei înregistrări importate (sursă, URL, dată import, hash conținut)."""

    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    source_key: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    source_url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    imported_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("source", "source_key", name="uq_source_record"),
        Index("ix_source_records_entity", "entity_type", "entity_id"),
    )


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(60))
    params: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)


class ImportError_(Base):
    """Eroare la o singură înregistrare — importul continuă."""

    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), index=True)
    row_ref: Mapped[str | None] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    raw: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 6))  # RON pentru 1 unitate


class AnafCache(Base):
    """Răspunsuri ANAF brute, pe CUI (evită cereri repetate)."""

    __tablename__ = "anaf_cache"

    cui: Mapped[str] = mapped_column(String(20), primary_key=True)
    found: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    county_code: Mapped[str | None] = mapped_column(String(3), index=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LocalityGeo(Base):
    __tablename__ = "locality_geo"

    county_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    locality_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="nominatim")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Subscription(Base):
    """Abonare la alerte (double opt-in)."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # authority | company
    target_key: Mapped[str] = mapped_column(String(40))  # id autoritate sau CUI firmă
    token: Mapped[str] = mapped_column(String(64), unique=True)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_notified_contract_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("email", "target_type", "target_key", name="uq_subscription"),)


class CorrectionRequest(Base):
    """Formular de corecție (pagina Disclaimer)."""

    __tablename__ = "correction_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    entity_url: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="nou")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AiSummary(Base):
    """Rezumate AI pentru firme/ONG-uri și instituții (cache; se regenerează după o vreme)."""

    __tablename__ = "ai_summaries"

    kind: Mapped[str] = mapped_column(String(20), primary_key=True)  # company | authority
    ref: Mapped[str] = mapped_column(String(40), primary_key=True)  # CUI / cheie firmă sau id instituție
    text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ContractExplanation(Base):
    __tablename__ = "contract_explanations"

    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
