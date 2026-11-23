"use client";

import "leaflet/dist/leaflet.css";

import Link from "next/link";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";

import type { MapPoint } from "@/lib/api";
import { leiShort } from "@/lib/format";

type Group = { key: string; lat: number; lon: number; locality: string; total: number; items: MapPoint[] };

/** Bule proporționale (aria ∝ cheltuieli), grupate pe localitate ca să nu se suprapună. */
export default function AuthorityMap({ points, center }: { points: MapPoint[]; center: [number, number] }) {
  const groups = new Map<string, Group>();
  for (const p of points) {
    const key = `${p.lat.toFixed(4)}|${p.lon.toFixed(4)}`;
    const g = groups.get(key) ?? { key, lat: p.lat, lon: p.lon, locality: p.locality ?? "", total: 0, items: [] };
    g.total += Number(p.total_ron);
    g.items.push(p);
    groups.set(key, g);
  }
  const list = [...groups.values()].sort((a, b) => b.total - a.total);
  const max = Math.max(1, ...list.map((g) => g.total));
  return (
    <MapContainer center={center} zoom={9} scrollWheelZoom={false} className="h-[520px] w-full rounded-lg border">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {list.map((g) => (
        <CircleMarker
          key={g.key}
          center={[g.lat, g.lon]}
          radius={6 + 34 * Math.sqrt(g.total / max)}
          pathOptions={{ color: "#ffffff", weight: 2, fillColor: "#2a78d6", fillOpacity: 0.6 }}
        >
          <Popup>
            <div className="max-h-64 overflow-y-auto text-sm">
              <p className="font-semibold">{g.locality || "Localitate necunoscută"}</p>
              <p className="mb-2">Total: {leiShort(g.total)}</p>
              <ul className="space-y-1">
                {g.items
                  .sort((a, b) => Number(b.total_ron) - Number(a.total_ron))
                  .slice(0, 15)
                  .map((p) => (
                    <li key={p.id}>
                      <Link href={`/institutii/${p.id}`}>{p.name}</Link> — {leiShort(p.total_ron)}
                    </li>
                  ))}
                {g.items.length > 15 && <li>… și încă {g.items.length - 15} instituții</li>}
              </ul>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
