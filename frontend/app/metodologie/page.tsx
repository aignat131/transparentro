import type { Metadata } from "next";
import Link from "next/link";

import { Term } from "@/components/term";

export const metadata: Metadata = {
  title: "Metodologie — cum citesc datele",
  description: "Cum colectăm, curățăm și interpretăm datele despre achizițiile publice și cum calculăm semnalele de verificat.",
};

const SIGNALS = [
  {
    id: "new_company",
    name: "Firmă nou-înființată la primul contract",
    rule: "Firma a primit primul contract public la mai puțin de 6 luni (183 de zile) după înregistrare.",
    why: "O firmă foarte nouă poate să nu aibă experiența cerută; uneori firmele sunt create special pentru un contract.",
    caveat: "Calculăm doar pentru firmele înființate după începutul perioadei acoperite de date, ca să fim siguri că e cu adevărat primul contract.",
  },
  {
    id: "single_bidder",
    name: "Procedură cu un singur ofertant",
    rule: "La o procedură competitivă s-a depus o singură ofertă.",
    why: "Lipsa concurenței poate indica cerințe restrictive sau o piață foarte mică.",
    caveat: "Rapoartele SEAP publicate pe data.gov.ro NU conțin numărul de oferte. Semnalul apare doar acolo unde această informație există.",
  },
  {
    id: "fragmentation",
    name: "Achiziții directe repetate (posibilă fragmentare)",
    rule: "Aceeași instituție face cel puțin 3 achiziții directe de la același furnizor, în același an, pentru aceeași categorie CPV (primele 3 cifre), iar suma lor depășește pragul legal; sau cel puțin 2 achiziții au fiecare peste 80% din prag.",
    why: "Legea interzice împărțirea unei achiziții în bucăți mai mici pentru a evita licitația.",
    caveat: "Pragurile (270.120 lei produse/servicii, 900.400 lei lucrări, fără TVA) sunt configurabile. Nevoile neprevăzute sau livrările eșalonate pot explica repetarea.",
  },
  {
    id: "amendment_increase",
    name: "Act adițional care crește valoarea cu peste 20%",
    rule: "Valoarea contractului după modificare este cu peste 20% mai mare decât înainte.",
    why: "Creșterile mari după atribuire pot însemna că oferta inițială a fost subdimensionată.",
    caveat: "Ajustările de preț prevăzute în contract sau lucrările suplimentare neprevăzute sunt legale.",
  },
  {
    id: "public_revenue_share",
    name: "Venituri majoritar din contracte publice",
    rule: "Contractele publice atribuite într-un an reprezintă cel puțin 50% din cifra de afaceri raportată la ANAF pentru același an.",
    why: "Dependența de bani publici este un context util pentru înțelegerea firmei.",
    caveat: "Un contract se poate întinde pe mai mulți ani, deci raportul e orientativ. Bilanțurile sunt cerute doar pentru furnizorii cu încasări publice semnificative.",
  },
  {
    id: "concentration",
    name: "Furnizor dominant la o instituție",
    rule: "Un furnizor primește peste 30% din valoarea contractată de o instituție într-un an (instituții cu minim 200.000 lei și 5 contracte în acel an).",
    why: "Concentrarea mare poate reduce concurența.",
    caveat: "Poate fi firească: furnizor unic de utilități, o singură investiție mare într-un an.",
  },
];

