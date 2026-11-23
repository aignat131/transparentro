import { AlertTriangle } from "lucide-react";

import { api, type Overview } from "@/lib/api";
import { date } from "@/lib/format";

/** Banner afișat pe toate paginile când baza de date conține date SINTETICE. */
export async function DataBanner() {
  let ov: Overview | null = null;
  try {
    ov = await api<Overview>("/stats/overview", { county: "all" }, 60);
  } catch {
    return (
      <div role="status" className="bg-amber-50 py-2 text-center text-sm text-amber-900">
        Serviciul de date nu răspunde momentan. Încercați din nou peste câteva minute.
      </div>
    );
  }
  if (!ov.data.has_synthetic) return null;
  const onlySynthetic = ov.data.real_contracts === 0;
  return (
    <div role="alert" className="border-b border-fuchsia-300 bg-fuchsia-50 py-2 text-sm text-fuchsia-950">
      <div className="container flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <p>
          <strong>Atenție: {onlySynthetic ? "toate datele afișate sunt SINTETICE" : "o parte din date sunt SINTETICE"}</strong>{" "}
          (generate pentru demonstrație, marcate cu eticheta „sintetic”). Nu descriu instituții sau firme reale.
          {!onlySynthetic && ov.data.last_import_at && <> Ultimul import real: {date(ov.data.last_import_at)}.</>}
        </p>
      </div>
    </div>
  );
}

export function SyntheticBadge({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <span className="ml-1 inline-flex items-center rounded-full border border-fuchsia-300 bg-fuchsia-50 px-2 py-0.5 text-xs font-medium text-fuchsia-900">
      sintetic
    </span>
  );
}
