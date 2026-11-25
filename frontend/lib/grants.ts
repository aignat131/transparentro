// Unde își publică instituțiile apelurile de finanțare nerambursabilă pentru ONG-uri (Legea 350/2005).
// Aceste apeluri NU apar în SEAP, așa că lista e întreținută de mână. Punem doar pagini oficiale
// verificate; data verificării apare pe site, ca omul să știe cât de proaspătă e informația.

export type GrantSource = {
  institution: string;
  url: string;
  domains: string[];
  note: string;
  platform?: string;
  checked: string; // AAAA-LL-ZZ
};

export const GRANT_SOURCES: GrantSource[] = [
  {
    institution: "Consiliul Județean Sibiu",
    url: "https://www.cjsibiu.ro/agendele-consiliului-judetean/",
    domains: ["Cultură", "Sport", "Tineret", "Educație"],
    note: "„Agendele județului”: sesiune anuală, de obicei deschisă primăvara. Pentru 2026 s-au publicat anunțul de deschidere, ghidurile și rezultatele.",
    platform: "https://agende.cjsibiu.ro/manager/main/index.html#/login",
    checked: "2026-11-25",
  },
];
