import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink } from "lucide-react";

import { SyntheticBadge } from "@/components/data-banner";
import { ExplainBox } from "@/components/forms";
import { SignalCard, SignalsNote } from "@/components/signals";
import { CompanyLink } from "@/components/tables";
import { Term } from "@/components/term";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, type ContractDetail } from "@/lib/api";
import { date, lei, num } from "@/lib/format";

async function load(id: string): Promise<ContractDetail> {
  if (!/^\d+$/.test(id)) notFound();
  try {
    return await api<ContractDetail>(`/contracts/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const c = await load(params.id);
  const title = c.title || c.cpv_name || `Contract #${c.id}`;
  const description = `${c.authority.name} a plătit ${lei(c.value_ron)} către ${c.company?.name ?? "un furnizor"} (${date(c.contract_date)}).`;
  return { title, description, alternates: { canonical: `/contracte/${c.id}` }, openGraph: { title, description } };
}

function procedureTerm(p: string | null): string | undefined {
  const s = (p || "").toLowerCase();
  if (s.includes("directă") || s.includes("directa")) return "achizitie_directa";
  if (s.includes("licitatie") || s.includes("licitație")) return "licitatie_deschisa";
  if (s.includes("simplificat")) return "procedura_simplificata";
  if (s.includes("negociere")) return "negociere_fara_publicare";
  return undefined;
}

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-b py-2 text-sm last:border-0 sm:grid-cols-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="sm:col-span-2">{children}</dd>
    </div>
  );
}

