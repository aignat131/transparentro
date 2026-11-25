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

const LOWER_WORDS = new Set(["de", "din", "si", "și", "la", "cu", "pentru", "a", "al", "ale", "in", "în", "pe", "sau"]);
const KEEP_UPPER = /^(S\.?A\.?|S\.?R\.?L\.?|R\.?A\.?|SRL|SA|RA|UAT|DGASPC|ISU|CJ|ONG|IT|SMIS|II|III|IV)$/;

/** „SPITALUL CLINIC JUDETEAN” → „Spitalul Clinic Judetean”; textele scrise normal rămân la fel. */
export function prettyName(s: string | null | undefined): string {
  if (!s) return "";
  const letters = s.replace(/[^A-Za-zĂÂÎȘȚŞŢăâîșțşţ]/g, "");
  const upper = letters.replace(/[^A-ZĂÂÎȘȚŞŢ]/g, "").length;
  if (!letters || upper / letters.length < 0.7) return s.trim();
  return s
    .trim()
    .toLowerCase()
    .split(/(\s+)/)
    .map((w, i) => {
      if (/^\s+$/.test(w)) return w;
      if (KEEP_UPPER.test(w.toUpperCase())) return w.toUpperCase();
      if (i > 0 && LOWER_WORDS.has(w)) return w;
      return w.charAt(0).toUpperCase() + w.slice(1);
    })
    .join("");
}

/** Obiectul unui contract ca bucată de propoziție: fără majuscule în exces, scurtat. */
export function asPhrase(title: string | null | undefined, max = 140): string {
  if (!title) return "un contract fără descriere";
  let t = title.replace(/\s+/g, " ").trim().replace(/^["„”'«]+|["„”'»]+$/g, "");
  const letters = t.replace(/[^A-Za-zĂÂÎȘȚŞŢăâîșțşţ]/g, "");
  const upper = letters.replace(/[^A-ZĂÂÎȘȚŞŢ]/g, "").length;
  t = t.replace(/\s*\(Rev\.\s*\d+\)/gi, ""); // „(Rev.2)” din denumirile CPV
  if (letters && upper / letters.length > 0.7) t = t.toLowerCase();
  else if (/^[A-ZĂÂÎȘȚŞŢ][a-zăâîșțşţ]/.test(t)) t = t.charAt(0).toLowerCase() + t.slice(1);
  if (t.length > max) t = t.slice(0, max).replace(/\s+\S*$/, "") + "…";
  return t;
}
