import Link from "next/link";

import { CategoryChart, YearChart } from "@/components/charts";
import { ContractTable, TotalsTable } from "@/components/tables";
import { Term } from "@/components/term";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  api,
  DEFAULT_COUNTY,
  type AuthorityItem,
  type CompanyItem,
  type ContractItem,
  type NamedTotal,
  type Meta,
  type Overview,
  type Page,
} from "@/lib/api";
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

function shareOf(total: string | null, all: string): number | null {
  const t = Number(total ?? 0);
  const a = Number(all);
  return a > 0 ? t / a : null;
}

function Section({ id, title, intro, more, children }: {
  id: string;
  title: string;
  intro?: React.ReactNode;
  more?: { href: string; label: string };
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id}>
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={id} className="text-xl">{title}</h2>
        {more && <Link href={more.href}>{more.label} →</Link>}
      </div>
      {intro && <p className="mb-3 text-sm text-muted-foreground">{intro}</p>}
      <Card>
        <CardContent className="pt-4">{children}</CardContent>
      </Card>
    </section>
  );
}

const ALL_YEARS = "toti";

type Choice = { value: string | null; label: string };

function Pills({ label, choices, selected, href }: {
  label: string;
  choices: Choice[];
  selected: string | null;
  href: (value: string | null) => string;
}) {
  const pill = "rounded-full border px-3 py-1 text-sm no-underline transition-colors";
  const on = "border-primary bg-primary text-primary-foreground";
  const off = "bg-white text-foreground hover:border-primary hover:text-primary";
  return (
    <nav aria-label={`Alege ${label.toLowerCase()}`} className="flex flex-wrap items-center gap-2">
      <span className="w-full text-sm font-medium sm:w-20">{label}:</span>
      {choices.map((c) => {
        const active = c.value === selected;
        return (
          <Link key={c.value ?? "_"} href={href(c.value)} scroll={false} aria-current={active ? "page" : undefined}
            className={`${pill} ${active ? on : off}`}>
            {c.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const county = DEFAULT_COUNTY;
  const meta = await api<Meta>("/meta", { county }, 600);
  const years = [...meta.years].sort((a, b) => b - a);
  const domains = meta.domains ?? [];
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
  const raw = one(searchParams.year);
  // implicit: cel mai recent an cu date; „toti” = toți anii
  const year: number | null =
    raw === ALL_YEARS ? null : raw && years.includes(Number(raw)) ? Number(raw) : (years[0] ?? null);
  const rawDomain = one(searchParams.domain);
  const domain = domains.find((d) => d.key === rawDomain) ?? null;
  const yq = year ?? undefined;
  const dq = domain?.key;
  const [ov, ovAll, companies, biggest, authorities, ngos] = await Promise.all([
    api<Overview>("/stats/overview", { county, year: yq, domain: dq }),
    year === null ? null : api<Overview>("/stats/overview", { county, domain: dq }),
    api<Page<CompanyItem>>("/companies", { county, year: yq, domain: dq, sort: "total_desc", page_size: 15 }),
    api<Page<ContractItem>>("/contracts", { county, year: yq, domain: dq, sort: "value_desc", page_size: 10 }),
    api<Page<AuthorityItem>>("/authorities", { county, year: yq, domain: dq, sort: "total_desc", page_size: 10 }),
    api<Page<CompanyItem>>("/companies", { county, year: yq, domain: dq, ngo: true, sort: "total_desc", page_size: 5 }),
  ]);
  const countyName = ov.county_name ?? "județ";
  const inYear = year === null ? "" : ` în ${year}`;
  const filterParams = [year === null ? "" : `year=${year}`, dq ? `domain=${dq}` : ""];
  const withYear = (path: string, extra = "") => {
    const q = [...filterParams, extra].filter(Boolean).join("&");
    return q ? `${path}?${q}` : path;
  };
  // linkurile din selectoare păstrează celălalt filtru
  const homeHref = (y: string | null, d: string | null) => {
    const q = [y ? `year=${y}` : "", d ? `domain=${d}` : ""].filter(Boolean).join("&");
    return q ? `/?${q}` : "/";
  };
  const yearValue = year === null ? ALL_YEARS : String(year);
  const yearChoices: Choice[] = [
    ...years.map((y) => ({ value: String(y), label: String(y) })),
    { value: ALL_YEARS, label: "Toți anii" },
  ];
  const domainChoices: Choice[] = [{ value: null, label: "Toate" }, ...domains.map((d) => ({ value: d.key, label: d.label }))];
  const coverageTo = ov.data.coverage_to;
  const yearUnfinished =
    year !== null && year === years[0] && coverageTo != null && coverageTo < `${year}-12-31`;
  const firmRows: NamedTotal[] = companies.items.map((c) => ({
    key: c.key,
    name: c.name,
    count: c.contracts,
    total_ron: c.total_ron ?? "0",
    share: shareOf(c.total_ron, ov.total_ron),
  }));
  const ngoRows: NamedTotal[] = ngos.items.map((c) => ({
    key: c.key,
    name: c.name,
    count: c.contracts,
    total_ron: c.total_ron ?? "0",
    share: shareOf(c.total_ron, ov.total_ron),
  }));
  const authorityRows: NamedTotal[] = authorities.items.map((a) => ({
    key: String(a.id),
    name: a.name,
    count: a.contracts,
    total_ron: a.total_ron ?? "0",
    share: shareOf(a.total_ron, ov.total_ron),
  }));
  return (
    <div className="space-y-10">
      <section className="py-4">
        <h1 className="text-3xl md:text-4xl">Unde se duc banii publici din județul {countyName}?</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Ce firme au încasat cei mai mulți bani de la instituțiile publice, de la cine și pentru ce.
        </p>
        <div className="mt-5 space-y-3 rounded-lg border bg-white p-4">
          <Pills label="Anul" choices={yearChoices} selected={yearValue} href={(v) => homeHref(v, dq ?? null)} />
          {domains.length > 0 && (
            <Pills label="Domeniul" choices={domainChoices} selected={dq ?? null} href={(v) => homeHref(yearValue, v)} />
          )}
          <p className="border-t pt-3 text-base">
            {year === null ? (
              <>Vezi datele pentru <strong>toți anii</strong></>
            ) : (
              <>Vezi datele pentru anul <strong>{year}</strong></>
            )}
            {domain ? (
              <>, domeniul <strong>{domain.label}</strong></>
            ) : (
              <>, <strong>toate domeniile</strong></>
            )}
            {ov.data.coverage_from && (
              <span className="text-muted-foreground"> ({date(ov.data.coverage_from)} – {date(coverageTo)})</span>
            )}
            : {num(ov.contracts)} contracte în valoare de <strong>{leiShort(ov.total_ron)}</strong>.
          </p>
          {yearUnfinished && (
            <p className="text-sm text-amber-800">
              Anul {year} nu s-a încheiat: datele sunt până la {date(coverageTo)}. Alege un an anterior pentru un an complet.
            </p>
          )}
        </div>
      </section>

      <Section
        id="firme"
        title={`Firmele care au primit cei mai mulți bani${inYear}`}
        intro="Totalul contractelor câștigate de la instituțiile publice din județ. Apasă pe o firmă ca să vezi de la cine a primit banii și pentru ce."
        more={{ href: withYear("/firme"), label: `Toate cele ${num(ov.companies)} firme` }}
      >
        <TotalsTable rows={firmRows} linkBase="/firme" caption="Firmele cu cele mai mari sume" nameHeader="Firmă" />
      </Section>

      <Section
        id="mari"
        title={`Cele mai mari contracte${inYear}`}
        intro="Cine a plătit, cui și pentru ce — ordonate după valoare."
        more={{ href: withYear("/contracte", "sort=value_desc"), label: "Toate contractele" }}
      >
        <ContractTable items={biggest.items} />
      </Section>

      <Section
        id="institutii"
        title={`Instituțiile care au cheltuit cel mai mult${inYear}`}
        more={{ href: withYear("/institutii"), label: `Toate cele ${num(ov.authorities)} instituții` }}
      >
        <TotalsTable rows={authorityRows} linkBase="/institutii" caption="Instituțiile cu cele mai mari cheltuieli" nameHeader="Instituție" />
      </Section>

      {ngoRows.length > 0 && (
        <Section
          id="ong"
          title={`ONG-urile care au primit cei mai mulți bani${inYear}`}
          intro="Asociații, fundații și cluburi sportive plătite de instituțiile publice prin contracte."
          more={{ href: withYear("/ong"), label: `Toate cele ${num(ngos.total)} ONG-uri` }}
        >
          <TotalsTable rows={ngoRows} linkBase="/firme" caption="ONG-urile cu cele mai mari sume" nameHeader="ONG" />
        </Section>
      )}

      <section aria-labelledby="cifre">
        <h2 id="cifre" className="mb-3 text-xl">Pe scurt{year === null ? "" : ` (${year})`}</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="Valoare totală contracte" value={leiShort(ov.total_ron)} hint={year === null ? "toți anii" : `anul ${year}`} />
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
            <YearChart data={(ovAll ?? ov).by_year} title="Valoarea contractelor pe ani" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Pe ce s-au cheltuit banii{inYear} (lei)</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryChart data={ov.by_category} title="Cheltuieli pe categorii" limit={7} />
          </CardContent>
        </Card>
      </div>

      <section aria-labelledby="ultimele">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="ultimele" className="text-xl">Ultimele contracte{inYear}</h2>
          <Link href={withYear("/contracte")}>Toate contractele →</Link>
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
