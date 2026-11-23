import { ogImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "TransparentRO — banii publici, pe înțeles";
export const dynamic = "force-dynamic";

export default function Image() {
  return ogImage({ kicker: "achiziții publice", title: "Ce cumpără instituțiile publice, de la cine și cu cât" });
}
