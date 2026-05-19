"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, SlidersHorizontal, Loader2, ArrowUpDown } from "lucide-react";
import { useState, useTransition } from "react";
import { api } from "@/lib/api";
import { OpportunityCard } from "@/components/opportunities/OpportunityCard";
import { Button } from "@/components/ui/button";
import { ANGOLA_PROVINCES, OPPORTUNITY_TYPES } from "@/lib/utils";
import type { PaginatedResponse, OpportunityListItem, OpportunityFilters } from "@/types";

const SORT_OPTIONS = [
  { value: "recent", label: "Mais recentes" },
  { value: "deadline", label: "Prazo a chegar" },
] as const;

export function OpportunitiesContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const filters: OpportunityFilters = {
    page: Number(searchParams.get("page") ?? 1),
    type: (searchParams.get("type") as OpportunityFilters["type"]) ?? undefined,
    province: searchParams.get("province") ?? undefined,
    search: searchParams.get("search") ?? undefined,
    sort: (searchParams.get("sort") as OpportunityFilters["sort"]) ?? "recent",
  };

  const [searchInput, setSearchInput] = useState(filters.search ?? "");

  const { data, isLoading } = useQuery({
    queryKey: ["opportunities", filters],
    queryFn: () =>
      api.get<PaginatedResponse<OpportunityListItem>>("/opportunities", {
        params: { ...filters, per_page: 18 },
      }),
  });

  function updateFilter(key: string, value: string | undefined) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.set("page", "1");
    startTransition(() => {
      router.push(`/oportunidades?${params.toString()}`);
    });
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    updateFilter("search", searchInput || undefined);
  }

  return (
    <div className="container mx-auto px-4 max-w-7xl py-8">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground mb-1">
          {filters.type
            ? OPPORTUNITY_TYPES[filters.type as keyof typeof OPPORTUNITY_TYPES]?.label
            : "Todas as Oportunidades"}
        </h1>
        <p className="text-muted-foreground text-sm">
          {data?.total !== undefined ? `${data.total} oportunidades encontradas` : "A carregar..."}
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* ─── Sidebar Filters ───────────────────────── */}
        <aside className="lg:w-64 flex-shrink-0">
          <div className="rounded-xl border border-border bg-card p-4 space-y-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <SlidersHorizontal className="h-4 w-4" />
              Filtros
            </div>

            {/* Type filter */}
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
                Tipo
              </label>
              <div className="space-y-1">
                <button
                  onClick={() => updateFilter("type", undefined)}
                  className={`w-full text-left px-3 py-1.5 rounded-md text-sm transition-colors ${
                    !filters.type ? "bg-primary text-white" : "hover:bg-muted text-muted-foreground"
                  }`}
                >
                  Todos
                </button>
                {Object.entries(OPPORTUNITY_TYPES).map(([key, { label }]) => (
                  <button
                    key={key}
                    onClick={() => updateFilter("type", key)}
                    className={`w-full text-left px-3 py-1.5 rounded-md text-sm transition-colors ${
                      filters.type === key
                        ? "bg-primary text-white"
                        : "hover:bg-muted text-muted-foreground"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Province filter */}
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
                Província
              </label>
              <select
                className="w-full h-9 px-3 rounded-lg border border-border bg-background text-sm"
                value={filters.province ?? ""}
                onChange={(e) => updateFilter("province", e.target.value || undefined)}
              >
                <option value="">Todas</option>
                {ANGOLA_PROVINCES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </aside>

        {/* ─── Main Content ──────────────────────────── */}
        <div className="flex-1 min-w-0">
          {/* Search bar */}
          <form onSubmit={handleSearch} className="flex gap-2 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Pesquisar oportunidades..."
                className="w-full h-10 pl-9 pr-4 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>
            <Button type="submit" loading={isPending}>
              Pesquisar
            </Button>
          </form>

          {/* Sort + results header */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-muted-foreground">
              {data?.total !== undefined ? `${data.total} resultado${data.total !== 1 ? "s" : ""}` : ""}
            </p>
            <div className="flex items-center gap-2">
              <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
              <select
                className="h-8 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                value={filters.sort ?? "recent"}
                onChange={(e) => updateFilter("sort", e.target.value)}
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Results */}
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
            </div>
          ) : data?.items.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-muted-foreground font-medium">Nenhuma oportunidade encontrada.</p>
              <p className="text-sm text-muted-foreground mt-1 mb-4">
                Tenta ajustar os filtros ou pesquisar por outro termo.
              </p>
              <Button
                variant="outline"
                onClick={() => router.push("/oportunidades")}
              >
                Limpar filtros
              </Button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {data?.items.map((opp) => (
                  <OpportunityCard key={opp.id} opportunity={opp} />
                ))}
              </div>

              {/* Pagination */}
              {data && data.pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-8">
                  <Button
                    variant="outline"
                    disabled={filters.page! <= 1}
                    onClick={() => updateFilter("page", String(filters.page! - 1))}
                  >
                    Anterior
                  </Button>
                  <span className="text-sm text-muted-foreground px-3">
                    Página {filters.page} de {data.pages}
                  </span>
                  <Button
                    variant="outline"
                    disabled={filters.page! >= data.pages}
                    onClick={() => updateFilter("page", String(filters.page! + 1))}
                  >
                    Próxima
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
