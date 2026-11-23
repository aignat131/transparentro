import type { Metadata } from "next";
import Link from "next/link";

import { SyntheticBadge } from "@/components/data-banner";
import { pageNum, Pagination, sp } from "@/components/pagination";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { api, DEFAULT_COUNTY, exportUrl, type CompanyItem, type Meta, type Page } from "@/lib/api";
import { lei, num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Firme care lucrează cu statul",
  description: "Firmele care au primit contracte de la instituțiile publice din județ.",
};

export default async function CompaniesPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const page = pageNum(searchParams.page);
  const q = {
    county: DEFAULT_COUNTY,
    q: sp(searchParams.q),
    year: sp(searchParams.year),
    with_signals: sp(searchParams.with_signals) === "true",
    sort: sp(searchParams.sort) ?? "total_desc",
  };
  const [data, meta] = await Promise.all([
    api<Page<CompanyItem>>("/companies", { ...q, page, page_size: 25 }),
    api<Meta>("/meta", { county: DEFAULT_COUNTY }, 600),
  ]);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl">Firme care lucrează cu statul</h1>
      <form method="get" className="grid gap-2 rounded-lg border bg-white p-4 md:grid-cols-4" aria-label="Filtre firme">
        <div className="md:col-span-2">
          <label htmlFor="f-q" className="text-sm font-medium">Denumire sau CUI</label>
          <Input id="f-q" name="q" defaultValue={q.q} />
        </div>
        <div>
          <label htmlFor="f-year" className="text-sm font-medium">An</label>
          <Select id="f-year" name="year" defaultValue={q.year ?? ""}>
            <option value="">Toți anii</option>
            {meta.years.map((y) => <option key={y}>{y}</option>)}
          </Select>
        </div>
        <div>
          <label htmlFor="f-sort" className="text-sm font-medium">Ordonare</label>
          <Select id="f-sort" name="sort" defaultValue={q.sort}>
            <option value="total_desc">Valoare contracte</option>
            <option value="contracts_desc">Nr. contracte</option>
            <option value="signals_desc">Nr. semnale</option>
            <option value="name_asc">Nume (A–Z)</option>
          </Select>
        </div>
        <label className="flex items-center gap-2 text-sm md:col-span-4">
          <input type="checkbox" name="with_signals" value="true" defaultChecked={q.with_signals} /> Doar firmele cu semnale de verificat
        </label>
        <div className="flex gap-2 md:col-span-4">
          <Button type="submit">Aplică filtrele</Button>
          <Button variant="outline" asChild><a href={exportUrl("companies", q)}>Descarcă CSV</a></Button>
        </div>
      </form>
      <p className="text-sm text-muted-foreground">{num(data.total)} firme</p>
      <ul className="divide-y rounded-lg border bg-white">
        {data.items.map((c) => (
          <li key={c.key} className="flex flex-col gap-1 p-3 md:flex-row md:items-center md:justify-between">
            <div>
              <Link href={`/firme/${encodeURIComponent(c.key)}`} className="font-medium">{c.name}</Link>
              <SyntheticBadge show={c.is_synthetic} />
              <div className="text-xs text-muted-foreground">
                {[c.is_natural_person ? null : `CUI ${c.key}`, c.locality].filter(Boolean).join(" · ")}
                {c.signal_count > 0 && <span className="ml-2 text-amber-800">{c.signal_count} semnale</span>}
              </div>
            </div>
            <div className="text-right text-sm tabular">
              <div className="font-semibold">{lei(c.total_ron)}</div>
              <div className="text-xs text-muted-foreground">{num(c.contracts)} contracte</div>
            </div>
          </li>
        ))}
      </ul>
      <Pagination base="/firme" params={searchParams} page={page} pageSize={25} total={data.total} />
    </div>
  );
}
