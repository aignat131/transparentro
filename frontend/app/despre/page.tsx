import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Despre proiect" };

export default function AboutPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl">Despre TransparentRO</h1>
      <p>
        TransparentRO arată, pe înțelesul oricui, cum cheltuie instituțiile publice banii: ce cumpără, de la cine și cu
        cât. Datele există deja public, dar sunt împrăștiate în fișiere mari și greu de citit. Noi le adunăm, le legăm
        între ele și le explicăm.
      </p>
      <p>
        Proiectul pornește cu județul Sibiu și este construit să poată fi extins la toate județele: județul este un
        parametru, nu o presupunere.
      </p>
      <h2 className="text-xl">Principii</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>Doar date din surse oficiale, cu link la sursă pentru fiecare înregistrare.</li>
        <li>Limbaj neutru: semnalele sunt întrebări, nu acuzații.</li>
        <li>Respectarea datelor personale: persoanele fizice nu sunt nominalizate.</li>
        <li>Metodologie publică și praguri configurabile.</li>
        <li>Erorile se corectează: <Link href="/disclaimer#corectie">trimiteți o corecție</Link>.</li>
      </ul>
      <p>
        Pentru programatori: există un API public documentat (OpenAPI) și export CSV pentru orice listă filtrată.
      </p>
    </article>
  );
}
