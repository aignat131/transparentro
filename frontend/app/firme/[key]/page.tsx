import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink } from "lucide-react";

import { CategoryChart, YearChart } from "@/components/charts";
import { SyntheticBadge } from "@/components/data-banner";
import { ExplainBox, SubscribeForm } from "@/components/forms";
import { SignalCard, SignalsNote } from "@/components/signals";
import { ContractTable, TotalsTable } from "@/components/tables";
import { Term } from "@/components/term";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, type CompanyDetail, type ContractItem, type Page } from "@/lib/api";
import { date, lei, leiShort, num, pct } from "@/lib/format";

async function load(key: string): Promise<CompanyDetail> {
  try {
    return await api<CompanyDetail>(`/companies/${encodeURIComponent(decodeURIComponent(key))}`);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: { key: string } }): Promise<Metadata> {
  const c = await load(params.key);
  const description = `${c.name}: ${lei(c.total_ron)} din ${num(c.contracts)} contracte cu instituții publice. Clienți, istoric și semnale de verificat.`;
  return {
    title: c.name,
    description,
    alternates: { canonical: `/firme/${encodeURIComponent(c.key)}` },
    openGraph: { title: c.name, description },
    // persoanele fizice nu se indexează (GDPR)
    robots: c.is_natural_person ? { index: false, follow: false } : undefined,
  };
}

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b py-2 text-sm last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

