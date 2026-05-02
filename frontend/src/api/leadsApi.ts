import { downloadRequest, apiRequest } from "./httpClient";
import type {
  ExportLeadsResponse,
  AddLeadEmailRequest,
  DeleteLeadEmailResponse,
  LeadEmailResponse,
  LeadFilterOptionsResponse,
  ListLeadsParams,
  ListLeadsResponse,
  ListLeadEmailsResponse,
  UpdateLeadEmailRequest,
  UpdateLeadRequest,
  UpdateLeadResponse,
} from "./types";

function toQueryString(params: ListLeadsParams = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });

  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export function listLeads(params: ListLeadsParams = {}) {
  return apiRequest<ListLeadsResponse>(`/leads${toQueryString(params)}`);
}

export function listLeadFilterOptions() {
  return apiRequest<LeadFilterOptionsResponse>("/leads/filter-options");
}

export function updateLead(leadId: number, payload: UpdateLeadRequest) {
  return apiRequest<UpdateLeadResponse>(`/leads/${leadId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listLeadEmails(leadId: number) {
  return apiRequest<ListLeadEmailsResponse>(`/leads/${leadId}/emails`);
}

export function addLeadEmail(leadId: number, payload: AddLeadEmailRequest) {
  return apiRequest<LeadEmailResponse>(`/leads/${leadId}/emails`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateLeadEmail(emailId: number, payload: UpdateLeadEmailRequest) {
  return apiRequest<LeadEmailResponse>(`/lead-emails/${emailId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteLeadEmail(emailId: number) {
  return apiRequest<DeleteLeadEmailResponse>(`/lead-emails/${emailId}`, {
    method: "DELETE",
  });
}

export function exportLeadsJson() {
  return apiRequest<ExportLeadsResponse>("/leads/export?format=json");
}

export function downloadLeadsCsv() {
  return downloadRequest("/leads/export");
}
