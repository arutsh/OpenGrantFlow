import { useQuery } from "@tanstack/react-query";
import { listCurrencies } from "@/api/budgetApi";

// The ISO 4217 list is static server-side, so it is fetched once per session.
export function useCurrencies(enabled = true) {
  return useQuery({
    queryKey: ["currencies"],
    queryFn: listCurrencies,
    enabled,
    staleTime: Infinity,
  });
}
