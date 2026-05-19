"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  className?: string;
  defaultValue?: string;
}

export function SearchBar({ className, defaultValue = "" }: Props) {
  const [query, setQuery] = useState(defaultValue);
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q) {
      router.push(`/oportunidades?search=${encodeURIComponent(q)}`);
    } else {
      router.push("/oportunidades");
    }
  }

  return (
    <form onSubmit={handleSubmit} className={cn("flex flex-col sm:flex-row gap-3", className)}>
      <div className="relative flex-1">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Pesquisar vagas, concursos, bolsas..."
          className="w-full h-11 pl-10 pr-4 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          autoComplete="off"
        />
      </div>
      <Button type="submit" size="lg" className="w-full sm:w-auto gap-2">
        Pesquisar <Search className="h-4 w-4" />
      </Button>
    </form>
  );
}
