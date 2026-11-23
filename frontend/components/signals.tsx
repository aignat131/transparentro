import Link from "next/link";
import { ExternalLink, Info } from "lucide-react";

import { SyntheticBadge } from "@/components/data-banner";
import { Term } from "@/components/term";
import type { Signal } from "@/lib/api";

function level(score: number): { label: string; cls: string } {
  if (score >= 70) return { label: "prioritate mare", cls: "border-amber-400 bg-amber-50 text-amber-900" };
  if (score >= 45) return { label: "prioritate medie", cls: "border-amber-200 bg-amber-50/60 text-amber-900" };
  return { label: "prioritate mică", cls: "border-slate-200 bg-slate-50 text-slate-700" };
}

export function SignalCard({ s, compact = false }: { s: Signal; compact?: boolean }) {
  const lv = level(s.score);
  return (
    <article className="rounded-lg border bg-white p-4" data-testid="signal-card">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1 rounded-full border border-slate-300 px-2 py-0.5 font-medium">
          <Info className="h-3 w-3" aria-hidden /> {s.signal_label}
        </span>
        <span className={`rounded-full border px-2 py-0.5 ${lv.cls}`}>
          Scor {s.score}/100 · {lv.label}
        </span>
        {s.year && <span className="text-muted-foreground">{s.year}</span>}
        <SyntheticBadge show={s.is_synthetic} />
      </div>
      <h3 className="font-semibold">{s.title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{s.explanation}</p>
      {!compact && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {s.authority && <Link href={`/institutii/${s.authority.id}`}>Instituția: {s.authority.name}</Link>}
          {s.company && <Link href={`/firme/${encodeURIComponent(s.company.key)}`}>Firma: {s.company.name}</Link>}
          {s.contract_id && <Link href={`/contracte/${s.contract_id}`}>Vezi contractul</Link>}
          {s.source_url && (
            <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1">
              Sursa oficială <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          )}
        </div>
      )}
    </article>
  );
}

export function SignalsNote() {
  return (
    <p className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
      <Term id="semnal">Semnalele</Term> sunt calculate automat din date publice și arată situații care merită o
      privire mai atentă. <strong>Nu sunt acuzații</strong> și nu dovedesc nereguli — de multe ori există explicații
      legitime. <Link href="/metodologie#semnale">Cum sunt calculate?</Link>
    </p>
  );
}
