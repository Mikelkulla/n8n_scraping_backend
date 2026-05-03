import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyEmailCategoryRules,
  listEmailCategoryRules,
  listUnknownEmailLocalParts,
  updateEmailCategoryRule,
} from "../api";
import type { UpdateEmailCategoryRuleRequest } from "../api";
import { queryKeys } from "./queryKeys";

export function useEmailCategoryRules() {
  return useQuery({
    queryKey: queryKeys.emailCategoryRules,
    queryFn: listEmailCategoryRules,
  });
}

export function useUnknownEmailLocalParts() {
  return useQuery({
    queryKey: queryKeys.unknownEmailLocalParts,
    queryFn: listUnknownEmailLocalParts,
  });
}

export function useUpdateEmailCategoryRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ pattern, payload }: { pattern: string; payload: UpdateEmailCategoryRuleRequest }) =>
      updateEmailCategoryRule(pattern, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.emailCategoryRules });
      void queryClient.invalidateQueries({ queryKey: queryKeys.unknownEmailLocalParts });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["lead-emails"] });
    },
  });
}

export function useApplyEmailCategoryRules() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: applyEmailCategoryRules,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.emailCategoryRules });
      void queryClient.invalidateQueries({ queryKey: queryKeys.unknownEmailLocalParts });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["lead-emails"] });
    },
  });
}
