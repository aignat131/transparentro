import Link from "next/link";

import { SearchBar } from "@/components/search-bar";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl space-y-4 py-12 text-center">
      <h1 className="text-2xl">Pagina nu a fost găsită</h1>
      <p className="text-muted-foreground">Poate căutați altceva?</p>
      <SearchBar />
      <Link href="/">Înapoi la pagina principală</Link>
    </div>
  );
}
