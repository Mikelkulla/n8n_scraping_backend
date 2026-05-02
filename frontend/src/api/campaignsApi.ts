import { apiRequest, downloadRequest } from "./httpClient";
import type {
  CampaignLeadResponse,
  CampaignResponse,
  CreateCampaignRequest,
  CreateCampaignResponse,
  ListCampaignLeadsParams,
  ListCampaignLeadsResponse,
  ListCampaignsResponse,
  UpdateCampaignLeadRequest,
  UpdateCampaignRequest,
} from "./types";

function toQueryString(params: Record<string, unknown> = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });

  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export function listCampaigns() {
  return apiRequest<ListCampaignsResponse>("/campaigns");
}

export function createCampaign(payload: CreateCampaignRequest) {
  return apiRequest<CreateCampaignResponse>("/campaigns", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCampaign(campaignId: number) {
  return apiRequest<CampaignResponse>(`/campaigns/${campaignId}`);
}

export function updateCampaign(campaignId: number, payload: UpdateCampaignRequest) {
  return apiRequest<CampaignResponse>(`/campaigns/${campaignId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listCampaignLeads(campaignId: number, params: ListCampaignLeadsParams = {}) {
  return apiRequest<ListCampaignLeadsResponse>(
    `/campaigns/${campaignId}/leads${toQueryString(params)}`,
  );
}

export function updateCampaignLead(campaignLeadId: number, payload: UpdateCampaignLeadRequest) {
  return apiRequest<CampaignLeadResponse>(`/campaign-leads/${campaignLeadId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function downloadCampaignCsv(campaignId: number, stage?: string) {
  return downloadRequest(`/campaigns/${campaignId}/export${toQueryString({ stage })}`);
}
