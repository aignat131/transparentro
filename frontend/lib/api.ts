// Client pentru API-ul TransparentRO. Pe server folosim adresa internă (rețeaua docker).
export const PUBLIC_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
export const DEFAULT_COUNTY = process.env.NEXT_PUBLIC_DEFAULT_COUNTY || "SB";

function base(): string {
  if (typeof window === "undefined") return process.env.API_INTERNAL_URL || PUBLIC_API;
  return PUBLIC_API;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export type Query = Record<string, string | number | boolean | undefined | null>;

export function qs(q: Query = {}): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v !== undefined && v !== null && v !== "" && v !== false) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(path: string, q: Query = {}, revalidate = 120): Promise<T> {
  const res = await fetch(`${base()}${path}${qs(q)}`, { next: { revalidate } });
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} pentru ${path}`);
  return res.json() as Promise<T>;
}

export function exportUrl(entity: string, q: Query = {}): string {
  return `${PUBLIC_API}/export/${entity}.csv${qs(q)}`;
}

// ------------------------------------------------------------------ tipuri
export type AuthorityRef = { id: number; name: string; county_code: string | null; is_synthetic: boolean };
export type CompanyRef = {
  key: string;
  name: string;
  is_natural_person: boolean;
  locality: string | null;
  is_synthetic: boolean;
};
export type Page<T> = { items: T[]; total: number; page: number; page_size: number };
export type YearTotal = { year: number; total_ron: string; count: number };
export type NamedTotal = { name: string; total_ron: string; count: number; share: number | null; key: string | null };

export type ContractItem = {
  id: number;
  title: string | null;
  value_ron: string | null;
  contract_date: string | null;
  year: number | null;
  procedure_type: string | null;
  contract_type: string | null;
  cpv_code: string | null;
  cpv_name: string | null;
  category: string;
  source: string;
  notice_number: string | null;
  authority: AuthorityRef;
  company: CompanyRef | null;
  signal_count: number;
  duplicate_of_id: number | null;
  is_synthetic: boolean;
};

export type Signal = {
  id: number;
  signal_type: string;
  signal_label: string;
  score: number;
  target_type: string;
  title: string;
  explanation: string;
  details: Record<string, unknown>;
  year: number | null;
  county_code: string | null;
  source_url: string | null;
  computed_at: string;
  authority: AuthorityRef | null;
  company: CompanyRef | null;
  contract_id: number | null;
  is_synthetic: boolean;
};

export type Procedure = {
  id: number;
  notice_number: string | null;
  title: string | null;
  procedure_type: string | null;
  contract_type: string | null;
  cpv_code: string | null;
  estimated_value_ron: string | null;
  number_of_offers: number | null;
  award_criteria: string | null;
  legislation: string | null;
  status: string | null;
  publication_date: string | null;
};

export type Amendment = {
  id: number;
  publication_date: string | null;
  description: string | null;
  value_before_ron: string | null;
  value_after_ron: string | null;
  delta_ron: string | null;
  delta_pct: number | null;
  source_url: string | null;
  is_synthetic: boolean;
};

export type ContractDetail = ContractItem & {
  original_value: string | null;
  currency: string;
  exchange_rate: string | null;
  publication_date: string | null;
  contract_number: string | null;
  lot_number: string | null;
  duration_days: number | null;
  framework: string | null;
  eu_funded: boolean | null;
  eu_program: string | null;
  source_url: string | null;
  source_dataset: string | null;
  sicap_search_url: string;
  last_updated: string;
  procedure: Procedure | null;
  amendments: Amendment[];
  signals: Signal[];
  provenance: { source: string; source_url: string | null; imported_at: string; first_seen_at: string; content_hash: string }[];
};

export type AuthorityItem = {
  id: number;
  cui: string;
  name: string;
  county_code: string | null;
  locality: string | null;
  authority_type: string | null;
  total_ron: string | null;
  contracts: number;
  is_synthetic: boolean;
};
export type AuthorityDetail = AuthorityItem & {
  county_name: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  by_year: YearTotal[];
  top_suppliers: NamedTotal[];
  by_category: NamedTotal[];
  by_procedure_type: NamedTotal[];
  signals: Signal[];
  signal_count: number;
};

export type CompanyItem = {
  key: string;
  name: string;
  is_natural_person: boolean;
  locality: string | null;
  county_code: string | null;
  total_ron: string | null;
  contracts: number;
  signal_count: number;
  is_synthetic: boolean;
  is_ngo?: boolean;
};
export type CompanyDetail = CompanyItem & {
  cui: string | null;
  founded_on: string | null;
  founded_source: string | null;
  caen_code: string | null;
  status: string | null;
  legal_form: string | null;
  registry_number: string | null;
  vat_payer: boolean | null;
  inactive: boolean | null;
  anaf_checked_at: string | null;
  aliases: string[];
  by_year: YearTotal[];
  clients: NamedTotal[];
  by_category: NamedTotal[];
  financials: {
    year: number;
    turnover_ron: string | null;
    net_profit_ron: string | null;
    employees: number | null;
    public_total_ron: string | null;
  }[];
  signals: Signal[];
  first_contract_date: string | null;
  official_url: string | null;
};

export type SearchHit = {
  type: string;
  id: string;
  title: string;
  subtitle: string | null;
  value_ron: string | null;
  is_synthetic: boolean;
};
export type SearchResult = { query: string; authorities: SearchHit[]; companies: SearchHit[]; contracts: SearchHit[] };

export type Overview = {
  county_code: string | null;
  county_name: string | null;
  total_ron: string;
  contracts: number;
  authorities: number;
  companies: number;
  signals: number;
  direct_awards_share: number | null;
  by_year: YearTotal[];
  by_category: NamedTotal[];
  latest_contracts: ContractItem[];
  data: {
    real_contracts: number;
    synthetic_contracts: number;
    has_synthetic: boolean;
    last_import_at: string | null;
    coverage_from: string | null;
    coverage_to: string | null;
  };
};

export type MapPoint = {
  id: number;
  name: string;
  lat: number;
  lon: number;
  locality: string | null;
  authority_type: string | null;
  total_ron: string;
  contracts: number;
  is_synthetic: boolean;
};

export type Meta = {
  default_county: string | null;
  counties: { code: string; name: string; has_data: boolean; lat: number; lon: number }[];
  years: number[];
  procedure_types: string[];
  authority_types: string[];
  categories: string[];
  signal_types: { code: string; label: string }[];
  domains?: { key: string; label: string }[];
};

export type ProcedureItem = {
  id: number;
  notice_number: string | null;
  title: string | null;
  authority: AuthorityRef;
  authority_type: string | null;
  procedure_type: string | null;
  contract_type: string | null;
  cpv_code: string | null;
  category: string;
  estimated_value_ron: string | null;
  status: string | null;
  publication_date: string | null;
  official_url: string;
  is_open: boolean;
};

export type SpendingReport = {
  county_code: string | null;
  county_name: string;
  year: number | null;
  total_ron: string;
  contracts: number;
  authorities: number;
  companies: number;
  by_domain: NamedTotal[];
  by_category: NamedTotal[];
  by_contract_type: NamedTotal[];
  by_procedure_type: NamedTotal[];
  by_authority_type: NamedTotal[];
  by_month: { month: string; total_ron: string; count: number }[];
  top_authorities: NamedTotal[];
  top_companies: NamedTotal[];
  ngo_total_ron: string;
  ngo_contracts: number;
  direct_awards_ron: string;
  eu_funded_ron: string;
};
