import Link from "next/link";

import { ShareButton } from "@/components/actions";
import type { ContractItem } from "@/lib/api";
import { asPhrase, date, leiShort, prettyName } from "@/lib/format";

/** Un contract spus ca o propoziție: cine a plătit, cât, pentru ce, cui. */
export function storyText(c: ContractItem): { headline: string; who: string } {
  const buyer = prettyName(c.authority.name);
  const headline = `${buyer} a plătit ${leiShort(c.value_ron)} pentru ${asPhrase(c.title)}`;
  const who = c.company ? `Banii au mers la ${prettyName(c.company.name)}` : "Furnizorul nu apare în date";
  return { headline, who };
}

export function StoryCard({ c, badge }: { c: ContractItem; badge?: string }) {
  const { headline, who } = storyText(c);
  const path = `/contracte/${c.id}`;
  return (
    <li className="rounded-lg border bg-white">
      <Link href={path} className="block p-4 text-foreground no-underline hover:bg-slate-50">
        {badge && <p className="text-xs font-medium uppercase tracking-wide text-primary">{badge}</p>}
        <p className="mt-1 font-semibold leading-snug">{headline}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {who}
          {c.contract_date ? ` · ${date(c.contract_date)}` : ""}
        </p>
      </Link>
      <div className="flex items-center justify-between border-t px-4 py-2">
        <Link href={path} className="text-sm">Detalii și sursa oficială →</Link>
        <ShareButton title="TransparentRO" text={headline} path={path} />
      </div>
    </li>
  );
}
