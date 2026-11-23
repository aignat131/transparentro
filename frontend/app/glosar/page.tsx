import type { Metadata } from "next";

import { GLOSSARY } from "@/lib/glossary";

export const metadata: Metadata = { title: "Glosar", description: "Termenii tehnici din achizițiile publice, explicați simplu." };

export default function GlossaryPage() {
  const items = Object.entries(GLOSSARY).sort((a, b) => a[1].term.localeCompare(b[1].term, "ro"));
  return (
    <article className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl">Glosar</h1>
      <dl className="divide-y rounded-lg border bg-white">
        {items.map(([id, e]) => (
          <div key={id} id={id} className="p-4">
            <dt className="font-semibold">{e.term}</dt>
            <dd className="mt-1 text-sm text-muted-foreground">{e.text}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}
