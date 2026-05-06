import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAppSettings,
  getEmailSettings,
  listBusinessTypeEmailRules,
  updateAppSettings,
  updateBusinessTypeEmailRule,
  updateEmailSettings,
} from "../api";
import type { UpdateAppSettingsRequest, UpdateBusinessTypeEmailRuleRequest, UpdateEmailSettingsRequest } from "../api";
import { queryKeys } from "./queryKeys";

export function useEmailSettings() {
  return useQuery({
    queryKey: queryKeys.emailSettings,
    queryFn: getEmailSettings,
  });
}

export function useUpdateEmailSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateEmailSettingsRequest) => updateEmailSettings(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.emailSettings });
    },
  });
}

export function useAppSettings() {
  return useQuery({
    queryKey: queryKeys.appSettings,
    queryFn: getAppSettings,
  });
}

export function useUpdateAppSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateAppSettingsRequest) => updateAppSettings(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.appSettings });
    },
  });
}

export function useBusinessTypeEmailRules() {
  return useQuery({
    queryKey: queryKeys.businessTypeEmailRules,
    queryFn: listBusinessTypeEmailRules,
  });
}

export function useUpdateBusinessTypeEmailRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ businessType, payload }: { businessType: string; payload: UpdateBusinessTypeEmailRuleRequest }) =>
      updateBusinessTypeEmailRule(businessType, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.businessTypeEmailRules });
    },
  });
}
