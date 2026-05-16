import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCampaign,
  downloadCampaignCsv,
  generateCampaignEmails,
  generateCampaignLeadEmail,
  getCampaign,
  listCampaignLeads,
  listCampaigns,
  updateCampaign,
  updateCampaignLead,
} from "../api";
import type {
  CreateCampaignRequest,
  GenerateCampaignEmailsRequest,
  ListCampaignLeadsParams,
  UpdateCampaignLeadRequest,
  UpdateCampaignRequest,
} from "../api";
import { queryKeys } from "./queryKeys";

export function useCampaigns() {
  return useQuery({
    queryKey: queryKeys.campaigns,
    queryFn: listCampaigns,
  });
}

export function useCampaign(campaignId?: number) {
  return useQuery({
    queryKey: queryKeys.campaign(campaignId ?? 0),
    queryFn: () => getCampaign(campaignId ?? 0),
    enabled: Boolean(campaignId),
  });
}

export function useCampaignLeads(campaignId?: number, params: ListCampaignLeadsParams = {}) {
  return useQuery({
    queryKey: queryKeys.campaignLeads(campaignId ?? 0, params),
    queryFn: () => listCampaignLeads(campaignId ?? 0, params),
    enabled: Boolean(campaignId),
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateCampaignRequest) => createCampaign(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useUpdateCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ campaignId, payload }: { campaignId: number; payload: UpdateCampaignRequest }) =>
      updateCampaign(campaignId, payload),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(variables.campaignId) });
    },
  });
}

export function useUpdateCampaignLead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ campaignLeadId, campaignId, payload }: { campaignLeadId: number; campaignId: number; payload: UpdateCampaignLeadRequest }) =>
      updateCampaignLead(campaignLeadId, payload),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(variables.campaignId) });
      void queryClient.invalidateQueries({ queryKey: ["campaign-leads", variables.campaignId] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useGenerateCampaignLeadEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ campaignLeadId }: { campaignLeadId: number; campaignId: number }) =>
      generateCampaignLeadEmail(campaignLeadId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(variables.campaignId) });
      void queryClient.invalidateQueries({ queryKey: ["campaign-leads", variables.campaignId] });
    },
  });
}

export function useGenerateCampaignEmails() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ campaignId, payload }: { campaignId: number; payload: GenerateCampaignEmailsRequest }) =>
      generateCampaignEmails(campaignId, payload),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(variables.campaignId) });
      void queryClient.invalidateQueries({ queryKey: ["campaign-leads", variables.campaignId] });
    },
  });
}

export async function downloadCampaignExport(campaignId: number, stage?: string, filename = `campaign_${campaignId}_export.csv`) {
  const blob = await downloadCampaignCsv(campaignId, stage);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
