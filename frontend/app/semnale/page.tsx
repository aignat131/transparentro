import type { Metadata } from "next";

import { pageNum, Pagination, sp } from "@/components/pagination";
import { SignalCard, SignalsNote } from "@/components/signals";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { api, DEFAULT_COUNTY, exportUrl, type Meta, type Page, type Signal } from "@/lib/api";
import { num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Semnale de verificat",
  description: "Situații din achizițiile publice care merită o privire mai atentă. Semnalele nu sunt acuzații.",
};

export default async function SignalsPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const page = pageNum(searchParams.page);
  const q = {
    county: DEFAULT_COUNTY,
    signal_type: sp(searchParams.signal_type),
    min_score: sp(searchParams.min_score),
    year: sp(searchParams.year),
    authority_id: sp(searchParams.authority_id),
    company: sp(searchParams.company),
    sort: sp(searchParams.sort) ?? "score_desc",
  };
  const [data, meta, summary] = await Promise.all([
    api<Page<Signal>>("/risk-signals", { ...q, page, page_size: 20 }),
    api<Meta>("/meta", { county: DEFAULT_COUNTY }, 600),
    api<Record<string, number>>("/risk-signals/summary", { county: DEFAULT_COUNTY }),
  ]);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl">Semnale de verificat</h1>
      <SignalsNote />
      <form method="get" className="grid gap-3 rounded-lg border bg-white p-4 md:grid-cols-4" aria-label="Filtre semnale">
        <div className="md:col-span-2">
          <label htmlFor="f-type" className="text-sm font-medium">Tip de semnal</label>
          <Select id="f-type" name="signal_type" defaultValue={q.signal_type ?? ""}>
            <option value="">Toate tipurile</option>
            {meta.signal_types.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label} ({num(summary[t.code] ?? 0)})
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label htmlFor="f-score" className="text-sm font-medium">Scor minim</label>
          <Select id="f-score" name="min_score" defaultValue={q.min_score ?? ""}>
            <option value="">Oricare</option>
            <option value="45">≥ 45 (medie)</option>
            <option value="70">≥ 70 (mare)</option>
          </Select>
        </div>
        <div>
          <label htmlFor="f-year" className="text-sm font-medium">An</label>
          <Select id="f-year" name="year" defaultValue={q.year ?? ""}>
            <option value="">Toți anii</option>
            {meta.years.map((y) => <option key={y}>{y}</option>)}
          </Select>
        </div>
        {q.authority_id && <input type="hidden" name="authority_id" value={q.authority_id} />}
        {q.company && <input type="hidden" name="company" value={q.company} />}
        <div className="flex flex-wrap gap-2 md:col-span-4">
          <Button type="submit">Aplică filtrele</Button>
          <Button variant="outline" asChild><a href="/semnale">Resetează</a></Button>
          <Button variant="outline" asChild><a href={exportUrl("risk-signals", q)}>Descarcă CSV</a></Button>
        </div>
      </form>
      <p className="text-sm text-muted-foreground" aria-live="polite">{num(data.total)} semnale</p>
      <div className="space-y-3">
        {data.items.map((s) => <SignalCard key={s.id} s={s} />)}
        {data.items.length === 0 && <p className="text-muted-foreground">Niciun semnal pentru filtrele alese.</p>}
      </div>
      <Pagination base="/semnale" params={searchParams} page={page} pageSize={20} total={data.total} />
    </div>
  );
}
