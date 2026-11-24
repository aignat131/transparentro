"""Schemele răspunsurilor API (pydantic v2) — apar și în documentația OpenAPI."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class AuthorityRef(BaseModel):
    id: int
    name: str
    county_code: str | None = None
    is_synthetic: bool = False


class CompanyRef(BaseModel):
    key: str = Field(description="CUI pentru persoane juridice; 'pf-<id>' pentru persoane fizice (anonimizat)")
    name: str
    is_natural_person: bool = False
    locality: str | None = None
    is_synthetic: bool = False


class ContractItem(BaseModel):
    id: int
    title: str | None
    value_ron: Decimal | None
    contract_date: dt.date | None
    year: int | None
    procedure_type: str | None
    contract_type: str | None
    cpv_code: str | None
    cpv_name: str | None
    category: str
    source: str
    notice_number: str | None
    authority: AuthorityRef
    company: CompanyRef | None
    signal_count: int = 0
    duplicate_of_id: int | None = Field(
        default=None, description="Rând repetat al aceluiași contract (asociere/loturi); nu intră în totaluri"
    )
    is_synthetic: bool = False


class AmendmentOut(BaseModel):
    id: int
    publication_date: dt.date | None
    description: str | None
    value_before_ron: Decimal | None
    value_after_ron: Decimal | None
    delta_ron: Decimal | None
    delta_pct: float | None
    source_url: str | None
    is_synthetic: bool = False


class RiskSignalOut(BaseModel):
    id: int
    signal_type: str
    signal_label: str
    score: int
    target_type: str
    title: str
    explanation: str
    details: dict[str, Any]
    year: int | None
    county_code: str | None
    source_url: str | None
    computed_at: dt.datetime
    authority: AuthorityRef | None = None
    company: CompanyRef | None = None
    contract_id: int | None = None
    is_synthetic: bool = False


class ProcedureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    notice_number: str | None
    title: str | None
    procedure_type: str | None
    contract_type: str | None
    cpv_code: str | None
    estimated_value_ron: Decimal | None
    number_of_offers: int | None
    award_criteria: str | None
    legislation: str | None
    status: str | None
    publication_date: dt.date | None


class ProvenanceOut(BaseModel):
    source: str
    source_url: str | None
    imported_at: dt.datetime
    first_seen_at: dt.datetime
    content_hash: str


class ContractDetail(ContractItem):
    original_value: Decimal | None
    currency: str
    exchange_rate: Decimal | None
    publication_date: dt.date | None
    contract_number: str | None
    lot_number: str | None
    duration_days: int | None
    framework: str | None
    eu_funded: bool | None
    eu_program: str | None
    source_url: str | None
    source_dataset: str | None
    sicap_search_url: str
    last_updated: dt.datetime
    procedure: ProcedureOut | None
    amendments: list[AmendmentOut]
    signals: list[RiskSignalOut]
    provenance: list[ProvenanceOut]


class YearTotal(BaseModel):
    year: int
    total_ron: Decimal
    count: int


class NamedTotal(BaseModel):
    name: str
    total_ron: Decimal
    count: int
    share: float | None = None
    key: str | None = None  # id/cui pentru link


class AuthorityItem(BaseModel):
    id: int
    cui: str
    name: str
    county_code: str | None
    locality: str | None
    authority_type: str | None
    total_ron: Decimal | None = None
    contracts: int = 0
    is_synthetic: bool = False


class AuthorityDetail(AuthorityItem):
    county_name: str | None
    address: str | None
    lat: float | None
    lon: float | None
    by_year: list[YearTotal]
    top_suppliers: list[NamedTotal]
    by_category: list[NamedTotal]
    by_procedure_type: list[NamedTotal]
    signals: list[RiskSignalOut]
    signal_count: int


class FinancialOut(BaseModel):
    year: int
    turnover_ron: Decimal | None
    net_profit_ron: Decimal | None
    employees: int | None
    public_total_ron: Decimal | None = None


class CompanyItem(BaseModel):
    key: str
    name: str
    is_natural_person: bool
    locality: str | None
    county_code: str | None
    total_ron: Decimal | None = None
    contracts: int = 0
    signal_count: int = 0
    is_synthetic: bool = False
    is_ngo: bool = False


class CompanyDetail(CompanyItem):
    cui: str | None
    founded_on: dt.date | None
    founded_source: str | None
    caen_code: str | None
    status: str | None
    legal_form: str | None
    registry_number: str | None
    vat_payer: bool | None
    inactive: bool | None
    anaf_checked_at: dt.datetime | None
    aliases: list[str]
    by_year: list[YearTotal]
    clients: list[NamedTotal]
    by_category: list[NamedTotal]
    financials: list[FinancialOut]
    signals: list[RiskSignalOut]
    first_contract_date: dt.date | None
    official_url: str | None


class SearchHit(BaseModel):
    type: str  # authority | company | contract
    id: str
    title: str
    subtitle: str | None
    value_ron: Decimal | None = None
    is_synthetic: bool = False


class SearchResult(BaseModel):
    query: str
    authorities: list[SearchHit]
    companies: list[SearchHit]
    contracts: list[SearchHit]


class DataMode(BaseModel):
    real_contracts: int
    synthetic_contracts: int
    has_synthetic: bool
    last_import_at: dt.datetime | None
    coverage_from: dt.date | None
    coverage_to: dt.date | None


class Overview(BaseModel):
    county_code: str | None
    county_name: str | None
    total_ron: Decimal
    contracts: int
    authorities: int
    companies: int
    signals: int
    direct_awards_share: float | None
    by_year: list[YearTotal]
    by_category: list[NamedTotal]
    latest_contracts: list[ContractItem]
    data: DataMode


class MapPoint(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    locality: str | None
    authority_type: str | None
    total_ron: Decimal
    contracts: int
    is_synthetic: bool = False


class CorrectionIn(BaseModel):
    email: EmailStr | None = None
    entity_url: str | None = Field(default=None, max_length=1000)
    message: str = Field(min_length=10, max_length=5000)


class SubscribeIn(BaseModel):
    email: EmailStr
    target_type: str = Field(pattern="^(authority|company)$")
    target_key: str = Field(min_length=1, max_length=40)


class Message(BaseModel):
    ok: bool = True
    message: str
