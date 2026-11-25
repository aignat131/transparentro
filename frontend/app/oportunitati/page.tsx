import type { Metadata } from "next";
import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { FilterPanel } from "@/components/filter-panel";
import { pageNum, Pagination, sp } from "@/components/pagination";
import { type Choice, hrefWith, Pills } from "@/components/pills";
import { Term } from "@/components/term";
import {
  api,
  DEFAULT_COUNTY,
  type ContractItem,
  type Locality,
  type Meta,
  type Page,
  type ProcedureItem,
  type UpcomingItem,
} from "@/lib/api";
import { asPhrase, date, lei, leiShort, num, prettyName } from "@/lib/format";
import { GRANT_SOURCES } from "@/lib/grants";

export const metadata: Metadata = {
  title: "Oportunități pentru firme și ONG-uri",
  description:
    "Licitațiile deschise ale instituțiilor publice, cine a câștigat recent, ce se cumpără în fiecare an și finanțările pentru ONG-uri.",
};

const PAGE_SIZE = 20;
const TABS: Choice[] = [
  { value: null, label: "Deschise acum" },
  { value: "castigate", label: "Câștigate recent" },
  { value: "urmeaza", label: "Ce urmează" },
  { value: "ong", label: "Finanțări ONG" },
];
const VALUES: (Choice & { max?: number })[] = [
  { value: null, label: "Orice valoare" },
  { value: "100k", label: "Până la 100.000 lei", max: 100_000 },
  { value: "500k", label: "Până la 500.000 lei", max: 500_000 },
];

type SP = Record<string, string | string[] | undefined>;

export default async function OpportunitiesPage({ searchParams }: { searchParams: SP }) {
  const county = DEFAULT_COUNTY;
  const tab = TABS.find((t) => t.value === sp(searchParams.tab)) ?? TABS[0];
  const page = pageNum(searchParams.page);
  const val = VALUES.find((v) => v.value === sp(searchParams.val)) ?? VALUES[0];
  const [meta, localities] = await Promise.all([
    api<Meta>("/meta", { county }, 600),
    api<Locality[]>("/localities", { county }, 600),
  ]);
  const domains = meta.domains ?? [];
  const domain = domains.find((d) => d.key === sp(searchParams.domain)) ?? null;
  const locality = localities.find((l) => l.slug === sp(searchParams.locality)) ?? null;
  const state = { tab: tab.value, val: val.value, domain: domain?.key ?? null, locality: locality?.slug ?? null };
  const link = (change: Partial<typeof state>) => hrefWith("/oportunitati", { ...state, ...change });
  const filters = { county, domain: domain?.key, locality: locality?.slug };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section>
        <h1 className="text-2xl md:text-3xl">Oportunități pentru firme și ONG-uri</h1>
        <p className="mt-2 text-muted-foreground">
          Ce vor să cumpere instituțiile publice din județ, cine a câștigat până acum și la ce preț, ce se cumpără în
          fiecare an și unde găsești finanțări pentru ONG-uri. Orice firmă sau ONG înregistrat în <Term id="seap">SEAP</Term>{" "}
          poate depune ofertă.
        </p>
        <div className="mt-4">
          <Pills label="Arată" choices={TABS} selected={tab.value} href={(v) => link({ tab: v, val: null })} />
        </div>
      </section>

      {tab.value !== "ong" && (
        <FilterPanel active={[tab.value === null && val.max ? val.label : null, domain?.label, locality?.name]}>
          <div className="space-y-3 p-4">
            {tab.value === null && <Pills label="Valoare" choices={VALUES} selected={val.value} href={(v) => link({ val: v })} />}
            {tab.value !== "urmeaza" && <Pills label="Domeniul" choices={[{ value: null, label: "Toate" }, ...domains.map((d) => ({ value: d.key, label: d.label }))]}
              selected={domain?.key ?? null} href={(v) => link({ domain: v })} />}
            <form method="get" className="flex flex-wrap items-end gap-2">
              {Object.entries(state).filter(([k, v]) => v && k !== "locality").map(([k, v]) => (
                <input key={k} type="hidden" name={k} value={v as string} />
              ))}
              <div>
                <label htmlFor="o-loc" className="text-sm font-medium">Localitatea</label>
                <select id="o-loc" name="locality" defaultValue={locality?.slug ?? ""} className="mt-1 block rounded-md border px-3 py-2 text-sm">
                  <option value="">Tot județul</option>
                  {[...localities].sort((a, b) => a.name.localeCompare(b.name, "ro")).map((l) => (
                    <option key={l.slug} value={l.slug}>{l.name}</option>
                  ))}
                </select>
              </div>
              <button type="submit" className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">Aplică</button>
            </form>
          </div>
        </FilterPanel>
      )}

      {tab.value === null && <OpenNow filters={filters} max={val.max} page={page} searchParams={searchParams} />}
      {tab.value === "castigate" && <RecentlyWon filters={filters} page={page} searchParams={searchParams} />}
      {tab.value === "urmeaza" && <Upcoming county={county} locality={locality?.slug} />}
      {tab.value === "ong" && <NgoGrants />}
    </div>
  );
}

