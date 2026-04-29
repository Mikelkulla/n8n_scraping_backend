import { useQuery } from "@tanstack/react-query";
import { getBackendHealth } from "../api";
import { queryKeys } from "./queryKeys";

export function useBackendHealth() {
  return useQuery({
    queryKey: queryKeys.backendHealth,
    queryFn: getBackendHealth,
    refetchInterval: 30_000,
    retry: 1,
  });
}
