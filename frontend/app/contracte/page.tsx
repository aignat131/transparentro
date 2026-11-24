import type { Metadata } from "next";

import { pageNum, Pagination, sp } from "@/components/pagination";
import { ContractTable } from "@/components/tables";
import { Term } from "@/components/term";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { api, DEFAULT_COUNTY, exportUrl, type ContractItem, type Meta, type Page } from "@/lib/api";
import { lei, num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Contracte publice",
  description: "Toate contractele și achizițiile directe ale instituțiilor publice, cu filtre pe an, valoare, procedură și CPV.",
};

export default async function ContractsPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const page = pageNum(searchParams.page);
  const q = {
    county: DEFAULT_COUNTY,
    q: sp(searchParams.q),
    year: sp(searchParams.year),
    domain: sp(searchParams.domain),
    min_value: sp(searchParams.min_value),
    max_value: sp(searchParams.max_value),
    procedure_type: sp(searchParams.procedure_type),
    cpv: sp(searchParams.cpv),
    authority_id: sp(searchParams.authority_id),
    company: sp(searchParams.company),
    with_signals: sp(searchParams.with_signals) === "true",
    sort: sp(searchParams.sort) ?? "date_desc",
  };
  const [data, meta] = await Promise.all([
    api<Page<ContractItem>>("/contracts", { ...q, page, page_size: 25 }),
    api<Meta>("/meta", { county: DEFAULT_COUNTY }, 600),
  ]);
  const sum = data.items.reduce((s, c) => s + Number(c.value_ron ?? 0), 0);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl">Contracte publice</h1>
      <form method="get" className="grid gap-3 rounded-lg border bg-white p-4 md:grid-cols-4" aria-label="Filtre contracte">
        <div className="md:col-span-2">
          <label htmlFor="f-q" className="text-sm font-medium">Text (obiect, număr anunț)</label>
          <Input id="f-q" name="q" defaultValue={q.q} placeholder="ex. asfaltare, laptop, SCNA1126001" />
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
          <label htmlFor="f-proc" className="text-sm font-medium">Tip procedură</label>
          <Select id="f-proc" name="procedure_type" defaultValue={q.procedure_type ?? ""}>
            <option value="">Toate</option>
            {meta.procedure_types.map((p) => <option key={p}>{p}</option>)}
          </Select>
        </div>
        <div>
          <label htmlFor="f-min" className="text-sm font-medium">Valoare minimă (lei)</label>
          <Input id="f-min" name="min_value" type="number" min={0} inputMode="numeric" defaultValue={q.min_value} />
        </div>
        <div>
          <label htmlFor="f-max" className="text-sm font-medium">Valoare maximă (lei)</label>
          <Input id="f-max" name="max_value" type="number" min={0} inputMode="numeric" defaultValue={q.max_value} />
        </div>
        <div>
          <label htmlFor="f-cpv" className="text-sm font-medium"><Term id="cpv">Cod CPV</Term> (prefix)</label>
          <Input id="f-cpv" name="cpv" defaultValue={q.cpv} placeholder="ex. 45 sau 45233" inputMode="numeric" />
        </div>
        <div>
          <label htmlFor="f-sort" className="text-sm font-medium">Ordonare</label>
          <Select id="f-sort" name="sort" defaultValue={q.sort}>
            <option value="date_desc">Cele mai noi</option>
            <option value="date_asc">Cele mai vechi</option>
            <option value="value_desc">Valoare (desc.)</option>
            <option value="value_asc">Valoare (asc.)</option>
          </Select>
        </div>
        {q.authority_id && <input type="hidden" name="authority_id" value={q.authority_id} />}
        {q.company && <input type="hidden" name="company" value={q.company} />}
        <label className="flex items-center gap-2 text-sm md:col-span-4">
          <input type="checkbox" name="with_signals" value="true" defaultChecked={q.with_signals} /> Doar contractele cu semnale de verificat
        </label>
        <div className="flex flex-wrap gap-2 md:col-span-4">
          <Button type="submit">Aplică filtrele</Button>
          <Button variant="outline" asChild><a href="/contracte">Resetează</a></Button>
          <Button variant="outline" asChild><a href={exportUrl("contracts", q)}>Descarcă CSV</a></Button>
        </div>
      </form>
      <p className="text-sm text-muted-foreground" aria-live="polite" data-testid="result-count">
        {num(data.total)} rezultate{q.authority_id || q.company ? " (filtrat pe instituție/firmă)" : ""} · total pe această pagină: {lei(sum)}
      </p>
      <Card><CardContent className="pt-4"><ContractTable items={data.items} /></CardContent></Card>
      <Pagination base="/contracte" params={searchParams} page={page} pageSize={25} total={data.total} />
    </div>
  );
}
