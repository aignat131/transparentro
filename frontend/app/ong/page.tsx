import type { Metadata } from "next";
import Link from "next/link";

import { pageNum, Pagination, sp } from "@/components/pagination";
import { ALL_YEARS, pickYear, Pills, yearChoices } from "@/components/pills";
import { TotalsTable } from "@/components/tables";
import { Card, CardContent } from "@/components/ui/card";
import { api, DEFAULT_COUNTY, type AuthorityItem, type CompanyItem, type Meta, type NamedTotal, type Page } from "@/lib/api";
import { num } from "@/lib/format";

export const metadata: Metadata = {
  title: "ONG-uri și banii publici",
  description: "Asociațiile, fundațiile și cluburile sportive care primesc sau cheltuie bani publici prin achiziții.",
};

const PAGE_SIZE = 25;

export default async function NgoPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const county = DEFAULT_COUNTY;
  const meta = await api<Meta>("/meta", { county }, 600);
  const years = [...meta.years].sort((a, b) => b - a);
  const year = pickYear(sp(searchParams.year), years);
  const yq = year ?? undefined;
  const page = pageNum(searchParams.page);
  const [receivers, buyers] = await Promise.all([
    api<Page<CompanyItem>>("/companies", { county, year: yq, ngo: true, sort: "total_desc", page, page_size: PAGE_SIZE }),
    api<Page<AuthorityItem>>("/authorities", { county, year: yq, ngo: true, sort: "total_desc", page_size: 15 }),
  ]);
  const inYear = year === null ? "" : ` în ${year}`;
  const offset = (page - 1) * PAGE_SIZE;
  const receiverRows: NamedTotal[] = receivers.items.map((c) => ({
    key: c.key,
    name: c.name,
    count: c.contracts,
    total_ron: c.total_ron ?? "0",
    share: null,
  }));
  const buyerRows: NamedTotal[] = buyers.items.map((a) => ({
    key: String(a.id),
    name: a.name,
    count: a.contracts,
    total_ron: a.total_ron ?? "0",
    share: null,
  }));
  const yearValue = year === null ? ALL_YEARS : String(year);

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl md:text-3xl">ONG-uri și banii publici</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Asociații, fundații, federații și cluburi sportive care au contracte cu instituțiile publice din județ: unele
          primesc bani pentru servicii (de exemplu sociale sau sportive), altele cumpără ele însele prin SEAP, de obicei
          din proiecte cu fonduri europene.
        </p>
        <div className="mt-4 space-y-3 rounded-lg border bg-white p-4">
          <Pills label="Anul" choices={yearChoices(years)} selected={yearValue} href={(v) => `/ong?year=${v}`} />
          <p className="border-t pt-3 text-base">
            {year === null ? <>Toți anii</> : <>Anul <strong>{year}</strong></>}: <strong>{num(receivers.total)}</strong> ONG-uri
            au primit bani publici, iar <strong>{num(buyers.total)}</strong> au cumpărat prin achiziții publice.
          </p>
        </div>
      </section>

      <section aria-labelledby="primite">
        <h2 id="primite" className="mb-1 text-xl">ONG-urile care au primit cei mai mulți bani{inYear}</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Contracte câștigate de la instituțiile publice. Apasă pe un ONG ca să vezi de la cine a primit banii și un rezumat AI.
        </p>
        <Card>
          <CardContent className="pt-4">
            {offset > 0 && <p className="mb-2 text-sm text-muted-foreground">Locurile {offset + 1}–{offset + receiverRows.length}</p>}
            <TotalsTable rows={receiverRows} linkBase="/firme" caption="ONG-urile care au primit bani publici" nameHeader="ONG" />
          </CardContent>
        </Card>
        <div className="mt-3">
          <Pagination base="/ong" params={searchParams} page={page} pageSize={PAGE_SIZE} total={receivers.total} />
        </div>
      </section>

      <section aria-labelledby="cumparate">
        <h2 id="cumparate" className="mb-1 text-xl">ONG-urile care au cumpărat prin achiziții publice{inYear}</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          ONG-urile care derulează proiecte cu bani publici (de exemplu fonduri europene) trebuie să cumpere prin SEAP, ca
          instituțiile. Aici vezi cât au contractat.
        </p>
        <Card>
          <CardContent className="pt-4">
            <TotalsTable rows={buyerRows} linkBase="/institutii" caption="ONG-urile care au cumpărat prin SEAP" nameHeader="ONG" />
          </CardContent>
        </Card>
      </section>

      <p className="text-sm text-muted-foreground">
        Cum recunoaștem un ONG: SEAP nu spune forma juridică, așa că ne uităm la denumire (asociație, fundație, federație,
        club sportiv, uniune, organizație). Nu includem asociațiile de dezvoltare intercomunitară (ale primăriilor) și
        asociațiile de proprietari. Pot exista și ONG-uri cu alte denumiri pe care nu le prindem.{" "}
        <Link href="/metodologie">Metodologia</Link>
      </p>
    </div>
  );
}
