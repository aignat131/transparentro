const nf = new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const nf1 = new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 1 });

function toNum(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

export function lei(v: string | number | null | undefined, exact = false): string {
  const n = toNum(v);
  if (n === null) return "—";
  return `${exact ? nf2.format(n) : nf.format(n)} lei`;
}

/** 1.234.567 → „1,2 mil. lei” */
export function leiShort(v: string | number | null | undefined): string {
  const n = toNum(v);
  if (n === null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${nf1.format(n / 1e9)} mld. lei`;
  if (abs >= 1e6) return `${nf1.format(n / 1e6)} mil. lei`;
  if (abs >= 1e3) return `${nf1.format(n / 1e3)} mii lei`;
  return `${nf.format(n)} lei`;
}

export function num(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : nf.format(v);
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(digits).replace(".", ",")}%`;
}

export function date(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("ro-RO", { day: "2-digit", month: "2-digit", year: "numeric" });
}
