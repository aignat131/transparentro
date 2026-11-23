"use client";

import dynamic from "next/dynamic";

import type { MapPoint } from "@/lib/api";

// Leaflet folosește `window` → se încarcă doar în browser.
const AuthorityMap = dynamic(() => import("@/components/authority-map"), {
  ssr: false,
  loading: () => <div className="flex h-[520px] items-center justify-center rounded-lg border bg-muted text-sm">Se încarcă harta…</div>,
});

export function MapClient(props: { points: MapPoint[]; center: [number, number] }) {
  return <AuthorityMap {...props} />;
}
