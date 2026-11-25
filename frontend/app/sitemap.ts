import type { MetadataRoute } from "next";

import { api, DEFAULT_COUNTY, SITE_URL, type AuthorityItem, type CompanyItem, type ContractItem, type Page } from "@/lib/api";

export const dynamic = "force-dynamic";

const STATIC = ["", "/institutii", "/firme", "/ong", "/contracte", "/raport", "/oportunitati", "/localitati", "/semnale", "/harta", "/metodologie", "/surse-de-date", "/despre", "/disclaimer", "/glosar"];

async function all<T>(path: string, q: Record<string, string | number>, maxPages = 20): Promise<T[]> {
  const out: T[] = [];
  for (let page = 1; page <= maxPages; page++) {
    const r = await api<Page<T>>(path, { ...q, page, page_size: path === "/contracts" ? 100 : 200 }, 3600);
    out.push(...r.items);
    if (page * r.page_size >= r.total) break;
  }
  return out;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const entries: MetadataRoute.Sitemap = STATIC.map((p) => ({ url: `${SITE_URL}${p}`, lastModified: now }));
  try {
    const [auths, comps, contracts] = await Promise.all([
      all<AuthorityItem>("/authorities", { county: DEFAULT_COUNTY }),
      all<CompanyItem>("/companies", { county: DEFAULT_COUNTY }),
      all<ContractItem>("/contracts", { county: DEFAULT_COUNTY, sort: "value_desc" }, 20),
    ]);
    entries.push(...auths.map((a) => ({ url: `${SITE_URL}/institutii/${a.id}`, changeFrequency: "weekly" as const })));
    // persoanele fizice nu intră în sitemap (GDPR)
    entries.push(
      ...comps.filter((c) => !c.is_natural_person).map((c) => ({ url: `${SITE_URL}/firme/${encodeURIComponent(c.key)}`, changeFrequency: "weekly" as const })),
    );
    entries.push(...contracts.map((c) => ({ url: `${SITE_URL}/contracte/${c.id}`, changeFrequency: "monthly" as const })));
  } catch {
    /* API indisponibil: doar paginile statice */
  }
  return entries;
}
