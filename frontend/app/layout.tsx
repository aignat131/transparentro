import type { Metadata } from "next";
import "./globals.css";

import { DataBanner } from "@/components/data-banner";
import { SiteFooter, SiteHeader } from "@/components/site-header";
import { SITE_URL } from "@/lib/api";

// Paginile citesc date vii din API (nu se pre-generează la build).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "TransparentRO — banii publici, pe înțeles", template: "%s · TransparentRO" },
  description:
    "Ce cumpără instituțiile publice, de la cine și cu cât. Contracte, firme, istoricul lor și semnale de verificat, din date oficiale SEAP, ANAF și ONRC.",
  openGraph: { type: "website", locale: "ro_RO", siteName: "TransparentRO" },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro">
      <body className="min-h-screen">
        <SiteHeader />
        <DataBanner />
        <main id="continut" className="container py-6">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
