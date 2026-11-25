import Link from "next/link";
import { Bell, Briefcase, ChevronDown, MapPin, X } from "lucide-react";

import { ALL_YEARS, hrefWith, pickYear } from "@/components/pills";
import { StoryCard, toStories } from "@/components/story";
import {
  api,
  DEFAULT_COUNTY,
  type ContractItem,
  type Locality,
  type Meta,
  type Page,
  type Signal,
  type SpendingReport,
} from "@/lib/api";
import { leiShort, num } from "@/lib/format";

// Prima pagină, pentru cetățeanul curios, pe telefon:
// un cârlig (cât, cât pe locuitor) → ce s-a întâmplat la tine → povești (cele mai mari, recente, neobișnuite)
// → pe ce s-au dus banii → ce poți face.

function H2({ id, children, intro }: { id: string; children: React.ReactNode; intro?: React.ReactNode }) {
  return (
    <div>
      <h2 id={id} className="text-xl md:text-2xl">{children}</h2>
      {intro && <p className="mt-1 text-sm text-muted-foreground">{intro}</p>}
    </div>
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

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const county = DEFAULT_COUNTY;
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
  const meta = await api<Meta>("/meta", { county }, 600);
  const years = [...meta.years].sort((a, b) => b - a);
  const year = pickYear(one(searchParams.year), years);
  const domain = (meta.domains ?? []).find((d) => d.key === one(searchParams.domain)) ?? null;
  const yq = year ?? undefined;
  const dq = domain?.key;
  const [report, localities, biggest, recent, signals] = await Promise.all([
    api<SpendingReport>("/stats/report", { county, year: yq }),
    api<Locality[]>("/localities", { county, year: yq }, 600),
    api<Page<ContractItem>>("/contracts", { county, year: yq, domain: dq, sort: "value_desc", page_size: 12 }),
    // „recente” interesante: peste 50.000 lei, ca să nu apară pixuri și hârtie
    api<Page<ContractItem>>("/contracts", { county, year: yq, domain: dq, sort: "date_desc", min_value: 50_000, page_size: 12 }),
    dq ? null : api<Page<Signal>>("/risk-signals", { county, year: yq, sort: "score_desc", page_size: 3 }),
  ]);
  const yearValue = year === null ? ALL_YEARS : String(year);
  const dom = domain ? report.by_domain.find((d) => d.key === domain.key) : null;
  const shown = dom ? dom.total_ron : report.total_ron;
  const perPerson = meta.population ? Number(shown) / meta.population : null;
  const maxShare = Math.max(...report.by_domain.map((d) => d.share ?? 0), 0.01);
  const when = year === null ? "În toți anii pentru care avem date" : `În ${year}`;
  const topPlaces = localities.filter((l) => l.contracts > 0).slice(0, 8);

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <section aria-labelledby="cat" className="pt-2">
        <YearMenu years={years} year={year} domain={dq ?? null} />
        <h1 id="cat" className="mt-4 text-2xl leading-tight md:text-4xl">
          {when}, instituțiile publice din județul {report.county_name} au cheltuit{" "}
          <span className="text-primary">{leiShort(shown)}</span> pe contracte
          {domain ? <> pentru <span className="text-primary">{domain.label.toLowerCase()}</span></> : null}.
        </h1>
        {perPerson !== null && perPerson > 0 && (
          <p className="mt-3 text-lg">
            Cam <strong>{num(Math.round(perPerson / 10) * 10)} lei</strong> pentru fiecare locuitor al județului.
          </p>
        )}
        {year !== null && year === new Date().getFullYear() && (
          <p className="mt-1 text-sm text-muted-foreground">Anul nu s-a încheiat, datele sunt parțiale.</p>
        )}
      </section>

      <section aria-labelledby="la-tine" className="rounded-lg border bg-white p-4">
        <h2 id="la-tine" className="flex items-center gap-2 text-lg">
          <MapPin className="h-5 w-5 text-primary" aria-hidden /> Ce s-a cheltuit la tine?
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">Alege localitatea: vezi școlile, primăria și ce s-a cumpărat acolo.</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {topPlaces.map((l) => (
            <li key={l.slug}>
              <Link href={`/localitate/${l.slug}`} className="inline-block rounded-full border px-3 py-1 text-sm no-underline hover:border-primary">
                {l.name}
              </Link>
            </li>
          ))}
          <li>
            <Link href="/localitati" className="inline-block rounded-full border border-primary px-3 py-1 text-sm font-medium no-underline">
              Toate localitățile →
            </Link>
          </li>
        </ul>
      </section>

      <section aria-labelledby="mari" className="space-y-3">
        <H2 id="mari" intro="Contractele cu cele mai mari sume. Apasă pe unul ca să vezi detaliile și sursa oficială.">
          Cele mai mari cheltuieli{domain ? ` (${domain.label.toLowerCase()})` : ""}
        </H2>
        <ul className="space-y-3">
          {toStories(biggest.items, 5).map((st, i) => <StoryCard key={st.c.id} c={st.c} partners={st.partners} badge={`Locul ${i + 1}`} />)}
        </ul>
      </section>

      <section aria-labelledby="recente" className="space-y-3">
        <H2 id="recente" intro="Ultimele contracte de peste 50.000 lei.">Cele mai recente</H2>
        <ul className="space-y-3">
          {toStories(recent.items, 5).map((st) => <StoryCard key={st.c.id} c={st.c} partners={st.partners} />)}
        </ul>
        <Link href={hrefWith("/contracte", { year: year ? String(year) : null, domain: dq })} className="inline-block font-medium">
          Toate contractele →
        </Link>
      </section>

      {signals && signals.items.length > 0 && (
        <section aria-labelledby="neobisnuite" className="space-y-3">
          <H2 id="neobisnuite" intro={<>Situații ieșite din tipar, găsite automat. <strong>Nu sunt acuzații</strong>: pot avea explicații legitime.</>}>
            Neobișnuite
          </H2>
          <ul className="space-y-3">
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
          <Link href="/semnale" className="inline-block font-medium">Toate situațiile de verificat →</Link>
        </section>
      )}

      <section aria-labelledby="pe-ce">
        <H2 id="pe-ce" intro="Apasă pe un domeniu ca să vezi doar poveștile din el.">Pe ce s-au dus banii</H2>
        <ul className="mt-4 space-y-2">
          {report.by_domain
            .filter((d) => d.key !== "altele")
            .map((d) => {
              const active = d.key === dq;
              return (
                <li key={d.key}>
                  <Link
                    href={hrefWith("/", { year: yearValue, domain: active ? null : d.key })}
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
          <Link href={hrefWith("/", { year: yearValue })} className="mt-3 inline-flex items-center gap-1 text-sm">
            <X className="h-4 w-4" aria-hidden /> Toate domeniile
          </Link>
        )}
      </section>

      <section aria-labelledby="ce-poti-face" className="space-y-3">
        <H2 id="ce-poti-face">Ce poți face</H2>
        <ul className="grid gap-3 md:grid-cols-2">
          <li className="rounded-lg border bg-white p-4">
            <p className="flex items-center gap-2 font-semibold"><Bell className="h-4 w-4 text-primary" aria-hidden /> Urmărește</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Primești e-mail când primăria ta, școala copilului sau o firmă are un contract nou. Intră pe pagina instituției și apasă „Anunță-mă”.
            </p>
            <Link href="/localitati" className="mt-2 inline-block text-sm font-medium">Alege localitatea →</Link>
          </li>
          <li className="rounded-lg border bg-white p-4">
            <p className="flex items-center gap-2 font-semibold"><Briefcase className="h-4 w-4 text-primary" aria-hidden /> Ești firmă sau ONG?</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Licitațiile deschise acum, cine a câștigat recent, ce cumpără instituțiile în fiecare an și finanțările pentru ONG-uri.
            </p>
            <Link href="/oportunitati" className="mt-2 inline-block text-sm font-medium">Vezi oportunitățile →</Link>
          </li>
        </ul>
        <p className="text-sm">
          Mai mult: <Link href={hrefWith("/raport", { year: yearValue })}>raportul complet</Link> ·{" "}
          <Link href="/firme">firmele</Link> · <Link href="/institutii">instituțiile</Link> ·{" "}
          <Link href={hrefWith("/ong", { year: yearValue })}>ONG-urile</Link> · <Link href="/metodologie">cum citim datele</Link>
        </p>
      </section>
    </div>
  );
}
