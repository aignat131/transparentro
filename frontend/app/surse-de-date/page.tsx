import type { Metadata } from "next";

import { api, type Overview } from "@/lib/api";
import { date, num } from "@/lib/format";

export const metadata: Metadata = { title: "Surse de date", description: "Sursele oficiale folosite de TransparentRO." };

const SOURCES = [
  {
    name: "SEAP / SICAP — rapoarte de achiziții publice",
    who: "Autoritatea pentru Digitalizarea României, pe data.gov.ro",
    url: "https://data.gov.ro/dataset?q=achizitii+publice",
    format: "Fișiere Excel (XLSX/XLS/ODS) trimestriale: achiziții directe, contracte, atribuiri fără anunț, anunțuri de inițiere, modificări de contract.",
    freq: "Trimestrial, cu întârziere de 1–2 luni",
  },
  {
    name: "ANAF — date despre firme și instituții",
    who: "Agenția Națională de Administrare Fiscală",
    url: "https://www.anaf.ro",
    format: "Serviciu web public (JSON, versiunea 9): denumire, adresă, data înregistrării, cod CAEN, stare, TVA; plus bilanțuri anuale (cifră de afaceri, angajați).",
    freq: "Zilnic (date fiscale), anual (bilanțuri)",
  },
  {
    name: "ONRC — firme înregistrate",
    who: "Oficiul Național al Registrului Comerțului, pe data.gov.ro",
    url: "https://data.gov.ro/organization/onrc",
    format: "Fișiere CSV: denumire, CUI, număr de înmatriculare, data înmatriculării, formă juridică, stare.",
    freq: "Periodic (lunar–trimestrial)",
  },
  {
    name: "BNR — cursuri de schimb",
    who: "Banca Națională a României",
    url: "https://curs.bnr.ro/nbrfxrates.xml",
    format: "XML zilnic și anual.",
    freq: "Zilnic (zile lucrătoare)",
  },
  {
    name: "OpenStreetMap — hartă și coordonate localități",
    who: "Contribuitorii OpenStreetMap (serviciul Nominatim)",
    url: "https://www.openstreetmap.org/copyright",
    format: "Coordonatele localităților sunt cerute o singură dată și păstrate local.",
    freq: "La nevoie",
  },
];

export default async function SourcesPage() {
  let ov: Overview | null = null;
  try {
    ov = await api<Overview>("/stats/overview", { county: "all" });
  } catch {
    /* pagina rămâne utilă și fără API */
  }
  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-3xl">Surse de date</h1>
      {ov && (
        <div className="rounded-lg border bg-white p-4 text-sm">
          <p>Contracte din surse reale: <strong>{num(ov.data.real_contracts)}</strong></p>
          <p>Contracte sintetice (demonstrative): <strong>{num(ov.data.synthetic_contracts)}</strong></p>
          <p>Perioadă acoperită: {date(ov.data.coverage_from)} – {date(ov.data.coverage_to)}</p>
          <p>Ultimul import SEAP reușit: {date(ov.data.last_import_at)}</p>
        </div>
      )}
      {SOURCES.map((s) => (
        <section key={s.name} className="rounded-lg border bg-white p-4">
          <h2 className="text-lg">{s.name}</h2>
          <p className="text-sm text-muted-foreground">{s.who}</p>
          <p className="mt-2 text-sm">{s.format}</p>
          <p className="mt-1 text-sm"><strong>Actualizare:</strong> {s.freq}</p>
          <a href={s.url} className="mt-1 inline-block text-sm" target="_blank" rel="noopener noreferrer">{s.url}</a>
        </section>
      ))}
      <p className="text-sm text-muted-foreground">
        Folosim exporturile oficiale; nu extragem date prin scraping. Fiecare înregistrare importată păstrează sursa,
        adresa fișierului, data importului și o amprentă a conținutului.
      </p>
    </article>
  );
}
