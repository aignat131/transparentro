import type { Metadata } from "next";
import Link from "next/link";

import { CategoryChart, MonthChart } from "@/components/charts";
import { sp } from "@/components/pagination";
import { ALL_YEARS, hrefWith, pickYear, Pills, yearChoices } from "@/components/pills";
import { TotalsTable } from "@/components/tables";
import { Term } from "@/components/term";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, DEFAULT_COUNTY, exportUrl, type Meta, type NamedTotal, type SpendingReport } from "@/lib/api";
import { leiShort, num, pct } from "@/lib/format";

export const metadata: Metadata = {
  title: "Raport: pe ce s-au dus banii",
  description: "Toate achizițiile publice din județ, pe domenii, instituții, firme, proceduri și luni.",
};

function share(part: string, total: string): number | null {
  const t = Number(total);
  return t > 0 ? Number(part) / t : null;
}

function Block({ title, intro, children }: { title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {intro && <p className="text-sm text-muted-foreground">{intro}</p>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default async function ReportPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const county = DEFAULT_COUNTY;
  const meta = await api<Meta>("/meta", { county }, 600);
  const years = [...meta.years].sort((a, b) => b - a);
  const year = pickYear(sp(searchParams.year), years);
  const yq = year ?? undefined;
  const r = await api<SpendingReport>("/stats/report", { county, year: yq });
  const yearValue = year === null ? ALL_YEARS : String(year);
  const period = year === null ? "toți anii" : `anul ${year}`;
  const domainRows: NamedTotal[] = r.by_domain.map((d) => ({ ...d, key: d.key === "altele" ? null : d.key }));

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl md:text-3xl">Raport: pe ce s-au dus banii</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Toate contractele și achizițiile publice ale instituțiilor din județul {r.county_name}, adunate: pe domenii, pe
          instituții, pe firme, pe tipuri de procedură și pe luni.
        </p>
        <div className="mt-4 space-y-3 rounded-lg border bg-white p-4">
          <Pills label="Anul" choices={yearChoices(years)} selected={yearValue} href={(v) => `/raport?year=${v}`} />
          <p className="border-t pt-3 text-base">
            În <strong>{period}</strong>, {num(r.authorities)} instituții au încheiat <strong>{num(r.contracts)}</strong>{" "}
            contracte cu {num(r.companies)} furnizori, în valoare totală de <strong>{leiShort(r.total_ron)}</strong>.
          </p>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Raportul cuprinde doar <strong>achizițiile publice</strong> (cumpărări de produse, servicii și lucrări prin{" "}
          <Term id="seap">SEAP</Term>). Salariile, pensiile, subvențiile și alte plăți din buget nu trec prin SEAP și nu
          apar aici.
        </p>
      </section>

      <section aria-labelledby="pe-scurt" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <h2 id="pe-scurt" className="sr-only">Pe scurt</h2>
        {[
          ["Total contracte", leiShort(r.total_ron), `${num(r.contracts)} contracte`],
          ["Achiziții directe", leiShort(r.direct_awards_ron), `${pct(share(r.direct_awards_ron, r.total_ron))} din total, fără licitație`],
          ["Cu fonduri europene", leiShort(r.eu_funded_ron), `${pct(share(r.eu_funded_ron, r.total_ron))} din total`],
          ["Către ONG-uri", leiShort(r.ngo_total_ron), `${num(r.ngo_contracts)} contracte`],
        ].map(([label, value, hint]) => (
          <div key={label} className="rounded-lg border bg-white p-4">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular">{value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
          </div>
        ))}
      </section>

      <Block title="Pe domenii" intro="Apasă pe un domeniu ca să vezi firmele și contractele din el.">
        <TotalsTable rows={domainRows} linkBase={undefined} caption="Cheltuieli pe domenii" nameHeader="Domeniu" />
        <p className="mt-3 flex flex-wrap gap-2 text-sm">
          {r.by_domain
            .filter((d) => d.key && d.key !== "altele")
            .map((d) => (
              <Link key={d.key} href={hrefWith("/", { year: yearValue, domain: d.key })} className="rounded-full border px-3 py-1 no-underline">
                {d.name} →
              </Link>
            ))}
        </p>
      </Block>

      <div className="grid gap-6 lg:grid-cols-2">
        <Block title={`Pe luni (${period}, lei)`}>
          <MonthChart data={r.by_month} title="Valoarea contractelor pe luni" />
        </Block>
        <Block title="Pe ce s-au cheltuit banii (categorii, lei)">
          <CategoryChart data={r.by_category} title="Cheltuieli pe categorii" limit={10} />
        </Block>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Block title="Instituțiile care au cheltuit cel mai mult">
          <TotalsTable rows={r.top_authorities} linkBase="/institutii" caption="Instituțiile cu cele mai mari cheltuieli" nameHeader="Instituție" />
        </Block>
        <Block title="Firmele care au primit cei mai mulți bani">
          <TotalsTable rows={r.top_companies} linkBase="/firme" caption="Firmele cu cele mai mari sume" nameHeader="Firmă" />
        </Block>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Block title="Pe tipuri de instituții">
          <TotalsTable rows={r.by_authority_type} caption="Cheltuieli pe tipuri de instituții" nameHeader="Tip" />
        </Block>
        <Block title="Pe tipuri de procedură" intro={<>De exemplu <Term id="achizitie_directa">achiziție directă</Term> sau licitație.</>}>
          <TotalsTable rows={r.by_procedure_type} caption="Cheltuieli pe tipuri de procedură" nameHeader="Procedură" />
        </Block>
        <Block title="Produse, servicii sau lucrări">
          <TotalsTable rows={r.by_contract_type} caption="Cheltuieli pe tipuri de contract" nameHeader="Tip" />
        </Block>
      </div>

      <section className="rounded-lg border bg-white p-6">
        <h2 className="text-lg">Toate cheltuielile, rând cu rând</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Descarcă toate contractele din {period} (instituție, firmă, obiect, valoare, dată) și deschide-le în Excel.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild><a href={exportUrl("contracts", { county, year: yq })}>Descarcă contractele (CSV)</a></Button>
          <Button variant="outline" asChild><Link href={hrefWith("/contracte", { year: year ? String(year) : null, sort: "value_desc" })}>Vezi lista pe site</Link></Button>
        </div>
      </section>
    </div>
  );
}
