import type { Metadata } from "next";

import { MapClient } from "@/components/map-client";
import { sp } from "@/components/pagination";
import { Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api, DEFAULT_COUNTY, type MapPoint, type Meta } from "@/lib/api";
import { leiShort, num } from "@/lib/format";

export const metadata: Metadata = {
  title: "Harta cheltuielilor",
  description: "Harta instituțiilor publice din județ, cu bule proporționale cu valoarea contractelor.",
};

export default async function MapPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const year = sp(searchParams.year);
  const [points, meta] = await Promise.all([
    api<MapPoint[]>("/map/authorities", { county: DEFAULT_COUNTY, year }),
    api<Meta>("/meta", { county: DEFAULT_COUNTY }, 600),
  ]);
  const county = meta.counties.find((c) => c.code === DEFAULT_COUNTY);
  const center: [number, number] = county ? [county.lat, county.lon] : [45.9, 24.9];
  const top = [...points].sort((a, b) => Number(b.total_ron) - Number(a.total_ron)).slice(0, 10);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl">Harta cheltuielilor{county ? ` — județul ${county.name}` : ""}</h1>
      <p className="text-sm text-muted-foreground">
        Fiecare bulă grupează instituțiile dintr-o localitate; suprafața ei e proporțională cu valoarea totală a
        contractelor. Apăsați pe o bulă pentru detalii.
      </p>
      <form method="get" className="flex items-end gap-2">
        <div>
          <label htmlFor="f-year" className="text-sm font-medium">An</label>
          <Select id="f-year" name="year" defaultValue={year ?? ""}>
            <option value="">Toți anii</option>
            {meta.years.map((y) => <option key={y}>{y}</option>)}
          </Select>
        </div>
        <Button type="submit">Afișează</Button>
      </form>
      <MapClient points={points} center={center} />
      <section aria-labelledby="tabel-harta">
        <h2 id="tabel-harta" className="mb-2 text-lg">Primele 10 instituții (varianta tabelară a hărții)</h2>
        <table className="w-full text-sm">
          <thead className="border-b text-left text-muted-foreground">
            <tr><th scope="col" className="py-2">Instituție</th><th scope="col" className="py-2">Localitate</th><th scope="col" className="py-2 text-right">Contracte</th><th scope="col" className="py-2 text-right">Total</th></tr>
          </thead>
          <tbody>
            {top.map((p) => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="py-2"><a href={`/institutii/${p.id}`}>{p.name}</a></td>
                <td className="py-2">{p.locality}</td>
                <td className="py-2 text-right tabular">{num(p.contracts)}</td>
                <td className="py-2 text-right tabular">{leiShort(p.total_ron)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
