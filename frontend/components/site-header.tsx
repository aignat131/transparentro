import Link from "next/link";

const NAV = [
  { href: "/institutii", label: "Instituții" },
  { href: "/firme", label: "Firme" },
  { href: "/ong", label: "ONG-uri" },
  { href: "/contracte", label: "Contracte" },
  { href: "/semnale", label: "Semnale" },
  { href: "/harta", label: "Hartă" },
  { href: "/metodologie", label: "Cum citesc datele?" },
];

export function SiteHeader() {
  return (
    <header className="border-b bg-white">
      <a href="#continut" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-white focus:p-2">
        Sari la conținut
      </a>
      <div className="container flex flex-col gap-2 py-3 md:flex-row md:items-center md:justify-between">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-primary no-underline">
          <span aria-hidden className="inline-block h-6 w-6 rounded bg-primary" />
          TransparentRO
          <span className="text-sm font-normal text-muted-foreground">· banii publici, pe înțeles</span>
        </Link>
        <nav aria-label="Navigare principală">
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {NAV.map((n) => (
              <li key={n.href}>
                <Link href={n.href} className="text-foreground hover:text-primary hover:underline">
                  {n.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
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
