import Link from "next/link";
import { Menu } from "lucide-react";

// Puține linkuri, pentru cetățeanul curios; restul paginilor sunt în meniul de jos (footer).
const NAV = [
  { href: "/", label: "Acasă" },
  { href: "/localitati", label: "Localitatea ta" },
  { href: "/firme", label: "Firme" },
  { href: "/institutii", label: "Instituții" },
  { href: "/oportunitati", label: "Oportunități" },
  { href: "/cautare", label: "Caută" },
];

function NavLinks({ className }: { className: string }) {
  return (
    <ul className={className}>
      {NAV.map((n) => (
        <li key={n.href}>
          <Link href={n.href} className="block py-2 text-foreground no-underline hover:text-primary md:py-0">
            {n.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function SiteHeader() {
  return (
    <header className="border-b bg-white">
      <a href="#continut" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-white focus:p-2">
        Sari la conținut
      </a>
      <div className="container flex items-center justify-between gap-4 py-3">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-primary no-underline">
          <span aria-hidden className="inline-block h-6 w-6 rounded bg-primary" />
          TransparentRO
          <span className="hidden text-sm font-normal text-muted-foreground lg:inline">· banii publici, pe înțeles</span>
        </Link>
        <nav aria-label="Navigare principală" className="hidden md:block">
          <NavLinks className="flex gap-5 text-sm" />
        </nav>
        {/* pe telefon: buton ☰ care deschide lista (fără JavaScript) */}
        <details className="group relative md:hidden">
          <summary className="flex cursor-pointer list-none items-center gap-1 rounded-md border px-3 py-1.5 text-sm [&::-webkit-details-marker]:hidden">
            <Menu className="h-4 w-4" aria-hidden /> Meniu
          </summary>
          <nav aria-label="Navigare principală (telefon)" className="absolute right-0 z-50 mt-2 w-56 rounded-lg border bg-white px-4 py-2 shadow-lg">
            <NavLinks className="divide-y text-base" />
          </nav>
        </details>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t bg-white">
      <div className="container grid gap-4 py-8 text-sm text-muted-foreground md:grid-cols-3">
        <div>
          <p className="font-semibold text-foreground">TransparentRO</p>
          <p>Date din surse oficiale: SEAP/SICAP (data.gov.ro), ANAF, ONRC, BNR.</p>
        </div>
        <ul className="space-y-1">
          <li><Link href="/contracte">Toate contractele</Link></li>
          <li><Link href="/semnale">Semnale de verificat</Link></li>
          <li><Link href="/raport">Raport: pe ce s-au dus banii</Link></li>
          <li><Link href="/ong">ONG-uri și banii publici</Link></li>
          <li><Link href="/harta">Hartă</Link></li>
          <li><Link href="/metodologie">Metodologie</Link></li>
          <li><Link href="/surse-de-date">Surse de date</Link></li>
          <li><Link href="/glosar">Glosar</Link></li>
        </ul>
        <ul className="space-y-1">
          <li><Link href="/despre">Despre proiect</Link></li>
          <li><Link href="/disclaimer">Disclaimer și corecții</Link></li>
          <li>Semnalele sunt indicii de verificat, nu acuzații.</li>
        </ul>
      </div>
    </footer>
  );
}
