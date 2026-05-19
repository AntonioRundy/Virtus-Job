import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { virtusApi } from "@/lib/api";
import type { Opportunity, OpportunityListItem, OpportunityFilters, PaginatedResponse } from "@virtus/types";

export function useOpportunities(filters: OpportunityFilters = {}) {
  return useInfiniteQuery<PaginatedResponse<OpportunityListItem>>({
    queryKey: ["opportunities", filters],
    queryFn: ({ pageParam = 1 }) =>
      virtusApi.get<PaginatedResponse<OpportunityListItem>>("/opportunities", {
        page: pageParam as number,
        per_page: 20,
        ...filters,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
    staleTime: 1000 * 60 * 2,
  });
}

export function useOpportunity(slug: string) {
  return useQuery<Opportunity>({
    queryKey: ["opportunity", slug],
    queryFn: () => virtusApi.get<Opportunity>(`/opportunities/${slug}`),
    enabled: !!slug,
    staleTime: 1000 * 60 * 5,
  });
}
