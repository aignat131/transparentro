import Link from "next/link";

import { CategoryChart, YearChart } from "@/components/charts";
import { SearchBar } from "@/components/search-bar";
import { ContractTable } from "@/components/tables";
import { Term } from "@/components/term";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, DEFAULT_COUNTY, type Overview } from "@/lib/api";
import { date, leiShort, num, pct } from "@/lib/format";

function Stat({ label, value, hint }: { label: string; value: string; hint?: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default async function Home() {
  const ov = await api<Overview>("/stats/overview", { county: DEFAULT_COUNTY });
  const county = ov.county_name ?? "județ";
  return (
    <div className="space-y-10">
      <section className="mx-auto max-w-3xl py-6 text-center">
        <h1 className="text-3xl md:text-4xl">Pe ce se cheltuie banii publici în județul {county}?</h1>
        <p className="mt-3 text-muted-foreground">
          Contractele instituțiilor publice, firmele care le câștigă și situațiile care merită verificate — din date
          oficiale, explicate simplu.
        </p>
        <div className="mt-6">
          <SearchBar large />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Exemple: <Link href="/cautare?q=primaria">primăria</Link> · <Link href="/cautare?q=spital">spital</Link> ·{" "}
          <Link href="/cautare?q=drumuri">drumuri</Link> · sau un CUI
        </p>
      </section>

      <section aria-labelledby="cifre">
        <h2 id="cifre" className="mb-3 text-xl">Cifre-cheie pentru județul {county}</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="Valoare totală contracte" value={leiShort(ov.total_ron)} hint={ov.data.coverage_from ? `${date(ov.data.coverage_from)} – ${date(ov.data.coverage_to)}` : undefined} />
          <Stat label="Contracte și achiziții" value={num(ov.contracts)} />
          <Stat label="Instituții cumpărătoare" value={num(ov.authorities)} />
          <Stat label="Firme furnizoare" value={num(ov.companies)} />
          <Stat
            label="Semnale de verificat"
            value={num(ov.signals)}
            hint={<Link href="/semnale">vezi semnalele</Link>}
          />
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          <Term id="achizitie_directa">Achizițiile directe</Term> reprezintă {pct(ov.direct_awards_share)} din valoarea totală.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Valoarea contractelor, pe ani (lei)</CardTitle>
          </CardHeader>
          <CardContent>
            <YearChart data={ov.by_year} title="Valoarea contractelor pe ani" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Pe ce s-au cheltuit banii (lei)</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryChart data={ov.by_category} title="Cheltuieli pe categorii" limit={7} />
          </CardContent>
        </Card>
      </div>

      <section aria-labelledby="ultimele">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="ultimele" className="text-xl">Ultimele contracte</h2>
          <Link href="/contracte">Toate contractele →</Link>
        </div>
        <Card>
          <CardContent className="pt-4">
            <ContractTable items={ov.latest_contracts} />
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="cum" className="rounded-lg border bg-white p-6">
        <h2 id="cum" className="text-xl">Cum citesc datele?</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">
          <li>
            <strong>Instituția</strong> (<Term id="autoritate_contractanta">autoritatea contractantă</Term>) cumpără produse,
            servicii sau lucrări. Fiecare contract are o valoare în lei și un cod <Term id="cpv">CPV</Term> care arată ce s-a cumpărat.
          </li>
          <li>
            Contractele mici se fac prin <Term id="achizitie_directa">achiziție directă</Term>; cele mari prin proceduri
            competitive, ca <Term id="licitatie_deschisa">licitația deschisă</Term>.
          </li>
          <li>
            Contractele pot fi modificate prin <Term id="act_aditional">acte adiționale</Term>. Toate valorile sunt în lei.
          </li>
          <li>
            <Term id="semnal">Semnalele</Term> marchează situații care merită verificate — <strong>nu sunt acuzații</strong>.
          </li>
        </ol>
        <p className="mt-3 text-sm">
          <Link href="/metodologie">Metodologia completă</Link> · <Link href="/glosar">Glosar</Link> ·{" "}
          <Link href="/surse-de-date">De unde vin datele</Link>
        </p>
      </section>
    </div>
  );
}