export default function MethodologyPage() {
  return (
    <article className="prose-sm mx-auto max-w-3xl space-y-6">
      <h1 className="text-3xl">Cum citesc datele?</h1>
      <section className="space-y-2">
        <h2 className="text-xl">De unde vin datele</h2>
        <p>
          Contractele provin din rapoartele trimestriale SEAP/SICAP publicate de Autoritatea pentru Digitalizarea României
          pe <a href="https://data.gov.ro">data.gov.ro</a>: <Term id="achizitie_directa">achiziții directe</Term>, contracte
          atribuite prin proceduri, atribuiri fără anunț și <Term id="act_aditional">modificări de contract</Term>. Datele
          firmelor vin de la ANAF și ONRC, iar cursurile valutare de la BNR. Detalii în{" "}
          <Link href="/surse-de-date">Surse de date</Link>.
        </p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl">Cum prelucrăm datele</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Legăm sursele prin <Term id="cui">CUI</Term></strong>, normalizat (fără „RO”, spații sau zerouri la început).
            Aceeași firmă scrisă diferit („S.C. ALFA S.R.L.”, „Alfa SRL”) este tratată ca o singură firmă; variantele de nume sunt păstrate.
          </li>
          <li>
            <strong>Județul instituției</strong> nu apare în rapoartele SEAP. Îl aflăm din registrul ANAF, după CUI-ul instituției (adresa sediului).
          </li>
          <li><strong>Valorile sunt în lei</strong>, așa cum sunt declarate în SEAP (de regulă fără TVA). Sumele în alte valute sunt convertite la cursul BNR din ziua contractului.</li>
          <li>
            <strong>Ce s-a cumpărat</strong>: codurile <Term id="cpv">CPV</Term> sunt traduse în categorii pe înțeles (ex. „Construcții drumuri”, „IT”, „Alimente”).
          </li>
          <li>
            <strong>Tipul instituției</strong> (primărie, școală, spital…) este dedus automat din denumire și poate fi uneori greșit.
          </li>
          <li>
            <strong>Persoanele fizice</strong> (PFA, întreprinderi individuale sau familiale) sunt anonimizate: afișăm doar „Persoană fizică autorizată” și localitatea.
          </li>
          <li>
            <strong>Nu numărăm de două ori.</strong> Același contract apare uneori pe mai multe rânduri (o asociere de
            firme, mai multe loturi cu valoarea totală repetată). Când un <Term id="acord_cadru">acord-cadru</Term> are
            contracte subsecvente raportate, numărăm subsecventele (cheltuiala efectivă), nu valoarea maximă a acordului.
          </li>
          <li>
            <strong>Județul</strong> este cel al sediului instituției. Companiile naționale cu sediul în județ (de ex.
            Transgaz, Romgaz la Mediaș) apar aici, deși cheltuie pentru toată țara.
          </li>
          <li>
            <strong>Anul</strong> unui contract este anul semnării. Unele contracte vechi apar în rapoarte recente, când instituția publică anunțul cu întârziere.
          </li>
        </ul>
      </section>
      <section id="semnale" className="space-y-3">
        <h2 className="text-xl">Semnalele de verificat</h2>
        <p>
          Semnalele sunt calculate automat după reguli simple și publice. <strong>Nu sunt acuzații</strong> și nu dovedesc
          nereguli: sunt puncte de plecare pentru întrebări. Fiecare semnal are un scor între 1 și 100 (cât de puternic
          este indiciul, ținând cont și de valoarea în joc), o explicație și un link la sursa oficială.
        </p>
        {SIGNALS.map((s) => (
          <div key={s.id} className="rounded-lg border bg-white p-4">
            <h3 className="font-semibold">{s.name}</h3>
            <p className="mt-1 text-sm"><strong>Regula:</strong> {s.rule}</p>
            <p className="mt-1 text-sm"><strong>De ce contează:</strong> {s.why}</p>
            <p className="mt-1 text-sm text-muted-foreground"><strong>Limite:</strong> {s.caveat}</p>
          </div>
        ))}
        <p className="text-sm text-muted-foreground">
          Pragurile sunt într-un fișier de configurare separat (<code>risk_thresholds.yaml</code>) și pot fi ajustate.
        </p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl">Limite cunoscute</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Datele oficiale pot conține greșeli de introducere (valori, CUI-uri, date). Le afișăm așa cum sunt publicate.</li>
          <li>Rapoartele sunt trimestriale, cu întârziere de 1–2 luni.</li>
          <li>Numărul de oferte nu este publicat în datele deschise SEAP.</li>
          <li>Dacă observați o eroare, folosiți <Link href="/disclaimer#corectie">formularul de corecție</Link>.</li>
        </ul>
      </section>
    </article>
  );
}
