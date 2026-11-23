import type { Metadata } from "next";
import Link from "next/link";

import { SyntheticBadge } from "@/components/data-banner";
import { sp } from "@/components/pagination";
import { SearchBar } from "@/components/search-bar";
import { api, DEFAULT_COUNTY, type SearchHit, type SearchResult } from "@/lib/api";
import { leiShort } from "@/lib/format";

export const metadata: Metadata = { title: "Căutare", robots: { index: false } };

function Hits({ title, hits, href, more }: { title: string; hits: SearchHit[]; href: (h: SearchHit) => string; more?: string }) {
  return (
    <section aria-label={title} className="rounded-lg border bg-white p-4">
      <h2 className="mb-2 text-lg">
        {title} <span className="text-sm font-normal text-muted-foreground">({hits.length})</span>
      </h2>
      {hits.length === 0 ? (
        <p className="text-sm text-muted-foreground">Niciun rezultat.</p>
      ) : (
        <ul className="divide-y">
          {hits.map((h) => (
            <li key={`${h.type}-${h.id}`} className="py-2">
              <Link href={href(h)} className="font-medium">
                {h.title}
              </Link>
              <SyntheticBadge show={h.is_synthetic} />
              <div className="text-xs text-muted-foreground">
                {h.subtitle}
                {h.value_ron ? ` · ${leiShort(h.value_ron)}` : ""}
              </div>
            </li>
          ))}
        </ul>
      )}
      {more && hits.length > 0 && (
        <p className="mt-2 text-sm">
          <Link href={more}>Vezi toate →</Link>
        </p>
      )}
    </section>
  );
}

export default async function SearchPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = (sp(searchParams.q) ?? "").trim();
  const res = q.length >= 1 ? await api<SearchResult>("/search", { q, county: DEFAULT_COUNTY, limit: 10 }, 60) : null;
  const enc = encodeURIComponent(q);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl">Căutare</h1>
      <SearchBar defaultValue={q} />
      {res && (
        <>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            Rezultate pentru „{q}”. Căutarea nu ține cont de diacritice.
          </p>
          <div className="grid gap-4 lg:grid-cols-3">
            <Hits title="Instituții" hits={res.authorities} href={(h) => `/institutii/${h.id}`} more={`/institutii?q=${enc}`} />
            <Hits title="Firme" hits={res.companies} href={(h) => `/firme/${encodeURIComponent(h.id)}`} more={`/firme?q=${enc}`} />
            <Hits title="Contracte" hits={res.contracts} href={(h) => `/contracte/${h.id}`} more={`/contracte?q=${enc}`} />
          </div>
        </>
      )}
    </div>
  );
}
