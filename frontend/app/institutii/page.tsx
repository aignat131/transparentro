import type { Metadata } from "next";
import Link from "next/link";

import { SyntheticBadge } from "@/components/data-banner";
import { FilterPanel } from "@/components/filter-panel";
import { pageNum, Pagination, sp } from "@/components/pagination";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { api, DEFAULT_COUNTY, exportUrl, type AuthorityItem, type Meta, type Page } from "@/lib/api";
import { leiShort, num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Instituții publice",
  description: "Instituțiile publice din județ și cât au cheltuit prin contracte de achiziții.",
};

export default async function AuthoritiesPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const page = pageNum(searchParams.page);
  const q = {
    county: DEFAULT_COUNTY,
    q: sp(searchParams.q),
    authority_type: sp(searchParams.authority_type),
    year: sp(searchParams.year),
    domain: sp(searchParams.domain),
    sort: sp(searchParams.sort) ?? "total_desc",
  };
  const [data, meta] = await Promise.all([
    api<Page<AuthorityItem>>("/authorities", { ...q, context: true, page, page_size: 25 }),
    api<Meta>("/meta", { county: DEFAULT_COUNTY }, 600),
  ]);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl">Instituțiile publice și cât au cheltuit</h1>
      <p className="text-sm text-muted-foreground">
        {num(data.total)} instituții{q.year ? ` în ${q.year}` : ""}, de la cea care a cheltuit cel mai mult. Apasă pe una ca să vezi pe ce și la cine s-au dus banii.
      </p>
      <FilterPanel active={[q.q && `„${q.q}”`, q.year, q.authority_type, meta.domains?.find((d) => d.key === q.domain)?.label]}>
      <form method="get" className="grid gap-2 p-4 md:grid-cols-5" aria-label="Filtre instituții">
        <div className="md:col-span-2">
          <label htmlFor="f-q" className="text-sm font-medium">Nume</label>
          <Input id="f-q" name="q" defaultValue={q.q} placeholder="ex. primăria, școala" />
        </div>
        <div>
          <label htmlFor="f-type" className="text-sm font-medium">Tip</label>
          <Select id="f-type" name="authority_type" defaultValue={q.authority_type ?? ""}>
            <option value="">Toate</option>
            {meta.authority_types.map((t) => <option key={t}>{t}</option>)}
          </Select>
        </div>
        <div>
          <label htmlFor="f-year" className="text-sm font-medium">An</label>
          <Select id="f-year" name="year" defaultValue={q.year ?? ""}>
            <option value="">Toți anii</option>
            {meta.years.map((y) => <option key={y}>{y}</option>)}
          </Select>
        </div>
        {(meta.domains?.length ?? 0) > 0 && (
          <div>
            <label htmlFor="f-domain" className="text-sm font-medium">Domeniu</label>
            <Select id="f-domain" name="domain" defaultValue={q.domain ?? ""}>
              <option value="">Toate domeniile</option>
              {meta.domains?.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
            </Select>
          </div>
        )}
        <div>
          <label htmlFor="f-sort" className="text-sm font-medium">Ordonare</label>
          <Select id="f-sort" name="sort" defaultValue={q.sort}>
            <option value="total_desc">Cheltuieli (desc.)</option>
            <option value="contracts_desc">Nr. contracte</option>
            <option value="name_asc">Nume (A–Z)</option>
          </Select>
        </div>
        <div className="flex gap-2 md:col-span-5">
          <Button type="submit">Aplică filtrele</Button>
          <Button variant="outline" asChild><a href={exportUrl("authorities", q)}>Descarcă CSV</a></Button>
        </div>
      </form>
      </FilterPanel>
      <ul className="divide-y rounded-lg border bg-white">
        {data.items.map((a) => (
          <li key={a.id} className="flex flex-col gap-1 p-3 md:flex-row md:items-center md:justify-between">
            <div>
              <Link href={`/institutii/${a.id}`} className="font-medium">{a.name}</Link>
              <SyntheticBadge show={a.is_synthetic} />
              {a.top_category && (
                <div className="text-sm text-muted-foreground">
                  Cel mai mult pe {a.top_category.toLowerCase()}{a.top_supplier ? `, furnizor principal: ${a.top_supplier}` : ""}
                </div>
              )}
              <div className="text-xs text-muted-foreground">{[a.authority_type, a.locality].filter(Boolean).join(" · ")}</div>
            </div>
            <div className="text-sm tabular md:text-right">
              <div className="font-semibold text-primary">{leiShort(a.total_ron)}</div>
              <div className="text-xs text-muted-foreground">{num(a.contracts)} contracte</div>
            </div>
          </li>
        ))}
      </ul>
      <Pagination base="/institutii" params={searchParams} page={page} pageSize={25} total={data.total} />
    </div>
  );
}
