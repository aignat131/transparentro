import Link from "next/link";
import { AlertCircle } from "lucide-react";

import { SyntheticBadge } from "@/components/data-banner";
import type { ContractItem, NamedTotal } from "@/lib/api";
import { date, lei, pct } from "@/lib/format";

export function CompanyLink({ c }: { c: ContractItem["company"] }) {
  if (!c) return <span className="text-muted-foreground">—</span>;
  return (
    <Link href={`/firme/${encodeURIComponent(c.key)}`}>
      {c.name}
      {c.is_natural_person && c.locality ? <span className="text-muted-foreground"> ({c.locality})</span> : null}
    </Link>
  );
}

export function ContractTable({ items, showAuthority = true, showCompany = true }: {
  items: ContractItem[];
  showAuthority?: boolean;
  showCompany?: boolean;
}) {
  if (!items.length) return <p className="text-muted-foreground">Nu am găsit contracte pentru criteriile alese.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="contract-table">
        <thead className="border-b text-left text-muted-foreground">
          <tr>
            <th scope="col" className="py-2 pr-3 font-medium">Data</th>
            <th scope="col" className="py-2 pr-3 font-medium">Ce s-a cumpărat</th>
            {showAuthority && <th scope="col" className="py-2 pr-3 font-medium">Instituție</th>}
            {showCompany && <th scope="col" className="py-2 pr-3 font-medium">Furnizor</th>}
            <th scope="col" className="py-2 pr-3 text-right font-medium">Valoare</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id} className="border-b align-top last:border-0">
              <td className="whitespace-nowrap py-2 pr-3 tabular">{date(c.contract_date)}</td>
              <td className="py-2 pr-3">
                <Link href={`/contracte/${c.id}`} className="font-medium">
                  {c.title || c.cpv_name || `Contract #${c.id}`}
                </Link>
                <div className="text-xs text-muted-foreground">
                  {c.category} · {c.procedure_type || "procedură necunoscută"}
                  {c.signal_count > 0 && (
                    <span className="ml-2 inline-flex items-center gap-1 text-amber-800">
                      <AlertCircle className="h-3 w-3" aria-hidden /> {c.signal_count} semnal{c.signal_count > 1 ? "e" : ""}
                    </span>
                  )}
                  {c.duplicate_of_id && <span className="ml-2" title="Valoarea nu intră în totaluri">(nu se adună în totaluri)</span>}
                  <SyntheticBadge show={c.is_synthetic} />
                </div>
              </td>
              {showAuthority && (
                <td className="py-2 pr-3">
                  <Link href={`/institutii/${c.authority.id}`}>{c.authority.name}</Link>
                </td>
              )}
              {showCompany && (
                <td className="py-2 pr-3">
                  <CompanyLink c={c.company} />
                </td>
              )}
              <td className="whitespace-nowrap py-2 pr-3 text-right font-medium tabular">{lei(c.value_ron)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TotalsTable({ rows, linkBase, caption, nameHeader = "Nume" }: {
  rows: NamedTotal[];
  linkBase?: string;
  caption: string;
  nameHeader?: string;
}) {
  if (!rows.length) return <p className="text-muted-foreground">Nu există date.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b text-left text-muted-foreground">
          <tr>
            <th scope="col" className="hidden py-2 pr-3 font-medium sm:table-cell">#</th>
            <th scope="col" className="py-2 pr-3 font-medium">{nameHeader}</th>
            <th scope="col" className="hidden py-2 pr-3 text-right font-medium sm:table-cell">Contracte</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">Total</th>
            <th scope="col" className="hidden py-2 text-right font-medium sm:table-cell">Pondere</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.key}-${r.name}-${i}`} className="border-b last:border-0">
              <td className="hidden py-2 pr-3 text-muted-foreground tabular sm:table-cell">{i + 1}</td>
              <td className="py-2 pr-3">
                {linkBase && r.key ? <Link href={`${linkBase}/${encodeURIComponent(r.key)}`}>{r.name}</Link> : r.name}
              </td>
              <td className="hidden py-2 pr-3 text-right tabular sm:table-cell">{r.count}</td>
              <td className="whitespace-nowrap py-2 pr-3 text-right tabular">{lei(r.total_ron)}</td>
              <td className="hidden py-2 text-right tabular sm:table-cell">{pct(r.share, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
