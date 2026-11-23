import { ImageResponse } from "next/og";

export const OG_SIZE = { width: 1200, height: 630 };

/** Imagine Open Graph sobră: eticheta tipului, titlul, o cifră-cheie. */
export function ogImage({ kicker, title, stat, synthetic }: { kicker: string; title: string; stat?: string; synthetic?: boolean }) {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 64,
          background: "#fcfcfb",
          color: "#0b0b0b",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 30, color: "#1f5a9e" }}>
          <div style={{ width: 36, height: 36, background: "#1f5a9e", borderRadius: 6 }} />
          TransparentRO · {kicker}
        </div>
        <div style={{ display: "flex", fontSize: title.length > 60 ? 52 : 64, fontWeight: 700, lineHeight: 1.15 }}>{title}</div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 34, color: "#52514e" }}>
          <span>{stat ?? "Banii publici, pe înțeles"}</span>
          {synthetic ? <span style={{ color: "#86198f" }}>DATE SINTETICE</span> : <span>date oficiale SEAP · ANAF · ONRC</span>}
        </div>
      </div>
    ),
    OG_SIZE,
  );
}
