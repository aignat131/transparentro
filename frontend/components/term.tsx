"use client";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { GLOSSARY } from "@/lib/glossary";

/** Termen tehnic cu explicație (tooltip accesibil: hover, focus, atingere). */
export function Term({ id, children }: { id: keyof typeof GLOSSARY | string; children?: React.ReactNode }) {
  const entry = GLOSSARY[id];
  if (!entry) return <>{children}</>;
  return (
    <Popover>
      <PopoverTrigger
        className="cursor-help border-b border-dotted border-current text-left"
        aria-label={`Ce înseamnă: ${entry.term}`}
      >
        {children ?? entry.term}
      </PopoverTrigger>
      <PopoverContent role="tooltip">
        <p className="mb-1 font-semibold">{entry.term}</p>
        <p className="text-muted-foreground">{entry.text}</p>
      </PopoverContent>
    </Popover>
  );
}
