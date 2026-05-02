import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addLeadEmail,
  deleteLeadEmail,
  downloadLeadsCsv,
  exportLeadsJson,
  listLeadFilterOptions,
  listLeadEmails,
  listLeads,
  updateLead,
  updateLeadEmail,
} from "../api";
import type {
  AddLeadEmailRequest,
  ListLeadsParams,
  UpdateLeadEmailRequest,
  UpdateLeadRequest,
} from "../api";
import { queryKeys } from "./queryKeys";

export function useLeads(params: ListLeadsParams = {}) {
  return useQuery({
    queryKey: queryKeys.leads(params),
    queryFn: () => listLeads(params),
  });
}

export function useLeadFilterOptions() {
  return useQuery({
    queryKey: queryKeys.leadFilterOptions,
    queryFn: listLeadFilterOptions,
  });
}

export function useLeadEmails(leadId?: number) {
  return useQuery({
    queryKey: queryKeys.leadEmails(leadId ?? 0),
    queryFn: () => listLeadEmails(leadId ?? 0),
    enabled: Boolean(leadId),
  });
}

export function useExportLeadsJson() {
  return useQuery({
    queryKey: queryKeys.exportLeads,
    queryFn: exportLeadsJson,
  });
}

export function useUpdateLead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ leadId, payload }: { leadId: number; payload: UpdateLeadRequest }) =>
      updateLead(leadId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.summary });
    },
  });
}

export function useAddLeadEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ leadId, payload }: { leadId: number; payload: AddLeadEmailRequest }) =>
      addLeadEmail(leadId, payload),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.leadEmails(variables.leadId) });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.summary });
    },
  });
}

export function useUpdateLeadEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ emailId, leadId, payload }: { emailId: number; leadId: number; payload: UpdateLeadEmailRequest }) =>
      updateLeadEmail(emailId, payload),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.leadEmails(variables.leadId) });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.summary });
    },
  });
}

export function useDeleteLeadEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ emailId }: { emailId: number; leadId: number }) => deleteLeadEmail(emailId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.leadEmails(variables.leadId) });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.summary });
    },
  });
}

export async function downloadExportedLeads(filename = "leads_export.csv") {
  const blob = await downloadLeadsCsv();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
