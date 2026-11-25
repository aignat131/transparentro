"use client";

import { useState } from "react";
import { Check, Copy, FileText, Share2 } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Buton „Distribuie”: pe telefon deschide meniul de partajare al sistemului; altfel copiază linkul. */
export function ShareButton({ title, text, path }: { title: string; text: string; path: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 rounded-full border bg-white px-3 py-1 text-xs text-foreground hover:border-primary"
      onClick={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const url = new URL(path, window.location.origin).toString();
        try {
          if (navigator.share) {
            await navigator.share({ title, text, url });
            return;
          }
          await navigator.clipboard.writeText(`${text}\n${url}`);
          setDone(true);
          setTimeout(() => setDone(false), 2000);
        } catch {
          /* utilizatorul a renunțat */
        }
      }}
    >
      {done ? <Check className="h-3 w-3" aria-hidden /> : <Share2 className="h-3 w-3" aria-hidden />}
      {done ? "Link copiat" : "Distribuie"}
    </button>
  );
}

/**
 * Cerere de informații publice (Legea 544/2001), gata completată. Omul o copiază și o trimite pe e-mailul
 * instituției. Nu trimitem nimic noi: textul rămâne în browser.
 */
export function AskBox({ institution, subject, questions }: { institution: string; subject: string; questions: string[] }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [copied, setCopied] = useState(false);
  const today = new Date().toLocaleDateString("ro-RO");
  const text = [
    `Către: ${institution}`,
    "Compartimentul pentru relația cu publicul / informații de interes public",
    "",
    "Cerere de informații de interes public",
    "",
    `Subsemnatul/Subsemnata ${name || "[numele și prenumele]"}, în temeiul Legii nr. 544/2001 privind liberul acces la informațiile de interes public, vă rog să-mi comunicați următoarele informații privind ${subject}:`,
    "",
    ...questions.map((q, i) => `${i + 1}. ${q}`),
    "",
    "Doresc să primesc informațiile în format electronic, la adresa de e-mail de la care trimit această cerere.",
    "",
    `Data: ${today}`,
    `Semnătura: ${name || "[numele]"}`,
  ].join("\n");
  return (
    <section className="rounded-lg border bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-lg"><FileText className="h-4 w-4" aria-hidden /> Întreabă instituția</h2>
          <p className="text-sm text-muted-foreground">
            Ai dreptul să ceri detalii (Legea 544/2001). Instituția trebuie să răspundă în 10 zile, cel mult 30.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setOpen(!open)}>{open ? "Ascunde" : "Scrie cererea"}</Button>
      </div>
      {open && (
        <div className="mt-3 space-y-3">
          <div>
            <label htmlFor="ask-name" className="text-sm font-medium">Numele tău (apare doar în textul de mai jos)</label>
            <input id="ask-name" value={name} onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border px-3 py-2 text-sm" autoComplete="name" />
          </div>
          <textarea readOnly value={text} rows={14} aria-label="Textul cererii"
            className="w-full rounded-md border bg-slate-50 p-3 font-mono text-xs" />
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={async () => {
              await navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 2500);
            }}>
              {copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
              {copied ? " Copiat" : " Copiază textul"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Trimite-l pe e-mailul instituției (îl găsești pe site-ul ei, la „Contact” sau „Informații de interes public”).
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
