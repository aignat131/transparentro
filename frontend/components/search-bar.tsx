import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Formular GET simplu: funcționează și fără JavaScript. */
export function SearchBar({ defaultValue, large = false }: { defaultValue?: string; large?: boolean }) {
  return (
    <form action="/cautare" method="get" role="search" className="flex w-full gap-2">
      <label htmlFor={large ? "q-hero" : "q"} className="sr-only">
        Caută o instituție, o firmă sau un contract
      </label>
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          id={large ? "q-hero" : "q"}
          name="q"
          type="search"
          defaultValue={defaultValue}
          placeholder="Caută o instituție, o firmă sau un contract"
          className={cn("pl-10", large && "h-14 text-base shadow-sm")}
          autoComplete="off"
          required
          minLength={2}
        />
      </div>
      <Button type="submit" size={large ? "lg" : "default"} className={cn(large && "h-14")}>
        Caută
      </Button>
    </form>
  );
}
