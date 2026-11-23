import { api, type CompanyDetail } from "@/lib/api";
import { leiShort } from "@/lib/format";
import { ogImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Profilul firmei";

export default async function Image({ params }: { params: { key: string } }) {
  try {
    const c = await api<CompanyDetail>(`/companies/${encodeURIComponent(decodeURIComponent(params.key))}`);
    return ogImage({ kicker: "firmă", title: c.name, stat: `${leiShort(c.total_ron)} din contracte publice`, synthetic: c.is_synthetic });
  } catch {
    return ogImage({ kicker: "firmă", title: "Furnizor al statului" });
  }
}
