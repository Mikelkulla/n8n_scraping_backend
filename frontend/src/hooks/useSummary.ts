import { useQuery } from "@tanstack/react-query";
import { getSummary } from "../api";
import { queryKeys } from "./queryKeys";

export function useSummary() {
  return useQuery({
    queryKey: queryKeys.summary,
    queryFn: getSummary,
    refetchInterval: 10_000,
  });
}
