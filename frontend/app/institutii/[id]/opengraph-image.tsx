import { api, type AuthorityDetail } from "@/lib/api";
import { leiShort } from "@/lib/format";
import { ogImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Profilul instituției";

export default async function Image({ params }: { params: { id: string } }) {
  try {
    const a = await api<AuthorityDetail>(`/authorities/${params.id}`);
    return ogImage({ kicker: "instituție", title: a.name, stat: `${leiShort(a.total_ron)} în ${a.contracts} contracte`, synthetic: a.is_synthetic });
  } catch {
    return ogImage({ kicker: "instituție", title: "Instituție publică" });
  }
}
