import { SlidersHorizontal } from "lucide-react";

/** Filtrele unei liste, strânse sub un buton: pe telefon lista apare prima, filtrele doar la cerere. */
export function FilterPanel({ active, children }: { active: (string | null | undefined | false)[]; children: React.ReactNode }) {
  const on = active.filter(Boolean) as string[];
  return (
    <details className="group rounded-lg border bg-white">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm [&::-webkit-details-marker]:hidden">
        <SlidersHorizontal className="h-4 w-4" aria-hidden />
        <span className="font-medium">Filtre și căutare</span>
        {on.length > 0 && <span className="truncate text-muted-foreground">· {on.join(" · ")}</span>}
        <span className="ml-auto text-muted-foreground group-open:hidden">Arată</span>
        <span className="ml-auto hidden text-muted-foreground group-open:inline">Ascunde</span>
      </summary>
      <div className="border-t">{children}</div>
    </details>
  );
}
