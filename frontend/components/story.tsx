import Link from "next/link";

import { ShareButton } from "@/components/actions";
import type { ContractItem } from "@/lib/api";
import { asPhrase, date, leiShort, prettyName } from "@/lib/format";

/** Un contract spus ca o propoziție: cine a plătit, cât, pentru ce, cui. */
export function storyText(c: ContractItem, partners: string[] = []): { headline: string; who: string } {
  const buyer = prettyName(c.authority.name);
  const headline = `${buyer} a plătit ${leiShort(c.value_ron)} pentru ${asPhrase(c.title)}`;
  const names = [...new Set([c.company?.name, ...partners].filter(Boolean).map((n) => prettyName(n as string)))];
  const who =
    names.length === 0
      ? "Furnizorul nu apare în date"
      : names.length === 1
        ? `Banii au mers la ${names[0]}`
        : `Câștigat în asociere de ${names.slice(0, -1).join(", ")} și ${names[names.length - 1]}`;
  return { headline, who };
}

export type Story = { c: ContractItem; partners: string[] };

/**
 * Un contract câștigat de mai multe firme în asociere apare în SEAP pe mai multe rânduri, cu aceeași
 * valoare. Ca povești le unim într-una singură, cu toate firmele.
 */
export function toStories(items: ContractItem[], limit: number): Story[] {
  const out: Story[] = [];
  const seen = new Map<string, Story>();
  for (const c of items) {
    const key = [c.authority.id, c.value_ron, c.title, c.contract_date].join("|");
    const prev = seen.get(key);
    if (prev) {
      if (c.company) prev.partners.push(c.company.name);
      continue;
    }
    const s = { c, partners: [] };
    seen.set(key, s);
    out.push(s);
  }
  return out.slice(0, limit);
}

export function StoryCard({ c, partners = [], badge }: { c: ContractItem; partners?: string[]; badge?: string }) {
  const { headline, who } = storyText(c, partners);
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
