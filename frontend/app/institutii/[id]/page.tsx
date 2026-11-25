import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AskBox } from "@/components/actions";
import { ExplainBox, SubscribeForm } from "@/components/forms";
import { CategoryChart, YearChart } from "@/components/charts";
import { SyntheticBadge } from "@/components/data-banner";
import { SignalCard, SignalsNote } from "@/components/signals";
import { ContractTable, TotalsTable } from "@/components/tables";
import { Term } from "@/components/term";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, type AuthorityDetail, type ContractItem, type Page } from "@/lib/api";
import { lei, leiShort, num } from "@/lib/format";

async function load(id: string): Promise<AuthorityDetail> {
  if (!/^\d+$/.test(id)) notFound();
  try {
    return await api<AuthorityDetail>(`/authorities/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const a = await load(params.id);
  const description = `${a.name}: ${lei(a.total_ron)} în ${num(a.contracts)} contracte publice. Furnizori, categorii de cheltuieli și semnale de verificat.`;
  return {
    title: a.name,
    description,
    alternates: { canonical: `/institutii/${a.id}` },
    openGraph: { title: a.name, description },
  };
}

export default async function AuthorityPage({ params }: { params: { id: string } }) {
  const a = await load(params.id);
  const contracts = await api<Page<ContractItem>>("/contracts", { authority_id: a.id, page_size: 15 });
  return (
    <div className="space-y-6">
      <nav aria-label="Fir de navigare" className="text-sm text-muted-foreground">
        <Link href="/institutii">Instituții</Link> / {a.name}
      </nav>
      <header>
        <h1 className="text-2xl md:text-3xl">
          {a.name}
          <SyntheticBadge show={a.is_synthetic} />
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {[a.authority_type, a.locality, a.county_name && `județul ${a.county_name}`, `CUI ${a.cui}`].filter(Boolean).join(" · ")}
        </p>
        {a.contracts > 0 && (
          <p className="mt-3 max-w-3xl text-lg leading-relaxed">
            A cheltuit <strong>{leiShort(a.total_ron)}</strong> prin {num(a.contracts)}{" "}
            {a.contracts === 1 ? "contract" : "contracte"}
            {a.by_category[0] && <>, cel mai mult pe {a.by_category[0].name.toLowerCase()}</>}
            {a.top_suppliers[0] && (
              <>
                . Cei mai mulți bani au mers la{" "}
                {a.top_suppliers[0].key ? (
                  <Link href={`/firme/${encodeURIComponent(a.top_suppliers[0].key)}`}>{a.top_suppliers[0].name}</Link>
                ) : (
                  a.top_suppliers[0].name
                )}
              </>
            )}
            .
          </p>
        )}
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
          <div className="rounded-lg border bg-white p-4">
            <p className="text-sm text-muted-foreground">Total contractat</p>
            <p className="text-2xl font-semibold tabular">{lei(a.total_ron)}</p>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <p className="text-sm text-muted-foreground">Contracte</p>
            <p className="text-2xl font-semibold tabular">{num(a.contracts)}</p>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <p className="text-sm text-muted-foreground"><Term id="semnal">Semnale de verificat</Term></p>
            <p className="text-2xl font-semibold tabular">{num(a.signal_count)}</p>
          </div>
        </div>
      </header>

      <ExplainBox
        path={`/explain/authority/${a.id}`}
        intro="Pe ce cheltuie această instituție banii, pe scurt?"
        button="Rezumat AI"
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Total cheltuit pe ani (lei)</CardTitle></CardHeader>
          <CardContent><YearChart data={a.by_year} title={`Total cheltuit pe ani de ${a.name}`} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Pe ce s-au cheltuit banii (lei)</CardTitle></CardHeader>
          <CardContent><CategoryChart data={a.by_category} title="Cheltuieli pe categorii" /></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Top 10 furnizori</CardTitle></CardHeader>
        <CardContent>
          <TotalsTable rows={a.top_suppliers} linkBase="/firme" caption="Top 10 furnizori" nameHeader="Furnizor" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Cum au fost atribuite contractele</CardTitle></CardHeader>
        <CardContent>
          <TotalsTable rows={a.by_procedure_type} caption="Distribuție pe tip de procedură" nameHeader="Tip procedură" />
          <p className="mt-2 text-xs text-muted-foreground">
            Vezi <Term id="achizitie_directa" />, <Term id="licitatie_deschisa" />, <Term id="negociere_fara_publicare" />.
          </p>
        </CardContent>
      </Card>

      {a.signals.length > 0 && (
        <section aria-labelledby="semnale" className="space-y-3">
          <h2 id="semnale" className="text-xl">Semnale de verificat</h2>
          <SignalsNote />
          {a.signals.slice(0, 5).map((s) => <SignalCard key={s.id} s={s} />)}
          {a.signal_count > 5 && <Link href={`/semnale?authority_id=${a.id}`}>Toate cele {a.signal_count} semnale →</Link>}
        </section>
      )}

      <section aria-labelledby="contracte" className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 id="contracte" className="text-xl">Contracte recente</h2>
          <Link href={`/contracte?authority_id=${a.id}`}>Filtrează toate cele {num(contracts.total)} contracte →</Link>
        </div>
        <Card><CardContent className="pt-4"><ContractTable items={contracts.items} showAuthority={false} /></CardContent></Card>
      </section>

      <SubscribeForm targetType="authority" targetKey={String(a.id)} label={a.name} />
      <AskBox
        institution={a.name}
        subject={`achizițiile și cheltuielile ${a.name}`}
        questions={[
          "Programul anual al achizițiilor publice pentru anul în curs.",
          "Lista contractelor de achiziție publică încheiate în ultimele 12 luni, cu valoarea și furnizorul.",
          "Bugetul aprobat pentru anul în curs și execuția bugetară la zi.",
          "Lista proiectelor de investiții în derulare și stadiul lor.",
        ]}
      />
    </div>
  );
}
