import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AskBox } from "@/components/actions";
import { SubscribeForm } from "@/components/forms";
import { sp } from "@/components/pagination";
import { ALL_YEARS, hrefWith, pickYear, Pills, yearChoices } from "@/components/pills";
import { StoryCard, toStories } from "@/components/story";
import {
  api,
  DEFAULT_COUNTY,
  type AuthorityItem,
  type ContractItem,
  type Locality,
  type Meta,
  type Page,
  type ProcedureItem,
  type SpendingReport,
} from "@/lib/api";
import { lei, leiShort, num, prettyName } from "@/lib/format";

const PRIMARIE = "Primărie / administrație locală";

async function findLocality(slug: string): Promise<Locality> {
  const all = await api<Locality[]>("/localities", { county: DEFAULT_COUNTY }, 600);
  const l = all.find((x) => x.slug === slug);
  if (!l) notFound();
  return l;
}

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const l = await findLocality(params.slug);
  return {
    title: `${l.name}: unde se duc banii publici`,
    description: `Ce au cumpărat primăria, școlile și instituțiile din ${l.name}, de la cine și cu cât.`,
  };
}

export default async function LocalityPage({ params, searchParams }: {
  params: { slug: string };
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const county = DEFAULT_COUNTY;
  const loc = await findLocality(params.slug);
  const meta = await api<Meta>("/meta", { county }, 600);
  const years = [...meta.years].sort((a, b) => b - a);
  const year = pickYear(sp(searchParams.year), years);
  const yq = year ?? undefined;
  const q = { county, locality: loc.slug };
  const [report, authorities, biggest, recent, open] = await Promise.all([
    api<SpendingReport>("/stats/report", { ...q, year: yq }),
    api<Page<AuthorityItem>>("/authorities", { ...q, year: yq, context: true, sort: "total_desc", page_size: 50 }),
    api<Page<ContractItem>>("/contracts", { ...q, year: yq, sort: "value_desc", page_size: 12 }),
    api<Page<ContractItem>>("/contracts", { ...q, year: yq, sort: "date_desc", min_value: 10_000, page_size: 12 }),
    api<Page<ProcedureItem>>("/procedures", { ...q, status: "open", sort: "recent", page_size: 5 }),
  ]);
  const yearValue = year === null ? ALL_YEARS : String(year);
  const when = year === null ? "În toți anii" : `În ${year}`;
  const active = authorities.items.filter((a) => a.contracts > 0);
  const primarie = authorities.items.find((a) => a.authority_type === PRIMARIE) ?? null;
  const maxShare = Math.max(...report.by_domain.map((d) => d.share ?? 0), 0.01);

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <nav aria-label="Fir de navigare" className="text-sm text-muted-foreground">
        <Link href="/localitati">Localități</Link> / {loc.name}
      </nav>
      <section>
        <h1 className="text-2xl leading-tight md:text-4xl">
          {when}, instituțiile din {loc.name} au cheltuit <span className="text-primary">{leiShort(report.total_ron)}</span>
          {report.contracts > 0 && <> prin {num(report.contracts)} contracte</>}.
        </h1>
        <div className="mt-4">
          <Pills label="Anul" choices={yearChoices(years)} selected={yearValue} href={(v) => hrefWith(`/localitate/${loc.slug}`, { year: v })} />
        </div>
      </section>

      {report.contracts > 0 && (
        <section aria-labelledby="pe-ce">
          <h2 id="pe-ce" className="text-xl">Pe ce</h2>
          <ul className="mt-3 space-y-2">
            {report.by_domain.filter((d) => Number(d.total_ron) > 0).slice(0, 6).map((d) => (
              <li key={d.name}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{d.name}</span>
                  <span className="shrink-0 tabular text-muted-foreground">{leiShort(d.total_ron)}</span>
                </div>
                <div className="mt-1 h-2.5 rounded-full bg-slate-100" aria-hidden>
                  <div className="h-2.5 rounded-full bg-primary" style={{ width: `${Math.max(((d.share ?? 0) / maxShare) * 100, 1)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {biggest.items.length > 0 && (
        <section aria-labelledby="mari" className="space-y-3">
          <h2 id="mari" className="text-xl">Cele mai mari cheltuieli</h2>
          <ul className="space-y-3">{toStories(biggest.items, 5).map((st, i) => <StoryCard key={st.c.id} c={st.c} partners={st.partners} badge={`Locul ${i + 1}`} />)}</ul>
        </section>
      )}

      {recent.items.length > 0 && (
        <section aria-labelledby="recente" className="space-y-3">
          <h2 id="recente" className="text-xl">Cele mai recente</h2>
          <ul className="space-y-3">{toStories(recent.items, 5).map((st) => <StoryCard key={st.c.id} c={st.c} partners={st.partners} />)}</ul>
          <Link href={hrefWith("/contracte", { locality: loc.slug, year: year ? String(year) : null })} className="inline-block font-medium">
            Toate contractele din {loc.name} →
          </Link>
        </section>
      )}

      <section aria-labelledby="institutii" className="space-y-3">
        <h2 id="institutii" className="text-xl">Instituțiile din {loc.name}</h2>
        <ul className="grid gap-3 md:grid-cols-2">
          {active.map((a) => (
            <li key={a.id}>
              <Link href={`/institutii/${a.id}`} className="block h-full rounded-lg border bg-white p-4 text-foreground no-underline hover:border-primary">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold leading-snug">{prettyName(a.name)}</p>
                  <p className="shrink-0 font-semibold tabular text-primary">{leiShort(a.total_ron)}</p>
                </div>
                {a.top_category && <p className="mt-1 text-sm text-muted-foreground">Cel mai mult pe {a.top_category.toLowerCase()}</p>}
                {a.top_supplier && <p className="text-sm text-muted-foreground">Furnizor principal: {prettyName(a.top_supplier)}</p>}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {open.items.length > 0 && (
        <section aria-labelledby="deschise" className="space-y-3">
          <h2 id="deschise" className="text-xl">Licitații deschise acum în {loc.name}</h2>
          <ul className="divide-y rounded-lg border bg-white">
            {open.items.map((p) => (
              <li key={p.id} className="p-4">
                <p className="font-medium leading-snug">{p.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {prettyName(p.authority.name)} · {p.estimated_value_ron ? lei(p.estimated_value_ron) : "valoare nepublicată"}
                </p>
                <a href={p.official_url} target="_blank" rel="noopener noreferrer" className="text-sm">Anunțul oficial →</a>
              </li>
            ))}
          </ul>
          <Link href={hrefWith("/oportunitati", { locality: loc.slug })} className="inline-block font-medium">Toate oportunitățile →</Link>
        </section>
      )}

      {primarie && (
        <section aria-labelledby="actiuni" className="space-y-4">
          <h2 id="actiuni" className="text-xl">Ce poți face</h2>
          <SubscribeForm targetType="authority" targetKey={String(primarie.id)} label={prettyName(primarie.name)} />
          <AskBox
            institution={prettyName(primarie.name)}
            subject={`cheltuielile și proiectele ${prettyName(primarie.name)}`}
            questions={[
              "Lista proiectelor de investiții în derulare, cu valoarea, firma executantă și termenul de finalizare.",
              "Bugetul local aprobat pentru anul în curs și execuția bugetară la zi.",
              "Lista contractelor de achiziție publică încheiate în ultimele 12 luni și stadiul lor.",
              "Sumele acordate ca finanțări nerambursabile (Legea 350/2005) asociațiilor și fundațiilor în ultimul an.",
            ]}
          />
        </section>
      )}
    </div>
  );
}