type Filters = { county: string; domain?: string; locality?: string };

async function OpenNow({ filters, max, page, searchParams }: { filters: Filters; max?: number; page: number; searchParams: SP }) {
  const data = await api<Page<ProcedureItem>>("/procedures", { ...filters, status: "open", max_value: max, sort: "recent", page, page_size: PAGE_SIZE });
  return (
    <section aria-label="Licitații deschise" className="space-y-3">
      <p className="text-base"><strong>{num(data.total)}</strong> licitații în desfășurare.</p>
      <p className="text-sm text-amber-800">
        Datele vin din exporturile periodice ale SEAP, nu în timp real. Verifică pe e-licitatie.ro termenul limită înainte să depui o ofertă.
      </p>
      {data.items.length === 0 ? (
        <p className="rounded-lg border bg-white p-6 text-muted-foreground">Nu am găsit licitații deschise pentru aceste filtre.</p>
      ) : (
        <ul className="space-y-3" data-testid="tender-list">
          {data.items.map((p) => (
            <li key={p.id} className="rounded-lg border bg-white p-4">
              <p className="font-medium leading-snug">{p.title || "Procedură fără titlu"}</p>
              <p className="mt-1 text-sm"><Link href={`/institutii/${p.authority.id}`}>{prettyName(p.authority.name)}</Link></p>
              <div className="mt-2 flex flex-wrap items-end justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  {[p.category, p.procedure_type, p.publication_date && `publicat ${date(p.publication_date)}`].filter(Boolean).join(" · ")}
                </p>
                <p className="text-right">
                  <span className="block text-xs text-muted-foreground">Valoare estimată</span>
                  <span className="font-semibold tabular">{p.estimated_value_ron ? lei(p.estimated_value_ron) : "—"}</span>
                </p>
              </div>
              <a href={p.official_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm">
                Anunțul oficial <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            </li>
          ))}
        </ul>
      )}
      <Pagination base="/oportunitati" params={searchParams} page={page} pageSize={PAGE_SIZE} total={data.total} />
    </section>
  );
}

async function RecentlyWon({ filters, page, searchParams }: { filters: Filters; page: number; searchParams: SP }) {
  const data = await api<Page<ContractItem>>("/contracts", {
    ...filters, source: "contracte,atribuire_fara", sort: "date_desc", page, page_size: PAGE_SIZE,
  });
  return (
    <section aria-label="Licitații câștigate recent" className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Licitațiile atribuite recent: cine a câștigat și la ce preț. Bun ca reper dacă vrei să participi data viitoare.
      </p>
      <ul className="space-y-3">
        {data.items.map((c) => (
          <li key={c.id} className="rounded-lg border bg-white p-4">
            <Link href={`/contracte/${c.id}`} className="font-medium leading-snug">{c.title || "Contract fără titlu"}</Link>
            <p className="mt-1 text-sm text-muted-foreground">
              {prettyName(c.authority.name)} → <strong className="text-foreground">{c.company ? prettyName(c.company.name) : "furnizor necunoscut"}</strong>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {[leiShort(c.value_ron), c.procedure_type, c.contract_date && date(c.contract_date)].filter(Boolean).join(" · ")}
            </p>
          </li>
        ))}
      </ul>
      <Pagination base="/oportunitati" params={searchParams} page={page} pageSize={PAGE_SIZE} total={data.total} />
    </section>
  );
}

async function Upcoming({ county, locality }: { county: string; locality?: string }) {
  const items = await api<UpcomingItem[]>("/procedures/upcoming", { county, locality, months: 3, limit: 60 });
  const byMonth = new Map<string, UpcomingItem[]>();
  for (const it of items) byMonth.set(it.month_name, [...(byMonth.get(it.month_name) ?? []), it]);
  return (
    <section aria-label="Ce urmează" className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Ce au cumpărat instituțiile în aceeași lună, în cel puțin doi ani diferiți. E probabil să cumpere din nou: te poți
        pregăti din timp. Nu e o garanție, ci un tipar din date.
      </p>
      {items.length === 0 && <p className="rounded-lg border bg-white p-6 text-muted-foreground">Nu am găsit tipare pentru lunile următoare.</p>}
      {[...byMonth.entries()].map(([month, list]) => (
        <div key={month}>
          <h2 className="text-lg capitalize">{month}</h2>
          <ul className="mt-2 space-y-2">
            {list.map((it) => (
              <li key={`${it.authority.id}-${it.cpv_prefix}-${it.month}`} className="rounded-lg border bg-white p-4">
                <p className="font-medium leading-snug">
                  <Link href={`/institutii/${it.authority.id}`}>{prettyName(it.authority.name)}</Link> cumpără de obicei:{" "}
                  {it.category.toLowerCase()}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  În {month} {it.years.join(", ")} · în medie {leiShort(it.typical_value_ron)}
                </p>
                {it.last_title && <p className="mt-1 text-xs text-muted-foreground">Ultima dată: {asPhrase(it.last_title, 160)}</p>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function NgoGrants() {
  return (
    <section aria-label="Finanțări pentru ONG-uri" className="space-y-4">
      <div className="rounded-lg border bg-white p-4 text-sm">
        <p>
          Pe lângă licitații, instituțiile dau bani ONG-urilor prin <strong>finanțări nerambursabile</strong> (Legea 350/2005):
          pentru proiecte culturale, sportive, sociale sau pentru tineret. Aceste apeluri <strong>nu apar în SEAP</strong>: fiecare
          instituție le publică pe site-ul ei, de obicei o dată pe an.
        </p>
        <p className="mt-2">Pe scurt: se depune un proiect cu buget, ONG-ul pune de obicei o contribuție proprie (minimum 10%), o comisie îl punctează.</p>
      </div>
      <ul className="space-y-3">
        {GRANT_SOURCES.map((g) => (
          <li key={g.url} className="rounded-lg border bg-white p-4">
            <p className="font-semibold">{g.institution}</p>
            <p className="mt-1 text-sm text-muted-foreground">{g.domains.join(" · ")}</p>
            <p className="mt-2 text-sm">{g.note}</p>
            <div className="mt-2 flex flex-wrap gap-3 text-sm">
              <a href={g.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1">
                Apelurile și ghidurile <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
              {g.platform && (
                <a href={g.platform} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1">
                  Platforma de depunere <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
              )}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Verificat la {date(g.checked)}.</p>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">
        Primăriile (Sibiu, Mediaș și celelalte) au și ele apeluri, dar nu am găsit încă o pagină oficială pe care s-o putem
        verifica. Cunoști una? <Link href="/disclaimer">Scrie-ne</Link>. Vezi și <Link href="/ong">ce ONG-uri au primit deja bani publici</Link>.
      </p>
    </section>
  );
}
