import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCampaignLeadGmailDraft,
  disconnectGmail,
  getGmailStatus,
  startGmailAuth,
} from "../api";
import type { GmailAuthStartRequest } from "../api";
import { queryKeys } from "./queryKeys";

export function useGmailStatus() {
  return useQuery({
    queryKey: queryKeys.gmailStatus,
    queryFn: getGmailStatus,
  });
}

export function useStartGmailAuth() {
  return useMutation({
    mutationFn: (payload: GmailAuthStartRequest = {}) => startGmailAuth(payload),
    onSuccess: (response) => {
      window.open(response.authorization_url, "_blank", "noopener,noreferrer");
    },
  });
}

export function useDisconnectGmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: disconnectGmail,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.gmailStatus });
    },
  });
}

export function useCreateCampaignLeadGmailDraft() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ campaignLeadId }: { campaignLeadId: number; campaignId: number }) =>
      createCampaignLeadGmailDraft(campaignLeadId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(variables.campaignId) });
      void queryClient.invalidateQueries({ queryKey: ["campaign-leads", variables.campaignId] });
    },
  });
}
