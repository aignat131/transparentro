import Link from "next/link";
import { ChevronDown, X } from "lucide-react";

import { ALL_YEARS, hrefWith, pickYear } from "@/components/pills";
import {
  api,
  DEFAULT_COUNTY,
  type AuthorityItem,
  type CompanyItem,
  type Meta,
  type Page,
  type Signal,
  type SpendingReport,
} from "@/lib/api";
import { leiShort, num } from "@/lib/format";

// Prima pagină, gândită pentru telefon și pentru cetățeanul curios:
// cât s-a cheltuit → pe ce → cine a primit banii → cine i-a dat → ce merită verificat.

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return <h2 id={id} className="text-xl md:text-2xl">{children}</h2>;
}

function More({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="mt-3 inline-block font-medium">
      {children} →
    </Link>
  );
}

function YearMenu({ years, year, domain }: { years: number[]; year: number | null; domain: string | null }) {
  const label = year === null ? "toți anii" : String(year);
  const choices = [...years.map(String), ALL_YEARS];
  return (
    <details className="relative inline-block">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-full border bg-white px-3 py-1 text-sm [&::-webkit-details-marker]:hidden">
        Anul: <strong>{label}</strong> <ChevronDown className="h-4 w-4" aria-hidden />
      </summary>
      <ul className="absolute left-0 z-40 mt-2 w-40 rounded-lg border bg-white py-1 shadow-lg">
        {choices.map((y) => (
          <li key={y}>
            <Link href={hrefWith("/", { year: y, domain })} scroll={false}
              className="block px-4 py-2 text-foreground no-underline hover:bg-slate-50">
              {y === ALL_YEARS ? "Toți anii" : y}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}

function Card({ href, title, amount, lines }: { href: string; title: string; amount: string; lines: (string | null)[] }) {
  return (
    <li>
      <Link href={href} className="block h-full rounded-lg border bg-white p-4 text-foreground no-underline hover:border-primary">
        <div className="flex items-start justify-between gap-3">
          <p className="font-semibold leading-snug">{title}</p>
          <p className="shrink-0 font-semibold tabular text-primary">{amount}</p>
        </div>
        {lines.filter(Boolean).map((l) => (
          <p key={l} className="mt-1 text-sm text-muted-foreground">{l}</p>
        ))}
      </Link>
    </li>
  );
}

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const county = DEFAULT_COUNTY;
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
  const meta = await api<Meta>("/meta", { county }, 600);
  const years = [...meta.years].sort((a, b) => b - a);
  const year = pickYear(one(searchParams.year), years);
  const domain = (meta.domains ?? []).find((d) => d.key === one(searchParams.domain)) ?? null;
  const yq = year ?? undefined;
  const dq = domain?.key;
  const [report, companies, authorities, signals] = await Promise.all([
    api<SpendingReport>("/stats/report", { county, year: yq }),
    api<Page<CompanyItem>>("/companies", { county, year: yq, domain: dq, context: true, sort: "total_desc", page_size: 6 }),
    api<Page<AuthorityItem>>("/authorities", { county, year: yq, domain: dq, context: true, sort: "total_desc", page_size: 5 }),
    dq ? null : api<Page<Signal>>("/risk-signals", { county, year: yq, sort: "score_desc", page_size: 3 }),
  ]);
  const yearValue = year === null ? ALL_YEARS : String(year);
  const dom = domain ? report.by_domain.find((d) => d.key === domain.key) : null;
  const shown = dom ? dom.total_ron : report.total_ron;
  const maxShare = Math.max(...report.by_domain.map((d) => d.share ?? 0), 0.01);
  const when = year === null ? "În toți anii pentru care avem date" : `În ${year}`;
  const withFilters = (path: string) => hrefWith(path, { year: yearValue, domain: dq });

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <section aria-labelledby="cat" className="pt-2">
        <YearMenu years={years} year={year} domain={dq ?? null} />
        <h1 id="cat" className="mt-4 text-2xl leading-tight md:text-4xl">
          {when}, instituțiile publice din județul {report.county_name} au dat{" "}
          <span className="text-primary">{leiShort(shown)}</span> pe contracte
          {domain ? <> pentru <span className="text-primary">{domain.label.toLowerCase()}</span></> : null}.
        </h1>
        {year !== null && year === new Date().getFullYear() && (
          <p className="mt-2 text-sm text-muted-foreground">Anul nu s-a încheiat, datele sunt parțiale.</p>
        )}
      </section>

      <section aria-labelledby="pe-ce">
        <H2 id="pe-ce">Pe ce s-au dus banii</H2>
        <p className="mt-1 text-sm text-muted-foreground">Apasă pe un domeniu ca să vezi doar firmele și instituțiile din el.</p>
        <ul className="mt-4 space-y-2">
          {report.by_domain
            .filter((d) => d.key !== "altele")
            .map((d) => {
              const active = d.key === dq;
              return (
                <li key={d.key}>
                  <Link
                    href={hrefWith("/", { year: yearValue, domain: active ? null : d.key })}
                    scroll={false}
                    aria-current={active ? "true" : undefined}
                    className={`block rounded-md px-2 py-1.5 text-foreground no-underline hover:bg-white ${active ? "bg-white ring-2 ring-primary" : ""}`}
                  >
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span className="font-medium">{d.name}</span>
                      <span className="shrink-0 tabular text-muted-foreground">{leiShort(d.total_ron)}</span>
                    </div>
                    <div className="mt-1 h-2.5 rounded-full bg-slate-100" aria-hidden>
                      <div className="h-2.5 rounded-full bg-primary" style={{ width: `${Math.max(((d.share ?? 0) / maxShare) * 100, 1)}%` }} />
                    </div>
                  </Link>
                </li>
              );
            })}
        </ul>
        {domain && (
          <Link href={hrefWith("/", { year: yearValue })} scroll={false} className="mt-3 inline-flex items-center gap-1 text-sm">
            <X className="h-4 w-4" aria-hidden /> Toate domeniile
          </Link>
        )}
      </section>

      <section aria-labelledby="cine-a-primit">
        <H2 id="cine-a-primit">Cine a primit cei mai mulți bani{domain ? ` (${domain.label.toLowerCase()})` : ""}</H2>
        <ul className="mt-4 grid gap-3 md:grid-cols-2">
          {companies.items.map((c) => (
            <Card
              key={c.key}
              href={`/firme/${encodeURIComponent(c.key)}`}
              title={c.name}
              amount={leiShort(c.total_ron)}
              lines={[
                c.top_category && c.top_client ? `${c.top_category}, mai ales pentru ${c.top_client}` : c.top_category ?? null,
                `${num(c.contracts)} ${c.contracts === 1 ? "contract" : "contracte"}`,
              ]}
            />
          ))}
        </ul>
        <More href={withFilters("/firme")}>Vezi toate firmele</More>
      </section>

      <section aria-labelledby="cine-a-dat">
        <H2 id="cine-a-dat">Cine a cheltuit cel mai mult</H2>
        <ul className="mt-4 grid gap-3 md:grid-cols-2">
          {authorities.items.map((a) => (
            <Card
              key={a.id}
              href={`/institutii/${a.id}`}
              title={a.name}
              amount={leiShort(a.total_ron)}
              lines={[
                a.top_category ? `Cel mai mult pe: ${a.top_category.toLowerCase()}` : null,
                a.top_supplier ? `Furnizorul principal: ${a.top_supplier}` : null,
              ]}
            />
          ))}
        </ul>
        <More href={withFilters("/institutii")}>Vezi toate instituțiile</More>
      </section>

      {signals && signals.items.length > 0 && (
        <section aria-labelledby="verificat">
          <H2 id="verificat">Merită verificat</H2>
          <p className="mt-1 text-sm text-muted-foreground">
            Situații neobișnuite găsite automat în date. <strong>Nu sunt acuzații</strong>: pot avea explicații legitime.
          </p>
          <ul className="mt-4 space-y-3">
            {signals.items.map((s) => (
              <li key={s.id}>
                <Link href={s.contract_id ? `/contracte/${s.contract_id}` : "/semnale"}
                  className="block rounded-lg border border-amber-200 bg-amber-50 p-4 text-foreground no-underline hover:border-amber-400">
                  <p className="text-xs font-medium uppercase tracking-wide text-amber-800">{s.signal_label}</p>
                  <p className="mt-1 font-semibold leading-snug">{s.title}</p>
                  <p className="mt-1 text-sm text-slate-700">{s.explanation}</p>
                </Link>
              </li>
            ))}
          </ul>
          <More href="/semnale">Toate semnalele</More>
        </section>
      )}

      <section aria-labelledby="mai-mult" className="rounded-lg border bg-white p-5">
        <h2 id="mai-mult" className="text-lg">Vrei mai mult?</h2>
        <ul className="mt-2 space-y-2 text-sm">
          <li><Link href={hrefWith("/raport", { year: yearValue })}>Raportul complet</Link>: toate cheltuielile pe domenii, luni, proceduri.</li>
          <li><Link href={hrefWith("/ong", { year: yearValue })}>ONG-urile</Link> care au primit bani publici.</li>
          <li><Link href="/cautare">Caută</Link> o firmă, o instituție sau un contract.</li>
          <li><Link href="/metodologie">Cum citim datele</Link> și de unde vin.</li>
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Date oficiale din SEAP: {num(report.contracts)} contracte{year === null ? "" : ` în ${year}`}.
        </p>
      </section>
    </div>
  );
}
