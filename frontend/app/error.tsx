"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-xl space-y-4 py-12 text-center">
      <h1 className="text-2xl">Datele nu au putut fi încărcate</h1>
      <p className="text-muted-foreground">Serviciul de date nu răspunde momentan. Încercați din nou.</p>
      <button onClick={reset} className="rounded-md bg-primary px-4 py-2 text-primary-foreground">
        Reîncearcă
      </button>
    </div>
  );
}
