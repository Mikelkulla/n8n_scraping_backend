import { apiRequest } from "./httpClient";
import type {
  CampaignLeadResponse,
  GmailAuthStartRequest,
  GmailAuthStartResponse,
  GmailStatusResponse,
} from "./types";

export function getGmailStatus() {
  return apiRequest<GmailStatusResponse>("/gmail/status");
}

export function startGmailAuth(payload: GmailAuthStartRequest = {}) {
  return apiRequest<GmailAuthStartResponse>("/gmail/auth/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function disconnectGmail() {
  return apiRequest<GmailStatusResponse>("/gmail/disconnect", {
    method: "POST",
  });
}

export function createCampaignLeadGmailDraft(campaignLeadId: number) {
  return apiRequest<CampaignLeadResponse>(`/campaign-leads/${campaignLeadId}/gmail-draft`, {
    method: "POST",
  });
}
