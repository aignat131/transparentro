import { api, type ContractDetail } from "@/lib/api";
import { leiShort } from "@/lib/format";
import { ogImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Detalii contract public";

export default async function Image({ params }: { params: { id: string } }) {
  try {
    const c = await api<ContractDetail>(`/contracts/${params.id}`);
    const title = (c.title || c.cpv_name || `Contract #${c.id}`).slice(0, 110);
    return ogImage({ kicker: c.authority.name.slice(0, 60), title, stat: leiShort(c.value_ron), synthetic: c.is_synthetic });
  } catch {
    return ogImage({ kicker: "contract", title: "Contract public" });
  }
}
