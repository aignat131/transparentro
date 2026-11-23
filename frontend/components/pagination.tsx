import Link from "next/link";

type Params = Record<string, string | string[] | undefined>;

function href(base: string, params: Params, page: number): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (k === "page" || v === undefined || v === "") continue;
    p.set(k, Array.isArray(v) ? v[0] : v);
  }
  if (page > 1) p.set("page", String(page));
  const s = p.toString();
  return s ? `${base}?${s}` : base;
}

export function Pagination({ base, params, page, pageSize, total }: {
  base: string;
  params: Params;
  page: number;
  pageSize: number;
  total: number;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <nav aria-label="Paginare" className="mt-4 flex items-center justify-between text-sm">
      {page > 1 ? <Link href={href(base, params, page - 1)} rel="prev">← Pagina anterioară</Link> : <span />}
      <span className="text-muted-foreground">
        Pagina {page} din {pages.toLocaleString("ro-RO")}
      </span>
      {page < pages ? <Link href={href(base, params, page + 1)} rel="next">Pagina următoare →</Link> : <span />}
    </nav>
  );
}

export function sp(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export function pageNum(v: string | string[] | undefined): number {
  const n = Number(sp(v));
  return Number.isInteger(n) && n > 0 ? n : 1;
}
