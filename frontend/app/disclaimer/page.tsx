import type { Metadata } from "next";

import { CorrectionForm } from "@/components/forms";

export const metadata: Metadata = { title: "Disclaimer legal și corecții" };

export default function DisclaimerPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl">Disclaimer legal</h1>
      <ul className="list-disc space-y-2 pl-5">
        <li>
          <strong>Datele provin din surse oficiale publice</strong> (SEAP/SICAP prin data.gov.ro, ANAF, ONRC, BNR) și sunt
          afișate așa cum au fost publicate de aceste instituții. Nu garantăm exactitatea datelor primare.
        </li>
        <li>
          <strong>Semnalele de verificat nu sunt acuzații.</strong> Ele sunt rezultatul unor reguli automate, publice, și
          indică doar situații care pot merita o analiză suplimentară. Existența unui semnal nu înseamnă că o instituție,
          o firmă sau o persoană a încălcat legea.
        </li>
        <li>
          <strong>Date personale:</strong> nu publicăm numele persoanelor fizice, ale persoanelor fizice autorizate sau ale
          întreprinderilor individuale/familiale; afișăm doar „Persoană fizică autorizată” și localitatea.
        </li>
        <li>
          <strong>Date sintetice:</strong> în mediile de dezvoltare pot fi afișate date generate artificial, marcate clar cu
          eticheta „sintetic” și cu un banner. Acestea nu descriu entități reale.
        </li>
        <li>Informațiile au caracter informativ și nu constituie consultanță juridică.</li>
      </ul>
      <section id="corectie" className="rounded-lg border bg-white p-4">
        <h2 className="mb-2 text-xl">Formular de corecție</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Ați găsit o informație greșită sau reprezentați o instituție/firmă și doriți o rectificare? Scrieți-ne. Analizăm
          fiecare cerere și corectăm datele care nu corespund surselor oficiale.
        </p>
        <CorrectionForm />
      </section>
    </article>
  );
}
