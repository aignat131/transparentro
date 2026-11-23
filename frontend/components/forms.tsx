"use client";

import { useState } from "react";
import { Bell, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PUBLIC_API } from "@/lib/api";

type Status = { kind: "idle" | "busy" | "ok" | "error"; message?: string };

async function post(path: string, body: unknown): Promise<{ ok: boolean; message: string }> {
  try {
    const r = await fetch(`${PUBLIC_API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = Array.isArray(j.detail) ? "Verificați câmpurile completate." : j.detail;
      return { ok: false, message: detail || "Cererea nu a putut fi trimisă." };
    }
    return { ok: true, message: j.message || "Trimis." };
  } catch {
    return { ok: false, message: "Serviciul nu răspunde. Încercați mai târziu." };
  }
}

function StatusLine({ s }: { s: Status }) {
  if (s.kind === "idle" || s.kind === "busy") return null;
  return (
    <p role="status" className={s.kind === "ok" ? "text-sm text-green-800" : "text-sm text-red-700"}>
      {s.message}
    </p>
  );
}

export function SubscribeForm({ targetType, targetKey, label }: { targetType: "authority" | "company"; targetKey: string; label: string }) {
  const [s, setS] = useState<Status>({ kind: "idle" });
  return (
    <section aria-labelledby="alerte" className="rounded-lg border bg-white p-4">
      <h2 id="alerte" className="flex items-center gap-2 text-lg">
        <Bell className="h-4 w-4" aria-hidden /> Anunță-mă la contracte noi
      </h2>
      <p className="text-sm text-muted-foreground">
        Primiți un e-mail când apar contracte noi pentru <strong>{label}</strong>. Veți confirma abonarea printr-un link
        (double opt-in); vă puteți dezabona oricând.
      </p>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={async (e) => {
          e.preventDefault();
          const email = String(new FormData(e.currentTarget).get("email") || "");
          setS({ kind: "busy" });
          const r = await post("/alerts/subscribe", { email, target_type: targetType, target_key: targetKey });
          setS({ kind: r.ok ? "ok" : "error", message: r.message });
        }}
      >
        <label htmlFor={`email-${targetKey}`} className="sr-only">Adresa de e-mail</label>
        <Input id={`email-${targetKey}`} name="email" type="email" required placeholder="adresa@exemplu.ro" className="sm:max-w-xs" />
        <Button type="submit" disabled={s.kind === "busy"}>Abonează-mă</Button>
      </form>
      <StatusLine s={s} />
    </section>
  );
}

export function CorrectionForm() {
  const [s, setS] = useState<Status>({ kind: "idle" });
  return (
    <form
      className="space-y-3"
      aria-label="Formular de corecție"
      onSubmit={async (e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        setS({ kind: "busy" });
        const r = await post("/corrections", {
          email: fd.get("email") || null,
          entity_url: fd.get("entity_url") || null,
          message: fd.get("message"),
        });
        setS({ kind: r.ok ? "ok" : "error", message: r.message });
        if (r.ok) e.currentTarget.reset();
      }}
    >
      <div>
        <label htmlFor="c-url" className="text-sm font-medium">Pagina la care vă referiți (opțional)</label>
        <Input id="c-url" name="entity_url" placeholder="ex. http://localhost:3000/contracte/123" />
      </div>
      <div>
        <label htmlFor="c-msg" className="text-sm font-medium">Ce informație este greșită și care este varianta corectă?</label>
        <textarea
          id="c-msg"
          name="message"
          required
          minLength={10}
          rows={5}
          className="w-full rounded-md border border-input bg-background p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
      <div>
        <label htmlFor="c-email" className="text-sm font-medium">E-mail pentru răspuns (opțional)</label>
        <Input id="c-email" name="email" type="email" />
      </div>
      <Button type="submit" disabled={s.kind === "busy"}>Trimite cererea de corecție</Button>
      <StatusLine s={s} />
    </form>
  );
}

export function ExplainBox({ contractId }: { contractId: number }) {
  const [s, setS] = useState<Status>({ kind: "idle" });
  const [text, setText] = useState<string | null>(null);
  return (
    <div className="rounded-lg border border-dashed bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">Vreți o explicație pe scurt, în cuvinte simple?</p>
        <Button
          variant="outline"
          size="sm"
          disabled={s.kind === "busy"}
          onClick={async () => {
            setS({ kind: "busy" });
            try {
              const r = await fetch(`${PUBLIC_API}/explain/${contractId}`);
              const j = await r.json();
              if (!r.ok) throw new Error(j.detail || "Explicația nu este disponibilă.");
              setText(j.text);
              setS({ kind: "idle" });
            } catch (err) {
              setS({ kind: "error", message: (err as Error).message });
            }
          }}
        >
          <Sparkles className="h-4 w-4" aria-hidden /> {s.kind === "busy" ? "Se generează…" : "Explică-mi contractul"}
        </Button>
      </div>
      {text && (
        <div className="mt-3 space-y-2 text-sm" aria-live="polite">
          {text.split(/\n+/).map((p, i) => <p key={i}>{p}</p>)}
          <p className="text-xs text-muted-foreground">Text generat automat (AI) pe baza datelor de pe această pagină. Poate conține greșeli; datele oficiale au prioritate.</p>
        </div>
      )}
      <StatusLine s={s} />
    </div>
  );
}
