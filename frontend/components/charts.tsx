"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { NamedTotal, YearTotal } from "@/lib/api";
import { lei, leiShort, pct } from "@/lib/format";

// O singură serie per grafic → o singură culoare (albastru, slotul 1 al paletei validate),
// fără legendă (titlul numește seria). Bare ≤ 24px, capăt rotunjit 4px, grilă discretă.
const SERIES = "#2a78d6";
const GRID = "#e4e4e0";
const INK_MUTED = "#52514e";
// etichete scurte pe bare: „4,3 mld.” (unitatea „lei” e în titlu/tooltip)
const short = (v: number) => leiShort(v).replace(/ lei$/, "");

type TipProps = { active?: boolean; payload?: { payload: { label: string; total: number; count: number; share?: number | null } }[] };

function Tip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border bg-white px-3 py-2 text-sm shadow-md">
      <p className="font-semibold">{d.label}</p>
      <p className="tabular">{lei(d.total)}</p>
      <p className="text-muted-foreground">
        {d.count.toLocaleString("ro-RO")} contracte{d.share != null ? ` · ${pct(d.share, 1)} din total` : ""}
      </p>
    </div>
  );
}

export function YearChart({ data, title }: { data: YearTotal[]; title: string }) {
  const rows = data.map((d) => ({ label: String(d.year), total: Number(d.total_ron), count: d.count }));
  if (!rows.length) return <p className="text-muted-foreground">Nu există date.</p>;
  return (
    <figure>
      <figcaption className="sr-only">{title}</figcaption>
      <div className="h-64 w-full" role="img" aria-label={`${title}: ${rows.map((r) => `${r.label} ${leiShort(r.total)}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 28, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: GRID }} tick={{ fill: INK_MUTED, fontSize: 12 }} />
            <YAxis
              tickFormatter={short}
              tickLine={false}
              axisLine={false}
              width={70}
              tick={{ fill: INK_MUTED, fontSize: 12 }}
            />
            <Tooltip content={<Tip />} cursor={{ fill: "rgba(42,120,214,0.08)" }} />
            <Bar
              dataKey="total"
              fill={SERIES}
              isAnimationActive={false}
              maxBarSize={24}
              radius={[4, 4, 0, 0]}
              label={{ position: "top", fill: "#0b0b0b", fontSize: 12, formatter: short }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export function CategoryChart({ data, title, limit = 8 }: { data: NamedTotal[]; title: string; limit?: number }) {
  const top = data.slice(0, limit);
  const rest = data.slice(limit);
  const rows = top.map((d) => ({ label: d.name, total: Number(d.total_ron), count: d.count, share: d.share }));
  if (rest.length) {
    rows.push({
      label: "Altele",
      total: rest.reduce((s, d) => s + Number(d.total_ron), 0),
      count: rest.reduce((s, d) => s + d.count, 0),
      share: rest.reduce((s, d) => s + (d.share ?? 0), 0),
    });
  }
  if (!rows.length) return <p className="text-muted-foreground">Nu există date.</p>;
  return (
    <figure>
      <figcaption className="sr-only">{title}</figcaption>
      <div className="w-full" style={{ height: rows.length * 36 + 20 }} role="img" aria-label={`${title}: ${rows.map((r) => `${r.label} ${pct(r.share)}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 72, left: 8, bottom: 0 }}>
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="label"
              width={170}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#0b0b0b", fontSize: 12 }}
            />
            <Tooltip content={<Tip />} cursor={{ fill: "rgba(42,120,214,0.08)" }} />
            <Bar
              dataKey="total"
              fill={SERIES}
              isAnimationActive={false}
              maxBarSize={20}
              radius={[0, 4, 4, 0]}
              label={{ position: "right", fill: "#52514e", fontSize: 12, formatter: short }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