export default async function CompanyPage({ params }: { params: { key: string } }) {
  const c = await load(params.key);
  const contracts = await api<Page<ContractItem>>("/contracts", { company: c.key, page_size: 15 });
  return (
    <div className="space-y-6">
      <nav aria-label="Fir de navigare" className="text-sm text-muted-foreground">
        {c.is_ngo ? <Link href="/ong">ONG-uri</Link> : <Link href="/firme">Firme</Link>} / {c.name}
      </nav>
      <header>
        <h1 className="text-2xl md:text-3xl">
          {c.name}
          <SyntheticBadge show={c.is_synthetic} />
          {c.is_ngo && (
            <span className="ml-2 inline-block rounded-full bg-emerald-50 px-2 py-0.5 align-middle text-xs font-medium text-emerald-800">ONG</span>
          )}
        </h1>
        {c.contracts > 0 && (
          <p className="mt-3 max-w-3xl text-lg leading-relaxed">
            A primit <strong>{leiShort(c.total_ron)}</strong> din {num(c.contracts)}{" "}
            {c.contracts === 1 ? "contract" : "contracte"} cu instituțiile publice
            {c.clients[0] && (
              <>
                , mai ales de la <Link href={`/institutii/${c.clients[0].key}`}>{c.clients[0].name}</Link>
                {c.clients[0].share != null && c.clients.length > 1 ? ` (${pct(c.clients[0].share)} din bani)` : ""}
              </>
            )}
            {c.by_category[0] && <>, pentru {c.by_category[0].name.toLowerCase()}</>}.
          </p>
        )}
        {c.is_natural_person && (
          <p className="mt-2 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
            Furnizorul este o <Term id="pfa">persoană fizică autorizată</Term> (PFA, întreprindere individuală sau familială).
            Pentru protecția datelor personale nu afișăm numele, ci doar localitatea: {c.locality || "necunoscută"}.
          </p>
        )}
      </header>

      <ExplainBox
        path={`/explain/company/${encodeURIComponent(c.key)}`}
        intro={`Ce face ${c.is_ngo ? "acest ONG" : "această firmă"} cu banii publici, pe scurt?`}
        button="Rezumat AI"
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader><CardTitle>Profil</CardTitle></CardHeader>
          <CardContent>
            <dl>
              {c.cui && <Row label={<Term id="cui">CUI</Term>}>{c.cui}</Row>}
              {c.registry_number && <Row label="Nr. Registrul Comerțului">{c.registry_number}</Row>}
              {!c.is_natural_person && (
                <Row label="Data înființării">
                  {date(c.founded_on)}
                  {c.founded_source && <span className="text-xs text-muted-foreground"> ({c.founded_source.toUpperCase()})</span>}
                </Row>
              )}
              <Row label="Localitate">{c.locality || "—"}</Row>
              <Row label="Cod CAEN (activitate)">{c.caen_code || "—"}</Row>
              <Row label="Formă juridică">{c.legal_form || "—"}</Row>
              <Row label="Stare">{c.status || "—"}{c.inactive ? " · inactiv fiscal" : ""}</Row>
              <Row label="Plătitor de TVA">{c.vat_payer == null ? "—" : c.vat_payer ? "da" : "nu"}</Row>
              <Row label="Primul contract public (în date)">{date(c.first_contract_date)}</Row>
            </dl>
            {c.official_url && (
              <a href={c.official_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm">
                Fișa oficială (Ministerul Finanțelor) <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            )}
            {c.anaf_checked_at && <p className="mt-2 text-xs text-muted-foreground">Date ANAF verificate la {date(c.anaf_checked_at)}.</p>}
            {c.aliases.length > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">Apare în SEAP și ca: {c.aliases.join("; ")}</p>
            )}
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Contracte cu statul, pe ani (lei)</CardTitle>
            <p className="text-sm text-muted-foreground">Total: {lei(c.total_ron)} · {num(c.contracts)} contracte</p>
          </CardHeader>
          <CardContent><YearChart data={c.by_year} title={`Contracte publice pe ani pentru ${c.name}`} /></CardContent>
        </Card>
      </div>

      {c.signals.length > 0 && (
        <section aria-labelledby="semnale" className="space-y-3">
          <h2 id="semnale" className="text-xl">Semnale de verificat</h2>
          <SignalsNote />
          {c.signals.map((s) => <SignalCard key={s.id} s={s} />)}
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Instituții-client</CardTitle></CardHeader>
          <CardContent><TotalsTable rows={c.clients} linkBase="/institutii" caption="Instituții-client" nameHeader="Instituție" /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Ce vinde statului</CardTitle></CardHeader>
          <CardContent><CategoryChart data={c.by_category} title="Contracte pe categorii" limit={6} /></CardContent>
        </Card>
      </div>

      {c.financials.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Date financiare (bilanț ANAF)</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2">An</th>
                  <th scope="col" className="py-2 text-right">Cifră de afaceri</th>
                  <th scope="col" className="py-2 text-right">Profit net</th>
                  <th scope="col" className="py-2 text-right">Angajați</th>
                  <th scope="col" className="py-2 text-right">Contracte publice în an</th>
                  <th scope="col" className="py-2 text-right">Raport</th>
                </tr>
              </thead>
              <tbody>
                {c.financials.map((f) => (
                  <tr key={f.year} className="border-b last:border-0 tabular">
                    <td className="py-2">{f.year}</td>
                    <td className="py-2 text-right">{lei(f.turnover_ron)}</td>
                    <td className="py-2 text-right">{lei(f.net_profit_ron)}</td>
                    <td className="py-2 text-right">{num(f.employees)}</td>
                    <td className="py-2 text-right">{lei(f.public_total_ron)}</td>
                    <td className="py-2 text-right">
                      {f.public_total_ron && f.turnover_ron && Number(f.turnover_ron) > 0
                        ? pct(Number(f.public_total_ron) / Number(f.turnover_ron))
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-muted-foreground">Un contract se poate întinde pe mai mulți ani, deci raportul este orientativ.</p>
          </CardContent>
        </Card>
      )}

      <section aria-labelledby="contracte" className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 id="contracte" className="text-xl">Contracte recente</h2>
          <Link href={`/contracte?company=${encodeURIComponent(c.key)}`}>Toate cele {num(contracts.total)} contracte →</Link>
        </div>
        <Card><CardContent className="pt-4"><ContractTable items={contracts.items} showCompany={false} /></CardContent></Card>
      </section>

      {!c.is_natural_person && <SubscribeForm targetType="company" targetKey={c.key} label={c.name} />}
    </div>
  );
}
