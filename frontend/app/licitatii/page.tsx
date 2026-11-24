import type { Metadata } from "next";
import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { pageNum, Pagination, sp } from "@/components/pagination";
import { type Choice, hrefWith, Pills } from "@/components/pills";
import { Term } from "@/components/term";
import { api, DEFAULT_COUNTY, type Meta, type Page, type ProcedureItem } from "@/lib/api";
import { date, lei, num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Licitații deschise",
  description: "Achizițiile publice aflate în desfășurare în județ, la care pot participa și firmele mici sau ONG-urile.",
};

const PAGE_SIZE = 20;
const PRIMARII = "Primărie / administrație locală";

const VALUES: (Choice & { max?: number })[] = [
  { value: null, label: "Orice valoare" },
  { value: "100k", label: "Până la 100.000 lei", max: 100_000 },
  { value: "500k", label: "Până la 500.000 lei", max: 500_000 },
];
const WHO: Choice[] = [
  { value: null, label: "Toate instituțiile" },
  { value: "primarii", label: "Doar primăriile" },
];

export default async function TendersPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const county = DEFAULT_COUNTY;
  const page = pageNum(searchParams.page);
  const val = VALUES.find((v) => v.value === sp(searchParams.val)) ?? VALUES[0];
  const who = WHO.find((w) => w.value === sp(searchParams.who)) ?? WHO[0];
  const meta = await api<Meta>("/meta", { county }, 600);
  const domains = meta.domains ?? [];
  const domain = domains.find((d) => d.key === sp(searchParams.domain)) ?? null;
  const data = await api<Page<ProcedureItem>>("/procedures", {
    county,
    status: "open",
    max_value: val.max,
    authority_type: who.value === "primarii" ? PRIMARII : undefined,
    domain: domain?.key,
    sort: "recent",
    page,
    page_size: PAGE_SIZE,
  });
  const state = { val: val.value, who: who.value, domain: domain?.key ?? null };
  const link = (change: Partial<typeof state>) => hrefWith("/licitatii", { ...state, ...change });
  const domainChoices: Choice[] = [{ value: null, label: "Toate" }, ...domains.map((d) => ({ value: d.key, label: d.label }))];

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl md:text-3xl">Licitații deschise</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Ce vor să cumpere acum instituțiile publice din județ. Orice firmă sau ONG înregistrat în{" "}
          <Term id="seap">SEAP</Term> poate depune o ofertă. Contractele de valoare mică sunt cele mai potrivite pentru
          firmele mici și ONG-uri.
        </p>
        <div className="mt-4 space-y-3 rounded-lg border bg-white p-4">
          <Pills label="Valoare" choices={VALUES} selected={val.value} href={(v) => link({ val: v })} />
          <Pills label="Cine" choices={WHO} selected={who.value} href={(v) => link({ who: v })} />
          {domains.length > 0 && (
            <Pills label="Domeniul" choices={domainChoices} selected={domain?.key ?? null} href={(v) => link({ domain: v })} />
          )}
          <p className="border-t pt-3 text-base">
            <strong>{num(data.total)}</strong> licitații în desfășurare
            {val.max ? <>, cu valoare estimată {val.label.toLowerCase()}</> : null}
            {who.value === "primarii" ? <>, organizate de primării</> : null}
            {domain ? <>, domeniul <strong>{domain.label}</strong></> : null}.
          </p>
        </div>
        <p className="mt-2 text-sm text-amber-800">
          Datele vin din exporturile periodice ale SEAP, nu sunt în timp real. Înainte să depui o ofertă, verifică pe
          e-licitatie.ro termenul limită și dacă procedura mai este deschisă.
        </p>
      </section>

      {data.items.length === 0 ? (
        <p className="rounded-lg border bg-white p-6 text-muted-foreground">
          Nu am găsit licitații în desfășurare pentru aceste filtre. <Link href="/licitatii">Șterge filtrele</Link>
        </p>
      ) : (
        <ul className="space-y-3" data-testid="tender-list">
          {data.items.map((p) => (
            <li key={p.id} className="rounded-lg border bg-white p-4">
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <p className="font-medium">{p.title || "Procedură fără titlu"}</p>
                  <p className="mt-1 text-sm">
                    <Link href={`/institutii/${p.authority.id}`}>{p.authority.name}</Link>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {[p.category, p.contract_type, p.procedure_type, p.publication_date && `publicat ${date(p.publication_date)}`, p.notice_number]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <div className="shrink-0 text-left md:text-right">
                  <p className="text-xs text-muted-foreground">Valoare estimată</p>
                  <p className="text-lg font-semibold tabular">{p.estimated_value_ron ? lei(p.estimated_value_ron) : "—"}</p>
                  <a href={p.official_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm">
                    Anunțul oficial <ExternalLink className="h-3 w-3" aria-hidden />
                  </a>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Pagination base="/licitatii" params={searchParams} page={page} pageSize={PAGE_SIZE} total={data.total} />

      <section className="rounded-lg border bg-white p-6 text-sm">
        <h2 className="text-lg">Ești ONG și cauți finanțare?</h2>
        <p className="mt-2">
          Pe lângă licitații, primăriile și consiliul județean dau bani ONG-urilor prin finanțări nerambursabile (Legea
          350/2005), pentru proiecte sociale, culturale sau sportive. Aceste apeluri nu apar în SEAP, ci pe site-ul fiecărei
          instituții, la secțiunea „Finanțări nerambursabile”. Vezi și ce ONG-uri au primit deja bani publici:{" "}
          <Link href="/ong">ONG-uri</Link>.
        </p>
      </section>
    </div>
  );
}