export default async function ContractPage({ params }: { params: { id: string } }) {
  const c = await load(params.id);
  const title = c.title || c.cpv_name || `Contract #${c.id}`;
  const pt = procedureTerm(c.procedure_type);
  const sourceName: Record<string, string> = {
    ad: "Achiziții directe (SEAP)",
    dan: "Notificări de achiziție directă (SEAP)",
    contracte: "Contracte atribuite prin procedură (SEAP)",
    atribuire_fara: "Atribuiri fără anunț de inițiere (SEAP)",
  };
  return (
    <div className="space-y-6">
      <nav aria-label="Fir de navigare" className="text-sm text-muted-foreground">
        <Link href="/contracte">Contracte</Link> / #{c.id}
      </nav>
      <header>
        <h1 className="text-2xl md:text-3xl">
          {title}
          <SyntheticBadge show={c.is_synthetic} />
        </h1>
        <p className="mt-3 rounded-lg border bg-white p-4 text-base leading-relaxed">
          Pe scurt: <Link href={`/institutii/${c.authority.id}`}>{c.authority.name}</Link> a cumpărat{" "}
          <strong>{c.category.toLowerCase()}</strong> de la <CompanyLink c={c.company} /> pentru{" "}
          <strong className="tabular">{lei(c.value_ron, true)}</strong>
          {c.contract_date ? `, contract din ${date(c.contract_date)}` : null}. Atribuirea s-a făcut prin{" "}
          {pt ? <Term id={pt}>{c.procedure_type}</Term> : c.procedure_type || "o procedură necunoscută"}.
          {c.amendments.length > 0 && <> Contractul a fost modificat de {c.amendments.length} ori prin <Term id="act_aditional">acte adiționale</Term>.</>}
        </p>
      </header>

      {c.duplicate_of_id && (
        <p className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          {c.framework?.toLowerCase() === "cu acord cadru" ? (
            <>
              Acesta este un <Term id="acord_cadru">acord-cadru</Term>: valoarea lui e un maxim. Pentru că sub același
              anunț au fost raportate contracte subsecvente (cheltuiala efectivă), în totaluri numărăm subsecventele, nu
              această valoare. <Link href={`/contracte/${c.duplicate_of_id}`}>Vezi un contract subsecvent</Link>.
            </>
          ) : (
            <>
              Același contract apare în datele SEAP pe mai multe rânduri (o asociere de firme sau mai multe loturi
              cu valoarea totală repetată). Valoarea este numărată o singură dată, la{" "}
              <Link href={`/contracte/${c.duplicate_of_id}`}>rândul principal</Link>.
            </>
          )}
        </p>
      )}

      {c.signals.length > 0 && (
        <section aria-labelledby="semnale" className="space-y-3">
          <h2 id="semnale" className="text-xl">Semnale de verificat</h2>
          <SignalsNote />
          {c.signals.map((s) => <SignalCard key={s.id} s={s} />)}
        </section>
      )}

      <ExplainBox path={`/explain/${c.id}`} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Tot ce se știe despre contract</CardTitle></CardHeader>
          <CardContent>
            <dl>
              <Row label="Valoare">
                <span className="tabular">{lei(c.value_ron, true)}</span>
                {c.currency !== "RON" && c.original_value && (
                  <span className="text-muted-foreground"> (inițial {c.original_value} {c.currency}, curs BNR {c.exchange_rate})</span>
                )}
                <span className="block text-xs text-muted-foreground">Valoarea declarată în SEAP, de regulă fără TVA.</span>
              </Row>
              <Row label="Instituția">
                <Link href={`/institutii/${c.authority.id}`}>{c.authority.name}</Link>
              </Row>
              <Row label="Furnizorul"><CompanyLink c={c.company} /></Row>
              <Row label="Ce s-a cumpărat">
                {c.category}
                {c.cpv_code && (
                  <span className="block text-xs text-muted-foreground">
                    <Term id="cpv">CPV</Term> {c.cpv_code} — {c.cpv_name}
                  </span>
                )}
              </Row>
              <Row label="Tipul contractului">{c.contract_type || "—"}</Row>
              <Row label="Procedura">{c.procedure_type || "—"}</Row>
              <Row label="Data contractului">{date(c.contract_date)}</Row>
              <Row label="Data publicării">{date(c.publication_date)}</Row>
              {c.contract_number && <Row label="Număr contract">{c.contract_number}</Row>}
              {c.notice_number && <Row label="Număr anunț / achiziție">{c.notice_number}</Row>}
              {c.lot_number && <Row label="Lot">{c.lot_number}</Row>}
              {c.duration_days && <Row label="Durată">{num(c.duration_days)} zile</Row>}
              {c.framework && <Row label={<Term id="acord_cadru">Încheiat prin</Term>}>{c.framework}</Row>}
              {c.eu_funded != null && <Row label="Fonduri europene">{c.eu_funded ? `da${c.eu_program ? ` (${c.eu_program})` : ""}` : "nu"}</Row>}
            </dl>
          </CardContent>
        </Card>
        <div className="space-y-6">
          {c.procedure && (
            <Card>
              <CardHeader><CardTitle>Procedura de atribuire</CardTitle></CardHeader>
              <CardContent className="text-sm">
                <dl className="space-y-2">
                  {c.procedure.title && <div><dt className="text-muted-foreground">Denumire</dt><dd>{c.procedure.title}</dd></div>}
                  <div><dt className="text-muted-foreground">Anunț inițiere</dt><dd>{c.procedure.notice_number || "—"}</dd></div>
                  <div>
                    <dt className="text-muted-foreground"><Term id="valoare_estimata">Valoare estimată</Term></dt>
                    <dd className="tabular">{lei(c.procedure.estimated_value_ron)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Număr de oferte</dt>
                    <dd>{c.procedure.number_of_offers ?? "nepublicat în datele deschise"}</dd>
                  </div>
                  {c.procedure.award_criteria && <div><dt className="text-muted-foreground">Criteriu</dt><dd>{c.procedure.award_criteria}</dd></div>}
                  {c.procedure.legislation && <div><dt className="text-muted-foreground">Lege</dt><dd>{c.procedure.legislation}</dd></div>}
                </dl>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>Sursa oficială</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>{sourceName[c.source] ?? c.source_dataset}</p>
              {c.source_url && (
                <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1">
                  Fișierul de date pe data.gov.ro <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
              )}
              {c.notice_number && !c.is_synthetic && (
                <p>
                  <a href={c.sicap_search_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1">
                    Caută „{c.notice_number}” pe e-licitatie.ro <ExternalLink className="h-3 w-3" aria-hidden />
                  </a>
                </p>
              )}
              <p className="text-xs text-muted-foreground">Ultima actualizare a datelor: {date(c.last_updated)}</p>
              {c.provenance[0] && (
                <p className="text-xs text-muted-foreground">
                  Importat prima dată: {date(c.provenance[0].first_seen_at)} · amprentă {c.provenance[0].content_hash.slice(0, 12)}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {c.amendments.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Acte adiționale / modificări</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-3">Data</th>
                  <th scope="col" className="py-2 pr-3">Descriere</th>
                  <th scope="col" className="py-2 pr-3 text-right">Înainte</th>
                  <th scope="col" className="py-2 pr-3 text-right">După</th>
                  <th scope="col" className="py-2 text-right">Diferență</th>
                </tr>
              </thead>
              <tbody>
                {c.amendments.map((m) => (
                  <tr key={m.id} className="border-b align-top last:border-0">
                    <td className="py-2 pr-3 tabular">{date(m.publication_date)}</td>
                    <td className="max-w-md py-2 pr-3">{m.description}</td>
                    <td className="py-2 pr-3 text-right tabular">{lei(m.value_before_ron)}</td>
                    <td className="py-2 pr-3 text-right tabular">{lei(m.value_after_ron)}</td>
                    <td className="py-2 text-right tabular">
                      {lei(m.delta_ron)}
                      {m.delta_pct != null && <span className="block text-xs text-muted-foreground">{m.delta_pct > 0 ? "+" : ""}{m.delta_pct.toFixed(1)}%</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
