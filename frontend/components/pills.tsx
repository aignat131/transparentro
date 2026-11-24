import Link from "next/link";

export type Choice = { value: string | null; label: string };

/** Rând de butoane-link pentru filtre (an, domeniu, valoare): fiecare alegere e un link, merge fără JavaScript. */
export function Pills({ label, choices, selected, href }: {
  label: string;
  choices: Choice[];
  selected: string | null;
  href: (value: string | null) => string;
}) {
  const pill = "rounded-full border px-3 py-1 text-sm no-underline transition-colors";
  const on = "border-primary bg-primary text-primary-foreground";
  const off = "bg-white text-foreground hover:border-primary hover:text-primary";
  return (
    <nav aria-label={`Alege ${label.toLowerCase()}`} className="flex flex-wrap items-center gap-2">
      <span className="w-full text-sm font-medium sm:w-20">{label}:</span>
      {choices.map((c) => {
        const active = c.value === selected;
        return (
          <Link key={c.value ?? "_"} href={href(c.value)} scroll={false} aria-current={active ? "page" : undefined}
            className={`${pill} ${active ? on : off}`}>
            {c.label}
          </Link>
        );
      })}
    </nav>
  );
}

export const ALL_YEARS = "toti";

/** Anul ales din URL: implicit cel mai recent an cu date; „toti” = toți anii (null). */
export function pickYear(raw: string | undefined, years: number[]): number | null {
  if (raw === ALL_YEARS) return null;
  if (raw && years.includes(Number(raw))) return Number(raw);
  return years[0] ?? null;
}

export function yearChoices(years: number[]): Choice[] {
  return [...years.map((y) => ({ value: String(y), label: String(y) })), { value: ALL_YEARS, label: "Toți anii" }];
}

/** Construiește un link cu parametrii nevizi. */
export function hrefWith(path: string, params: Record<string, string | null | undefined>): string {
  const q = Object.entries(params)
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}=${encodeURIComponent(v as string)}`)
    .join("&");
  return q ? `${path}?${q}` : path;
}
