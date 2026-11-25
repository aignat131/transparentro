import type { Metadata } from "next";
import Link from "next/link";

import { api, DEFAULT_COUNTY, type Locality, type Meta } from "@/lib/api";
import { leiShort, num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Localitățile din județ",
  description: "Alege localitatea și vezi ce au cheltuit primăria, școlile și celelalte instituții de acolo.",
};

export default async function LocalitiesPage() {
  const county = DEFAULT_COUNTY;
  const meta = await api<Meta>("/meta", { county }, 600);
  const year = [...meta.years].sort((a, b) => b - a)[0];
  const all = await api<Locality[]>("/localities", { county, year }, 600);
  const withData = all.filter((l) => l.contracts > 0);
  const sorted = [...withData].sort((a, b) => a.name.localeCompare(b.name, "ro"));
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section>
        <h1 className="text-2xl md:text-3xl">Alege localitatea</h1>
        <p className="mt-2 text-muted-foreground">
          Vezi ce au cumpărat primăria, școlile, spitalul și celelalte instituții cu sediul acolo{year ? ` în ${year}` : ""}.
        </p>
      </section>
      <ul className="grid gap-2 sm:grid-cols-2">
        {sorted.map((l) => (
          <li key={l.slug}>
            <Link href={`/localitate/${l.slug}`}
              className="flex items-baseline justify-between gap-3 rounded-lg border bg-white px-4 py-3 text-foreground no-underline hover:border-primary">
              <span className="font-medium">{l.name}</span>
              <span className="shrink-0 text-sm tabular text-muted-foreground">{leiShort(l.total_ron)}</span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">
        {num(withData.length)} localități cu contracte{year ? ` în ${year}` : ""}. Satele apar la comuna lor. O localitate
        lipsește dacă nicio instituție de acolo nu a avut contracte în SEAP în acest an.
      </p>
    </div>
  );
}
