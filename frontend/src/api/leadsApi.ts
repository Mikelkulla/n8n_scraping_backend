import { downloadRequest, apiRequest } from "./httpClient";
import type {
  ExportLeadsResponse,
  ListLeadsParams,
  ListLeadsResponse,
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

export function updateLead(leadId: number, payload: UpdateLeadRequest) {
  return apiRequest<UpdateLeadResponse>(`/leads/${leadId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function exportLeadsJson() {
  return apiRequest<ExportLeadsResponse>("/leads/export?format=json");
}

export function downloadLeadsCsv() {
  return downloadRequest("/leads/export");
}
